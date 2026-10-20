# Data Model — 009 Trace por requisição, Fase 1

Tudo aqui é value object congelado do `api.py` do módulo, exceto onde indicado. `JSONValue` vem de
`axon_ai_contracts` (001).

## Eventos (o que os emissores mandam)

Campo comum a todos: `request_id: str` (não vazio). O instante **não** é campo de evento: o serviço o estampa pela
porta `Clock` ([research.md](research.md) R3).

### `ExecutionStarted`

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | `str` | não vazio |
| `assistant` | `str` | não vazio — nome resolvido |
| `flow` | `str` | não vazio — nome do flow escolhido |
| `packs` | `tuple[str, ...]` | nomes dos packs ativos, na ordem da composição; pode ser vazia |
| `reference_time` | `datetime` | com timezone (ADR-013); é a data de referência da execução, não o instante do evento |

### `ModelCall`

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | `str` | não vazio |
| `role` | `str` | papel do modelo (`controller`, `generation`, `rerank`) — texto, para não duplicar aqui o vocabulário da 006 |
| `provider` | `str` | não vazio |
| `model` | `str` | não vazio |
| `input_tokens` | `int \| None` | `>= 0` quando presente; `None` quando o provider não informa |
| `output_tokens` | `int \| None` | idem |
| `duration_ms` | `float` | `>= 0`, medido pelo emissor |
| `finish_reason` | `str \| None` | texto livre → redigido |
| `cost_usd` | `float \| None` | `>= 0`; o custo que o provider **informou** (ADR-035); `None` quando ele não informa |

### `ValidationRun`

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | `str` | não vazio |
| `pack` | `str` | não vazio — pack dono do validator |
| `validator` | `str` | não vazio |
| `ok` | `bool` | resultado |
| `issues` | `tuple[str, ...]` | texto livre → redigido |
| `flags` | `frozenset[str]` | sinalizações do validator |

### `ExecutionError`

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | `str` | não vazio |
| `stage` | `str` | etapa em que ocorreu (texto do emissor) |
| `kind` | `str` | tipo do erro (nome da exceção, por exemplo) |
| `message` | `str` | **texto livre — redigido e truncado** (o vetor real de vazamento, R7) |

### `ExecutionFinished`

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | `str` | não vazio |
| `ok` | `bool` | desfecho |
| `duration_ms` | `float` | `>= 0` |
| `reason` | `str \| None` | por que terminou assim; texto livre → redigido. Deliberadamente livre: o vocabulário de estados é interno da 005 (R2) |

### `ToolCall` — Fase 3, emitido pela 004 ([ADR-017](../../docs/adr/ADR-017-trace-sink-cresce-por-eventos-aditivos.md))

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | `str` | não vazio |
| `tool` | `str` | não vazio — o nome pedido, com namespace |
| `kind` | `str \| None` | `native`, `retrieval`, `mcp`; `None` quando a tool não existe no catálogo |
| `status` | `str` | não vazio — `ok`, `error`, `timeout`, `unknown`, `invalid_arguments` |
| `duration_ms` | `float` | `>= 0` |
| `size_bytes` | `int` | `>= 0` — tamanho do conteúdo entregue ao modelo |
| `truncated` | `bool` | conteúdo cortado no limite |

Sem argumentos nem conteúdo.

### `ControllerDecision` — Fase 3, emitido pela 005 (ADR-017)

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | `str` | não vazio |
| `iteration` | `int` | `>= 0`; `0` só com `action="limit"` |
| `action` | `Literal["tool", "answer", "invalid", "limit"]` | — |
| `tool` | `str \| None` | obrigatório e não vazio em `tool`; ausente nas outras |
| `reason` | `str \| None` | obrigatório em `invalid` e `limit` (em `limit`: `iterations` ou `context`); ausente nas outras |

Sem argumentos de tool nem saída do modelo — o motivo é texto do motor.

