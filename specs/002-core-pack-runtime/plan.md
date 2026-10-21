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

**Fase 2 (2026-09-30): US4.** Os comandos `packs list` e `packs check` como funções em `adapters/cli.py` sobre o Pack
Registry já carregado — o mesmo que o servidor monta, pela mesma rotina de carga (R5). `check` reprova com código 1
qualquer pack em erro, inclusive instalado e desabilitado, e com 2 o `packs.yaml` malformado; o registro na raiz
`ai-core` é da 011 (US4) e a introspecção HTTP, da 008 (US5). Sem porta, dependência ou entidade novas
([research.md](research.md) R15–R17).

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

Nenhum `NEEDS CLARIFICATION` — resolvidos na clarificação de 2026-09-15 e em [research.md](research.md). A Fase 2 não
muda nenhuma linha acima: a US4 usa só a biblioteca padrão, dentro de `adapters/`.

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
│   ├── packs-yaml.md         # formato da configuração do operador
│   └── cli.md                # packs list e packs check (Fase 2, US4)
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
        │           ├── config_yaml.py    # YamlPackConfigSource (packs.yaml)
        │           └── cli.py            # Fase 2 (US4): packs list e packs check sobre o registry carregado
        └── tests/packs/
            ├── conftest.py           # packs de teste (PackBase) e fábrica de distribuições falsas
            ├── unit/                 # domain/*, service com adapters em memória, matriz de falhas
            ├── contract/             # conformidade das portas (memória × real) e dos seams
            └── integration/          # carga completa com entry points e packs.yaml reais em tmp_path;
                                      # test_packs_cli.py (Fase 2): os comandos contra a carga real
