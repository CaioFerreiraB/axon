---

description: "Task list for 009 — trace por requisição (Trace Sink e consulta), Fase 1"
---

# Tasks: Trace por requisição (Trace Sink e consulta)

**Input**: Design documents from `/specs/009-core-observability-evaluation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A constituição exige suíte de conformidade para cada seam exposto e para cada porta secundária
(princípio XIII), e FR-002 (nenhuma credencial) e FR-011 (falha do backend não interrompe) só se demonstram por teste.

**Organization**: só a **User Story 1** (Fase 1 do roadmap). US2–US4 (harness, regressão em CI, benchmark) são Fase 6:
nada é criado em `ai_core/eval/` nesta fase.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1)
- Todo caminho é relativo à raiz do repositório

## Path Conventions

- Código: `ai-core/packages/core/src/ai_core/observability/`
- Testes: `ai-core/packages/core/tests/observability/{unit,contract,integration}/`
- Configuração do workspace: `ai-core/pyproject.toml` (o gatilho de CI de `packages/core/**` já existe)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: o módulo existe no layout do ADR-012

- [X] T001 Criar o esqueleto do módulo em `ai-core/packages/core/src/ai_core/observability/`: `__init__.py`
  (docstring: consumidores importam `ai_core.observability.api`), `domain/__init__.py` e `adapters/__init__.py`.
  Nenhum arquivo em `ai_core/eval/` — o harness é Fase 6

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: o `api.py` (tipos que todo o resto usa), as portas e as fábricas de teste

**⚠️ CRITICAL**: T002 e T003 precedem o conftest e qualquer implementação de serviço ou adapter

- [X] T002 Implementar `ai-core/packages/core/src/ai_core/observability/api.py` conforme
  [contracts/trace-api.md](contracts/trace-api.md) e as tabelas de [data-model.md](data-model.md): as cinco
  dataclasses de evento (`frozen=True, slots=True, kw_only=True`) — `ExecutionStarted` (`request_id`, `assistant`,
  `flow`, `packs: tuple[str, ...]`, `reference_time: datetime` com timezone), `ModelCall` (`request_id`, `role`,
  `provider`, `model`, `input_tokens: int | None`, `output_tokens: int | None`, `duration_ms: float`,
  `finish_reason: str | None`), `ValidationRun` (`request_id`, `pack`, `validator`, `ok: bool`,
  `issues: tuple[str, ...]`, `flags: frozenset[str]`), `ExecutionError` (`request_id`, `stage`, `kind`, `message`) e
  `ExecutionFinished` (`request_id`, `ok: bool`, `duration_ms: float`, `reason: str | None`); `type TraceEvent` como
  união dos cinco; `TraceRecord` (`at`, `type`, `request_id`, `attributes: Mapping[str, JSONValue]`) e
  `Trace` (`request_id`, `records: tuple[TraceRecord, ...]`); Protocols `TraceSink` (`emit`) e `TraceQuery`
  (`trace`, `dropped_events`); `TraceQueryUnavailable(RuntimeError)`. Validação na construção: todo `str` marcado
  "não vazio" no data-model rejeita vazio e só-espaços (`ValueError`), `reference_time` exige timezone,
  `input_tokens`/`output_tokens` exigem `>= 0` quando presentes e `duration_ms` exige `>= 0`. Só stdlib e
  `ai_core_contracts`
- [X] T003 [P] Implementar `ai-core/packages/core/src/ai_core/observability/ports.py` conforme
  [contracts/ports.md](contracts/ports.md): Protocols `TraceExporter` (`export(record) -> None`, documentando que
  pode levantar e que quem chama trata), `TraceReader` (`read(request_id) -> Sequence[TraceRecord]`, vazio quando não
  há registro) e `Clock` (`now() -> datetime`, sempre com timezone)
- [X] T004 Criar `ai-core/packages/core/tests/observability/conftest.py` com as fábricas de teste: um instante fixo
  de referência (`datetime(2026, 9, 17, 14, tzinfo=UTC)`), construtores curtos para os cinco eventos com valores
  válidos por default, e `FailingTraceExporter` (levanta `OSError` em `export`) para os testes de FR-011 (depende de
  T002 e T003 — as fábricas usam os eventos e a porta)

**Checkpoint**: tipos, portas e fábricas de teste existem; o resto depende só deles

---

## Phase 3: User Story 1 — Entender por que uma execução se comportou assim (Priority: P1) 🎯 MVP

**Goal**: cada requisição produz um trace consultável pelo identificador, com os eventos dos módulos da Fase 1, sem
credencial, sobrevivendo a interrupção, e sem que falha de backend atrapalhe a execução.

**Independent Test**: [quickstart.md](quickstart.md) §2 a §5 — emitir e consultar em memória, conferir a redação,
quebrar o backend de propósito e ver o arquivo JSONL com rotação por dia.

### Tests for User Story 1 ⚠️

> Escreva estes testes primeiro e confirme que falham antes de implementar.

- [X] T005 [P] [US1] Criar `ai-core/packages/core/tests/observability/unit/test_observability_api.py`: cada evento
  aceita valores válidos e é imutável e hashável; `request_id` vazio ou só-espaços → `ValueError`; `assistant`,
  `flow`, `pack`, `validator`, `provider`, `model`, `stage`, `kind` idem; `reference_time` sem timezone →
  `ValueError`; `input_tokens=-1`, `output_tokens=-1` e `duration_ms=-1` → `ValueError`; `packs`, `issues` e `flags`
  chegam congelados; os nomes públicos do módulo são exatamente os de
  [contracts/trace-api.md](contracts/trace-api.md) e o `api.py` só importa stdlib e `ai_core_contracts` (varredura
  AST, como em 002 T030)
- [X] T006 [P] [US1] Criar `ai-core/packages/core/tests/observability/unit/test_observability_redaction.py` com a
  tabela de redação de [data-model.md](data-model.md): cada nome sensível (`authorization`, `api_key`, `apikey`,
  `token`, `access_token`, `refresh_token`, `secret`, `password`, `passwd`, `cookie`, `set-cookie`, `private_key`)
  tem o valor trocado por `«redigido»`, com comparação sem distinguir maiúsculas nem `-`/`_`; chave sensível aninhada
  em mapeamento dentro de lista dentro de mapeamento também é redigida; `Bearer sk-abc123` → `Bearer «redigido»`;
  `api_key=sk-1` e `Authorization: Bearer x` em texto livre; `https://user:s3nha@host/v1` →
  `https://user:«redigido»@host/v1`; texto de 2001 caracteres é truncado com `… [truncado: N caracteres]` e texto de
  2000 não; chave e valor não sensíveis passam intactos; a redação é idempotente
- [X] T007 [P] [US1] Criar `ai-core/packages/core/tests/observability/unit/test_observability_records.py` conforme
  [contracts/record-format.md](contracts/record-format.md): o registro sempre tem `at` (ISO 8601 com deslocamento),
  `type` em `snake_case` derivado do nome da classe (os cinco nomes) e `request_id`; campo `None` é **omitido**;
  `frozenset` vira lista ordenada; `tuple` vira lista; `datetime` vira ISO 8601; texto livre chega redigido; o
  resultado é serializável por `json.dumps` sem `default=`; `request_id` é o único campo de evento que sobe para o
  nível do registro, e nenhum evento tem campo chamado `at` ou `type` (proteção contra colisão)
- [X] T008 [P] [US1] Criar `ai-core/packages/core/tests/observability/contract/test_observability_ports.py`: a suíte
  de conformidade de `TraceExporter` × `TraceReader` da tabela de [contracts/ports.md](contracts/ports.md),
  parametrizada sobre `InMemoryTraceBackend` e `JsonlTraceBackend` (este em `tmp_path`) — ida e volta preservando
  ordem e tipos JSON, duas requisições intercaladas, requisição desconhecida devolvendo vazio, atributos aninhados,
  `at` com timezone, centenas de registros; e a suíte de `Clock` (timezone presente; `FixedClock` repete o instante;
  `SystemClock` não retrocede)
- [X] T009 [P] [US1] Criar `ai-core/packages/core/tests/observability/contract/test_observability_seams.py` (seams
  Trace Sink e Trace, [contracts/trace-api.md](contracts/trace-api.md)): `emit` não devolve nada e não levanta para
  nenhum dos cinco eventos; o instante vem do relógio injetado, não do sistema; ordem de emissão preservada na
  consulta; `trace()` de requisição sem eventos → `Trace` com `records` vazio; `trace()` com `reader=None` →
  `TraceQueryUnavailable` nomeando o backend configurado; `dropped_events()` começa em zero, sobe a cada falha do
  exporter e nunca desce; exporter que levanta `OSError` não propaga e a emissão seguinte continua funcionando
  (FR-011); credencial emitida em `ExecutionError.message` não aparece no registro lido (FR-002, US1 cenário 2)
- [X] T010 [P] [US1] Criar
  `ai-core/packages/core/tests/observability/integration/test_observability_jsonl.py`: com `JsonlTraceBackend` em
  `tmp_path` — o arquivo `trace-YYYY-MM-DD.jsonl` é criado pela data de `at` em UTC; cada linha é JSON válido;
  escrever duas vezes anexa em vez de sobrescrever; registros de dias diferentes vão para arquivos diferentes e a
  leitura encontra os dois (quickstart §5); linha corrompida no meio do arquivo é ignorada na leitura, com aviso em
  log, e os registros válidos voltam (US1 cenário 3: o trace de uma execução interrompida continua consultável)

### Implementation for User Story 1

- [X] T011 [P] [US1] Implementar `ai-core/packages/core/src/ai_core/observability/domain/redaction.py` (puro):
  `SENSITIVE_NAMES` (a lista do data-model), `REDACTED = "«redigido»"`, `MAX_TEXT = 2000`;
  `redact_value(value: JSONValue) -> JSONValue` (percorre mapeamentos e listas, troca valor de chave sensível,
  redige e trunca texto livre) e `redact_text(text: str) -> str` (padrões `Bearer`, `<nome>=<valor>`,
  `<nome>: <valor>`, credencial em URL, truncamento com marca). Sem I/O; idempotente (depende de T003)
- [X] T012 [US1] Implementar `ai-core/packages/core/src/ai_core/observability/domain/records.py` (puro):
  `record_type(event) -> str` (nome da classe em `snake_case`) e
  `to_record(event: TraceEvent, at: datetime) -> TraceRecord` — `dataclasses.asdict`, remoção de `None`, conversão de
  `frozenset` para lista ordenada, `tuple` para lista e `datetime` para ISO 8601, redação de todos os atributos, e
  `at`/`type`/`request_id` fora de `attributes` (depende de T002, T011)
- [X] T013 [P] [US1] Implementar `ai-core/packages/core/src/ai_core/observability/adapters/memory.py`:
  `InMemoryTraceBackend` (`export` acumula por `request_id` preservando ordem; `read` devolve tupla; atributos
  devolvidos sem cópia mutável) e `FixedClock(instant)` (depende de T002, T003)
- [X] T014 [P] [US1] Implementar `ai-core/packages/core/src/ai_core/observability/adapters/jsonl.py`:
  `JsonlTraceBackend(directory: Path)` — `export` escreve uma linha `json.dumps` (com `ensure_ascii=False`) no
  arquivo `trace-<data de at em UTC>.jsonl`, criando o diretório se preciso e dando `flush` por linha; `read` varre
  os arquivos do diretório, filtra pelo `request_id`, ignora linha ilegível com `logger.warning` e devolve na ordem
  de emissão; e `SystemClock` (`datetime.now(UTC)`) (depende de T002, T003)
- [X] T015 [US1] Implementar `ai-core/packages/core/src/ai_core/observability/service.py`:
  `TraceService(*, exporter: TraceExporter, reader: TraceReader | None, clock: Clock)` implementando `TraceSink` e
  `TraceQuery` — `emit` estampa `clock.now()`, converte com `to_record`, entrega ao exporter e, em qualquer exceção,
  registra `logger.warning` com o tipo do erro e incrementa o contador de descartes sem propagar (FR-011, R8);
  `trace(request_id)` levanta `TraceQueryUnavailable` quando não há reader e, quando há, devolve
  `Trace(request_id, records)`; `dropped_events()` devolve o contador; logger `ai_core.observability`
  (depende de T012, T013)

**Checkpoint**: US1 completa — `uv run pytest packages/core/tests/observability` verde e quickstart §2 a §5 conferem

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T016 Acrescentar a `ai-core/pyproject.toml` os contratos de import-linter de [research.md](research.md) R12 —
  `ai_core.observability.api` não importa `domain`/`ports`/`service`/`adapters`; `ai_core.observability.domain` não
  importa `ports`/`service`/`adapters`; `ai_core.observability.service` não importa `adapters`;
  `ai_core.observability.api`/`domain`/`ports`/`service` não importam `opentelemetry`, `logfire` nem `sentry_sdk`; e
  `ai_core.observability` não importa `ai_core.packs` — e rodar `uv run lint-imports` até todos aparecerem como
  `KEPT`
- [X] T017 Executar as seções 1–7 de [quickstart.md](quickstart.md) e corrigir divergências entre o resultado e o
  "Esperado"
- [X] T018 [P] Atualizar a seção "Código" de `CLAUDE.md` (o módulo `ai_core/observability/` existe, com Trace Sink,
  consulta por requisição e backends de memória e JSONL; `ai_core/eval/` continua para a Fase 6) e a linha da 009 em
  `specs/README.md` (status "Fase 1 implementada (US1: trace e Trace Sink)")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001, sem dependência
- **Foundational (Phase 2)**: T002 primeiro (tudo depende dos tipos), T003 em paralelo com ele e T004 depois dos dois
- **User Story 1 (Phase 3)**: depende de Setup + Foundational
- **Polish (Phase 4)**: T016 depende de T015; T017 depende de tudo; T018 pode ir em paralelo

### Within User Story 1

- Testes (T005–T010) antes da implementação e falhando
- T011 → T012 (a serialização usa a redação) → T015; T011 depende de T002; T013 e T014 em paralelo entre si; T015 depende de T012 e de um
  adapter para os testes de seam

### Parallel Opportunities

- T005, T006, T007, T008, T009 e T010 em paralelo (arquivos distintos)
- T011, T013 e T014 em paralelo
- T018 em paralelo com qualquer tarefa da Phase 3 concluída

---

## Parallel Example: User Story 1

```bash
# Testes da US1, juntos:
Task: "unit/test_observability_api.py (T005)"
Task: "unit/test_observability_redaction.py (T006)"
Task: "unit/test_observability_records.py (T007)"
Task: "contract/test_observability_ports.py (T008)"
Task: "contract/test_observability_seams.py (T009)"
Task: "integration/test_observability_jsonl.py (T010)"
```

---

## Implementation Strategy

### MVP (US1, o escopo desta fase)

1. Phase 1 e 2: esqueleto, `api.py` e portas
2. Phase 3: testes primeiro; depois redação, serialização, adapters e serviço
3. **PARE e VALIDE**: quickstart §2 a §5 — emissão, redação, falha de backend e arquivo com rotação
4. Phase 4: fronteiras, quickstart completo, documentação

### Depois desta fase

- 005 e 006 (mesma fase) passam a receber o `TraceSink` e emitir; a 011 monta `TraceService` por perfil e injeta o
  mesmo `Clock` em todos os módulos com porta de tempo
- Fase 2: a 008 US5 expõe a consulta na superfície privada; a saúde agregada (011 US5) lê `dropped_events()`
- Fase 3: a 004 acrescenta o evento de tool — tipo novo, sem mudar o seam
- Fase 6: `ai_core/eval/` com o harness (US2–US4)

---

## Notes

- O módulo não importa nenhum outro módulo do core: quem emite chama o seam (princípio II)
- Nenhuma leitura de relógio fora da porta `Clock` (ADR-013); nenhuma biblioteca de observabilidade no núcleo (R1,
  garantido por T016)
- Falha de trace nunca derruba execução: se um teste precisar de exceção propagada, o teste está errado (FR-011)
- Commit por tarefa ou grupo lógico
