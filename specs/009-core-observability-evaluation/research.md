# Research — 009 Trace por requisição, Fase 1 (US1)

Insumos pré-aprovados: [design.md](design.md) (atualizado em 2026-09-17), [spec.md](spec.md) §Clarifications,
[ADR-007](../../docs/adr/ADR-007-citacao-mecanica.md),
[ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md),
[ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md), constituição (princípios V, VI, VII, XII, XIII).
Código já implementado: `ai-core-contracts` 0.1.0 (001), Pack Runtime (002), `ai-generic` (010).

## R1 — Forma do seam Trace Sink

**Decision**: `TraceSink` é um `Protocol` no `api.py` da 009 com um único método de emissão, que recebe um evento
tipado (dataclass congelada publicada no mesmo `api.py`). Nenhum tipo de biblioteca de observabilidade aparece no
seam. OpenTelemetry segue candidato como **adapter** do `TraceExporter`.

**Rationale (clarificação de 2026-09-17; ADR-013; princípio XIII)**: o ADR-013 listou a API do OpenTelemetry como
candidata para a porta, mas quem emite é 004, 005 e 006 — a biblioteca apareceria nos `api.py` desses módulos, e o
princípio XIII proíbe framework de infraestrutura em `api.py`, `domain/`, `ports.py` e `service.py`. O próprio ADR
autoriza outra forma desde que a semântica se mantenha, então não há divergência a registrar em ADR novo.

**Alternatives**: API do OpenTelemetry como porta (rejeitada acima); um método por tipo de dado
(`record_model_call`, `record_tool_call`, …), que exigiria mudar o seam — logo ADR — a cada módulo novo (004 e 007 na
Fase 3, RAG na Fase 5); spans hierárquicos com início/fim, que põem ciclo de vida de span em todo emissor e
transformam span vazado em bug silencioso.

## R2 — Eventos da Fase 1

**Decision**: cinco tipos, todos com `request_id`: `ExecutionStarted` (assistant, flow, packs, `reference_time`),
`ModelCall` (papel, provider, modelo, tokens de entrada e saída, duração, motivo de parada), `ValidationRun` (pack,
validator, resultado, issues, flags), `ExecutionError` (etapa, tipo, mensagem) e `ExecutionFinished` (duração,
resultado, motivo). Tool, iteração de controller e recuperação entram como tipos novos nas Fases 3 e 5.

**Rationale (clarificação; princípio XII)**: é o conjunto que os módulos da Fase 1 produzem (005 US1, 006 US1, hooks
de validator da 002) e é suficiente para o SC-001 no flow `chat`. `ExecutionFinished` carrega `ok: bool` e um `reason`
livre em vez de um enum de desfechos, para não fixar aqui o vocabulário de estados do motor — que é interno da 005
(princípio II).

**Alternatives**: modelar já os eventos de tool e de recuperação (a 009 teria de descrever dados de módulos que não
existem); nenhum evento concreto na Fase 1 (o SC-001 ficaria indemonstrável e cada módulo inventaria seu formato).

## R3 — Quem estampa o instante do evento

**Decision**: o `service.py` da 009 estampa o instante de recebimento, por uma porta `Clock` declarada em `ports.py`.
O emissor não passa horário; durações (`duration_ms`) vêm no evento, medidas por quem executou a operação. O
`reference_time` da execução (ADR-013) é dado do `ExecutionStarted`, distinto do instante do evento.

**Rationale (ADR-013, 011 FR-008)**: um relógio só para todo o processo, injetado pela composition root, mantém a
ordem dos eventos coerente e torna o trace determinístico em teste (relógio fixo). Deixar o horário a cargo do
emissor espalharia a porta de tempo por todos os módulos emissores sem ganho.

**Alternatives**: `datetime.now()` dentro do service (não-determinismo sem porta, proibido pelo princípio XIII);
horário no evento, preenchido pelo emissor (mais um campo obrigatório em cada evento e uma porta de tempo a mais por
módulo emissor).

## R4 — Escrita por evento, não por requisição

**Decision**: cada evento é entregue ao exporter no momento da emissão, um registro por evento.

**Rationale (clarificação; FR-011, FR-012)**: o trace de uma execução interrompida — queda, travamento, encerramento
forçado — é o que mais interessa, e ele só existe se cada evento já estiver gravado. Uma escrita bufferizada em disco
local custa microssegundos contra segundos de uma chamada de modelo, então "não atrasar perceptivelmente" continua
verdadeiro sem fila nem thread.

**Alternatives**: acumular por requisição e gravar um documento no fim (perde exatamente o trace das execuções que
falham); fila com escrita assíncrona (concorrência, ciclo de vida no boot/encerramento e um modo de falha novo, sem
medição que justifique — princípio XII).

## R5 — Duas portas: escrever e ler

