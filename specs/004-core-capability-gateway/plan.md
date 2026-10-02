# Implementation Plan: Catálogo de capacidades e execução segura de tools

**Branch**: `004-core-capability-gateway` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/004-core-capability-gateway/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/004-core-capability-gateway/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-002, ADR-003, ADR-005, ADR-012, ADR-013, ADR-015; as cinco clarificações
de 2026-10-01; os seams ao redor — contrato 001, Pack Registry e Pack Hooks (002), `ExecutionGrant` (003), cliente MCP
restrito (007, implementado), Trace Sink (009) e o motor (005, consumidor). **Refinamentos do `design.md`, sem
divergência de decisão**: o gateway é uma **sessão por execução** que reúne catálogo e execução e carrega o contexto
que o handler nativo e o retriever exigem (R2); duas portas a mais — `PackToolSource`, a forma que a 004 exige da 002
até a passada dela, e `Clock` (ADR-013) —; e a consulta de auditoria (clarificação 5). **Nenhum ADR novo.**

## Summary

Entregar o elo 3 da cadeia de enforcement e o ponto único de execução de tools. Para cada execução, a sessão monta o
catálogo — tools de pack, retrievers cujas coleções estão todas no grant e tools de MCP descobertas pelo cliente
restrito, todas com namespace, filtradas pelo `allowed_tools` exato e pela política de escrita — e executa chamadas:
nome fora do catálogo é "tool inexistente"; argumentos validados contra o esquema; despacho por tipo sob prazo e limite
do gateway; resultado cortado com marca e cercado como dado não confiável; tool de escrita auditada **antes** de
executar; e um evento de trace por chamada. Escopo da Fase 3: **US1–US5**. O encaixe na 002, 003, 005 e 011 é das
passadas delas; o evento de trace na 009 é toque declarado (R1).

## Technical Context

**Language/Version**: Python 3.14 (módulo da distribuição `ai-core`, `requires-python = ">=3.14"`)

**Primary Dependencies**: contrato 001 (`ToolSpec`, `ToolResult`, `ToolInvocation`, `NamedRetriever`, `Chunk`,
`JSONValue`); `api.py` de 002 (`Composition`), 003 (`ExecutionGrant`, `Principal`), 007 (`McpClients`, `Discovery`,
`UnknownServer`) e 009 (`TraceSink`, `ToolCall`, `ExecutionError`); `jsonschema` e `psycopg`/`psycopg-pool` (já
presentes). Nenhuma dependência nova (R12)

**Storage**: Postgres no schema `capabilities` — auditoria de tools de escrita (ADR-015); memória no perfil de teste

**Testing**: pytest + pytest-asyncio + hypothesis; `unit/` (domínio puro), `contract/` (sessão, suítes adversarial e de
prompt injection, `AuditLog` contra memória e Postgres, comando `audit`), `integration/` (cliente MCP real da 007 contra
o servidor de demonstração dela; auditoria no Postgres) (R11)

**Target Platform**: processo do core na imagem Linux ARM64 (2 OCPU, 12 GB)

**Project Type**: módulo de biblioteca dentro do monolito modular (`ai_core/capabilities/`)

**Performance Goals**: montagem do catálogo sem I/O além da descoberta de MCP (servida do cache da 007 dentro do TTL);
execução sem I/O além do despacho e, em tool de escrita, dois acessos à auditoria

**Constraints**: 0 execuções fora do catálogo (SC-001); 100% das escritas auditadas, registro antes do despacho
(SC-002); 100% dos resultados acima do limite cortados com marca (SC-003); 0 ampliações por prompt injection
(SC-004); `api.py`/`domain/`/`ports.py`/`service.py` sem driver de banco

**Scale/Scope**: 1 módulo com 3 seams (sessão de tools, consulta de auditoria, fragmento de instrução), 3 portas
secundárias, 5 regras de domínio; dezenas de tools por execução

