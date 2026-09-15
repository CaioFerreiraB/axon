# Implementation Plan: Contratos públicos do núcleo (`ai-core-contracts`)

**Branch**: `001-core-contracts` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-core-contracts/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/001-core-contracts/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-004, ADR-005, ADR-011, ADR-012, ADR-013 e ADR-014 (criado nesta sessão);
consumidores conferidos: 002, 004, 005, 006, 007, 010, 101, 103, 104. A única divergência do design.md — a política de
versões — está coberta pelo ADR-014; os refinamentos de tipo estão marcados em [research.md](research.md) (R10, R12,
R21).

## Summary

Entregar `ai-core-contracts` **0.1.0** — a única superfície que um pack enxerga — como distribuição do uv workspace
`ai-core/` (subpasta deste repositório até a separação, antes da Fase 4). Conteúdo: o contrato de pack (`AgentPack` +
`PackBase` com hooks opcionais, manifest, contextos de carga, tools nativas com `ToolInvocation`, retrievers nomeados com
coleções e tool de recuperação derivada, reranker, validators), a Turn View imutável com `reference_time`, os contratos de
serviço (`LLMProvider`, `MCPClient`, provisórios até a tag), a regra de versões e compatibilidade (subconjunto PEP 440
próprio, convenção 0.x deslocada), depreciação, regras de declaração reutilizáveis e o kit de testes público
`ai_core_contracts.testing` (fixtures e suíte de conformidade). O CI verifica fronteiras (allowlist stdlib +
import-linter), ambiente limpo (SC-001) e, a partir da tag, a superfície pública e o pack congelado (FR-020).

Escopo da Fase 0 (roadmap): **US1–US4**. A US5 (rotina isolada) fica fora da 0.1 e entra como patch aditivo (R23).

## Technical Context

**Language/Version**: Python — workspace e imagem em **3.14** (`ai-core/.python-version`); `ai-core-contracts` com
`requires-python = ">=3.12"`; CI dos contratos em 3.12, 3.13 e 3.14 (R2)

**Primary Dependencies**: runtime: só `typing_extensions>=4.12` (FR-001). Build: `uv_build`. Dev (grupo do workspace):
`pytest`, `pytest-asyncio`, `hypothesis`, `packaging` (oráculo de teste), `import-linter`, `ruff` e `mypy` (R24)

**Storage**: N/A — contratos não fazem I/O

**Testing**: `pytest` + `hypothesis` (testes diferenciais da regra de versões contra `packaging`); kit público
`ai_core_contracts.testing`, só stdlib e sem runner; testes de fronteira por AST; ferramenta de superfície pública
(`tools/api_surface.py`) com testes por categoria do SC-004

**Target Platform**: biblioteca Python pura, independente de SO; roda dentro da imagem do core (Linux ARM64) e no CI de
cada pack

**Project Type**: library (distribuição de contratos) num uv workspace

**Performance Goals**: sem metas de throughput. Import sem efeitos colaterais; construção de value objects linear no
tamanho dos dados (deep-freeze), sem I/O

**Constraints**: só stdlib + `typing_extensions`; nenhum import do projeto; nenhum tipo de motor, grafo, HTTP ou
armazenamento (FR-015); value objects imutáveis em profundidade; superfície pública = `__all__` de `ai_core_contracts` e
`ai_core_contracts.testing`; nada de domínio (princípio I)

**Scale/Scope**: 12 módulos de runtime + kit de testes (6 módulos); ~50 símbolos públicos no runtime e ~17 no kit;
consumidores: 002, 004, 005, 006, 007, 010 e specs `1xx`