### `CoverageGate` — Fase 5, emitido pela 005 (ADR-017)

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | `str` | não vazio |
| `candidates` | `int` | `>= 0` — trechos recuperados, somando as tools de recuperação |
| `passages` | `int` | `>= 0` e `<= candidates` — trechos depois do rerank, os que o portão compara |
| `best_score` | `float \| None` | ausente exatamente quando `passages == 0`; nunca NaN |
| `threshold` | `float \| None` | limiar do operador em `[0, 1]`; ausente sem limiar |
| `covered` | `bool` | verdadeiro exatamente quando `route == "generate"` |
| `route` | `Literal["generate", "controller", "fallback"]` | gerar com os trechos, escalar para o loop, gerar sem trechos |

Sem texto nem identificador de trecho.

Regra comum: campo `str` marcado como "não vazio" rejeita vazio e só-espaços na construção (`ValueError`), como os
value objects da 001; campos de texto livre são redigidos na serialização, não na construção.

## Registro (o que o backend guarda e a consulta devolve)

`TraceRecord` — value object de leitura:

| Campo | Tipo | Conteúdo |
|---|---|---|
| `at` | `datetime` | instante estampado pelo serviço, com timezone |
| `type` | `str` | nome do evento em `snake_case`: `execution_started`, `model_call`, `validation_run`, `tool_call`, `controller_decision`, `coverage_gate`, `execution_error`, `execution_finished` |
| `request_id` | `str` | identificador da requisição |
| `attributes` | `Mapping[str, JSONValue]` | demais campos do evento, já redigidos; `None` omitido |

`Trace` — resultado da consulta: `request_id: str` e `records: tuple[TraceRecord, ...]`, na ordem de emissão.

Formato serializado em [contracts/record-format.md](contracts/record-format.md).

## Redação (`domain/redaction.py`, puro)

| Entrada | Saída |
|---|---|
| mapeamento com chave sensível (`authorization`, `api_key`, `apikey`, `token`, `access_token`, `refresh_token`, `secret`, `password`, `passwd`, `cookie`, `set-cookie`, `private_key`), em qualquer profundidade; comparação sem distinguir maiúsculas, `-` e `_` | valor substituído por `«redigido»` |
| texto com `Bearer <valor>` | `Bearer «redigido»` |
| texto com `<nome sensível>=<valor>` ou `<nome sensível>: <valor>` | valor substituído por `«redigido»` |
| texto com credencial em URL (`https://usuário:senha@host`) | `https://usuário:«redigido»@host` |
| texto acima de 2000 caracteres | primeiros 2000 caracteres + `… [truncado: N caracteres]` |
| qualquer outro valor | inalterado |

A redação é idempotente: aplicá-la duas vezes dá o mesmo resultado.

## Estados e falhas

| Situação | Resultado |
|---|---|
| Emissão com exporter saudável | registro gravado; nada devolvido (a emissão não tem retorno) |
| Exporter levanta qualquer exceção | exceção **não** propaga; `logger.warning` com o tipo do erro; `dropped_events()` incrementa (R8) |
| Consulta de requisição sem nenhum evento | `Trace` com `records` vazio — a requisição pode não ter começado |
| Consulta com perfil sem `TraceReader` | erro explícito `TraceQueryUnavailable` nomeando o backend configurado (R5) |
| Evento com `request_id` vazio | `ValueError` na construção do evento — erro de quem emite, detectado antes de qualquer I/O |

## Portas

| Porta | Operação | Adapters da fase |
|---|---|---|
| `TraceExporter` | `export(record: TraceRecord) -> None` | memória, JSONL |
| `TraceReader` | `read(request_id: str) -> Sequence[TraceRecord]` | memória, JSONL |
| `Clock` | `now() -> datetime` (com timezone) | fixo (teste), sistema |

Detalhes e suítes de conformidade em [contracts/ports.md](contracts/ports.md).

# Fase 6 (US2, US3, US4: harness) — 2026-10-13

Decisões em [research.md](research.md) R13–R27.

## Trace (aditivo, ADR-017)

### `RetrievedChunk`

| Campo | Tipo | Regra |
|---|---|---|
| `chunk_id` | `str` | não vazio |
| `score` | `float` | o `Chunk.score` |
| `document` | `str` | não vazio |
| `version`, `status`, `section` | `str \| None` | do `Chunk` (001) |
| `page` | `int \| None` | ≥ 1 quando presente |
| `text` | `str \| None` | só nos `delivered` (o que o modelo viu); cortado em 2.000 caracteres e redigido na serialização |

