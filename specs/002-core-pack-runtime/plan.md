# Implementation Plan: Descoberta, carga e composição de packs

**Branch**: `002-core-pack-runtime` | **Date**: 2026-09-15 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-core-pack-runtime/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/002-core-pack-runtime/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-003, ADR-009, ADR-011, ADR-012; consumidores conferidos: 003, 005, 008, 010,
011; contrato 001 implementado (`ai-core-contracts` 0.1.0). Nenhuma divergência do design.md: `state_projection` ganhou
tipo (Turn View base + fatias) e o CLI, o pack declarativo e o template de instalação ficam para fases seguintes
([research.md](research.md) R1, R4).

## Summary

Criar a distribuição `ai-core` e seu primeiro módulo, `ai_core/packs/`, que descobre packs por entry point, verifica
identidade e compatibilidade antes de instanciar, habilita e configura pelos dados do operador (`packs.yaml`, lido só no
boot), coleta o catálogo uma vez e aplica falha fechada em cascata (dependências, ciclos). Expõe dois seams: **Pack
Registry** (entradas com status, erro e capacidades; `compose` com a regra "dependência antes do dependente") e **Pack
Hooks** (prompts na ordem, `prepare` com Turn View recortada e merge raso, `validate` encadeado, `PackHookError` que
nomeia o pack). Escopo da Fase 1: **US1, US2 e US3 cenários 2–4**; CLI (US4) na Fase 2, catálogo com namespace (US3
cenário 1) na Fase 3, template de instalação (US5) na Fase 4, pack declarativo (US6) em P3.

## Technical Context

**Language/Version**: Python 3.14 (`ai-core` com `requires-python = ">=3.14"`); `ai-core-contracts` mantém o piso 3.12,
testado fora do workspace (R3)

**Primary Dependencies**: `ai-core-contracts` (workspace), `pyyaml` (só em `adapters/config_yaml.py`), `jsonschema`
(validação de configuração); dev: as do workspace (pytest, pytest-asyncio, mypy, ruff, import-linter)

**Storage**: N/A — registry em memória, montado no boot e imutável

**Testing**: pytest + pytest-asyncio; testes de `domain/` puros; suítes de conformidade das portas (memória × entry
points reais em `tmp_path`; memória × YAML) e dos seams (service com adapters em memória); matriz de falhas injetadas

**Target Platform**: processo do core na imagem Linux ARM64 (Python 3.14)

**Project Type**: módulo de biblioteca dentro do monolito modular (`ai-core`)

**Performance Goals**: carga de dezenas de packs em menos de 1 s no hardware alvo, sem contar o import dos próprios
packs; `prepare`/`validate` sem custo além dos hooks (recorte de view e merge lineares no tamanho das fatias)

**Constraints**: nenhum código de pack instanciado antes da checagem de identidade e contrato (FR-002, FR-017); falha de
um pack nunca derruba o boot (FR-005); registry imutável (FR-003); só a API pública de `ai_core_contracts`; nada de
domínio (princípio I)

**Scale/Scope**: 1 módulo (`api.py`, `domain/` com 5 arquivos, `ports.py`, `service.py`, 3 adapters); ~15 símbolos
públicos no `api.py`

