# Data Model — 009 Trace por requisição, Fase 1

Tudo aqui é value object congelado do `api.py` do módulo, exceto onde indicado. `JSONValue` vem de
`ai_core_contracts` (001).

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

Regra comum: campo `str` marcado como "não vazio" rejeita vazio e só-espaços na construção (`ValueError`), como os
value objects da 001; campos de texto livre são redigidos na serialização, não na construção.

## Registro (o que o backend guarda e a consulta devolve)

`TraceRecord` — value object de leitura:

| Campo | Tipo | Conteúdo |
|---|---|---|
| `at` | `datetime` | instante estampado pelo serviço, com timezone |
| `type` | `str` | nome do evento em `snake_case`: `execution_started`, `model_call`, `validation_run`, `execution_error`, `execution_finished` |
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