Candidatos e reordenados nunca levam texto.

### `Retrieval` — emitido pela 005 na validação

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | `str` | não vazio |
| `retrieved` | `tuple[RetrievedChunk, ...]` | os candidatos (Turn View `retrieved`), na ordem |
| `reranked` | `tuple[RetrievedChunk, ...]` | a junção do rerank (vazia fora do `rag_first`) |
| `delivered` | `tuple[RetrievedChunk, ...]` | o `generation_context` |

Emitido só quando alguma lista tem trecho. Registro `type == "retrieval"`.

## Contrato 001 — `axon_ai_contracts.eval` (ADR-027)

| Tipo | Campos |
|---|---|
| `EvalEvidence` | `document: str`, `section: str \| None`, `chunk_id: str \| None` |
| `EvalItem` | `id`, `question`, `reference_time` (com fuso), `expected_documents: tuple[EvalEvidence, ...]`, `reference_answer: str \| None`, `expected_citations: tuple[EvalEvidence, ...]`, `extra: Mapping[str, JSONValue]` |
| `EvalChunk` | `chunk_id`, `score`, `document`, `version`, `status`, `section`, `page` |
| `EvalObservation` | `answer: str`, `citations: tuple[Citation, ...]`, `flags: frozenset[str]`, `retrieved`, `reranked`, `delivered: tuple[EvalChunk, ...]`, `issue_kinds: tuple[str, ...]` |
| `EvalMetric` (Protocol) | `name: str`, `better: Literal["higher", "lower"]`, `deterministic: bool`, `measure(item, observation) -> float \| None` |
| `ProvidesEvalMetrics` (Protocol) | `eval_metrics(ctx: PackContext) -> Sequence[EvalMetric]` |

`PackBase.eval_metrics` devolve `()`. `__version__ = "0.1.2"`.

## 002 — seam `PackEvalMetrics`

`eval_metrics(composition) -> Sequence[PackEvalMetric]`, com `PackEvalMetric(pack: str, metric: EvalMetric)`, na ordem
da composição; coletado uma vez na carga (hook que levanta ou devolve tipo errado → pack em erro, como os outros).

## Harness (`axon_ai/eval/api.py`)

| Tipo | Campos | Regra |
|---|---|---|
| `Evidence` | `document`, `section`, `chunk_id` | `document` não vazio |
| `GoldenItem` | `id`, `question`, `reference_time`, `expected_documents`, `reference_answer`, `expected_citations`, `extra` | id `^[a-z0-9][a-z0-9._-]*$`; `reference_time` com fuso |
| `GoldenSet` | `name`, `assistant: str \| None`, `k: tuple[int, ...]`, `tolerances: Mapping[str, float]`, `items`, `invalid: tuple[InvalidItem, ...]` | ids únicos; `k` ≥ 1; tolerâncias ≥ 0 |
| `InvalidItem` | `id: str \| None`, `reason: str` | o item não roda |
| `MetricValue` | `name`, `value: float \| None`, `variance: float \| None`, `n: int`, `deterministic: bool`, `better: Better \| None` | `value` `None` = ausente; `better` `None` = informativa (frações de flags e de rotas do portão), nunca regride |
| `ItemResult` | `id`, `metrics: Mapping[str, float \| None]`, `citations`, `flags`, `issue_kinds`, `gate_route: str \| None`, `failure: str \| None`, `warnings` | avisos: "evidência não vista" (R16) e métrica de domínio que levantou (R18) |
| `EvalReport` | `golden_set`, `assistant`, `judge: str \| None`, `started_at`, `core_version`, `k`, `metrics: tuple[MetricValue, ...]`, `items: tuple[ItemResult, ...]`, `invalid`, `annotations: tuple[str, ...]` | |
| `MetricDelta` | `name`, `baseline`, `current`, `delta`, `tolerance`, `regressed: bool` | só determinísticas regridem |
| `Comparison` | `deltas: tuple[MetricDelta, ...]`, `missing: tuple[str, ...]` | `regressed` = alguma delta regrediu |
| `GoldenSetError`, `EvalInputError` | exceções | arquivo do conjunto inutilizável; rodada que não pode começar (Assistant, trace sem leitura, relatório ilegível) → saída 2 |