Nenhum `NEEDS CLARIFICATION`: repositório e Python decididos pelo mantenedor (2026-09-15); o resto está em
[research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico de domínio | ✅ | Nenhum termo de domínio nos tipos nem nas fixtures (`doc#1`, `test-assistant`); `Chunk.status` tem semântica definida pelo pack |
| II. Módulos substituíveis por seams | ✅ | Module Boundary respeitado: não consome seam; expõe Contrato de pack, Turn View e Contratos de serviço; conformidade planejada; fronteiras no CI (R20). Os seams são **definidos** aqui pela primeira vez (0.1 sem tag), sem mudar spec consumidora — impactos listados em "Seam notes" |
| III. O core orquestra | ✅ | Sem `build_graph`; despacho por `kind` (ADR-005); tool `retrieval` derivada pelo core (R9); rotina isolada fora da 0.1 (R23) |
| IV. Assistant é a fronteira | ✅ | `ValidatorContext` sem modelo; `MCPClient` só com aliases; `NamedRetriever.collections` permite à 004 deixar fora do catálogo o retriever fora do grant |
| V. Determinismo antes de LLM | ✅ | Conformidade roda `prepare_context` e validators duas vezes e compara; filtros de recuperação nunca vêm do modelo (FR-006) |
| VI. Conteúdo externo não-confiável | ✅ | `ToolResult.untrusted=True` por default; handler nativo devolve conteúdo, e o `ToolResult` é montado pelo gateway (R10) |
| VII. Falha fechada e explícita | ✅ | Mensagem de incompatibilidade nomeia cláusula e versão (R6); `check_declaration` devolve issues com código estável para a 002 recusar a carga |
| VIII. Modelos explícitos por papel | ✅ | `LLMProvider.chat` exige `model` explícito |
| IX. Proveniência e vigência | ✅ | `Chunk` e `Citation` carregam documento, versão, status, seção e página |
| X. Medir antes de calibrar | N/A | Nenhum número de RAG ou modelo aqui |
| XI. Streaming desde o início | ✅ | `stream` no `LLMProvider` desde a 0.1 |
| XII. Simplicidade deliberada | ✅ | US5 adiada; complexidade adicional justificada em Complexity Tracking |
| XIII. Portas e adapters | ✅ (layout justificado) | Ver gate abaixo |
| Stack — "Versionamento" | ✅ | Constituição 1.2.0 (emendada em 2026-09-15 pelo ADR-014) adota a convenção 0.x deslocada do FR-016. O `/speckit-analyze` apontou o conflito com a redação anterior ("breaking change = major"), resolvido pela emenda (R4) |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths (listed in Project Structure) — `ai-core/packages/contracts/**`,
  mais a raiz do workspace (`ai-core/pyproject.toml`, `.python-version`, `uv.lock`) e `.github/workflows/contracts.yml`,
  que esta spec cria por ser a primeira do workspace
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — não consome nenhum
- [x] Every seam this module exposes has a conformance test planned — Contrato de pack e Turn View: suíte de conformidade
  do kit + pack de teste; Contratos de serviço: suítes mínimas no kit (`acheck_llm_provider`, `acheck_mcp_client`),
  rodadas contra falsos na 001 e contra os adapters reais na 006 e na 007, que podem ampliá-las (R21, R22)
- [x] No seam changes — or each change has an ADR and the affected consumer specs are listed — definição inicial dos
  seams, dentro do design.md e das clarificações; consumidores afetados listados em "Seam notes"
- [x] Import boundaries (import-linter) cover the new code — import-linter + teste de allowlist (R20)

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` (any collapsed part is
  justified) — a distribuição **é** o conjunto de portas do microkernel (ADR-012) e segue o layout do design.md:
  `__init__.py` faz o papel de `api.py` (superfície pública, `__all__`); `compat.py`, `declaration.py` e `_freeze.py` são
  política pura (papel de `domain/`); não há `ports.py`, `service.py` nem `adapters/` porque não há I/O (princípio XIII:
  "Módulo sem I/O PODE omitir")
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — só stdlib e
  `typing_extensions` (teste de allowlist)
- [x] Other modules are imported only through their `api.py` — não importa nenhum módulo; o runtime não importa
  `testing/` (import-linter)
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — o runtime não
  importa módulos de I/O, relógio ou aleatoriedade (teste de denylist); a versão instalada é uma constante (R3); tempo
  entra como dado (`reference_time`). A única leitura de disco — metadados da distribuição do pack e fontes para a
  varredura de imports — fica no kit de testes, em funções finas de borda sobre regras puras
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — nenhuma porta secundária
- [x] Every secondary port has an in-memory adapter and a conformance suite — N/A (sem portas secundárias)
- [x] Services and adapters of other modules are instantiated only in the composition root — N/A

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/001-core-contracts/
├── spec.md              # Feature spec (what/why)
├── design.md            # Pre-approved technical input carried from the architecture
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── python-api.md    #   superfície pública (assinaturas)
│   ├── compatibility.md #   versões, faixas, mensagens, classificação de mudanças
│   └── testing-kit.md   #   kit de testes e códigos de issue
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
.github/workflows/
└── contracts.yml                     # CI dos contratos (na raiz enquanto ai-core/ é subpasta)

ai-core/                              # uv workspace — futuro repositório ai-core (separação antes da Fase 4)
├── pyproject.toml                    # [tool.uv.workspace] members = ["packages/*"]; grupo dev; import-linter; ruff; mypy; pytest
├── .python-version                   # 3.14
├── uv.lock
└── packages/
    └── contracts/                    # distribuição ai-core-contracts
        ├── pyproject.toml            # version = "0.1.0"; requires-python >=3.12; dependencies = ["typing_extensions>=4.12"]; uv_build
        ├── README.md
        ├── CHANGELOG.md              # registro de mudanças (inclusive só-semânticas — FR-020)
        ├── src/ai_core_contracts/
        │   ├── __init__.py           # superfície pública (__all__) — papel de api.py
        │   ├── py.typed
        │   ├── _version.py           # __version__ (testado contra os metadados)
        │   ├── _freeze.py            # JSONValue; congelamento em profundidade — puro
        │   ├── pack.py               # AgentPack, PackBase, PackManifest, PackContext, RETRIEVAL_FILTERS_KEY
        │   ├── tools.py              # ToolSpec, ToolResult, ToolInvocation, NativeHandler, ToolKind
        │   ├── retrieval.py          # Retriever, Reranker, Chunk, NamedRetriever, retrieval_tool_spec
        │   ├── view.py               # TurnView, Message, Citation
        │   ├── validation.py         # AnswerValidator, ValidatorContext, ValidationResult
        │   ├── declaration.py        # ContractIssue, check_declaration — puro
        │   ├── llm.py                # LLMProvider e TypedDicts de chat (provisório até a tag)
        │   ├── mcp.py                # MCPClient (provisório até a tag)
        │   ├── compat.py             # Version, VersionRange, derive_range, check_compatibility, bumps — puro
        │   ├── deprecation.py        # contract_deprecated, ContractDeprecationWarning
        │   └── testing/              # kit público, só stdlib
        │       ├── __init__.py       # REFERENCE_TIME, ISSUE_CODES, reexports
        │       ├── fixtures.py       # turn_view, chunk, pack_context, validator_context, tool_invocation
        │       ├── conformance.py    # acheck_pack, check_pack, assert_pack_conforms, ConformanceReport
        │       ├── imports.py        # check_imports (AST) — leitura de fontes na borda
        │       ├── distribution.py   # check_contracts_requirement (puro) + leitura de Requires-Dist (borda)
        │       └── services.py       # acheck_llm_provider, acheck_mcp_client — suítes mínimas dos contratos de serviço
        ├── tools/
        │   └── api_surface.py        # dump/diff da superfície pública (FR-020) — fora da distribuição
        └── tests/
            ├── unit/                 # value objects, imutabilidade, PackBase, compat (+ hypothesis × packaging), depreciação
            ├── conformance/          # kit contra packs bons e defeituosos (um por código de issue)
            ├── boundary/             # allowlist stdlib, denylist de I/O no runtime
            ├── surface/              # classificação de mudanças e bump (uma linha da tabela por teste)
            └── fixtures/
                └── contract_test_pack/   # pack de teste: pyproject próprio, testes próprios (US1, SC-001, FR-020 b)
```

**Structure Decision**: uma única distribuição, no layout do design.md (`ai-core/packages/contracts/src/ai_core_contracts/`),
sem `ports.py`/`service.py`/`adapters/` porque não há I/O (gate XIII). Esta spec também cria o esqueleto do workspace
`ai-core/` (raiz com `members = ["packages/*"]`, para que `core` e `generic` entrem na Fase 1 sem mexer na raiz) e o
workflow de CI na raiz do repositório. O pack de teste mora em `tests/fixtures/` e não é membro do workspace, para que a
resolução dele seja só a de runtime (R19).

## Seam Notes for Consumers

A 001 define os seams pela primeira vez; nenhuma spec consumidora precisa mudar agora. O que cada plano consumidor deve
saber:

| Consumidor | O que muda para ele |
|---|---|
| 002 | Hooks de catálogo chamados uma vez, na carga (FR-019); usar `check_compatibility` e `check_declaration` (a carga fail-closed continua sendo da 002); merge **raso** do retorno de `prepare_context`; montar a Turn View de cada pack só com `own_slice` + `depends_on`; packs herdam de `PackBase`, então todo hook existe |
| 004 | Derivar tools `retrieval` com `retrieval_tool_spec`; deixar fora do catálogo o retriever cujas `collections` não estão no grant (a redação da 004 US5 diz "rejeitada" — ajustar quando a 004 for clarificada); construir `ToolInvocation` (`request_id`, `reference_time`) e embrulhar o retorno do handler num `ToolResult(untrusted=True)` |
| 005 | Produzir a Turn View com `reference_time` com fuso e `generation_context` exato; value objects congelam o que recebem |
| 006 | Implementar `LLMProvider`; pode refinar as formas de chat no workspace antes da tag; rodar `acheck_llm_provider` contra cada adapter e ampliá-la, se preciso |
| 007 | Implementar `MCPClient`; resolver a associação tool → alias de `discover_tools` (R22); rodar `acheck_mcp_client` contra o cliente restrito |
| 010, 101 | Herdar de `PackBase`; rodar `assert_pack_conforms` (010 com `check_distribution=False`); `contract_version = "0.1"` |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md) e [contracts/](contracts/): **PASS**, sem violações novas.