**Decision**: `TraceExporter` (escrita, obrigatória) e `TraceReader` (leitura por identificador de requisição,
opcional). Quando o perfil não tem `TraceReader`, a consulta responde explicitamente que o backend configurado não
oferece consulta, em vez de devolver vazio.

**Rationale (princípio VII)**: um exporter para ferramenta externa (OpenTelemetry, por exemplo) escreve mas não lê —
a leitura é da ferramenta. Uma porta única obrigaria esse adapter a implementar uma leitura que não existe. Com duas
portas, o seam de consulta continua honesto e a falha é explícita.

**Alternatives**: uma porta com `export` e `read` (empurra leitura falsa para adapters que só escrevem); consulta
sempre lendo direto do arquivo, sem porta (amarra o seam de consulta ao formato de arquivo).

## R6 — Adapters da Fase 1

**Decision**: `memory.py` (`InMemoryTraceBackend`, escrita e leitura, para teste e perfil de teste) e `jsonl.py`
(`JsonlTraceBackend`: um arquivo JSONL por dia, `trace-YYYY-MM-DD.jsonl`, append com `flush` por linha, leitura por
varredura filtrando o identificador).

**Rationale (design.md, roadmap "Trace → arquivo na Fase 1")**: arquivo é o que o roadmap pede na Fase 1, JSONL
casa com a escrita por evento (R4) e um arquivo por dia torna a retenção uma operação de arquivo. O volume da Fase 1
(uma instalação, poucas requisições por minuto) não pede índice.

**Alternatives**: Postgres já (o roadmap só prevê armazenamento persistente de trace depois, e a porta permite);
arquivo único crescendo sem limite (retenção viraria reescrita de arquivo).

## R7 — Redação de credenciais

**Decision**: `domain/redaction.py` puro: substitui por `«redigido»` (a) o valor de chave cujo nome casa com a lista
de nomes sensíveis (`authorization`, `api_key`, `apikey`, `token`, `access_token`, `refresh_token`, `secret`,
`password`, `passwd`, `cookie`, `set-cookie`, `private_key`), em qualquer profundidade de mapeamento, e (b) os
padrões de credencial em texto livre: `Bearer <valor>`, `<nome sensível>=<valor>` ou `: <valor>` após nome sensível,
e credencial embutida em URL (`esquema://usuário:senha@host`). Texto acima de 2000 caracteres é truncado com marca.

**Rationale (FR-002, princípio VI)**: com eventos tipados não há campo onde um segredo caiba por descuido, mas
mensagem de erro é texto livre e é por onde um token vaza de verdade (exceção de cliente HTTP que ecoa o cabeçalho).
A regra é pura e testável sem backend, e o truncamento evita que um erro gigante domine o arquivo.

**Alternatives**: confiar em quem emite (transfere a garantia de um requisito duro para cada módulo futuro); permitir
mapas livres nos eventos e depender só da lista de nomes (um nome fora da lista passa direto).

## R8 — Sinalização de dados perdidos

**Decision**: o `service.py` captura qualquer exceção do exporter, não a propaga, registra um `logger.warning` com o
tipo do erro e incrementa um contador de eventos descartados, legível pelo seam de consulta
(`dropped_events()`), que a saúde agregada (011 US5) consome depois.

**Rationale (FR-011)**: "dados perdidos são sinalizados" não pode depender do backend que acabou de falhar; um
contador em memória mais log é o que sobrevive. Falha de trace nunca derruba execução (princípio VII aplicado ao
lado certo: o trace é observação, não o trabalho).

**Alternatives**: propagar a exceção (uma falha de disco derrubaria a conversa); registrar a perda no próprio trace
(impossível, é o destino que falhou); silenciar (perda invisível).

## R9 — Consulta devolve registros genéricos

**Decision**: a emissão é tipada; a **leitura** devolve `TraceRecord(at, type, request_id, attributes)` com
`attributes` em JSON, agregados em `Trace(request_id, records)` na ordem de emissão. Não há reconstrução dos
dataclasses de evento.

**Rationale (princípio XII)**: quem escreve precisa de tipo (erro de campo é erro de compilação); quem lê — a
superfície privada da 008 (Fase 2) e o operador — só renderiza ou inspeciona JSON. Reconstruir exigiria um registro
de tipos e versionamento de formato sem nenhum consumidor que precise disso.

**Alternatives**: desserializar de volta para os tipos de evento (registry de tipos, migração de formato a cada
evento novo); devolver o texto bruto do arquivo (vaza o formato do adapter para o seam).

## R10 — Serialização do registro

**Decision**: `domain/records.py` puro converte evento + instante em registro JSON: `at` (ISO 8601 com timezone),
`type` (nome do evento em `snake_case`), `request_id` e os demais campos do evento, já redigidos. `None` é omitido.

**Rationale**: um conversor puro mantém `service.py` livre de formatação e dá um ponto único de teste para o formato
que o arquivo e a consulta compartilham. `snake_case` derivado do nome da classe evita uma tabela de nomes a manter.

