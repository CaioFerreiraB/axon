# ADR-034 — O trace se ramifica em destinos; conteúdo só por evento dedicado e opcional

- **Status:** Aceita · 2026-10-13
- **Specs afetadas:** [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md)
  (FR-012 refinada; destinos de uso e Langfuse), [006-core-llm-providers](../../specs/006-core-llm-providers/spec.md)
  (emite o evento de conteúdo), [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (monta os destinos);
  refina a regra de privacidade do [ADR-017](ADR-017-trace-sink-cresce-por-eventos-aditivos.md)
- **Origem:** pedido do mantenedor (2026-10-13): dashboard de requisições, tokens e custo por modelo e por dia, e envio
  de traces ao Langfuse, com o texto de prompt e resposta só quando ligado na console

## Contexto

O `TraceService` da 009 entrega cada registro a **um** exporter, de forma síncrona, no momento da emissão (FR-012).
Os backends são memória e JSONL; não há agregação nem banco. Pelo ADR-017, nenhum evento carrega texto de prompt, de
resposta, argumento de tool ou resultado.

O dashboard precisa de uma projeção persistente das chamadas de modelo. O Langfuse é um destino de rede, que não pode
bloquear o caminho da requisição, e só tem valor pleno com o que foi perguntado e respondido.

## Decisão

1. O trace passa a ter **vários destinos** (fan-out): o backend principal (memória ou JSONL, consultável por
   requisição), o destino de **uso** (projeção em Postgres para o dashboard) e o destino **Langfuse**. A falha de um
   destino é isolada e contada; nenhuma chega a quem emite. O seam `TraceSink` não muda.
2. Destinos de banco ou de rede **não bloqueiam**: enfileiram num buffer limitado, esvaziado fora do caminho da
   requisição; buffer cheio descarta e conta o descarte, que aparece na saúde. A FR-012 da 009 ("entregue no momento da
   emissão") passa a valer para o backend principal; os outros destinos entregam em lote, com atraso de segundos.
3. O texto de prompt e de resposta só existe num **evento dedicado** (`ModelExchange`, emitido pela 006 junto com o
   `ModelCall`), que:
   - só é entregue se a opção de captura de conteúdo estiver **ligada** (desligada por padrão; precedência do ADR-033);
   - só chega a destinos que **declaram aceitar conteúdo** (hoje, só o Langfuse). Memória e JSONL nunca o recebem, e
     uma suíte de conformidade prova isso;
   - passa pela redação de credenciais e é cortado por mensagem.
4. A regra do ADR-017 continua valendo para **todos os outros eventos**: nenhum outro carrega texto, argumento de tool
   ou resultado. Um evento novo de conteúdo exige ADR.
5. O custo **não** entra no trace: é uma projeção do destino de uso, calculada na consulta a partir de uma tabela de
   preços com vigência, mantida pela 009.

## Alternativas rejeitadas

*Texto nos eventos existentes (`ModelCall.prompt`).* Levaria conteúdo a todo destino, inclusive o JSONL do operador, e
abriria a regra do ADR-017 para qualquer evento.

*Langfuse por callbacks do LangChain/LangGraph.* Prenderia o trace ao framework do grafo (ADR-011, princípio XIII) e
não cobriria o que acontece fora dele (gateway de tools, Model Router).

*Dashboard lendo os arquivos JSONL.* Varre todos os arquivos a cada consulta, não sobrevive a trocar de backend e não
existe no perfil `memory`.

*Custo gravado na chamada.* Um preço lançado depois não corrigiria o histórico, e a 009 precisaria conhecer a 006 para
saber o preço na hora da emissão.

## Consequências

- O `TraceService` recebe uma lista de destinos, cada um declarando se aceita conteúdo; a porta interna da 009 muda, o
  seam não.
- O texto que vai ao Langfuse pode conter dados pessoais: a redação cobre credenciais, não dados pessoais. A console
  avisa ao ligar a opção, e a documentação da instalação também.
- O destino Langfuse é uma troca de adapter (ADR-013): o OpenTelemetry, já permitido em `observability/adapters/`, é o
  candidato, a confirmar no research da 009.
