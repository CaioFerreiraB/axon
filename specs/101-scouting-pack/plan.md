# Implementation Plan: Pack scouting — composição, contexto determinístico e prompts (Fase 4)

**Branch**: `101-scouting-pack` | **Date**: 2026-10-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/101-scouting-pack/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/101-scouting-pack/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-004, ADR-006, ADR-012, ADR-013, ADR-014 e
[ADR-021](../../docs/adr/ADR-021-workspace-ai-core-permanece-no-repositorio-da-plataforma.md); as cinco clarificações
de 2026-10-07; o contrato de pack da 001 na tag `contracts-v0.1.0` (`TurnView` com `question` e `reference_time`,
`RETRIEVAL_FILTERS_KEY`, kit `ai_core_contracts.testing` com `assert_pack_conforms`); consumidores conferidos no código —
002 (carga por entry point, `PackHooks.system_prompts`), 003 (`effective_flow`: o preferido do pack único ou `chat`),
011 (perfil `test` para suítes de packs externos); e o `ai-generic` (010) como molde. Três linhas do design.md foram
superadas pelas clarificações e pelo ADR-021 e ganharam nota de origem no próprio arquivo: a fonte dos contratos (o
`agentic-app`, subdiretório `ai-core/packages/contracts` — R2), o manifest da Fase 4 (sem `preferred_flow`,
`requires_collections` e `config_schema` — R4) e a vigência como intervalo (R12). Nenhum ADR novo nesta passada.

## Summary

Criar o pack `ai-scouting` no repositório próprio (submódulo `ai-scouting/`): distribuição que depende só de
`ai-core-contracts` pela tag `contracts-v0.1.0`, descoberta pelo entry point `ai_core.packs` com o nome `scouting`. Na
Fase 4 ele publica duas capacidades: o fragmento de instruções de domínio — que, sem corpus, manda declarar que nenhum
documento foi consultado e nunca inventar citação (FR-011) — e a preparação de contexto, uma derivação pura de (pergunta,
dia de referência, léxico) que produz ramo, temas, tipos de documento e a vigência como intervalo, inclusive em consulta
histórica, e publica os filtros para os retrievers do próprio pack. Sem modelo, sem relógio, sem I/O. O pack passa na
conformidade da 001 só com os contratos (SC-003); um grupo opcional de integração prova a carga e o prompt na
plataforma real, pelo perfil `test`. Escopo: **US1, US2, US3**; US4 e US5 são Fase 5.

## Technical Context

**Language/Version**: Python 3.12+ (`requires-python = ">=3.12"`, o piso dos contratos — R3); suíte em 3.12 e 3.14; a
integração com a plataforma só em 3.14 (o Python do core)

**Primary Dependencies**: `ai-core-contracts>=0.1,<0.2` pela tag `contracts-v0.1.0` do `agentic-app` (R2). Nenhuma
outra em runtime. Desenvolvimento: `pytest`, `mypy`, `ruff`, `import-linter`; grupo opcional `platform` com `ai-core`
pela mesma tag (R9)

**Storage**: N/A — nenhum estado entre execuções; o léxico é dado em código (R7)

**Testing**: pytest; conformidade da 001 com todas as etapas; testes por tabela da derivação e dos períodos; invariantes
do léxico; propriedades do prompt; pureza (sem relógio); integração opcional no perfil `test` da plataforma (R9)

**Target Platform**: processo do core na imagem Linux ARM64 (a instalação da 002 US5 traz o pack); o pack também
importa num ambiente só com os contratos

**Project Type**: distribuição Python de pack de domínio (plug-in do microkernel), em repositório próprio

**Performance Goals**: a derivação é casamento de termos sobre uma pergunta curta — tempo desprezível diante de uma
chamada de modelo (5 a 15 tok/s no hardware alvo); 0 chamadas de modelo (SC-002)

**Constraints**: zero import do core (US1 cen. 3); nenhum relógio do sistema (FR-005); nenhum modelo na derivação
(FR-004, SC-002); nenhuma dependência além dos contratos (FR-001); prompt sem citação inventada na Fase 4 (FR-011)