**Alternatives**: cada evento com seu método de serialização (espalha o formato por cinco classes e impede validar
o formato num só teste); `pickle` ou repr (ilegível e inseguro).

## R11 — Retenção

**Decision**: na Fase 1 não há expurgo automático; a rotação diária de arquivo (R6) é o que prepara a retenção.
Política por dias entra quando existir a configuração do operador que a expresse (011) e um caso de uso.

**Rationale (princípio XII, edge case da spec)**: "retenção limitada e configurável" descreve o estado final; nesta
fase não há operador configurando trace nem volume que exija expurgo, e o arquivo por dia permite apagar por data com
uma linha de shell.

**Alternatives**: expurgo por idade já no adapter (parâmetro que ninguém ajusta e um caminho de exclusão de arquivo
sem quem o peça).

## R12 — Fronteiras de import

**Decision**: contratos novos de import-linter para o módulo — `api.py` não importa `domain`/`ports`/`service`/
`adapters`; `domain` não importa `ports`/`service`/`adapters`; `service` não importa `adapters`; `api`, `domain`,
`ports` e `service` não importam bibliotecas de observabilidade (`opentelemetry`, `logfire`, `sentry_sdk`) — mais o
contrato geral de que `ai_core.observability` não importa outros módulos do core.

**Rationale (princípio XIII, R1)**: é a mesma forma usada no Pack Runtime (002 R13), e o contrato sobre
`opentelemetry` torna executável a decisão R1: se alguém puser a biblioteca no seam, o CI barra.

**Alternatives**: confiar na revisão (a 002 já estabeleceu que fronteira se verifica em CI).

## Fase 6 (US2, US3, US4: harness de avaliação) — 2026-10-13