Nenhum `NEEDS CLARIFICATION` — resolvidos na clarificação de 2026-09-15 e em [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Nenhum domínio; packs de teste neutros |
| II. Seams | ✅ | Consome só a API pública da 001; expõe Pack Registry e Pack Hooks com suítes de conformidade; não conhece Assistants (recebe lista de nomes), flows nem HTTP |
| III. O core orquestra | ✅ | Packs não alteram fluxo; composição é operação de conjunto; nada de grafo |
| IV. Assistant é a fronteira | ✅ | A ordem e a lista vêm do Assistant; `compose` recusa pack indisponível (a indisponibilidade é explícita) |
| V. Determinismo | ✅ | Carga e composição determinísticas; `prepare`/`validate` sem LLM |
| VI. Conteúdo externo | N/A | Execução de tools é da 004 |
| VII. Falha fechada | ✅ | Toda falha de pack vira `error` com causa; dependência quebrada propaga; hook que falha encerra a execução com `PackHookError`; configuração malformada para o boot |
| XI. Streaming | N/A | — |
| XII. Simplicidade | ✅ | CLI, declarativo, template e catálogo adiados para seus consumidores; sem recarga em execução |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/packs/**` e testes; mais o
  esqueleto da distribuição `ai-core` (`packages/core/pyproject.toml`, `ai_core/__init__.py`), configuração do
  workspace e o workflow `core.yml`; ajuste do `contracts.yml` e do quickstart da 001 por causa do Python 3.14 (R3)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — só a API pública de
  `ai_core_contracts` (001)
- [x] Every seam this module exposes has a conformance test planned — `test_packs_registry_seam.py`,
  `test_packs_hooks_seam.py`
- [x] No seam changes — os dois seams são definidos aqui pela primeira vez, na forma do design.md (R4)
- [x] Import boundaries (import-linter) cover the new code — contratos novos do R13

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/`
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — `yaml` só no adapter;
  `jsonschema` (validação pura, sem `$ref` remoto) em `domain/`
- [x] Other modules are imported only through their `api.py` — não há outro módulo do core ainda; o contrato de
  import-linter entra quando houver
- [x] All I/O, time, randomness, secrets and trace go through a secondary port — descoberta (`PackSource`) e
  configuração (`PackConfigSource`); sem tempo, segredos ou trace; log pela stdlib (R11)
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — as duas portas fazem I/O e têm troca
  prevista (declarativo; outras fontes de configuração)
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter
- [x] Services and adapters of other modules are instantiated only in the composition root — a 002 não instancia nada de
  outro módulo; quem monta `PackRuntime` com seus adapters é a 011 (e os testes)

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/002-core-pack-runtime/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── pack-runtime-api.md   # seams Pack Registry e Pack Hooks
│   ├── ports.md              # PackSource, PackConfigSource e suas conformidades
│   └── packs-yaml.md         # formato da configuração do operador
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
.github/workflows/
├── contracts.yml                     # ajuste: testes de piso 3.12/3.13 fora do workspace (R3)
└── core.yml                          # novo: lint, tipos, testes 3.14, fronteiras do core

ai-core/
├── pyproject.toml                    # mypy/ruff/pytest cobrindo packages/core; contratos novos do import-linter (R13)
└── packages/
    └── core/                         # distribuição ai-core (nasce aqui — R2)
        ├── pyproject.toml            # version 0.1.0; requires-python >=3.14; deps: ai-core-contracts, pyyaml, jsonschema
        ├── src/ai_core/
        │   ├── __init__.py
        │   ├── py.typed
        │   └── packs/
        │       ├── __init__.py
        │       ├── api.py            # seams: PackRegistry, PackHooks + value objects e erros
        │       ├── domain/           # puro
        │       │   ├── __init__.py
        │       │   ├── identity.py       # entry point × classe; leitura de name/contract_version
        │       │   ├── config.py         # validação de config contra config_schema (jsonschema)
        │       │   ├── dependencies.py   # dependência indisponível em cascata; ciclos
        │       │   ├── composition.py    # regras de compose (existência, status, ordem de dependência)
        │       │   └── hooks.py          # recorte de Turn View, merge raso, encadeamento de validators
        │       ├── ports.py          # PackSource, PackConfigSource, DiscoveredPack, PackSettings
        │       ├── service.py        # PackRuntime: carga (R5), PackRegistry e PackHooks
        │       └── adapters/
        │           ├── __init__.py
        │           ├── memory.py         # InMemoryPackSource, InMemoryPackConfigSource
        │           ├── entry_points.py   # EntryPointPackSource (grupo ai_core.packs)
        │           └── config_yaml.py    # YamlPackConfigSource (packs.yaml)
        └── tests/packs/
            ├── conftest.py           # packs de teste (PackBase) e fábrica de distribuições falsas
            ├── unit/                 # domain/*, service com adapters em memória, matriz de falhas
            ├── contract/             # conformidade das portas (memória × real) e dos seams
            └── integration/          # carga completa com entry points e packs.yaml reais em tmp_path
```

**Structure Decision**: layout hexagonal do ADR-012, no caminho do design.md (`ai-core/packages/core/src/ai_core/packs/`).
`adapters/cli.py` (US4) e `adapters/declarative.py` (US6) entram nas fases deles. A distribuição `ai-core` é criada com o
mínimo para este módulo; o script `ai-core` e a composition root são da 011.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 003 (Fase 2) | Validar Assistant = `PackRegistry.compose(assistant.packs)`; `CompositionError` torna o Assistant indisponível com a mensagem |
| 005 (Fase 1) | Guardar `slices` na execução; chamar `prepare`/`validate` com a Turn View base (fatias vazias) e o mapeamento; `PackHookError` encerra a execução com erro explícito |
| 008 | Introspecção = `PackRegistry.entries()` |
| 011 | Montar `PackRuntime(source, config_source)` pelo perfil (`memory` nos testes; entry points + YAML no real); configurar handlers do logger `ai_core.packs`; o registry é montado uma vez no boot |
| 010 | Pack genérico em `ai-core/packs/generic/` exige acrescentar `packs/*` aos membros do workspace |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md) e [contracts/](contracts/): **PASS**.

- II: `api.py` só tem value objects, Protocols e erros, com tipos da API pública da 001; `Composition` não carrega
  instâncias de pack.
- VII: cada transição para `error` do diagrama de estados tem mensagem com etapa e causa; configuração malformada é o
  único caso que para o boot, e é decisão da 011.
- XIII: `jsonschema` em `domain/config.py` é validação pura; o teste de fronteira proíbe `yaml` fora de `adapters/`.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Testes de piso dos contratos fora do workspace (R3) | o workspace passa a exigir 3.14 com o core | declarar o core `>=3.12` prometeria suporte não testado |
| Distribuições falsas (`*.dist-info`) nos testes do `EntryPointPackSource` | a conformidade da porta precisa rodar contra entry points reais | instalar distribuições num venv por teste é lento; esperar a 010 bloquearia a Fase 1 |
| Revalidação da composição no Pack Hooks (R10) | `Composition` é um value object público e pode ser montado à mão | token privado dentro de `Composition` acopla o seam à implementação |