- II: os tipos publicados não expõem nada do motor (sem estado, nó ou framework); `TurnView` só tem campos do FR-009;
  `ToolInvocation` só carrega dados já presentes na Turn View (`request_id`, `reference_time`).
- IV/VI: `ValidatorContext` e `PackContext` sem serviço; `ToolResult` fica fora do alcance do pack.
- XIII: `declaration.py` e `compat.py` puros; I/O só no kit de testes, na borda.
- XII: a Complexity Tracking segue com os mesmos itens; nenhum surgiu no design.
- "Versionamento": resolvido pela constituição 1.2.0 e pelo ADR-014.
- `/speckit-analyze` (2026-09-15): os dois itens CRITICAL (versionamento; suíte dos contratos de serviço) e os HIGH e
  MEDIUM foram incorporados a este plano, à research e ao tasks.md.

## Complexity Tracking

> Nenhuma violação da constituição. As linhas abaixo cumprem o princípio XII ("toda complexidade adicional num plano é
> justificada nesta tabela").

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Subconjunto PEP 440 próprio em `compat.py` (R5) | FR-016/FR-018 exigem regra de compatibilidade e checagem de faixa dentro da distribuição | depender de `packaging` viola o FR-001; vendorizá-lo traz ~2 mil linhas para usar uma fração |
| Congelamento em profundidade na construção (R11) | US4: Turn View imutável e idêntica entre produtores (fixture × motor) | congelar só no produtor deixa a garantia para cada produtor; congelamento raso deixa vazar mutação aninhada |
| `PackBase` ao lado do Protocol `AgentPack` (R7) | hooks opcionais (FR-003) em Python; hook novo como patch | um Protocol por hook multiplica tipos; `getattr` no core vira contrato implícito |
| `declaration.py` dentro dos contratos (R13) | os edge cases de "manifest inválido" precisam de uma só implementação, usada pela 002 e pela conformidade | cada consumidor reimplementaria e divergiria |
| `tools/api_surface.py` + pack congelado (R18, R19) | FR-020/SC-004 exigem detecção automática de breaking change e de bump insuficiente | revisão manual não é verificável; `griffe check` não reporta mudanças aditivas nem conhece a regra do `PackBase` |