> Insumos: [design.md](design.md) ("Harness de avaliação", "Julgamento por LLM", "Benchmark de modelos", "Portas e
> adapters"), ADR-007, ADR-012, ADR-013, ADR-017 e o [ADR-027](../../docs/adr/ADR-027-metricas-de-dominio-pelo-contrato-de-pack.md);
> as cinco clarificações de 2026-10-13. Conferido no código: o seam Execution Engine (005, `reference_time` no
> `ExecutionRequest`), a consulta de trace (`TraceQuery`), o `GrantResolver` da 003, o Pack Runtime (002), o Model Router
> (006) e o registro de subcomandos da 011.

### R13 — Escopo e toques fora da 009

**Decision**: o módulo `ai_core/eval/` (US2–US4). Toques declarados: **001** — `ai_core_contracts.eval` (`EvalItem`,
`EvalObservation`, `EvalChunk`, `EvalMetric`, `ProvidesEvalMetrics`) e o default em `PackBase`, contratos `0.1.2`
(ADR-027); **002** — coleta do hook `eval_metrics` na carga e o seam `PackEvalMetrics`; **005** — o evento `Retrieval`
emitido na validação (R15); **009/observabilidade** — o tipo `Retrieval` e `RetrievedChunk` (aditivos, ADR-017);
**011** — os subcomandos `ai-core eval run` e `ai-core eval compare` e a composição do harness. Ao fim, as tags
`contracts-v0.1.2` e `v0.3.0` (ADR-021).

**Rationale**: o harness é adapter primário sobre seams que já existem; o resto são as duas lacunas que a clarificação
nomeou (o que foi recuperado e as métricas de domínio).

**Alternatives**: um repositório ou distribuição à parte para o harness (o design o põe em `ai_core/eval/`; a imagem de
instalação já tem os packs, R25).

### R14 — O harness como adapter primário

**Decision**: `eval/service.py` (`EvalService`) executa cada item pelo seam **Execution Engine** (`run(grant,
ExecutionRequest(..., reference_time=item))`), consumindo os eventos, e depois lê o trace da requisição pela consulta
deste módulo. O grant vem do `GrantResolver` da 003, pelo nome do Assistant e um `Principal` da rodada (R21). Nada de
internals do motor, do Pack Runtime ou do índice.

**Rationale** (design.md; 008 FR-012; ADR-013): é o único caminho que fixa a data de referência, e ler o trace é o que
torna as métricas independentes do flow.

**Alternatives**: chamar a API HTTP (não fixa a data; 008 FR-012).

### R15 — O evento `Retrieval` (clarificação 1)

**Decision**: tipo novo e aditivo da 009 (ADR-017): `Retrieval(request_id, retrieved, reranked, delivered)`, cada lista
de `RetrievedChunk(chunk_id, score, document, version, status, section, page)` — a proveniência do contrato 001, **nunca
o texto**. A 005 o emite uma vez por execução, no passo de validação, a partir da Turn View que já monta
(`retrieved`, `reranked`, `generation_context`), e só quando alguma das três listas tem trecho. *Revisto na
implementação (clarificação de 2026-10-13, sexta pergunta)*: os trechos **entregues** levam também o `text` — o que o
modelo viu —, cortado em 2.000 caracteres e redigido pela serialização do trace, porque o juiz precisa dele para julgar
a fidelidade (R19); candidatos e reordenados seguem sem texto, e o `EvalChunk` do contrato 001 também (ADR-027): o
harness passa o texto ao juiz à parte. Vale para qualquer
flow: no `agentic`, os trechos das tools de recuperação do loop; no `rag_first`, os candidatos, a junção do rerank e os
entregues.

**Rationale**: o motor já projeta exatamente essas listas para os validators (US4 da 005); emitir a projeção é o menor
toque, e o harness lê o mesmo que os validators leram. Sem texto, o trace segue sem conteúdo do corpus.

**Alternatives**: no evento final do seam (muda o seam, ADR); no `ToolCall` da 004 (não veria o rerank nem o corte por
teto).

### R16 — Formato do conjunto dourado (FR-003; clarificação 2)

**Decision**: arquivo YAML (`version: 1`), versionado pelo pack:

| Campo | Regra |
|---|---|
| `name` | texto não vazio |
| `assistant` | default da rodada (o `--assistant` da CLI tem prioridade) |
| `k` | lista de inteiros ≥ 1 para recall@k; default `[5, 20]` |
| `tolerances` | métrica → tolerância absoluta ≥ 0; default 0,02 para as determinísticas |
| `items[].id` | único no arquivo, `^[a-z0-9][a-z0-9._-]*$` |
| `items[].question` | texto não vazio |
| `items[].reference_time` | ISO 8601 com fuso (obrigatório, ADR-013) |
| `items[].expected_documents` | lista de evidências: `document` (obrigatório), `section` e `chunk_id` opcionais |
| `items[].reference_answer` | texto (pode faltar: cobertura fica ausente para o item) |
| `items[].expected_citations` | lista de evidências, como acima |
| `items[].extra` | mapeamento JSON opaco, entregue às métricas de domínio |

Item com problema de formato vira **item inválido**, nomeado no relatório, e não roda; o arquivo inteiro só é recusado
quando não é YAML ou não tem `items`. Documento fora do corpus (Edge Case da spec): o core não conhece o corpus — a
conferência contra o catálogo é do pack (105, nos testes dele) —; o harness aponta, como **aviso** no item, cada
evidência esperada que não aparece entre os candidatos (`retrieved`) de nenhum item da rodada ("evidência não vista").
É sinal de evidência mal escrita ou fora do índice, sem invalidar o item. Casamento de evidência: `document` (e `section`, se dada) por igualdade
normalizada — caixa, espaços em sequência e acentos —; `chunk_id`, se dado, por igualdade exata e com prioridade.

**Rationale**: YAML como os outros arquivos do operador (`packs.yaml`, `assistants.yaml`, `mcp.yaml`); evidência por
documento sobrevive a mudanças de chunking (clarificação 2).

**Alternatives**: JSONL (pior para revisão humana de 30–50 perguntas).

### R17 — Métricas do core (FR-004)

**Decision**: por item, sobre o `Retrieval` e os demais eventos do trace e da execução; agregadas pela média entre os
itens em que se aplicam (salvo as de operação):

| Camada | Métrica | Definição | Determinística |
|---|---|---|---|
| Recuperação | `recall@k` (cada k) | fração das evidências esperadas casadas nos k primeiros de `retrieved` | sim |
| Recuperação | `mrr` | 1/posição da primeira evidência casada em `retrieved` (0 se nenhuma) | sim |
| Recuperação | `delivered_recall` | fração das evidências casadas em `delivered` (o que o modelo viu) | sim |
| Rerank | `rerank_gain` | `recall@n(reranked) − recall@n(retrieved)`, com n = tamanho de `reranked` | sim |
| Citação | `citation_resolvable_rate` | fração das citações finais cujo `chunk_id` está em `delivered` | não |
| Citação | `citation_invented_rate` | fração das citações finais fora de `delivered` | não |
| Citação | `expected_citation_recall` | fração das citações esperadas casadas nas finais | não |
| Geração | `faithfulness`, `coverage` | juiz (R19), 0 a 1 | não |
| Operação | `latency_ms` p50/p95, `ttft_ms` p50/p95, `tokens_per_answer`, `model_calls_per_answer`, `generation_tokens_per_s`, `controller_invalid_rate`, `error_rate`, `gate_routes` (distribuição) | dos eventos da execução e do trace | não |
| Flags | `flag_rate:<flag>` | fração das respostas com cada flag do evento final, sem interpretar o nome | não |

"Determinística" depende só do índice, da data e da composição — não do texto gerado. Recuperação "sem trecho nenhum"
num item com evidência esperada conta 0; item sem evidência esperada fica fora das métricas de recuperação.

**Rationale**: tabela do design; a citação é mecânica (ADR-007) e se mede por `chunk_id`; as flags (por exemplo a de
"não fundamentada") são contadas sem o core conhecer o domínio (princípio I).

**Alternatives**: recall por trecho (quebra com chunking, clarificação 2).

### R18 — Métricas de domínio (FR-005; ADR-027)

**Decision**: o harness pede ao seam `PackEvalMetrics` da 002 as métricas da composição do Assistant, monta o
`EvalItem` e o `EvalObservation` (contrato 001) de cada item e chama `measure`. Nome no relatório: `<pack>:<métrica>`.
Exceção numa métrica de domínio vira registro no relatório (métrica ausente para o item), nunca falha da rodada. Só as
declaradas `deterministic` podem barrar.

**Rationale**: ADR-027.

**Alternatives**: as do ADR-027.

### R19 — Juiz (FR-006; clarificação 4)

**Decision**: porta `Judge` (`async judge(question, answer, passages, reference) -> Judgement(faithfulness, coverage)`);
adapter sobre o Model Router (006) com uma `ModelPolicy` da rodada (`generation` = o modelo juiz; allowlist = só ele),
`request_id` próprio por julgamento (`<id do item>:judge:<n>`), saída por `response_format` com esquema
(`{"faithfulness": number, "coverage": number | null}`, 0 a 1). Os trechos que o juiz lê são o `text` dos entregues no
evento `Retrieval` (R15). Três julgamentos por item; o relatório traz média e
variância. Juiz que falha num julgamento: ele fica fora da média, e a métrica do item fica ausente se os três falham.
Sem juiz configurado (`--judge`), `faithfulness` e `coverage` aparecem como ausentes. O prompt do juiz é do core,
neutro quanto ao domínio.

**Rationale**: o design restringe o juiz ao offline; o Model Router já aplica allowlist, trace e saída estruturada.

**Alternatives**: o modelo de geração do Assistant (clarificação 4, opção C — juiz e réu iguais).

### R20 — Linha de base, tolerância e CI (FR-007, FR-008; US3)

**Decision**: porta `BaselineStore` (`load(path)`, `save(path, report)`), adapter em arquivo JSON — o próprio relatório
de uma rodada aceita. Comparação pura (`domain/compare.py`): por métrica agregada, `delta = atual − base`, regressão
quando `delta` piora além da tolerância no sentido da métrica (`better`); só métricas determinísticas barram. A CLI sai
com **0** sem regressão, **1** com regressão determinística, **2** com entrada inválida (arquivo ilegível, Assistant
inexistente). `--update-baseline` grava o relatório como nova base depois de uma rodada sem regressão (ou com
`--force`). Métrica nova (sem valor na base) não regride; métrica que sumiu é apontada.

**Rationale**: SC-003 (toda regressão determinística barrada) sem que a variância do texto gerado derrube o CI.

**Alternatives**: tolerância relativa (instável perto de 0).

### R21 — O `Principal` da rodada

**Decision**: a CLI aceita `--principal <subject>` (default `svc:eval` — o `Principal` da 003 exige `user:<id>` ou
`svc:<id>`) e `--group` (repetível); o `Principal` usa o esquema `api_key`. A grant é resolvida a cada item, para o
orçamento valer como em produção. O Assistant avaliado precisa admiti-lo na ACL (`allow`), como qualquer chamador; orçamento e
limites valem como para os outros.

**Rationale**: a resolução de grant é a da 003, sem atalho — avaliar o que roda em produção.

**Alternatives**: um principal privilegiado que ignora a ACL (avaliaria outra coisa).

### R22 — Execução e tempo

**Decision**: itens em sequência, na ordem do arquivo; `request_id` = `eval-<rodada>-<item>`, com a rodada estampada pela
porta `Clock`; latência e tempo até o primeiro token medidos pelo `monotonic` da mesma porta (do `run` ao `FinalEvent`
e ao primeiro `TokenEvent`); `stream=True`. Falha antes do primeiro evento (`ExecutionRequestInvalid`, Assistant
indisponível) marca o item como falho e segue.

**Rationale**: o hardware alvo é um nó só, e a ordem fixa torna as rodadas comparáveis; SC-002 (50 perguntas em até
30 min) cabe com modelo local de 1–2 s por resposta.

**Alternatives**: concorrência (mediria disputa pelo modelo, não o sistema).

### R23 — Relatório (formato de seam)

**Decision**: JSON (`version: 1`): metadados da rodada (nome do conjunto, Assistant, juiz, horário, versão do core,
`k`), `metrics` (agregadas: `value`, `variance` quando houver, `n` de itens, `deterministic`, `better`), `items` (por
item: métricas, citações, flags, registros, rotas do portão, invalidez ou falha) e `annotations` (texto livre do
operador). Saída humana no terminal: uma tabela das métricas e, na comparação, o delta e a regressão.

**Rationale**: o relatório é seam (Module Boundary): a linha de base é um relatório, e o `compare` lê dois.

**Alternatives**: CSV (perde a estrutura por item).

### R24 — Benchmark de modelos (US4; clarificação 5)

**Decision**: comparar modelos = comparar Assistants que diferem só no modelo — o operador os declara no
`assistants.yaml` — rodando `eval run` uma vez por Assistant, e `ai-core eval compare <relatório>…` mostra as métricas
lado a lado. RAM e CPU entram por `--annotate "<texto>"` no `eval run` (gravado em `annotations`). A confiabilidade de
tool calling é a `controller_invalid_rate`; a "qualidade em português" da US4 é a `coverage` julgada num conjunto dourado
em português, ao lado da `faithfulness` — nenhuma métrica nova.

**Rationale**: o grant continua o da 003 (sem trocar modelo por fora da allowlist); o benchmark é o mesmo harness.

**Alternatives**: um `--model` que sobrescreve a política do grant (contornaria a allowlist do Assistant).

### R25 — Onde roda

**Decision**: subcomandos da 011 — `ai-core eval run --golden <arquivo> [--assistant] [--judge provider/modelo]
[--baseline <arquivo>] [--update-baseline] [--report <arquivo>] [--principal] [--group] [--annotate]` e `ai-core eval
compare <relatório> <relatório>…` —, que sobem a plataforma do perfil configurado sem abrir a API e compõem o
`EvalService` com o motor, a consulta de trace, a 003, a 002, o juiz e a linha de base. O backend de trace precisa ler
(memória ou JSONL); sem leitura, a rodada sai com 2 e explica.

**Rationale**: design.md ("subcomando `ai-core eval run`, registrado pela 011"); roda na imagem de instalação, que já
tem os packs (105).

**Alternatives**: um executável à parte (duplicaria a composição da 011).

### R26 — Portas, testes e fronteiras

**Decision**: `eval/api.py` (seam: `EvalHarness`, `GoldenSet`, `GoldenItem`, `Evidence`, `EvalReport`, `MetricValue`,
`Comparison`, `GoldenSetError`); `eval/domain/` (`golden.py` validação e conversão, `matching.py`, `metrics.py`,
`judging.py` agregação, `compare.py`) puro; `eval/ports.py` (`Judge`, `BaselineStore`, `GoldenSetSource`, `Clock`);
`eval/service.py`; `eval/adapters/` (YAML, JSON, juiz pelo Model Router, CLI). import-linter: `ai_core.eval` só importa
os `api.py` de 002, 003, 005, 006 e 009; camadas como nos outros módulos. Testes: domínio por tabela; o serviço com o
motor real no perfil `test` e um pack de teste com retriever, reranker e uma métrica de domínio; conformidade das portas
(memória × arquivo).

**Rationale**: princípio XIII, como os outros módulos.

**Alternatives**: nenhum.

### R27 — Release

**Decision**: ao fim, `contracts-v0.1.2` (contratos `0.1.2`) e `v0.3.0` (core; o `ai-generic` não muda), no
`agentic-app` (ADR-021). A 105 aponta para elas.

**Rationale**: a 105 precisa do harness e do protocolo de métrica numa referência estável.

**Alternatives**: commit (ADR-021 prevê tag).

## Fase 9 (2026-10-14): destinos do trace, uso e custo, Langfuse e conteúdo opcional

Insumos: ADR-033, ADR-034, a clarificação de 2026-10-13 (avaliação entra no uso, marcada), o desenho aprovado da console
(tela "Uso e custo", "Tabela de preços", "Observabilidade") e a skill `dataviz` (a paleta das séries é da 013).

### R28 — Fan-out de destinos no `TraceService`

**Decision**: `TraceService(primary: TraceExporter, destinations: Sequence[TraceDestination], reader, clock,
content: ContentPolicy)`. O `primary` é o backend consultável (memória ou JSONL) e continua recebendo cada registro na
hora (FR-012). Cada `TraceDestination` tem `accepts_content: bool`, `export(record)` não bloqueante e `stats()`
(enfileirados, descartados, último erro); falha de um destino é contada nele e nunca chega a quem emite nem aos outros.
O seam `TraceSink` não muda.

**Rationale**: ADR-034; o primário mantém a semântica da FR-012, e os destinos de banco ou rede só enfileiram.

**Alternatives considered**: tornar todos os destinos iguais ao primário (o Langfuse lento atrasaria a execução).

### R29 — Evento `ModelExchange` e política de conteúdo

**Decision**: `ModelExchange(request_id, role, provider, model, messages: tuple[ExchangeMessage, ...], output: str)` no
`TraceEvent` (ADR-034 — o único evento com texto além dos trechos entregues da FR-004), emitido pela 006 logo depois do
`ModelCall`. `ContentPolicy.capture` (efetivo de `TraceDestinations`) decide no `TraceService`: desligado → o evento é
descartado antes de virar registro; ligado → passa pela redação de credenciais, cada mensagem e a saída cortadas em
16 KiB com marca, e só vai a destinos com `accepts_content`. O primário nunca o recebe.

**Rationale**: o texto existe só onde foi pedido e só para quem aceita (ADR-034); a regra fica num lugar.

**Alternatives considered**: campo opcional no `ModelCall` (ADR-034 rejeitou).

### R30 — Destino de uso e o relatório

**Decision**: `UsageDestination` (projeção pura em `domain/usage.py`): `execution_started` abre a entrada da requisição
(Assistant, flow, início) num mapa com TTL de 1 h; `model_call` vira linha de `model_calls` com o Assistant da entrada
(sem entrada → sem Assistant); `execution_finished` fecha a execução. Buffer `deque(maxlen=10_000)`; `flush()` assíncrono
grava em lote pelo `UsageStore` — chamado por uma tarefa periódica de 2 s (montada pela 011) e no encerramento. A origem
(`production`/`evaluation`) é um parâmetro do destino, fixado pela 011 por processo (clarificação de 2026-10-13).
Consulta: `UsageStore.daily(start, end, tz, by, origin)` agrega por dia local (`date_trunc('day', at AT TIME ZONE tz)`),
e o serviço junta os preços (R31) para o custo.

**Rationale**: linhas brutas são pequenas no volume esperado (SC-008: 100 mil chamadas em 90 dias); o fuso é parâmetro
da consulta, então mudar o fuso não exige migração.

**Alternatives considered**: agregados diários pré-calculados (um preço lançado depois exigiria recalcular; o fuso
ficaria preso).

### R31 — Preços com vigência e custo na consulta

**Decision**: `PriceStore` com `prices(provider, model, usd_per_mtok_in, usd_per_mtok_out, effective_from date,
created_by, created_at)`; preço vigente num dia = o de maior `effective_from` ≤ o dia. Custo de um dia e modelo =
`in_tok × in / 1e6 + out_tok × out / 1e6`, em `Decimal` com 6 casas e arredondado só na apresentação. Modelo sem preço
vigente num dia → custo ausente naquele dia e a linha marcada "sem preço"; o total do período fica "incompleto". Ollama
sem preço é "sem preço" até alguém cadastrar zero.

**Rationale**: ADR-034 (custo é projeção, calculado na consulta); `Decimal` evita erro de ponto flutuante em somas
longas.

**Alternatives considered**: preço por provider sem modelo (OpenRouter tem preço por modelo).

### R32 — Langfuse por OpenTelemetry

**Decision**: `LangfuseTransport` em `adapters/langfuse.py` com `opentelemetry-sdk` e
`opentelemetry-exporter-otlp-proto-http` (confinados a `observability/adapters/` — o import-linter já proíbe OTel no
núcleo, R1): endpoint `{host}/api/public/otel/v1/traces`, cabeçalho `Authorization: Basic base64(public:secret)`,
`BatchSpanProcessor` (fila de 2 048, lote de 256, 5 s; descarta quando cheia). Mapeamento: `execution_started` abre o
span raiz (nome = Assistant; `langfuse.trace.name`, `langfuse.trace.metadata.flow`/`packs`), guardado por `request_id`
com TTL; `model_call` vira span filho com `start_time = at − duration_ms` e `end_time = at`,
`langfuse.observation.type = "generation"`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`/`output_tokens`, nível
`ERROR` em falha; `model_exchange` preenche `langfuse.observation.input`/`output` do último span de geração da mesma
requisição; `tool_call` vira span `tool`; `controller_decision`, `coverage_gate`, `validation_run`, `retrieval` e
`execution_error` viram eventos do span raiz (mensagem redigida); `execution_finished` encerra o raiz. "Testar
conexão": `GET {host}/api/public/projects` com a mesma autenticação (200 → projeto; 401 → credencial recusada).
`reload()` ao gravar ajustes: novo provider/exportador; o antigo é esvaziado e desligado.

**Rationale**: o Langfuse recebe OTLP nativamente; o SDK de OTel dá lote, fila limitada e retentativa; ADR-013 e R1 já
deixavam o OTel como adapter. Os nomes de atributo seguem as convenções `gen_ai.*` e `langfuse.*` que o Langfuse mapeia
— **a conferir** contra uma instância real na tarefa de verificação (T070).

**Alternatives considered**: a API de ingestão própria do Langfuse com `httpx` (sem dependência nova, mas sem fila nem
lote prontos e marcada como legado); o SDK Python do Langfuse (puxa dependências e assume que controla o ciclo de vida
dos spans).

**Medição (T065, 2026-10-14)**: `emit` de 3 000 eventos com o exportador OTLP travado e o banco de uso lento — ~10 µs
por evento só com o primário, ~11,5 µs com o destino de uso, ~22,5 µs com uso e Langfuse. Nada espera rede nem banco,
mas o mapeamento para spans dobra o custo de CPU por evento: a SC-006 ao pé da letra ("primário sozinho + 10%") não se
cumpre com o Langfuse ligado. Em valor absoluto (~12 µs a mais por evento, dezenas de eventos por execução) é
desprezível diante de uma chamada de modelo. **Pendente do mantenedor**: reescrever a SC-006 como teto absoluto (o
teste usa 500 µs por evento) ou mover o mapeamento para a thread do exportador.

### R33 — Ajustes dos destinos, precedência e segredo

**Decision**: `DestinationSettingsStore` guarda `langfuse_enabled`, `langfuse_host`, `langfuse_public_key`,
`langfuse_secret_sealed` (selado pela porta `SecretCipher`, AES-GCM com subchave HKDF `ai-core/observability/v1` —
ADR-033), `capture_content`, `version`, `updated_by`, `updated_at`. Precedência pura em `domain/settings.py`:
`AI_CORE_LANGFUSE_HOST|PUBLIC_KEY|SECRET_KEY` (tudo ou nada: parcial é erro de configuração, nomeando a que falta) >
banco > padrão (desligado); `AI_CORE_LANGFUSE_CAPTURE_CONTENT` à parte. Campo da instalação → escrita recusada com
`InstallationDefined(field)`; segredo nunca devolvido (só `secret_set: bool` e a origem). Sem chave mestra → gravar o
segredo levanta `MasterKeyMissing`; o resto grava.

**Rationale**: decisão do mantenedor (com console, chaves pela console; sem, pela instalação), sem o core saber se há
console.

**Alternatives considered**: segredo em claro no banco (ADR-033 rejeitou).

### R34 — Retenção e saúde

**Decision**: `UsageStore.purge(before)` diário (tarefa da 011), com `AI_CORE_USAGE_RETENTION_DAYS` (padrão 400); preços
não expiram. Saúde: `TraceDestinations.health()` devolve, por destino, `ok | degraded` com descartes nas últimas 24 h e
último erro — a 011 vira os itens não críticos `trace:usage` e `trace:langfuse`.

**Rationale**: 400 dias cobrem comparação ano a ano; destino de observação nunca derruba a plataforma.

**Alternatives considered**: sem retenção (crescimento sem limite).

### R35 — Toque declarado na 006

**Decision**: em `llm/service.py`, o `TracedModel` monta o `ModelExchange` com as mensagens enviadas (papel e texto;
partes não textuais viram marcador) e a saída final — em streaming, a acumulada ao fim — e o emite depois do `ModelCall`.
Nada de cabeçalho nem credencial. Sem custo quando a captura está desligada além de montar a tupla (o `TraceService`
descarta).

**Rationale**: ADR-034; quem tem o texto é a 006.

**Alternatives considered**: a 009 pedir o texto à 006 (inverteria a seta).

### R36 — Testes da Fase 9

**Decision**: unidade (`usage.py`, preço vigente, fuso, precedência); conformidade (destinos: falha isolada, fila
cheia descarta e conta; conteúdo nunca no primário — SC-007; `UsageStore`/`PriceStore`/`DestinationSettingsStore`
memória × Postgres; `SecretCipher`; `LangfuseTransport` contra um coletor OTLP falso local); integração (SC-005: tokens
do relatório = soma das chamadas emitidas; SC-006: destino travado não atrasa `emit` — medido; SC-008: 100 mil
chamadas em 90 dias < 1 s no Postgres de teste). Marcas `us5`, `us6`, `us7`.

**Rationale**: os SC são mensuráveis por teste.

**Alternatives considered**: —

### R37 — Release

**Decision**: depois das passadas da Fase 9 (012, 003, 009+006, 008, 011), o core sobe para `0.6.0` — tag `v0.6.0`
**só com aprovação do mantenedor**; contratos não mudam.

**Rationale**: o padrão das fases anteriores.

**Alternatives considered**: —

### R38 — Encaixe na 011 (incremento 9.2, 2026-10-14)

**Decision**: duas mudanças de adapter, sem seam novo. (1) O exportador OTLP do `OtelLangfuseTransport` passa por um
invólucro (`_Watched`) que registra o resultado de cada exportação: a exportação roda na thread do
`BatchSpanProcessor`, e sem ele um Langfuse fora do ar nunca chegaria à saúde (011 US6 cenário 4); o último resultado
vale — o Langfuse que volta deixa de aparecer degradado. (2) `UsageDestination.flush(store=None)` aceita outro
`UsageStore` só para aquela gravação: a 011 passa o da sessão da linha de comando (`ai-core eval run`), em que o pool de
serviço não abre (011 R13).

**Rationale**: a saúde não pode dizer "ok" com o destino fora do ar; e o uso das rodadas de avaliação no `persistent`
não pode se perder no encerramento.

**Alternatives considered**: ler o log do OTel (frágil); uma tarefa periódica na linha de comando (o processo termina
antes).