```

**Structure Decision**: layout hexagonal do ADR-012, no caminho do design.md (`ai-core/packages/core/src/ai_core/packs/`).
`adapters/cli.py` entra na Fase 2 (US4) e `adapters/declarative.py` (US6) em P3. A distribuição `ai-core` é criada com o
mínimo para este módulo; o script `ai-core` e a composition root são da 011.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 003 (Fase 2) | Validar Assistant = `PackRegistry.compose(assistant.packs)`; `CompositionError` torna o Assistant indisponível com a mensagem |
| 005 (Fase 1) | Guardar `slices` na execução; chamar `prepare`/`validate` com a Turn View base (fatias vazias) e o mapeamento; `PackHookError` encerra a execução com erro explícito |
| 008 | Introspecção = `PackRegistry.entries()` |
| 011 | Montar `PackRuntime(source, config_source)` pelo perfil (`memory` nos testes; entry points + YAML no real); configurar handlers do logger `ai_core.packs`; o registry é montado uma vez no boot. Fase 2: registrar `packs list` e `packs check` (`adapters/cli.py`), carregando o registry com os mesmos adapters do servidor e sem abrir a API; `PackConfigError` vai para `config_error_command` (código 2) |
| 010 | Pack genérico em `ai-core/packages/generic/` — já coberto por `members = ["packages/*"]` (clarificação de 2026-09-17 da 010; a redação anterior dizia `packs/generic/`) |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md) e [contracts/](contracts/): **PASS**.

- II: `api.py` só tem value objects, Protocols e erros, com tipos da API pública da 001; `Composition` não carrega
  instâncias de pack.
- VII: cada transição para `error` do diagrama de estados tem mensagem com etapa e causa; configuração malformada é o
  único caso que para o boot, e é decisão da 011.
- XIII: `jsonschema` em `domain/config.py` é validação pura; o teste de fronteira proíbe `yaml` fora de `adapters/`.

## Constitution Check — Fase 2 (US4)

Reavaliado para a US4: **PASS**, sem mudança em nenhum item acima.

- II: nenhum seam muda; a CLI é adapter primário do próprio módulo e lê só `PackRegistry` (R15).
- VII: `check` reprova exatamente o que o boot marcaria como erro, com a mesma mensagem (R16).
- XIII: `adapters/cli.py` usa só a biblioteca padrão; nenhuma porta nova (não há I/O além da saída que recebe); quem monta
  e carrega o registry continua sendo a composition root.
- XII: sem saída estruturada nem parser próprio (R17, R15).

## Fase 3 (US3 cenário 1) — 2026-10-01

A composição do catálogo com namespace, que o roadmap põe "junto da 004": um seam novo, **Pack Toolset**
(`toolset(composition)` → `PackTool` por tool nativa e por retriever, com `<pack>.<nome>`), implementado pelo
`PackRuntime` sobre o catálogo coletado na carga (research R18, R19). Toque declarado na 004: ela reexporta o `PackTool`
daqui e a suíte da porta dela roda contra o `PackRuntime` (R20).

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | Seam novo, aditivo: nenhum existente muda; registrado em `specs/README.md`; consumidor (004) listado |
| III. O core orquestra | ✅ | Retrieval é tool (ADR-005): o retriever entra pela tool de recuperação do contrato |
| IV. Assistant é a fronteira | ✅ | Este módulo não filtra por Assistant — devolve o que a composição tem; quem restringe é a 004 |
| XIII. Portas e adapters | ✅ | Sem I/O: o catálogo foi coletado na carga; nenhuma porta nova |

**Module boundary gate (Fase 3)**: mudanças em `ai_core/packs/` e `tests/packs/`, mais o toque declarado na 004
(`capabilities/domain/records.py` e a suíte da porta); nenhum seam existente muda. **Resultado**: PASS.

## Fase 4 (US5) — 2026-10-07

O build da instalação (ADR-009) num repositório próprio, `agentic-deploy`, com o core construído num estágio do
próprio Dockerfile a partir da tag `v0.1.0` do `agentic-app` ([ADR-022](../../docs/adr/ADR-022-instalacao-constroi-o-core-num-estagio-proprio.md)),
os packs por build-arg, `ai-core packs check` no build e um runtime sem instalador. Decisões em
[research.md](research.md) R21–R29; contrato em [contracts/installation.md](contracts/installation.md). Nenhuma linha do
`ai-core/` muda: o `packs check` (US4) é o que o build roda.

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | O domínio entra só pelo build-arg da instalação; o core não muda |
| II. Seams | ✅ | A instalação usa a CLI publicada (`packs check`, `assistants validate`, `serve`) e a configuração por `AI_CORE_*` (011) |
| VI. Conteúdo externo | ✅ | Código privado baixado por montagem SSH; chave de host do GitHub fixada; nenhuma credencial em camada (R23) |
| VII. Falha fechada | ✅ | Pack incompatível falha o build, não a produção (US5 cen. 2) |
| XII. Simplicidade | ✅ | Sem registry nem pipeline de release do core (ADR-022); ARM64 adiado (R28) |
| XIII. Portas e adapters | N/A | Infraestrutura de empacotamento, fora do código dos módulos |

**Module boundary gate (Fase 4)**: tudo no repositório `agentic-deploy`; no `agentic-app`, só documentação, a tag
`v0.1.0` e o ponteiro do submódulo; deploy keys só de leitura no `agentic-app` e no `ai-scouting`. Nenhum seam muda.
**Resultado**: PASS.

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Três estágios no Dockerfile (ADR-022) | o runtime não pode carregar instalador nem credencial (FR-013, FR-014) | um estágio só deixaria `uv`, `git` e SSH na imagem final |
| Duas identidades SSH no build (R23) | deploy key vale para um repositório só | alias de host no SSH dentro do build é frágil e invisível no Dockerfile |

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Testes de piso dos contratos fora do workspace (R3) | o workspace passa a exigir 3.14 com o core | declarar o core `>=3.12` prometeria suporte não testado |
| Distribuições falsas (`*.dist-info`) nos testes do `EntryPointPackSource` | a conformidade da porta precisa rodar contra entry points reais | instalar distribuições num venv por teste é lento; esperar a 010 bloquearia a Fase 1 |
| Revalidação da composição no Pack Hooks (R10) | `Composition` é um value object público e pode ser montado à mão | token privado dentro de `Composition` acopla o seam à implementação |

## Fase 9 (US7) — 2026-10-14

Insumos: ADR-029, ADR-030, ADR-033; a clarificação de 2026-10-13; os planos da Fase 9 da 012, 011, 013 e 008. Decisões em
[research.md](research.md) R42–R50; contrato em [contracts/installation.md](contracts/installation.md) ("Fase 9").

**Summary**: a instalação de referência passa a ter três modos por `COMPOSE_PROFILES` — padrão (API), `webui` e
`console` —, sempre com Postgres; o Keycloak sai e o Open WebUI entra pelo provedor da própria plataforma; a imagem da
console sai do mesmo Dockerfile e da mesma tag do core; o `.env.example` explica onde fica cada segredo; as provas
cobrem o login da plataforma no chat e a administração pela console.

**Constitution Check (Fase 9)**: VII (falha cedo: build da console falha o build; chave mestra ausente para o boot) ✅;
XI (a console é opcional; a API funciona sem ela) ✅; ADR-022 (core e console da mesma tag) ✅. **Module boundary**: só
o submódulo `agentic-deploy/` e os artefatos da 002 neste repositório. **Resultado**: PASS.

**Project Structure (Fase 9)**:

```text
agentic-deploy/
├── Dockerfile                 # + console-build, console
├── docker-compose.yml         # + postgres, console; open-webui na plataforma; − keycloak
├── .env.example               # seções Sempre / Com interface / Sem console
├── config/identity.yaml       # novo; − config/keycloak/
├── config/assistants.yaml     # overrides num Assistant de exemplo
├── secrets/.gitignore         # o arquivo da senha do admin inicial fica fora do git
├── scripts/check-build.sh     # + alvo console
├── scripts/check-webui.py     # login da plataforma
├── scripts/check-console.py   # novo
└── README.md                  # modos, migração da Fase 7, Google, Langfuse
```

## Passada de 2026-10-20: identidade Axon (US8; [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md))

> As seções acima são os planos das passadas anteriores e ficam como foram executadas (ADR-037, item 6); os nomes
> antigos nelas se leem pela tabela do ADR-037. Esta seção é o plano da US8; a instalação (US7) tem passada própria.

**Insumos lidos**: [spec.md](spec.md) (US8, FR-023–FR-025, SC-008, clarificações de 2026-10-20), [design.md](design.md),
ADR-037, constituição 1.3.1 (já cita `axon.packs`), as passadas da 011 (import `axon_ai`, comando `axon`) e da 010
(`axon-generic` 0.2.0). Research: R51–R55. **Sem divergência do `design.md`** além do nome do grupo, sem ADR novo; o seam
que muda (o grupo de registro) é o que o ADR-037 decide.

**Summary**: o Pack Runtime passa a descobrir os packs pelo grupo `axon.packs` (R51), em corte seco: pack só no grupo
antigo não é descoberto e, habilitado, fica `error: não instalado` pela regra que já existe (R52). Os packs do workspace
e as distribuições falsas das suítes passam ao grupo novo (R53); um teste novo prova os dois lados (R54).

**Technical Context**: sem mudança de linguagem, dependência, storage ou lock. Uma constante de produção
(`PACKS_GROUP`), quatro arquivos de configuração e documentação de pack, o kit de teste e um teste novo. Nenhum `NEEDS
CLARIFICATION`.

**Constitution Check (US8)**

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Módulos substituíveis por seams | ✅ | O grupo é o seam de descoberta; muda por ADR (ADR-037), no módulo dono, com os consumidores do workspace na mesma passada (R53) |
| VII. Falha fechada e explícita | ✅ | Pack habilitado e não encontrado fica `error: não instalado`; `packs check` sai com 1; o build da instalação para (R52) |
| XII. Simplicidade deliberada | ✅ | Sem consulta ao grupo antigo nem janela de compatibilidade (R52) |
| XIII. Portas e adapters | ✅ | A mudança fica no adapter `EntryPointPackSource`; a porta `PackSource` não muda |
| Stack | ✅ | A constituição 1.3.1 já diz "entry point `axon.packs`" |

**Module boundary gate**: `axon_ai/packs/adapters/entry_points.py` e `tests/packs/**`. Fora do módulo, só quem se
anuncia no grupo (pack de referência, pack de teste e README dos contratos) e documentos vivos (R53, R55); nenhuma linha
de outro módulo do core. **Ports & adapters gate**: só o adapter muda. **Resultado**: PASS.

**Project Structure (US8)**

```text
axon-ai/packages/
├── core/
│   ├── src/axon_ai/packs/adapters/entry_points.py   # PACKS_GROUP = "axon.packs" (R51)
│   └── tests/packs/
│       ├── packs_testkit.py                         # FakeDistributions.add(..., group=PACKS_GROUP) (R53)
│       └── integration/test_packs_entry_point_group.py   # novo (R54)
├── generic/{pyproject.toml,README.md,src/axon_generic/__init__.py}   # grupo axon.packs (R53)
└── contracts/{README.md,tests/fixtures/contract_test_pack/pyproject.toml}   # grupo axon.packs (R53)
```

**Seam Notes for Consumers (US8)**

| Consumidor | O que muda para ele |
|---|---|
| Autor de pack | `[project.entry-points."axon.packs"]` no `pyproject.toml`; pack só no grupo antigo não é encontrado |
| 010 (`axon-generic`) | O grupo no `pyproject.toml`, nesta passada; versão igual (R53) |
| 011 | Nada: monta `EntryPointPackSource()` com o grupo padrão |
| 101 (`ai-scouting`) | Troca o grupo na passada dela, junto com a tag nova do core |
| Instalação | Nada até a passada dela: o estágio `core` instala uma tag antiga, com o grupo antigo de ponta a ponta |

**Complexity Tracking (US8)**: nenhuma linha nova.

**Constitution Check — pós-design (US8)**: reavaliado com [contracts/ports.md](contracts/ports.md),
[data-model.md](data-model.md) e [quickstart.md](quickstart.md) ("Fase 9, incremento 9.5"): **PASS**.

## Passada de 2026-10-20: a instalação com os nomes da Axon (US7 cen. 6; [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md))

**Insumos lidos**: [spec.md](spec.md) (US7 cen. 6, FR-026–FR-028, SC-009, clarificações de 2026-10-20),
[contracts/installation.md](contracts/installation.md), [design.md](design.md), ADR-037, as passadas da 011 (recusa de
`AI_CORE_*`), 003 (audiências), 008 (cabeçalhos), 013 (`AXON_UPSTREAM`) e 101 (`axon-scouting` 0.4.0). Research:
R56–R61. **Sem divergência do `design.md`** além dos nomes; sem ADR novo.

**Summary**: o repositório de instalação passa aos nomes da Axon — projeto `axon` fixo, serviço `axon`, imagens,
caminhos, banco, variáveis, cabeçalhos do Open WebUI e audiências (R56, R57) —, constrói o core da `v0.7.0-rc1` e o pack
0.4.0, mantém o pack incompatível incompatível (R58), documenta a migração (R59) e prova o corte seco no build (R60).

**Technical Context**: Dockerfile, compose, `.env.example`, `config/*.yaml`, scripts e README do `axon-deploy`; nenhuma
linha do core nem do pack. Nenhum `NEEDS CLARIFICATION`.

**Constitution Check (instalação)**

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Módulos substituíveis por seams | ✅ | A instalação consome só seams publicados: variáveis da 011, cabeçalhos da 008, audiências da 003, `AXON_UPSTREAM` da 013 |
| VII. Falha fechada e explícita | ✅ | `.env` antigo não sobe (recusa da 011 e da 101), provado no `check-build.sh` (R60) |
| XII. Simplicidade deliberada | ✅ | Volumes novos em vez de migração de dados (R59) |
| Segredos | ✅ | Nenhum valor real no repositório; segredos por arquivo e `.env` fora do git, como antes |

**Module boundary gate**: só o submódulo `agentic-deploy/` e os documentos vivos da 002 sobre a instalação. **Resultado**:
PASS.

**Project Structure (instalação)**

```text
agentic-deploy/                      # repositório axon-deploy
├── Dockerfile                       # CORE_REPO/CORE_REF, /opt/axon, /etc/axon, usuário axon, PACKS 0.4.0 (R56)
├── docker-compose.yml               # name: axon, serviço axon, Postgres axon, x-axon-*, WEBUI_NAME (R56, R57)
├── .env.example                     # AXON_*, AXON_SCOUTING_* (R56)
├── config/{assistants,identity,packs}.yaml   # audiências axon/axon-admin; AXON_SCOUTING_* nos comentários (R57)
├── packages/incompatible-pack/      # contratos 0.2, contract_version "0.3" (R58)
├── scripts/{check-build.sh,dev-users.sh,check-webui.py}   # comando axon, serviço axon, recusa (R60)
├── .github/workflows/build.yml      # comentários; segredos iguais (R60)
└── README.md                        # nomes e "Vindo dos nomes antigos" (R59)
```

**Constitution Check — pós-design (instalação)**: reavaliado com [contracts/installation.md](contracts/installation.md)
("Fase 9, incremento 9.5") e [quickstart.md](quickstart.md): **PASS**.
