---

description: "Task list for 009 — trace por requisição (Fase 1) e harness de avaliação (Fase 6)"
---

# Tasks: Trace por requisição (Trace Sink e consulta)

**Input**: Design documents from `/specs/009-core-observability-evaluation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A constituição exige suíte de conformidade para cada seam exposto e para cada porta secundária
(princípio XIII), e FR-002 (nenhuma credencial) e FR-011 (falha do backend não interrompe) só se demonstram por teste.

**Organization**: **User Story 1** (Fase 1 do roadmap, Phases 1–4, T001–T018); **US2–US4** (harness, regressão em CI,
benchmark) na seção "Fase 6" (Phases 5–11, T019–T046).

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

# Fase 6 (US2, US3, US4: harness de avaliação) — 2026-10-13

**Escopo**: o módulo `ai_core/eval/` e os toques declarados no [research.md](research.md) R13 — 001 (ADR-027,
contratos `0.1.2`), 002 (seam `PackEvalMetrics`), 009/observabilidade (evento `Retrieval`, ADR-017), 005 (emissão) e
011 (`ai-core eval run|compare`). Tipos na seção "Fase 6" do [data-model.md](data-model.md); contrato em
[contracts/eval-harness.md](contracts/eval-harness.md). Caminhos relativos a `ai-core/`, salvo indicação; testes novos
com `pytestmark = pytest.mark.us2`, `us3` ou `us4`. Testes primeiro em cada tarefa.

## Phase 5: Setup da Fase 6

- [X] T019 Esqueleto `packages/core/src/ai_core/eval/` (`__init__.py` com docstring: consumidores importam
  `ai_core.eval.api`; `domain/__init__.py`; `adapters/__init__.py`); em `pyproject.toml`, `packages/core/tests/eval` no
  `pythonpath` do pytest e as descrições das marcas `us2` ("009 US2 — harness"), `us3` ("009 US3 — regressão em CI") e
  `us4` ("009 US4 — benchmark de modelos")

---

## Phase 6: Fundação da Fase 6 (Blocking Prerequisites)

**⚠️ CRITICAL**: nenhuma tarefa de US2–US4 antes desta fase

- [X] T020 [P] Toque declarado no 001 (ADR-027). **Teste primeiro** em `packages/contracts/tests/test_eval_contracts.py`:
  `EvalEvidence(document, section=None, chunk_id=None)` recusa `document` vazio; `EvalItem` exige `id`, `question` não
  vazia e `reference_time` com fuso, congela as tuplas e o `extra`; `EvalChunk(chunk_id, score, document, version,
  status, section, page)` recusa `page < 1`; `EvalObservation` congela listas e `flags`; um objeto com `name`, `better ∈
  {"higher", "lower"}`, `deterministic` e `measure` satisfaz `EvalMetric` (runtime_checkable); `PackBase().eval_metrics(ctx)
  == ()`; `AgentPack` não muda (um pack sem o hook continua conforme); a conformidade (`check_pack`) confere o hook
  quando presente — devolve sequência de `EvalMetric`, nome não vazio e único, `better` válido, `measure` síncrono — e
  aponta cada violação; `__version__ == "0.1.2"`. Depois: `src/ai_core_contracts/eval.py`, o default em `pack.py`, as
  exportações em `__init__.py` (e o teste de nomes públicos), a checagem em `testing/conformance.py`, `_version.py` e
  o `pyproject.toml` dos contratos em `0.1.2`; a documentação em `specs/001-core-contracts/contracts/python-api.md` e
  `testing-kit.md` (citando o ADR-027); a suíte também no piso 3.12
- [X] T021 [P] Toque declarado na 002 (ADR-027; R13) (depende de T020). **Teste primeiro** em
  `packages/core/tests/packs/contract/test_packs_eval_metrics_seam.py`: pack com `eval_metrics` → `PackEvalMetric(pack,
  metric)` na ordem da composição e o hook chamado uma vez, na carga; pack sem o método (não herda de `PackBase`) → nenhum;
  hook que levanta ou devolve tipo errado → pack em erro com a mensagem; composição revalidada. Depois: `PackEvalMetric`
  e o `Protocol` `PackEvalMetrics` em `packs/api.py` (teste de nomes públicos), a coleta em `_collect_catalog` e o
  método em `PackRuntime`; `specs/002-core-pack-runtime/contracts/pack-runtime-api.md`
- [X] T022 [P] Toque na observabilidade (ADR-017; R15). **Teste primeiro** em
  `packages/core/tests/observability/unit/test_observability_retrieval.py`: `RetrievedChunk` recusa `chunk_id` e
  `document` vazios, `page < 1` e score NaN; `Retrieval(request_id, retrieved, reranked, delivered)` congela as listas;
  o registro tem `type == "retrieval"` e as listas como objetos JSON sem campos `None` e **sem texto** (nenhum campo
  `text`); os backends de memória e JSONL o guardam. Depois: as dataclasses e o membro em `TraceEvent` em
  `observability/api.py`, `EXPECTED_NAMES`, e `contracts/record-format.md` (um exemplo) e `data-model.md` da 009
- [X] T023 Toque na 005 (R15) (depende de T022). **Teste primeiro** em `packages/core/tests/graph/contract/test_retrieval_trace.py`:
  no `rag_first` coberto, um `Retrieval` com `retrieved` = candidatos, `reranked` = junção e `delivered` = os entregues,
  na ordem, com a proveniência de cada `Chunk`; no `chat`, nenhum; no `agentic` com uma tool de recuperação, `retrieved`
  e `delivered` = os chunks do passo; o evento sai depois da geração e antes dos `ValidationRun`. Depois: a emissão em
  `validate_answer` (`graph/adapters/langgraph/nodes/common.py`), a partir da Turn View que o passo já monta, só quando
  alguma lista tem trecho
- [X] T024 [P] `packages/core/src/ai_core/eval/api.py` (R26; data-model "Harness"). **Teste primeiro** em
  `packages/core/tests/eval/unit/test_eval_api.py`: `Evidence` recusa `document` vazio; `GoldenItem` exige id
  `^[a-z0-9][a-z0-9._-]*$`, pergunta não vazia e `reference_time` com fuso; `GoldenSet` recusa ids repetidos, `k` vazio
  ou < 1 e tolerância negativa; `MetricValue`, `ItemResult`, `EvalReport`, `MetricDelta` e `Comparison` (`regressed` =
  alguma delta regrediu) congelados; o `Protocol` `EvalHarness`; `GoldenSetError`; nomes públicos exatos. Depois: o
  módulo (só stdlib, contratos e `api.py`s)
- [X] T025 [P] `eval/domain/golden.py` (R16) (depende de T024). **Teste primeiro** em
  `packages/core/tests/eval/unit/test_eval_golden.py`, por tabela, a partir do mapeamento lido do YAML: válido →
  `GoldenSet` com defaults (`k = (5, 20)`, tolerância 0,02 para as determinísticas); item sem pergunta, com
  `reference_time` sem fuso, com id inválido ou repetido, evidência sem `document`, `extra` que não é mapeamento →
  `InvalidItem` nomeando o campo, e o resto segue; arquivo sem `items` ou `version` diferente de 1 → `GoldenSetError`.
  Depois: a conversão pura
- [X] T026 [P] `eval/domain/matching.py` (R16). **Teste primeiro** em `packages/core/tests/eval/unit/test_eval_matching.py`:
  normalização (casefold, espaços em sequência, acentos removidos por NFKD); evidência com `chunk_id` casa só pelo id;
  sem id, casa por `document` e, se dada, `section`; `first_match(evidences, chunks)` devolve a posição 1-based; evidência
  sem casamento conta como não recuperada
- [X] T027 [P] `eval/domain/metrics.py` (R17) (depende de T026). **Teste primeiro** em
  `packages/core/tests/eval/unit/test_eval_metrics.py`, por tabela: `recall@k` para cada k, `mrr`, `delivered_recall`,
  `rerank_gain` (n = tamanho de `reranked`), as três de citação (contra `delivered` e contra as esperadas), as de
  operação (p50/p95 por posição mais próxima, médias), `controller_invalid_rate`, `error_rate` (algum registro `error`),
  `gate_routes` e `flag_rate:<flag>`; item sem evidência esperada fica fora das de recuperação; agregação pela média dos
  itens em que se aplicam, com `n`; a marca `deterministic` e `better` de cada métrica; os avisos de "evidência não
  vista" (evidência esperada que não casa com nenhum candidato de nenhum item da rodada, R16). Depois: as funções puras
- [X] T028 [P] `eval/domain/judging.py` (R19). **Teste primeiro** em `packages/core/tests/eval/unit/test_eval_judging.py`:
  três julgamentos → média e variância; julgamento ausente fica fora; os três ausentes → métrica ausente no item;
  valores fora de `[0, 1]` recortados; a mensagem do juiz montada só com pergunta, resposta, trechos e referência, com a
  instrução neutra. Depois: o módulo
- [X] T029 [P] `eval/domain/compare.py` (R20). **Teste primeiro** em `packages/core/tests/eval/unit/test_eval_compare.py`:
  `delta = atual − base`; regressão só quando piora além da tolerância no sentido de `better` e só nas determinísticas;
  tolerância do conjunto ou default; métrica nova não regride; métrica que sumiu vai em `missing`; métrica ausente (None)
  num dos lados não regride. Depois: a função pura
- [X] T030 `eval/ports.py` e `eval/adapters/memory.py` (R26) (depende de T024): `GoldenSetSource`, `BaselineStore`,
  `Judge` (`Judgement(faithfulness, coverage)`), `Clock`; em memória: `InMemoryGoldenSetSource` (conjuntos por caminho),
  `InMemoryBaselineStore`, `ScriptedJudge` (roteiro de julgamentos, inclusive falha), `FixedEvalClock` (`now` fixo e
  `monotonic` por roteiro)
- [X] T031 [P] `eval/adapters/golden_yaml.py` e `eval/adapters/report_json.py` (R16, R20, R23) (depende de T025, T030).
  **Teste primeiro** em `packages/core/tests/eval/contract/test_eval_ports.py`, contra memória e arquivo (`tmp_path`):
  YAML lido vira o `GoldenSet` da T025, arquivo ilegível → `GoldenSetError`; relatório gravado e lido de volta é igual
  (ida e volta), base inexistente → `None`, `version` desconhecida → erro claro

**Checkpoint**: contratos `0.1.2`, seam da 002, evento `Retrieval` emitido, domínio do harness e portas prontos

---

## Phase 7: User Story 2 — Medir a qualidade com um conjunto dourado (Priority: P1) 🎯 MVP da Fase 6

**Goal**: o harness roda um conjunto dourado contra um Assistant e produz o relatório com as métricas de recuperação,
rerank, geração, citação e operação, mais as de domínio do pack.

**Independent Test**: `uv run pytest packages/core/tests/eval -m us2` — conjunto mínimo contra um pack de teste com
retriever no perfil `test`: todas as métricas do R17 e a de domínio no relatório.

- [X] T032 [P] [US2] `packages/core/tests/eval/integration/test_eval_run.py` (contracts/eval-harness.md, verificações 1, 2,
  6 e 7; Edge Case "documento fora do corpus"): plataforma no perfil `test` com `overrides` (`pack_source` com um pack de teste — retriever da coleção `docs`,
  reranker, uma métrica de domínio `deterministic` e o registro do `reference_time` que a preparação viu — e `providers`
  com um gerador que cita o primeiro `id:` do contexto); conjunto com 3 itens válidos e 1 inválido; espera-se: o
  inválido nomeado no relatório e não executado; para os válidos, `recall@5`, `recall@20`, `mrr`, `delivered_recall`,
  `rerank_gain`, as de citação, as de operação e `docs:<métrica>` com valores; o `reference_time` de cada item visto
  pela preparação; sem juiz, `faithfulness` e `coverage` ausentes; com o `ScriptedJudge`, média e variância; um item
  cuja evidência nomeia um documento que o pack não tem sai com o aviso "evidência não vista", sem invalidar o item
- [X] T033 [P] [US2] `packages/core/tests/eval/contract/test_eval_judge.py` (R19): o juiz pelo Model Router com um
  provider simulado — `response_format` com esquema enviado, `request_id` próprio por julgamento, política só com o
  modelo juiz (modelo fora dela → erro claro antes da chamada), resposta malformada → julgamento ausente, nunca exceção
- [X] T034 [US2] `eval/service.py` (R14, R17, R18, R21, R22) (depende de T021, T023, T027–T031): `EvalService(engine,
  trace, grants, pack_metrics, clock, judge=None)` com `run(golden, *, assistant, principal) -> EvalReport` — resolve o
  grant pela 003 (`AssistantNotFound`/`AssistantUnavailable` → entrada inválida), pede as métricas de domínio da
  composição, executa cada item em sequência (`request_id` `eval-<rodada>-<item>`, `stream=True`, `reference_time` do
  item), mede latência e tempo até o primeiro token pelo `Clock`, lê o trace (`Retrieval`, `ModelCall`,
  `ControllerDecision`, `CoverageGate`; sem `Retrieval`, as três listas vazias), monta `EvalObservation`, calcula as métricas do core e as de domínio (exceção →
  ausente no item e registro no relatório), julga 3 vezes quando há juiz e agrega; trace sem leitura → erro explícito
- [X] T035 [US2] `eval/adapters/judge.py` (R19) (depende de T028, T030): `RoutedJudge(routing, judge_ref)` sobre o
  `ModelRouting` da 006 — política da rodada com `generation` = o juiz e allowlist só dele; faz T033 passar
- [X] T036 [US2] `eval/adapters/cli.py` (R23, R25): `run_command(service, source, store, *, golden, assistant, principal,
  report, annotate, out, err)` — imprime a tabela das métricas (nome, valor, variância, n, determinística), grava o
  relatório com `--report` e as anotações; saída 0, ou 2 para entrada inválida (arquivo, Assistant)

**Checkpoint**: a US2 completa e testável sozinha

---

## Phase 8: User Story 3 — Barrar regressões no CI (Priority: P2)

**Goal**: com uma linha de base, o harness compara e sai com 1 quando uma métrica determinística regride além da
tolerância; as julgadas por modelo são reportadas com variância e não barram.

**Independent Test**: `uv run pytest packages/core/tests/eval -m us3` — regressão proposital no retriever de teste:
saída 1 nomeando `recall@k` e o delta.

- [X] T037 [P] [US3] `packages/core/tests/eval/integration/test_eval_regression.py` (verificações 3 e 4): rodada base
  gravada; o mesmo conjunto com o retriever de teste degradado (configuração do pack que inverte a ordem e corta
  candidatos) → `Comparison.regressed`, a saída da CLI 1 e o delta de `recall@k` e `mrr` impressos; juiz com variância
  alta não barra; `--update-baseline` só grava sem regressão (ou com `--force`); métrica sumida listada
- [X] T038 [US3] `eval/adapters/cli.py` (R20) (depende de T029, T036): `--baseline` (carrega, compara, imprime delta,
  tolerância e regressão), `--update-baseline`, `--force` e a saída 1; faz T037 passar

**Checkpoint**: a US3 completa

---

## Phase 9: User Story 4 — Comparar modelos (Priority: P3)

**Goal**: o mesmo harness compara Assistants que diferem no modelo, lado a lado, com as anotações de recursos do
operador.

**Independent Test**: `uv run pytest packages/core/tests/eval -m us4` — dois relatórios, `eval compare`, métricas e
anotações lado a lado.

- [X] T039 [P] [US4] `packages/core/tests/eval/integration/test_eval_benchmark.py` (verificação 5): dois Assistants
  (`agentic` com controller programado, um com ação inválida) rodam o mesmo conjunto; `compare` mostra cada métrica nas
  duas colunas, inclusive `controller_invalid_rate`, `ttft_ms` e `generation_tokens_per_s`, e as anotações
  (`--annotate "RAM 6 GB"`) de cada relatório
- [X] T040 [US4] `eval/adapters/cli.py` (R24) (depende de T036): `compare_command(store, paths, out, err)` — tabela lado a
  lado (métricas na linha, relatórios na coluna, com o Assistant e o juiz no cabeçalho) e as anotações; 2 para relatório
  ilegível; faz T039 passar

---

## Phase 10: Encaixe na 011 (`ai-core eval run|compare`)

- [X] T041 `packages/core/src/ai_core/bootstrap/cli.py` (R25) (depende de T034–T040): grupo `eval` com `run` e `compare`;
  `run` sobe a plataforma até a etapa `assistants` (sem a API), abre a sessão de armazenamento como o `audit`
  (`wiring.storage`) para a 003, e compõe o `EvalService` com o motor, a consulta de trace (`Platform.trace`), o
  `GrantResolver`, o `PackEvalMetrics` (o Pack Runtime), o `RoutedJudge` (com `--judge`) e o relógio do perfil; backend
  de trace sem leitura → 2 com a explicação. **Teste** em `packages/core/tests/bootstrap/contract/test_cli_eval.py`:
  `ai-core eval run` no perfil `test` com um conjunto do Assistant genérico (sem recuperação: as métricas de recuperação
  ausentes), relatório gravado, saída 0; conjunto ilegível → 2; `eval compare` de dois relatórios → 0. Documentar em
  `specs/011-core-bootstrap/contracts/cli.md`

---

## Phase 11: Polish da Fase 6

- [X] T042 Contratos de import-linter do `eval` em `pyproject.toml` (R26): camadas `api`/`domain`/`ports`/`service`/
  `adapters`; `ai_core.eval` só importa os `api.py` de `packs`, `assistants`, `graph`, `llm` e `observability`;
  `domain` sem `yaml`/`json`/I/O; `uv run lint-imports` com todos `KEPT`
- [X] T043 Executar a seção "Fase 6" de [quickstart.md](quickstart.md); com o mantenedor, uma rodada real curta na
  instalação (`agentic-deploy`) contra o Assistant `scouting` com 3 perguntas e o juiz do OpenRouter, para ver o
  relatório e o tempo, projetando o de 50 perguntas pela latência média (SC-002) e registrando no quickstart — e
  corrigir divergências
- [X] T044 [P] Documentação: linha da 009 em `specs/README.md` ("Fase 6 implementada (US2–US4): harness"), os seams
  **Eval Harness**, **formato de conjunto dourado** e **formato de relatório**, a linha do 001 (contratos `0.1.2`,
  ADR-027) e a da 002 (`PackEvalMetrics`); a 105 apontada para eles; seção "Código" de `CLAUDE.md`
- [X] T045 Verificação completa a partir de `ai-core/`: `uv run pytest` (com o Postgres de teste), `uv run mypy`, `uv run
  ruff check packages`, `uv run lint-imports`, os contratos no piso 3.12 e `packages/contracts/tools/check_clean_env.py`
- [X] T046 Release (R27; ADR-021), **só com aprovação do mantenedor**: contratos `0.1.2` → tag `contracts-v0.1.2`; core
  `0.3.0` (`packages/core/pyproject.toml`) → tag `v0.3.0`; `uv lock`, commits, tags anotadas e push

---

## Fase 6 — Dependencies & Execution Order

- **Setup (Phase 5)**: T019 primeiro
- **Fundação (Phase 6)**: T020, T022, T024, T026, T028 e T029 em paralelo; T021 depois de T020; T023 depois de T022;
  T025 depois de T024; T027 depois de T026; T030 depois de T024; T031 depois de T025 e T030
- **US2 (Phase 7)**: depende da Phase 6; T032 e T033 em paralelo (testes primeiro); T034 → T035 → T036
- **US3 (Phase 8)**: depende da US2 (usa o serviço e a CLI); T037 → T038
- **US4 (Phase 9)**: depende da US2; T039 → T040; pode correr junto com a US3
- **Encaixe (Phase 10)**: T041 depois das três histórias
- **Polish (Phase 11)**: T042 e T044 depois de T041; T043 e T045 depois de T042; T046 por último, com aprovação

## Parallel Example: Fase 6

```bash
# Fundação, juntos:
Task: "001 — ai_core_contracts.eval (T020)"
Task: "observabilidade — Retrieval (T022)"
Task: "eval/api.py (T024)"
Task: "domain/matching.py (T026)"
Task: "domain/judging.py (T028)"
Task: "domain/compare.py (T029)"
```

## Fase 6 — Implementation Strategy

1. Fundação: os toques fora da 009 (001, 002, observabilidade, 005), cada um com o próprio teste; o domínio do harness
   por tabela
2. US2 (MVP): o serviço, o juiz e a CLI — **PARE e VALIDE**: relatório completo no perfil `test`
3. US3 e US4: linha de base e comparação
4. Encaixe na 011, fronteiras, rodada real curta, documentação e a release (`contracts-v0.1.2`, `v0.3.0`) que destrava
   a 105

---

## Fase 9 (2026-10-14): destinos, uso e custo, Langfuse e conteúdo

**Escopo**: US5–US7 e o toque declarado na 006 ([research.md](research.md) R28–R37). Nada em `ai_core/http/` nem
`ai_core/bootstrap/` (passadas da 008 e da 011).

## Phase 12: Fundação da Fase 9 (Blocking Prerequisites)

- [ ] T047 Dependências `opentelemetry-sdk>=1.30,<2` e `opentelemetry-exporter-otlp-proto-http>=1.30,<2` em
  `packages/core/pyproject.toml` (comentário: spec 009 R32, confinadas a `observability/adapters/`); `uv sync`;
  conferir wheels aarch64 do `protobuf` no `uv.lock`
- [ ] T048 `observability/api.py`: `ModelExchange`, `ExchangeMessage` no `TraceEvent`; value objects e erros da Fase 9
  ([data-model.md](data-model.md)); os `Protocol` `UsageReportSeam`, `PriceBook`, `TraceDestinations`
  ([contracts/usage-api.md](contracts/usage-api.md)); `domain/records.py` reconhece `model_exchange`
- [ ] T049 `observability/ports.py`: as seis portas da Fase 9 ([contracts/ports.md](contracts/ports.md)); adapters em
  memória em `observability/adapters/memory.py` (destino gravador, destino que falha e que trava, stores, coletor OTLP
  falso no kit de teste)
- [ ] T050 [P] Testes e implementação de `observability/domain/content.py`: redação de credenciais e corte de 16 KiB
  por mensagem com marca
- [ ] T051 [P] `tests/observability/contract/test_cipher.py` e `observability/adapters/cipher.py` (HKDF
  `ai-core/observability/v1`)
- [ ] T052 `observability/adapters/postgres_schema.py` e `observability/adapters/sql/001_usage.sql`, `002_prices.sql`,
  `003_destination_settings.sql` ([data-model.md](data-model.md), Fase 9)
- [ ] T053 `tests/observability/contract/test_trace_destinations_fanout.py` e o `TraceService` com `primary` +
  `destinations` + `ContentPolicy` (R28–R29): falha e trava isoladas e contadas; `ModelExchange` descartado com a
  captura desligada; com ela ligada, só destinos com `accepts_content`; **nunca** no primário (SC-007); `emit` nunca
  levanta
- [ ] T054 Import-linter em `ai-core/pyproject.toml`: `opentelemetry` e `psycopg` só em `observability.adapters`;
  marcas `us5`, `us6`, `us7`

## Phase 13: User Story 5 — Ver uso e custo por modelo e por dia (Priority: P2)

- [ ] T055 [P] [US5] `tests/observability/unit/test_usage_projection.py` e `tests/observability/unit/test_prices.py`:
  projeção (`execution_started` → Assistant da chamada; sem execução → "fora de Assistant"); dia local com fuso
  (23h30 em `America/Sao_Paulo` conta no dia local); preço vigente pelo maior `effective_from` ≤ dia; custo em
  `Decimal`; sem preço → ausente e total incompleto
- [ ] T056 [P] [US5] `tests/observability/contract/test_usage_store.py` e `test_price_store.py` (memória × Postgres)
- [ ] T057 [US5] `observability/domain/usage.py` e `observability/domain/prices.py` para T055
- [ ] T058 [US5] `observability/adapters/postgres.py` (`UsageStore`, `PriceStore`) e o agregado em memória para T056
- [ ] T059 [US5] `observability/adapters/usage.py` (`UsageDestination`: buffer `maxlen=10_000`, `flush` em lote,
  descartes contados, origem por parâmetro) e, no serviço, `UsageReportSeam.report` e `PriceBook`
- [ ] T060 [P] [US5] `tests/observability/contract/test_usage_report.py` e `test_price_book.py` (cenários 1–6 da US5;
  SC-005); `tests/observability/integration/test_usage_volume.py` com 100 mil chamadas em 90 dias no Postgres de teste
  (SC-008: < 1 s)

## Phase 14: User Story 6 — Enviar traces ao Langfuse (Priority: P2)

- [ ] T061 [P] [US6] `tests/observability/unit/test_destination_settings.py`: precedência; grupo das variáveis do
  Langfuse tudo ou nada; origem por campo
- [ ] T062 [P] [US6] `tests/observability/contract/test_langfuse_transport.py` contra o coletor OTLP falso: mapeamento
  de R32 (raiz por requisição, geração com início = `at − duration_ms`, uso de tokens, tool, eventos, erro); lote; fila
  cheia descarta sem bloquear; Basic auth; `check` com 200 e 401
- [ ] T063 [P] [US6] `tests/observability/contract/test_trace_destinations.py`: segredo só de escrita;
  `InstallationDefined`; `MasterKeyMissing`; `Conflict`; `reload` troca o exportador sem perder o que estava na fila
- [ ] T064 [US6] `observability/domain/settings.py`, `observability/adapters/langfuse.py` (`LangfuseDestination`,
  `LangfuseTransport`), o `DestinationSettingsStore` no `adapters/postgres.py` e o seam `TraceDestinations` no serviço
- [ ] T065 [US6] `tests/observability/integration/test_destination_latency.py` (SC-006): com o transporte travado e o
  banco de uso lento, `emit` de 1 000 eventos não demora mais que o primário sozinho + 10%

## Phase 15: User Story 7 — Captura opcional de prompt e resposta (Priority: P3)

- [ ] T066 [P] [US7] `tests/llm/contract/test_model_exchange.py` (toque na 006): `TracedModel` emite `ModelExchange`
  depois do `ModelCall`, em `complete` e em `stream` (saída acumulada), sem credencial nem cabeçalho
- [ ] T067 [US7] `llm/service.py` (`TracedModel._emit`): monta e emite o `ModelExchange` (R35)
- [ ] T068 [US7] `tests/observability/integration/test_content_capture.py`: desligada → nenhum destino recebe texto;
  ligada → o Langfuse falso recebe entrada e saída na geração, redigidas e cortadas; o JSONL não recebe nada (SC-007)

## Phase 16: Polish da Fase 9

- [ ] T069 [P] `specs/README.md` (status da 009 e da 006 na Fase 9) e `contracts/eval-harness.md` (o harness ignora
  `model_exchange`)
- [ ] T070 Verificação manual com um Langfuse real (Cloud ou `docker compose` do Langfuse), com o mantenedor: conferir o
  trace, as gerações, os tokens e, com a captura ligada, entrada e saída — e corrigir os nomes de atributo do R32 se o
  Langfuse os mapear diferente
- [ ] T071 Rodar `uv run pytest`, `mypy`, `ruff check packages`, `lint-imports` e as portas contra o Postgres

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
- Fase 6 (Phases 5–11 acima): `ai_core/eval/` com o harness (US2–US4)

---

## Notes

- O módulo não importa nenhum outro módulo do core: quem emite chama o seam (princípio II)
- Nenhuma leitura de relógio fora da porta `Clock` (ADR-013); nenhuma biblioteca de observabilidade no núcleo (R1,
  garantido por T016)
- Falha de trace nunca derruba execução: se um teste precisar de exceção propagada, o teste está errado (FR-011)
- Commit por tarefa ou grupo lógico