Nenhum `NEEDS CLARIFICATION`: as cinco perguntas abertas foram resolvidas em 2026-10-01, e os pontos de plano —
formato da cerca (R7), defaults de prazo e tamanho (R6), contexto da execução (R2), validação de esquema de terceiros
(R5) e ordem da auditoria (R8) — estão em [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Nomes de pack, tool, alias e coleção são dados |
| II. Seams | ✅ | Consome só `api.py` de 002, 003, 007 e 009 e o contrato 001; expõe três seams com suíte; a forma exigida da 002 está declarada como porta (`PackToolSource`), como a 003 fez com a 007 |
| III. O core orquestra | ✅ | É o princípio implementado: um ponto de execução despacha por tipo (ADR-005); o motor só abre a sessão e envia chamadas |
| IV. Assistant é a fronteira | ✅ | Catálogo = só o que o grant declara, filtro exato com namespace, escrita só por `write_tools`, retriever só com todas as coleções; fora do catálogo é ausência — "tool inexistente" uniforme |
| V. Determinismo | ✅ | Montagem, filtros, validação, cerca e corte são funções puras; nenhum LLM |
| VI. Conteúdo externo | ✅ | Todo resultado cercado e rotulado, conteúdo neutralizado, corte com marca; escrita sempre auditada, antes de executar; esquema de MCP sem regex de terceiro |
| VII. Falha fechada | ✅ | Auditoria indisponível impede a escrita; colisão de nomes falha a montagem; MCP fora do ar fica em `unavailable` e no trace, nunca silencioso |
| VIII. Modelos por papel | N/A | Não chama modelo |
| IX. Proveniência | ✅ | Recuperação devolve os chunks com documento, seção e página; o motor os leva adiante |
| X. Medir antes de calibrar | ✅ | Prazo e tamanho são controles de segurança e custo, configuráveis pelo operador; nenhum número de RAG (o `top_k` é o do retriever) |
| XI. API independente, streaming | ✅ | O módulo não conhece HTTP |
| XII. Simplicidade | ✅ | Sem cache próprio (o de MCP é da 007), sem fila, uma sessão por execução |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/capabilities/**` e
  `tests/capabilities/**`; fora dele, `ai-core/pyproject.toml` (import-linter, pytest), `specs/README.md` e o **toque
  declarado na 009**: `ToolCall` no `observability/api.py` (aditivo, previsto pelo próprio `api.py` — R1, R9), com um
  exemplo no `contracts/record-format.md` dela
- [x] Every consumed seam is listed with its owner spec — `ToolSpec`, `ToolResult`, `ToolInvocation`,
  `NamedRetriever`, `Chunk` (001); `Composition` (002); `ExecutionGrant`, `Principal` (003); `McpClients`,
  `Discovery`, `UnknownServer` (007); `TraceSink`, `ToolCall`, `ExecutionError` (009)
- [x] Every seam this module exposes has a conformance test planned — `test_session_catalog.py`,
  `test_session_execute.py`, `test_capabilities_adversarial.py`, `test_prompt_injection.py`, `test_audit_query.py`
- [x] No seam changes — os seams da 004 nascem agora; o da 009 ganha um tipo de evento, aditivo e previsto; a forma
  exigida da 002 é porta deste módulo até a passada da 002
- [x] Import boundaries (import-linter) cover the new code — contratos novos em "Fronteiras verificadas"

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` — completo
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — `psycopg` e `psycopg_pool`
  só em `adapters/`; `jsonschema` é biblioteca de validação pura, usada no `domain/` como na 002
- [x] Other modules are imported only through their `api.py` — contrato de import-linter
- [x] All I/O, time, randomness, secrets and trace go through a secondary port or seam — banco (`AuditLog`), tools de
  pack (`PackToolSource`), tempo (`Clock`), trace pelo seam da 009; nenhuma aleatoriedade (R7)
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — [contracts/ports.md](contracts/ports.md)
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter —
  `AuditLog` contra Postgres; `PackToolSource` contra o `PackRuntime` quando a 002 o expuser (até lá, o adapter em
  memória); `Clock` é o da 005
- [x] Services and adapters of other modules are instantiated only in the composition root — a sessão recebe o
  cliente MCP pelo seam `McpClients`, já montado

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/004-core-capability-gateway/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md          # R1–R12
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── capabilities-api.md   # os seams, a montagem e o despacho, e as suítes de conformidade
│   ├── fencing.md            # a cerca, a neutralização, o corte e o fragmento de instrução
│   ├── audit.md              # o registro, a ordem antes/depois, a consulta e o comando `ai-core audit`
│   └── ports.md              # portas secundárias, adapters e conformidade
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                         # import-linter (contratos novos), pytest pythonpath
└── packages/core/
    ├── src/ai_core/capabilities/
    │   ├── __init__.py
    │   ├── api.py                         # seams, ToolContext, ToolCall, FencedToolResult, AuditRecord, erros
    │   ├── domain/
    │   │   ├── __init__.py
    │   │   ├── catalog.py                 # montagem: união, namespace, coleções, allowed_tools, escrita, colisão
    │   │   ├── arguments.py               # validação de argumentos; validador sem regex para MCP
    │   │   ├── fencing.py                 # cerca, neutralização, corte com marca (FENCE_INSTRUCTION mora no api.py)
    │   │   ├── rendering.py               # retorno nativo e chunks em texto
    │   │   └── write_policy.py            # tools de escrita conforme write_tools
    │   ├── ports.py                       # AuditLog, PackToolSource, Clock
    │   ├── service.py                     # Capabilities (open) e ToolSession (catálogo + execute); AuditQuery
    │   └── adapters/
    │       ├── __init__.py
    │       ├── memory.py                  # AuditLog e PackToolSource em memória
    │       ├── audit_postgres.py          # AuditLog
    │       ├── postgres_schema.py         # migrate(pool) do schema capabilities (ADR-015)
    │       ├── sql/001_audit.sql
    │       └── cli.py                     # audit_command — registrado pela 011
    ├── src/ai_core/observability/api.py   # toque declarado: ToolCall (R9)
    └── tests/capabilities/
        ├── conftest.py
        ├── capabilities_testkit.py        # grants, packs com tools e retrievers falsos, cliente MCP programado,
        │                                  # relógio, trace que grava, fixture de Postgres
        ├── unit/
        ├── contract/
        └── integration/
```

**Structure Decision**: layout do `design.md`, com dois arquivos de domínio a mais — `arguments.py` e `rendering.py` —
para que validação e renderização fiquem testáveis sem a sessão. `audit_memory.py` do `design.md` vira parte de
`memory.py`, como nos módulos anteriores.

## Fronteiras verificadas (import-linter)

1. `api.py` da 004 não importa o resto do módulo;
2. `domain/` da 004 não importa portas, service nem adapters;
3. `service.py` da 004 não importa adapters;
4. o núcleo da 004 (`api`, `domain`, `ports`, `service`) não importa `psycopg`, `psycopg_pool`, `mcp`, `httpx2`;
5. a 004 só enxerga outros módulos pelo `api.py` (internals de `packs`, `assistants`, `mcp`, `observability`, `llm` e
   `graph` proibidos; `http` e `bootstrap` inteiros proibidos);
6. nenhum outro módulo importa internals da 004 — só a composition root.

E a 004 entra na origem de "nenhum módulo do core importa a API" e "nenhum módulo importa a composition root".

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 005 (US2, `agentic`) | Abre `Capabilities.open(grant, ToolContext(request_id, reference_time, retrieval_filters))` uma vez por execução; mostra ao controller `session.tools` e põe `FENCE_INSTRUCTION` no texto de sistema; envia `session.execute(ToolCall(name, arguments))` e põe `FencedToolResult.text` no contexto (e os `chunks`, se houver, no estado de recuperação); sinaliza `session.unavailable` nos metadados da resposta. Pedido fora do catálogo volta `status="unknown"` e conta como iteração (005 US2 cen. 4) |
| 002 (passada da Fase 3, US3 cen. 1) | Satisfaz `PackToolSource.toolset(composition)`: uma entrada por tool nativa e por retriever dos packs da composição, na ordem, com o nome `<pack>.<tool>`, o `ToolSpec` (o de recuperação via `retrieval_tool_spec`), o handler ou o retriever, e as coleções do retriever |
| 003 (passada da Fase 3) | Exemplo de `allowed_tools` com namespace no contrato do `assistants.yaml`; regra de validação: alias de MCP igual a nome de pack do mesmo Assistant o torna indisponível |
| 009 | Ganha o evento `ToolCall` (tipo `tool_call`), nesta passada |
| 011 (passada da Fase 3) | Constrói `Capabilities` com `PackToolSource` (o `PackRuntime`), `McpClients` (o `McpService` da 007), `AuditLog` (memória ou Postgres, `migrate` do schema `capabilities`), `TraceSink`, `Clock` e `GatewayLimits` (`AI_CORE_TOOL_TIMEOUT_MS`, `AI_CORE_TOOL_MAX_RESPONSE_BYTES`); registra `ai-core audit` |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- IV: [contracts/capabilities-api.md](contracts/capabilities-api.md) amarra cada regra da montagem a um teste, e a suíte
  adversarial cobre SC-001 com nomes arbitrários.
- VI: [contracts/fencing.md](contracts/fencing.md) fixa a cerca e a neutralização; [contracts/audit.md](contracts/audit.md)
  fixa a ordem antes/depois e a recusa quando a auditoria cai.
- XIII: três portas, cada uma com motivo e adapter em memória; a de auditoria com suíte contra Postgres.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Auditoria em dois passos, antes e depois (R8) | SC-002 é 100%: a escrita acontece num sistema externo, fora de qualquer transação nossa | registrar só depois deixa escrita sem registro quando o banco cai entre as duas coisas |
| Validador sem regex para esquemas de MCP (R5) | expressão regular de terceiro sobre texto do modelo é ReDoS, e nenhum prazo assíncrono interrompe CPU | validar com o esquema inteiro, ou não validar MCP, contraria a FR-006 ou abre o travamento |
| Porta `PackToolSource` antes da 002 expor o seam (R2) | o módulo precisa da forma para ser construído e testado agora | esperar a passada da 002 inverteria a ordem do roadmap ("junto da 004") |
| Toque declarado na 009 (R9) | FR-014 exige o trace por chamada, com tamanho e truncamento | `ExecutionError` para tudo perde os campos que a FR-014 pede |
