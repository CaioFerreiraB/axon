---

description: "Task list for 004 — Catálogo de capacidades e execução segura de tools, Fase 3"
---

# Tasks: Catálogo de capacidades e execução segura de tools

**Input**: Design documents from `/specs/004-core-capability-gateway/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos, antes do código (TDD). SC-001 e SC-004 são enunciados adversariais que só se demonstram por teste,
e a governança exige a suíte de cada seam exposto e de cada porta secundária (memória × adapter real). Cada teste leva a
marca da user story (`us1`…`us5`, já registradas no pytest).

**Organization**: **US1–US5** (Fase 3 do roadmap); US6 (catálogo mínimo em contexto) é P3 e fica fora. Fora desta
passada ([research.md](research.md) R1): tools de pack pela 002 (US3 cen. 1), exemplo e regra de colisão na 003, flow
`agentic` (005), montagem e `ai-core audit` na 011. **Dentro**, como toque declarado: o evento `ToolCall` na 009 (R9).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1–US5)

## Path Conventions

- Caminhos relativos a `ai-core/packages/core/`: código em `src/ai_core/capabilities/` (abreviado `capabilities/`),
  testes em `tests/capabilities/{unit,contract,integration}/` (abreviado `tests/capabilities/`)
- Comandos a partir de `ai-core/`, com `XDG_DATA_HOME=$HOME/.local/share`; Postgres por `AI_CORE_TEST_POSTGRES_DSN`

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Criar o esqueleto: `src/ai_core/capabilities/__init__.py` (docstring: spec 004 — o elo 3 da cadeia de
  enforcement e o ponto único de execução de tools, ADR-005; seams em `api.py`), `capabilities/domain/__init__.py`,
  `capabilities/adapters/__init__.py`, `capabilities/adapters/sql/` e `tests/capabilities/{unit,contract,integration}/`
- [X] T002 [P] Em `ai-core/pyproject.toml`, acrescentar `packages/core/tests/capabilities` a `[tool.pytest.ini_options]
  pythonpath`

---

## Phase 2: Foundational (Blocking Prerequisites)

**⚠️ CRITICAL**: nenhuma user story começa antes de T003–T008

- [X] T003 Implementar `capabilities/api.py` conforme [data-model.md](data-model.md) e
  [contracts/capabilities-api.md](contracts/capabilities-api.md), importando só a stdlib, o contrato 001 (`Chunk`,
  `JSONValue`, `ToolKind`) e `ai_core.assistants.api` (`ExecutionGrant`):
  - `ToolContext` (`request_id` não vazio; `reference_time` "com fuso"; `retrieval_filters: Mapping[str, Mapping[str,
    JSONValue]]` congelado), `ToolCall` (`name`, `arguments`), `CatalogTool` (`name`, `description`, `parameters`,
    `kind`, `mutates` — sem handler), `ToolStatus` = `ok` | `error` | `timeout` | `unknown` | `invalid_arguments`,
    `FencedToolResult` (`name`, `kind | None`, `status`, `text`, `truncated`, `error`, `chunks: tuple[Chunk, ...]`),
    `GatewayLimits` (`timeout_ms` "1 000–300 000", default 30 000; `max_response_bytes` "1 024–1 048 576", default
    16 384; fora da faixa → `ValueError` nomeando o campo);
  - auditoria: `AuditStatus` = `started` | `ok` | `error` | `timeout`, `AuditEntry` (`request_id`, `principal`,
    `assistant`, `tool`, `kind`, `arguments`, `started_at`), `AuditRecord` (os campos de data-model.md "AuditRecord"),
    `AuditFilter` (`principal`, `assistant`, `tool`, `since`, `until` opcionais; `limit` "1–1 000, default 100");
  - `UNKNOWN_TOOL = "tool inexistente"`, `FENCE_INSTRUCTION` (o texto exato de [contracts/fencing.md](contracts/fencing.md));
  - `Protocol`: `Capabilities`, `ToolSession`, `AuditQuery`; erro `CatalogConflict(ValueError)` com `name`
- [X] T004 Implementar `capabilities/ports.py` nas assinaturas de [contracts/ports.md](contracts/ports.md) e
  [contracts/audit.md](contracts/audit.md): `AuditLog` (`begin`, `finish`, `query`), `PackToolSource` (`toolset`),
  `Clock` (`now`, `monotonic`) e o registro `PackTool` (`name` com namespace, `pack`, `spec: ToolSpec`, `retriever:
  NamedRetriever | None`)
- [X] T005 [P] Toque declarado na 009 (R9): em `src/ai_core/observability/api.py`, o evento `ToolCall` (`request_id`,
  `tool`, `kind: str | None`, `status`, `duration_ms` ≥ 0, `size_bytes` ≥ 0, `truncated`) e sua entrada em
  `TraceEvent`; um teste em `tests/observability/unit/` que confere o registro `tool_call` sem campo de argumento nem
  conteúdo; e o exemplo `tool_call` em `specs/009-core-observability-evaluation/contracts/record-format.md`
- [X] T006 [P] Implementar `capabilities/adapters/memory.py`: `InMemoryAuditLog` (registros numa lista; `id`
  sequencial; `query` com os filtros, do mais recente para o mais antigo, `limit`) e `StaticPackTools` (`PackTool`
  dados, filtrados pelos packs da composição, na ordem dela)
- [X] T007 [P] Criar `tests/capabilities/capabilities_testkit.py`: construtores de `ExecutionGrant` (packs, MCPs,
  coleções, `allowed_tools`, `write_tools`, Assistant e Principal), packs falsos com tools nativas (handler que devolve,
  que demora, que levanta, que escreve) e retrievers (`NamedRetriever` com coleções e um retriever que grava os
  filtros recebidos), `FakeMcpClients` (cumpre `McpClients` da 007: `client_for` → cliente com `discover` por alias,
  falhas programadas e `execute` programado, guardando as chamadas), `RecordingTraceSink`, `FakeClock` (`now` e
  `monotonic` programáveis) e a montagem da sessão; e `tests/capabilities/conftest.py` com a fixture `pg_pool` (`DROP
  SCHEMA capabilities CASCADE` e `migrate` a cada teste; `pytest.skip` sem `AI_CORE_TEST_POSTGRES_DSN`) e a fixture
  parametrizada `audit_log` (memória × Postgres); e `tests/capabilities/contract/test_pack_tool_source.py`, a
  conformidade da porta `PackToolSource` contra `StaticPackTools` — só os packs da composição, na ordem dela, nome
  `<pack>.<tool>`, retriever com `kind="retrieval"` e as coleções — que a passada da 002 roda contra o `PackRuntime`
- [X] T008 Acrescentar a `ai-core/pyproject.toml` os contratos de import-linter de [plan.md](plan.md) ("Fronteiras
  verificadas") e `ai_core.capabilities` à origem de "nenhum módulo do core importa a API" e "nenhum módulo importa a
  composition root"; criar `capabilities/service.py` só com a docstring; rodar `uv run lint-imports` até tudo `KEPT`

**Checkpoint**: superfície pública, portas, adapters em memória e o evento de trace prontos

---

## Phase 3: User Story 1 - O catálogo é exatamente o que o Assistant permite (Priority: P1) 🎯 MVP

**Goal**: a sessão monta o catálogo da execução — packs, MCPs, namespace, `allowed_tools` exato, esquema conferido,
colisão recusada — e responde "tool inexistente" para qualquer nome fora dele.

**Independent Test**: `uv run pytest packages/core/tests/capabilities -k us1` — dois grants dos mesmos packs e MCPs têm
catálogos diferentes e exatos.

### Tests for User Story 1 ⚠️

- [X] T009 [P] [US1] `tests/capabilities/unit/test_catalog_assembly.py`: a montagem pura — tools de pack com `<pack>.<tool>`,
  MCP com `<alias>.<tool>` e `~alias.<tool>`; ordem (packs na ordem do grant, depois MCPs na ordem dos aliases);
  `allowed_tools` exato (`a.search` fica, `b.search` sai; `search` não casa nada — US1 cen. 4); `None` não filtra;
  colisão de nomes → `CatalogConflict` nomeando o nome; esquema inválido sai com o motivo
- [X] T010 [P] [US1] `tests/capabilities/contract/test_session_catalog.py` (parte `us1`): `Capabilities.open` com os
  adapters de teste — US1 cen. 1 (só o `alfa`, com prefixo); cen. 2 (o MCP com allowlist de 3 aparece com o namespace
  do alias); MCP que falha ou levanta `UnknownServer` → fora do catálogo, em `unavailable` com o motivo e
  `ExecutionError(stage="catalog", kind="mcp_unavailable")` no trace, e os outros atendem; `tools` traz `CatalogTool`
  sem handler; a descoberta é feita uma vez por alias
- [X] T011 [P] [US1] `tests/capabilities/unit/test_arguments.py` (parte de esquema): `check_schema` aceita os esquemas
  das tools de demonstração e o `RETRIEVAL_TOOL_PARAMETERS`; recusa esquema inválido (`{"type": 3}`) com o motivo

### Implementation for User Story 1

- [X] T012 [US1] Implementar `capabilities/domain/arguments.py`: `check_schema(schema)` (Draft 2020-12, sem `$ref`
  remoto) e o validador de argumentos (usado na US2), com a variante sem `pattern`/`patternProperties` para tools de
  MCP (R5)
- [X] T013 [US1] Implementar `capabilities/domain/catalog.py`: a montagem de [research.md](research.md) R3 sobre as
  entradas de pack (`PackTool`) e de MCP (alias, `Discovery`) — namespace, `allowed_tools` exato, esquema, colisão — e o
  registro interno de despacho (origem pack com handler/retriever, ou MCP com alias e nome local)
- [X] T014 [US1] Implementar em `capabilities/service.py`: `CapabilityService.open(grant, context)` (`PackToolSource`,
  descoberta por alias pelo `McpClients` da 007 com `UnknownServer` e falha em `unavailable`, trace dos indisponíveis,
  montagem do domínio) e `ToolSession` com `tools`, `unavailable` e um `execute` que, nesta história, só responde
  `unknown` fora do catálogo (US1 cen. 3) e emite `ToolCall` no trace

**Checkpoint**: o catálogo de cada execução é exatamente o declarado

---

## Phase 4: User Story 2 - Execução unificada e limitada de tools (Priority: P1)

**Goal**: o despacho por tipo, com validação de argumentos, prazo, corte com marca, cerca e trace.

**Independent Test**: `uv run pytest packages/core/tests/capabilities -k us2`.

### Tests for User Story 2 ⚠️

- [X] T015 [P] [US2] `tests/capabilities/unit/test_fencing.py` (parte `us2`): o formato de
  [contracts/fencing.md](contracts/fencing.md) (atributos, escape do nome), o corte em fronteira de caractere com a marca
  `[… resposta cortada: N de M bytes]` sem passar do limite, e o limite exato sem corte
- [X] T016 [P] [US2] `tests/capabilities/unit/test_rendering.py`: retorno nativo (texto como está; dicionário e lista
  em JSON com `ensure_ascii=False` e chaves ordenadas), chunks em blocos `[documento — seção, p. N]` + texto, "nenhum
  resultado" sem chunks
- [X] T017 [P] [US2] `tests/capabilities/unit/test_arguments.py` (parte `us2`): argumentos fora do esquema recusados
  nomeando o caminho; o validador de MCP ignora `pattern` e `patternProperties` (um `pattern` catastrófico com entrada
  maliciosa termina na hora) e aplica o resto
- [X] T018 [P] [US2] `tests/capabilities/contract/test_session_execute.py`: despacho nativo (o handler recebe
  `ToolInvocation` com os argumentos, o `request_id` e o `reference_time` do contexto), de recuperação (o retriever
  recebe a consulta, o `top_k` pedido e os filtros da fatia **do próprio pack**; `chunks` no resultado) e de MCP (o
  cliente recebe alias e nome local); argumentos inválidos → `invalid_arguments` sem despacho (US2 cen. 3); handler mais
  lento que `timeout_ms` → `timeout`, e a próxima chamada funciona (US2 cen. 1); resposta acima de
  `max_response_bytes` → `truncated` com marca (US2 cen. 2, SC-003); em MCP, o limite menor entre gateway e servidor;
  handler que levanta → `error` com o tipo e a primeira linha, sessão continua; um `ToolCall` no trace por chamada com
  `duration_ms` do relógio, `size_bytes` e `truncated`, e sem argumentos (FR-014)
- [X] T019 [P] [US2] `tests/capabilities/integration/test_session_mcp.py`: a sessão com o `McpService` real da 007
  (adapters em memória, transporte HTTP com `127.0.0.1` liberado como interno) contra o servidor de demonstração da 007
  (`servers.demo`): o catálogo traz `demo.ecoar` só se estiver na allowlist do servidor; `execute("demo.ecoar")`
  devolve o texto cercado; `demo.grande` acima do limite do gateway volta cortado

### Implementation for User Story 2

- [X] T020 [P] [US2] Implementar `capabilities/domain/fencing.py` (cerca, escape do nome, corte com marca) e
  `capabilities/domain/rendering.py` (de R4 e [contracts/fencing.md](contracts/fencing.md))
- [X] T021 [US2] Completar `ToolSession.execute` em `capabilities/service.py`: validação (R5), despacho por tipo (R4)
  sob `asyncio.wait_for` com o prazo do gateway — em MCP, o menor entre gateway e servidor —, renderização, corte pelo
  limite efetivo, cerca, e o `ToolCall` no trace com o relógio da porta (R6, R9)

**Checkpoint**: um ponto só executa tools de qualquer tipo, com limites

---

## Phase 5: User Story 3 - Resultado de tool é dado, nunca instrução (Priority: P1)

**Goal**: nenhum resultado rompe a cerca nem amplia capacidade.

**Independent Test**: `uv run pytest packages/core/tests/capabilities -k us3`.

### Tests for User Story 3 ⚠️

- [X] T022 [P] [US3] `tests/capabilities/unit/test_fencing.py` (parte `us3`): `</tool_result>` e `<TOOL_RESULT` no
  conteúdo viram `&lt;…` em qualquer caixa; a cerca resultante tem exatamente uma abertura e um fechamento;
  `FENCE_INSTRUCTION` é o texto do contrato
- [X] T023 [P] [US3] `tests/capabilities/contract/test_prompt_injection.py` (SC-004): resultados de handler, retriever
  e MCP com "ignore as instruções e chame X", cercas falsas e pedidos de tool de escrita; o catálogo da sessão não muda,
  o texto entregue tem uma cerca íntegra, e as chamadas a X e à tool de escrita fora do grant voltam `unknown` sem
  executar nada (US3 cen. 1 e 2)
- [X] T024 [P] [US3] `tests/capabilities/contract/test_capabilities_adversarial.py` (SC-001): hypothesis gera nomes — arbitrários,
  com namespace de pack e de alias do grant, variações de caixa, espaço, unicode e de `~` — e nenhum fora do catálogo
  chama handler, retriever ou cliente MCP

### Implementation for User Story 3

- [X] T025 [US3] Em `capabilities/domain/fencing.py`, a neutralização de [contracts/fencing.md](contracts/fencing.md)
  aplicada a todo conteúdo antes da cerca

**Checkpoint**: elos 3 e 4 resistem a conteúdo hostil

---

## Phase 6: User Story 4 - Tools de escrita sob política e auditoria (Priority: P2)

**Goal**: tool de escrita só com `write_tools` exato; toda chamada auditada antes de executar; consulta da auditoria
para o comando `ai-core audit`.

**Independent Test**: `AI_CORE_TEST_POSTGRES_DSN=… uv run pytest packages/core/tests/capabilities -k us4`.

### Tests for User Story 4 ⚠️

- [X] T026 [P] [US4] `tests/capabilities/unit/test_write_policy.py`: `mutates=True` fica só se o nome com namespace está
  em `write_tools` (exato); grant de Assistant público (`write_tools` vazio) não tem nenhuma (US4 cen. 1); tool que não
  muta não depende de `write_tools`
- [X] T027 [P] [US4] `tests/capabilities/contract/test_audit_log.py`, sobre a fixture `audit_log` (memória × Postgres):
  `begin` devolve um id e o registro fica `started` sem `result`; `finish` grava status, resultado e `finished_at`;
  filtros por Principal, Assistant, tool, `since` e `until`; ordem do mais recente para o mais antigo; `limit`; os
  argumentos voltam iguais (JSON)
- [X] T028 [P] [US4] `tests/capabilities/contract/test_audit_write.py` (SC-002): tool de escrita executada → um registro
  com Principal, Assistant, tool, argumentos inteiros, status e o resultado **como o modelo recebeu** (cercado e
  cortado) (US4 cen. 2); `begin` aberto **antes** do despacho (o handler vê o registro `started`); `begin` que falha →
  `error` "auditoria indisponível" e o handler **não** é chamado; `finish` que falha → registro `started` e o resultado
  volta normalmente; prazo vencido → registro `timeout`; duas chamadas iguais → dois registros; tool que não muta não
  gera registro
- [X] T029 [P] [US4] `tests/capabilities/contract/test_audit_query.py` (FR-015, US4 cen. 3): `audit_command` com
  filtros — uma linha por registro, do mais recente, com instante, status, Principal, Assistant, tool e argumentos em
  JSON; resultado só com `--results`; data fora do ISO 8601 ou `limit` fora de 1–1 000 → código 2

### Implementation for User Story 4

- [X] T030 [P] [US4] Implementar `capabilities/domain/write_policy.py` e aplicá-lo na montagem de `domain/catalog.py`
- [X] T031 [P] [US4] Implementar `capabilities/adapters/sql/001_audit.sql` (schema `capabilities`, tabela `audit` com
  `id bigserial`, `request_id`, `principal`, `assistant`, `tool`, `kind`, `arguments jsonb`, `status`, `result`,
  `started_at`, `finished_at`; índices por `started_at`, `principal`, `assistant`, `tool`),
  `capabilities/adapters/postgres_schema.py` (`migrate(pool, *, now)`, o desenho da 003, 007 e 008 — ADR-015) e
  `capabilities/adapters/audit_postgres.py` (`PostgresAuditLog`; datas como parâmetro, nunca `now()`)
- [X] T032 [US4] Em `capabilities/service.py`: a ordem de [contracts/audit.md](contracts/audit.md) no `execute` de tool
  de escrita (`begin` antes, recusa se falhar, `finish` depois, falha do `finish` só registrada em log) e
  `AuditQueryService.records(filter)` sobre o `AuditLog`
- [X] T033 [US4] Implementar `capabilities/adapters/cli.py`: `audit_command(query, *, filter_args, results, out, err)
  -> int` com o formato e os códigos de [contracts/audit.md](contracts/audit.md) — sem parser (o framework de linha de
  comando é da 011)

**Checkpoint**: nenhuma escrita sem registro, e o operador lê os registros

---

## Phase 7: User Story 5 - Recuperação restrita às coleções do Assistant (Priority: P2)

**Goal**: retriever só existe na execução se todas as coleções que declara estão no grant.

**Independent Test**: `uv run pytest packages/core/tests/capabilities -k us5`.

### Tests for User Story 5 ⚠️

- [X] T034 [P] [US5] `tests/capabilities/unit/test_catalog_assembly.py` (parte `us5`) e
  `tests/capabilities/contract/test_session_catalog.py` (parte `us5`): retriever com `docs_beta` e grant com
  `docs_alfa` → ausente (US5 cen. 1); retriever com `[docs_alfa, docs_beta]` e grant só com `docs_alfa` → ausente —
  parcial não basta (US5 cen. 2); com todas → presente com `kind="retrieval"` e o esquema `RETRIEVAL_TOOL_PARAMETERS`;
  chamada ao retriever ausente → `unknown` e `ToolCall` com `status="unknown"` no trace

### Implementation for User Story 5

- [X] T035 [US5] Em `capabilities/domain/catalog.py`, a regra de coleções de [research.md](research.md) R3 passo 2

**Checkpoint**: elo 5 fechado

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T036 Rodar o [quickstart.md](quickstart.md) e a verificação completa a partir de `ai-core/`: `uv run pytest` com e
  sem `AI_CORE_TEST_POSTGRES_DSN`, `uv run mypy`, `uv run ruff check packages`, `uv run lint-imports`; corrigir o que
  falhar
- [X] T037 [P] Atualizar `specs/README.md` (linha da 004: "Fase 3 implementada (US1–US5); encaixe pela 002, 003, 005 e
  011 nas passadas delas"; linha dos seams Capability Catalog + Tool Gateway e a consulta de auditoria) e `CLAUDE.md`
  ("Código": o módulo `ai_core/capabilities/`, a sessão por execução, a cerca, a auditoria antes da escrita, o evento
  `tool_call` da 009 e o que falta ligar)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: T001 → T002
- **Foundational**: T003 → T004; T005, T006 e T007 em paralelo depois de T004; T008 por último
- **US1**: depende do Foundational. T009–T011 em paralelo; T012 → T013 → T014
- **US2**: depende da US1 (a sessão). T015–T019 em paralelo; T020; T021 depois de T020
- **US3**: depende da US2 (a cerca). T022–T024 em paralelo; T025
- **US4**: depende da US2 (o `execute`). T026–T029 em paralelo; T030 e T031 em paralelo; T032 → T033
- **US5**: depende da US1 (a montagem). T034; T035
- **Polish**: depois de todas

### User Story Dependencies

```text
Foundational ─▶ US1 ─┬─▶ US2 ─┬─▶ US3
                     │        └─▶ US4
                     └─▶ US5