### Portas (`axon_ai/eval/ports.py`)

| Porta | Métodos |
|---|---|
| `GoldenSetSource` | `load(path) -> GoldenSet` (levanta `GoldenSetError` só para arquivo ilegível ou sem `items`) |
| `BaselineStore` | `load(path) -> EvalReport \| None`, `save(path, report)` |
| `Judge` | `async judge(*, question, answer, passages: Sequence[str], reference: str \| None, request_id) -> Judgement` |
| `Clock` | `now() -> datetime`, `monotonic() -> float` |

`Judgement(faithfulness: float | None, coverage: float | None)`, em `[0, 1]` (definido em `domain/judging.py`; a porta o
reexporta). `EvalHarness.run(golden, *, assistant, principal, annotations=())`.

## Fase 9 (2026-10-14): destinos, uso, preços e conteúdo (research R28–R35)

### Evento novo no `TraceEvent` (seam, ADR-034)

`ModelExchange(request_id, role, provider, model, messages: tuple[ExchangeMessage, ...], output: str)`;
`ExchangeMessage(role: Literal["system", "user", "assistant", "tool"], content: str)`. Registro `model_exchange`; nunca
entregue ao backend primário.

### Value objects dos seams novos

| Nome | Campos |
|---|---|
| `UsageQuery` | `start: date`, `end: date` (inclusivos), `tz: str` (IANA), `by: Literal["model", "assistant"]`, `origin: Literal["production", "evaluation", "all"]` |
| `UsageRow` | `key` (modelo `provider/model` ou Assistant; `None` = "fora de Assistant"), `calls`, `requests`, `input_tokens`, `output_tokens`, `cost: Decimal \| None`, `priced: bool` |
| `UsageDay` | `day: date`, `rows: tuple[UsageRow, ...]` |
| `UsageReport` | `query`, `days: tuple[UsageDay, ...]`, `totals: tuple[UsageRow, ...]`, `total_cost: Decimal \| None`, `incomplete: bool`, `previous_total_cost: Decimal \| None` (mesmo tamanho de período, antes) |
| `Price` | `provider`, `model`, `usd_per_mtok_in: Decimal`, `usd_per_mtok_out: Decimal`, `effective_from: date`, `created_by`, `created_at`, `state: Literal["current", "superseded", "scheduled"]` |
| `DestinationSettingsView` | `langfuse_enabled`, `langfuse_host`, `langfuse_public_key`, `langfuse_secret_set: bool`, `capture_content`, `sources: Mapping[str, SettingSource]`, `version` |
| `DestinationHealth` | `name` (`usage`, `langfuse`), `state: Literal["ok", "degraded", "off"]`, `dropped_24h: int`, `last_error: str \| None`, `last_sent_at: datetime \| None` |
| `ConnectionCheck` | `ok: bool`, `detail: str` (ex.: projeto aceito, credencial recusada, endereço inalcançável) |

Erros novos: `InstallationDefined(field)`, `MasterKeyMissing`, `InvalidPrice(field)`, `Conflict` (versão).

### Tabelas (schema `observability`, ADR-015)

| Tabela | Chave | Colunas |
|---|---|---|
| `model_calls` | `id bigserial` | `request_id`, `at timestamptz`, `origin`, `assistant`, `provider`, `model`, `role`, `input_tokens`, `output_tokens`, `duration_ms`, `failed`, `reported_cost_usd numeric` (nulo quando o provider não informa; migração `004`, ADR-035); índices em `at` e (`provider`, `model`, `at`) |
| `executions` | `request_id` | `started_at`, `finished_at`, `origin`, `assistant`, `flow`, `ok`, `duration_ms`; índice em `started_at` |
| `prices` | (`provider`, `model`, `effective_from`) | `usd_per_mtok_in numeric(12,6)`, `usd_per_mtok_out numeric(12,6)`, `created_by`, `created_at` |
| `destination_settings` | `id = 1` | `langfuse_enabled`, `langfuse_host`, `langfuse_public_key`, `langfuse_secret_sealed bytea`, `capture_content`, `version`, `updated_by`, `updated_at` |
| `schema_version` | `version` | padrão |