**Scale/Scope**: 1 distribuição; `pack.py`, `context/` (léxico, normalização, períodos, derivação), `prompts/`; léxico
semente com 4 ramos, 6 tipos de documento e cerca de 15 temas

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Todo o domínio fica no `ai-scouting`; nenhuma linha do `ai-core/` muda, e o core não ganha teste de escotismo (a integração mora no pack — R9, R15) |
| II. Seams | ✅ | O pack consome só o contrato 001; o teste de integração usa a composition root (`platform`) e o seam `PackHooks` da 002 |
| III. O core orquestra | ✅ | O pack registra capacidades; não constrói grafo; o flow vem do Assistant na Fase 4 (R4) |
| IV. Assistant é a fronteira | ✅ | O pack não amplia o que uma execução enxerga; os filtros restringem a recuperação do próprio pack |
| V. Determinismo | ✅ | A derivação é função pura, sem modelo (SC-002 por construção e por import-linter — R13); a conformidade verifica determinismo |
| VI. Conteúdo externo | ✅ | O prompt afirma "dado, nunca instrução" (FR-009) |
| VII. Falha fechada | ✅ | Ambiguidade de ramo → sem filtro, nunca palpite; ano solto não vira período (R8) |
| VIII. Modelos por papel | N/A | O pack não fala com modelos |
| IX. Proveniência | ✅ | Sem corpus, o prompt proíbe citar ou nomear documento como consultado (FR-011, R10); consulta histórica liga `include_superseded` para a 104 marcar a fonte não vigente |
| X. Medir antes de calibrar | ✅ | Nenhum limiar calibrado; o acerto da derivação (SC-001) é medido na 105 |
| XI. Streaming | N/A | O pack não produz resposta |
| XII. Simplicidade | ✅ | Manifest mínimo na Fase 4, sem tools, validators ou retriever de placeholder; léxico em código; sem stemmer (R4, R6, R7, R11) |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-scouting/pyproject.toml`, `ai-scouting/uv.lock`,
  `ai-scouting/src/ai_scouting/{pack.py,context/,prompts/}`, `ai-scouting/tests/**`,
  `ai-scouting/.github/workflows/ci.yml`; no `agentic-app`, só documentação e o ponteiro do submódulo (R15)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — contrato de pack
  (001): `PackBase`, `PackManifest`, `PackContext`, `TurnView`, `JSONValue`, `RETRIEVAL_FILTERS_KEY`, kit
  `ai_core_contracts.testing`; na integração: `ai_core.bootstrap.wiring.platform` e `ai_core.bootstrap.profiles`
  (011, perfil `test`), `PackRegistry.entry`/`compose` e `PackHooks.system_prompts` (002)
- [x] Every seam this module exposes has a conformance test planned — o pack expõe o entry point e as capacidades:
  conformidade da 001 nos testes do pack e a integração na plataforma; o formato dos filtros (interno ao pack, 101 →
  103) tem contrato próprio e testes de forma
- [x] No seam changes — nenhum seam do core muda
- [x] Import boundaries (import-linter) cover the new code — três contratos no `pyproject.toml` do `ai-scouting` (R13)

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` (any collapsed part is
  justified) — num pack, `pack.py` é a composition root e as políticas puras ficam em `context/` e `prompts/` (como o
  `ai-generic`, 010 R7); `ports.py` e `adapters/` são omitidos porque a 101 não faz I/O (design.md, "Portas e
  adapters"); a superfície pública é o entry point
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — o pack importa só stdlib
  (`dataclasses`, `datetime`, `re`, `unicodedata`) e `ai_core_contracts`
- [x] Other modules are imported only through their `api.py` — o pack importa só `ai_core_contracts`; nada de
  `ai_core` (verificado pela conformidade e pelo import-linter)
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — não há I/O,
  aleatoriedade, segredo nem trace; o tempo vem da Turn View (`reference_time`, ADR-013), e `context/` é verificado sem
  chamada de relógio (R13)
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — nenhuma porta criada; uma porta para o
  léxico seria porta para dado puro
- [x] Every secondary port has an in-memory adapter and a conformance suite — N/A (nenhuma porta)
- [x] Services and adapters of other modules are instantiated only in the composition root — o pack não instancia
  nada de outro módulo; na integração, quem monta a plataforma é a composition root do core (`platform`)

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/101-scouting-pack/
├── spec.md
├── design.md            # notas de origem: fonte dos contratos (ADR-021), manifest da Fase 4, vigência como intervalo
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── scouting-pack.md       # capacidades publicadas na Fase 4 e conformidade
│   ├── retrieval-filters.md   # formato dos filtros, 101 → 103 (interno ao pack)
│   └── packaging.md           # distribuição, fontes, grupos, import-linter, CI
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-scouting/                                 # submódulo → CaioFerreiraB/ai-scouting (privado, ADR-021)
├── pyproject.toml                           # ai-scouting 0.1.0; >=3.12; ai-core-contracts>=0.1,<0.2 pela tag; entry point;
│                                            # grupos dev e platform; ruff, mypy strict, pytest, import-linter (R2, R3, R9, R13)
├── uv.lock
├── README.md                                # já existe (commit inicial)
├── .github/workflows/ci.yml                 # lint, test (3.12 e 3.14), clean-env, platform; deploy key (R14)
├── src/ai_scouting/
│   ├── __init__.py
│   ├── py.typed
│   ├── pack.py                              # ScoutingPack: identidade, manifest mínimo, system_prompt, prepare_context
│   ├── context/
│   │   ├── __init__.py
│   │   ├── lexicon.py                       # Lexicon + LEXICON (semente revisada pelo mantenedor — R7)
│   │   ├── text.py                          # normalize, contains_term (R6)
│   │   ├── periods.py                       # Validity, reference_day (UTC−03:00), find_period (R5, R8)
│   │   └── derivation.py                    # ScoutingContext, derive_context, to_slice (R8, R12)
│   └── prompts/
│       ├── __init__.py
│       └── domain.py                        # SYSTEM_PROMPT da Fase 4 (R10)
└── tests/
    ├── test_conformance.py                  # assert_pack_conforms, todas as etapas
    ├── test_pack.py                         # identidade, manifest mínimo, versão = distribuição
    ├── test_prompt.py                       # blocos do prompt (FR-009, FR-011)
    ├── test_lexicon.py                      # invariantes do léxico
    ├── test_text.py                         # normalização e casamento por palavra
    ├── test_periods.py                      # tabela de vigência; dia de referência em Brasília
    ├── test_derivation.py                   # US2, US3 e casos de borda, por tabela
    ├── test_purity.py                       # context/ sem chamada de relógio
    └── integration/
        └── test_platform.py                 # grupo platform; US1 cen. 1–2 no perfil test; pulado sem ai_core
```

**Structure Decision**: layout de pack do ADR-012 e do design.md — `pack.py` como composition root, políticas puras em
`context/` e `prompts/`, sem `ports.py`/`adapters/` (a 101 não faz I/O). As pastas `rag/`, `validators/` e `eval/` do
design.md nascem com as specs 102–105.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 002 (core) | Nada a mudar: o pack é descoberto por `EntryPointPackSource`; `packs.yaml` aceita só `enabled` na Fase 4 |
| 003 (core) | Na Fase 4, `packs: [scouting]` sem `flow` roda no `chat`; `flow: rag_first` deixa o Assistant indisponível até a Fase 5 |
| 002 US5 (instalação) | O pack se instala da tag/commit do `ai-scouting` (privado): o build precisa de leitura no `ai-scouting` e no `agentic-app` |
| 103 (Fase 5) | Consome `retrieval_filters` no formato de [contracts/retrieval-filters.md](contracts/retrieval-filters.md); a vigência é intervalo, e `previous_version` mira a versão imediatamente substituída |
| 104 (esqueleto, Fase 4) | Os validators entram pelo `pack.py` (toque declarado no plano da 104); `include_superseded` na fatia é o sinal de consulta histórica |
| 105 (Fase 6) | Mede a derivação chamando `derive_context` (ou `prepare_context`) com o léxico do pack e dia de referência fixo |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- I: o domínio inteiro está no `ai-scouting`; o `agentic-app` só ganha documentação e o ponteiro.
- V: a tabela de derivação do data-model é toda resolvida por regra e léxico; nenhum caminho consulta modelo.
- VII: o data-model fixa o resultado de cada ambiguidade (ramo ambíguo ou múltiplo → sem filtro; ano solto → sem
  período; vários períodos → o primeiro).
- IX: o contrato do prompt exige o bloco "sem documentos consultados" com as quatro proibições/recomendações da FR-011.
- XIII: continua sem porta; a única infraestrutura tocada é empacotamento e CI.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Grupo `platform` com o `ai-core` no repositório do pack (R9) | a US1 exige provar carga e prompt na plataforma real, e o core não pode ter teste de escotismo (princípio I) | só quickstart manual deixaria a US1 sem teste automatizado; pôr o teste no core violaria o princípio I |
| Deploy key do `agentic-app` na CI do `ai-scouting` (R14) | os contratos vêm do `agentic-app`, privado (ADR-021) | token pessoal daria acesso a todos os repositórios da conta |
| Dia de referência em UTC−03:00 fixo (R5) | o core entrega UTC; vigência de documento brasileiro é por dia local | `ZoneInfo` exigiria `tzdata`, dependência além dos contratos (FR-001) |
