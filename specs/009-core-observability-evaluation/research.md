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