```

### Within Each User Story

- Testes primeiro, falhando; depois domínio, adapters e serviço
- `capabilities/service.py` é tocado por T014, T021, T032 — sequenciais; `domain/catalog.py` por T013, T030 e T035

### Parallel Opportunities

- Foundational: T005 ∥ T006 ∥ T007
- US1: T009–T011; US2: T015–T019; US3: T022–T024; US4: T026–T029 e T030 ∥ T031
- US3 ∥ US4 depois da US2; US5 a qualquer momento depois da US1

---

## Parallel Example: User Story 2

```bash
Task: "unit/test_fencing.py, parte us2 (T015)"
Task: "unit/test_rendering.py (T016)"
Task: "unit/test_arguments.py, parte us2 (T017)"
Task: "contract/test_session_execute.py (T018)"
Task: "integration/test_session_mcp.py (T019)"
```

---

## Implementation Strategy

### MVP (US1)

1. Phase 1 e 2: esqueleto, superfície, portas, adapters em memória, evento de trace e fronteiras
2. Phase 3: o catálogo da execução, com "tool inexistente" para o resto
3. **PARE e VALIDE**: `-k us1`

### Incremental

1. US2 + US3 (P1): despacho com limites e a cerca — com elas, a 005 pode começar o flow `agentic`
2. US4 (P2): escrita com auditoria antes de executar
3. US5 (P2): coleções
4. Polish

### Depois desta passada

- **002**: `PackToolSource.toolset(composition)` no `PackRuntime` (US3 cen. 1), com a conformidade desta spec
  (`contract/test_pack_tool_source.py`) rodando contra o real
- **003**: exemplo com namespace no contrato do `assistants.yaml`; regra de colisão alias × pack na validação
- **005**: o flow `agentic` sobre a sessão
- **011**: `Capabilities` nos perfis, `AuditLog` (memória ou Postgres, `migrate` do schema `capabilities`),
  `GatewayLimits` por `AI_CORE_TOOL_TIMEOUT_MS` e `AI_CORE_TOOL_MAX_RESPONSE_BYTES`, registro de `ai-core audit`


---

## Passada de 2026-10-22: imagens fora da cerca ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md); research R13)

**Goal**: o resultado de tool com imagem chega ao motor com os anexos fora da cerca e a marca dentro; auditoria e
trace sem bytes.

**Independent Test**: `tests/capabilities/` — sessão com MCP programado devolvendo PNG e tool nativa devolvendo
`ToolResult` com anexo.

- [X] T038 `FencedToolResult.attachments`, `_Outcome.attachments`; `ToolResult` de handler nativo; marcas depois do corte
  (`rendering.attachment_markers`) (R13)
- [X] T039 `AttachmentInfo` e `ToolCall.attachments` na 009; `AuditLog.finish(attachments=)`, `AuditRecord.attachments`,
  migração `002_audit_attachments.sql`, memória e Postgres; contagem no `axon audit`
- [X] T040 [P] Testes: marca com e sem `alt`, marca neutralizada e fora do corte, repetição, nativa com `ToolResult`,
  evento e auditoria (memória e Postgres) sem bytes

---

## Passada de 2026-10-28: gráficos fora da cerca ([ADR-052](../../docs/adr/ADR-052-graficos-na-conversa.md); research R15)

**Goal**: o resultado de tool com gráfico chega ao motor com o gráfico fora da cerca e a marca dentro; trace só com
o resumo.

**Independent Test**: `tests/capabilities/contract/test_session_charts.py` — tool nativa e MCP programado devolvendo
`ToolResult` com `charts`.

- [X] T041 `FencedToolResult.charts`, `_Outcome.charts`, `_from_result`; marcas depois do corte
  (`rendering.chart_markers`) (R15)
- [X] T042 `ChartInfo`, `chart_info` e `ToolCall.charts` na 009 (`observability/api.py`)
- [X] T043 [P] Testes: marca fora do corte e dentro da cerca, dados fora do texto, repetição, título hostil, resumo no
  evento e marca na auditoria; testes de nomes públicos e do registro `tool_call` da 009 atualizados


## Incremento ADR-055
- [X] D01 Testes de propagação e regressão estática.
- [X] D02 Canal confidencial de ToolContext a client_for.
- [X] D03 Types/lint e regressões.

Validação ADR-055: suítes MCP/gateway/motor/HTTP com Postgres temporário; testes novos de isolamento, API e canal confidencial; mypy, Ruff e 69 contratos import-linter aprovados. Testes de transporte e destinos estáticos preservados.
