# Implementation Plan: Pack genérico de referência (`ai-generic`)

**Branch**: `010-core-generic-pack` | **Date**: 2026-09-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/010-core-generic-pack/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/010-core-generic-pack/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md) (atualizado em 2026-09-17), ADR-004, ADR-012, ADR-014; contratos da 001 e Pack
Runtime da 002 já implementados; consumidores conferidos: 002 (carga), 011 (perfil de teste), 1xx (o pack é o exemplo
que o `ai-scouting` copia). Duas linhas do design.md foram superadas pelas clarificações e atualizadas no próprio
arquivo, com nota de origem: a pasta (`packages/generic/`, não `packs/generic/` — [research.md](research.md) R1) e a
dependência de contratos (faixa derivada em vez de "sem faixa" — R2). Nenhuma outra divergência; nenhum ADR novo.

## Summary

Criar a distribuição `ai-generic` em `ai-core/packages/generic/`: um pack com o formato exato de um pack externo —
`pyproject.toml` próprio, entry point `ai_core.packs`, dependência só de `ai-core-contracts` pela faixa derivada — que
oferece, na v1, prompt de sistema de uso geral, a tool nativa determinística `calculate` e o validator
`non_empty_answer`, com manifest mínimo. O pack passa na suíte de conformidade publicada pelos contratos (inclusive as
etapas de imports e de distribuição) e é carregado pelo Pack Runtime nos testes de integração do core, pelo mecanismo
de entry point, sem nenhum caso especial. Escopo da Fase 1: **US1**. A US2 (Assistant genérico com MCP no flow
`agentic`) é Fase 3, junto da 007 e da decisão da FR-005.

## Technical Context

**Language/Version**: Python 3.12+ na distribuição do pack (`requires-python = ">=3.12"`, o piso dos contratos — R3);
a suíte roda em 3.14 dentro do workspace e em 3.12 no ambiente limpo

**Primary Dependencies**: `ai-core-contracts>=0.1,<0.2` com fonte do workspace (R2). Nenhuma outra — nem de runtime,
nem de teste além de `pytest` (os testes do pack não usam `pytest-asyncio`, R4)

**Storage**: N/A — o pack não tem estado entre execuções

**Testing**: pytest; suíte de conformidade de pack da 001 (`assert_pack_conforms`) nos testes do pack; testes puros da
aritmética e do validator; teste de integração no core carregando o pack por entry point (R8); job de ambiente limpo
em 3.12 (R4)

**Target Platform**: processo do core na imagem Linux ARM64; o pack também precisa importar num ambiente que tenha só
os contratos

**Project Type**: distribuição Python de pack (plug-in do microkernel), descoberta por entry point

**Performance Goals**: hooks de catálogo e `calculate` em tempo desprezível diante de uma chamada de modelo —
`calculate` é análise de AST sobre expressão curta, sem I/O; a carga do pack não faz nada além de instanciar

**Constraints**: zero import do core, verificado nas duas direções (R9); nenhum I/O, nenhum acesso a relógio, a
aleatoriedade ou a segredos — logo nenhuma porta secundária (princípio XIII); nada de domínio (princípio I); argumentos
de tool são conteúdo não-confiável (princípio VI, R6)

**Scale/Scope**: 1 distribuição, ~5 módulos (`pack.py`, `prompts/`, `tools/arithmetic.py`, `validators/answer.py`),
3 capacidades publicadas

Nenhum `NEEDS CLARIFICATION` no escopo da Fase 1. A FR-005 permanece aberta de propósito: é decisão da Fase 3, quando a
US2 e a 007 existirem, e não afeta nenhuma tarefa deste plano.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | O pack não tem domínio: prompt genérico, aritmética, resposta não vazia. E o core não ganha nada de pack: a única mudança em `ai_core` é um teste |
| II. Seams | ✅ | O pack consome apenas a API pública de `ai_core_contracts` (001) e expõe-se pelo entry point; não conhece Pack Runtime, motor, HTTP nem Assistants |
| III. O core orquestra | ✅ | O pack registra capacidades e não constrói grafo; não declara flow preferido (R5) |
| IV. Assistant é a fronteira | ✅ | O pack não decide o que uma execução enxerga; quem habilita é o operador (`packs.yaml`) e quem compõe é o Assistant |
| V. Determinismo | ✅ | `calculate` e o validator são funções puras, sem LLM; a conformidade verifica determinismo chamando cada hook duas vezes |
| VI. Conteúdo externo | ✅ | Os argumentos da tool vêm do modelo e são tratados como dado: AST com allowlist, sem `eval`, erro em vez de exceção (R6) |
| VII. Falha fechada | ✅ | Expressão inválida devolve erro explícito; um pack que falhasse na carga já é tratado pela 002 (`error` com a etapa) |
| VIII. Modelos por papel | N/A | O pack não fala com modelos |
| IX. Proveniência | N/A | Sem retrieval na v1 |
| X. Medir antes de calibrar | N/A | Nenhum número de RAG ou de modelo |
| XI. Streaming | N/A | O pack não produz resposta |
| XII. Simplicidade | ✅ | Manifest mínimo, sem `config_schema` inventado, sem `prepare_context` inerte, sem script de teste próprio (R4, R5) |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/generic/**`; fora dele apenas:
  configuração do workspace (`ai-core/pyproject.toml`, `uv.lock`), um teste de integração em
  `ai-core/packages/core/tests/packs/integration/`, o workflow novo `generic.yml` e o gatilho novo do `core.yml`
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — contrato de pack
  (001): `PackBase`, `PackManifest`, `PackContext`, `ToolSpec`, `ToolInvocation`, `AnswerValidator`,
  `ValidationResult`, `ValidatorContext`, `TurnView`, `JSONValue`, e o kit de testes `ai_core_contracts.testing`
- [x] Every seam this module exposes has a conformance test planned — o pack não expõe seam Python; o que ele expõe é
  o entry point e as capacidades, cobertos pela suíte de conformidade da 001 (nos testes do pack) e pelo teste de
  carga real (nos testes do core)
- [x] No seam changes — nenhum. O contrato 001 é consumido como está; nenhuma spec consumidora muda
- [x] Import boundaries (import-linter) cover the new code — três contratos novos (R9), nas duas direções

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` (any collapsed part is
  justified) — num pack, a organização equivalente é `pack.py` como composition root, com as políticas puras em
  `tools/` e `validators/` (R7); `ports.py` e `adapters/` são omitidos porque o pack não faz I/O, como o princípio
  XIII permite
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — o pack inteiro importa
  apenas stdlib (`ast`, `asyncio` nos testes) e `ai_core_contracts`; o contrato de lint proíbe frameworks (R9)
- [x] Other modules are imported only through their `api.py` — o pack importa só `ai_core_contracts` e **nada** de
  `ai_core`, nas duas direções verificadas no CI
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — não há I/O,
  tempo, aleatoriedade, segredo nem trace: a tool é pura e, se precisasse da data, usaria o `reference_time` da
  invocação, nunca o relógio (ADR-013)
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — nenhuma porta é criada; criar uma para
  aritmética seria porta para regra pura, proibida pelo princípio XIII
- [x] Every secondary port has an in-memory adapter and a conformance suite — N/A (nenhuma porta)
- [x] Services and adapters of other modules are instantiated only in the composition root — o pack não instancia
  nada de outro módulo; quem instancia o `PackRuntime` é a 011 (e os testes do core)

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/010-core-generic-pack/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── generic-pack.md       # capacidades publicadas: prompt, tool calculate, validator
│   └── packaging.md          # distribuição, entry point, faixa de contratos, piso de Python
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
.github/workflows/
├── core.yml                          # ajuste: gatilho também em ai-core/packages/generic/** (R10)
└── generic.yml                       # novo: lint, testes, ambiente limpo 3.12, fronteiras (R10)

ai-core/
├── pyproject.toml                    # members já cobre packages/*; dev += ai-generic (R8); testpaths, mypy,
│                                     # ruff e três contratos de import-linter (R9, R11)
├── uv.lock                           # regerado por uv sync
└── packages/
    ├── core/
    │   └── tests/packs/integration/
    │       └── test_packs_generic_entry_point.py   # carga real do pack pelo Pack Runtime (R8, SC-002)
    └── generic/                      # distribuição ai-generic (nasce aqui — R1)
        ├── pyproject.toml            # name ai-generic 0.1.0; requires-python >=3.12; ai-core-contracts>=0.1,<0.2
        │                             # + [tool.uv.sources] workspace; entry point ai_core.packs (R2, R3, R12)
        ├── README.md                 # uma linha: pack de referência e de uso geral
        ├── src/ai_generic/
        │   ├── __init__.py           # docstring; consumidores usam o entry point, não importam o módulo
        │   ├── py.typed
        │   ├── pack.py               # GenericPack: identidade, manifest, os três hooks — composition root (R7)
        │   ├── prompts/
        │   │   ├── __init__.py       # reexporta SYSTEM_PROMPT
        │   │   └── general.py        # SYSTEM_PROMPT: constante Python, sem domínio (não é arquivo de dados)
        │   ├── tools/
        │   │   ├── __init__.py
        │   │   └── arithmetic.py     # evaluate() puro (AST com allowlist) + handler assíncrono + ToolSpec (R6)
        │   └── validators/
        │       ├── __init__.py
        │       └── answer.py         # NonEmptyAnswer: ValidationResult com issues e flags
        └── tests/
            ├── test_conformance.py   # assert_pack_conforms (todas as etapas, inclusive distribuição e imports)
            ├── test_pack.py          # identidade, manifest mínimo, catálogo, consistência de versão (R12)
            ├── test_arithmetic.py    # aritmética pura: casos válidos, recusas, limites, determinismo (R6)
            └── test_validator.py     # resposta vazia, só espaços, resposta válida
```

**Structure Decision**: layout de pack do ADR-012 — `pack.py` como composition root, políticas puras em `tools/` e
`validators/`, sem `ports.py`/`adapters/` (R7). A pasta é `packages/generic/` (R1), dentro do `members` que já existe.
O pack não tem `api.py`: a superfície pública de um pack é o entry point, e quem a lê é o Pack Runtime (002).

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 002 (Fase 1) | Nada a mudar no código: o pack é descoberto por `EntryPointPackSource` como qualquer outro. O teste de integração da carga real passa a viver nos testes do core, com o pack como dependência de desenvolvimento (R8) |
| 011 (Fase 1) | O perfil de teste pode habilitar `generic` em `packs.yaml` sem configuração (`enabled: true` e nada mais — não há `config_schema`); o pack não declara flow preferido, então o Assistant escolhe |
| 003 (Fase 2) | `packs: [generic]` num Assistant não exige coleção nem MCP; `compose(["generic"])` basta |
| 004 (Fase 3) | A tool `calculate` é `kind="native"` com handler assíncrono; o namespace `generic.calculate` é aplicado pelo core |
| 1xx (Fase 4) | Este pack é o exemplo a copiar: faixa derivada + fonte do workspace enquanto no repositório, piso de Python dos contratos, suíte de conformidade nos próprios testes, zero import do core |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- I: revisado o texto do prompt e o nome de cada capacidade — nenhum termo de domínio; `calculate` e
  `non_empty_answer` valem para qualquer instalação.
- VI: o contrato da tool define a resposta para cada entrada recusada, então nenhuma entrada do modelo vira exceção ou
  execução de código (contracts/generic-pack.md §Tool `calculate`).
- XII: o data-model não introduziu entidade nova além do que os contratos da 001 já definem — o pack só instancia
  `PackManifest`, `ToolSpec`, `ValidationResult`.
- XIII: continua sem porta; a única infraestrutura tocada é empacotamento e CI, fora do código do pack.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Interpretador de AST em `tools/arithmetic.py` (R6) | a tool precisa ser útil e não pode executar código vindo do modelo | `eval` com `globals` vazio é contornável por atributos; biblioteca externa daria ao pack de referência uma dependência que nenhum pack precisa |
| `ai-generic` no grupo dev da raiz (R8) | o teste que prova SC-002 roda na suíte do core e precisa do pack instalado | instalar o pack ad-hoc no teste tornaria o próprio teste um caso especial, exatamente o que SC-002 proíbe |
| Job de ambiente limpo inline no `generic.yml` (R4) | o *Independent Test* da US1 é instalar o pack só com os contratos | parametrizar a ferramenta da 001 mexeria em módulo alheio; script próprio duplicaria infraestrutura de teste dentro do pack |

---

# Fase 3 (2026-10-07): US2 — Assistant genérico com MCP; FR-005, FR-007 e FR-008

Insumos: as três clarificações de 2026-10-07; [design.md](design.md) (a "Questão em aberto" ganhou nota de
fechamento, com origem); arch-v1 Parte IX; ADR-012 e
[ADR-019](../../docs/adr/ADR-019-papeis-por-flow-no-seam-execution-engine.md); consumidores conferidos no código —
002 (`PackHooks.system_prompts`), 003 (`effective_flow` e papéis exigidos por flow), 004 (catálogo com namespace,
resultado cercado), 005 (prompts de pack só na geração), 007 (servidor por alias) e 011 (perfil `test` com trocas de
porta). Decisões em [research.md](research.md) R13–R21. **Sem divergência do `design.md`, sem ADR novo, sem mudança de
seam.** A linha "Depois desta fase" do [tasks.md](tasks.md) que previa `preferred_flow` "se o pack continuar sendo
pack" fica superada pela clarificação 2 (R15).

## Summary (Fase 3)

O `ai-generic` continua pack (FR-005 decidida e permanente) e continua sem flow preferido (FR-007): o Assistant
genérico com MCP é uma declaração — `flow: agentic`, `packs: [generic]`, `mcp: [<alias>]`, `generation` e `controller`
— sobre capacidades que já existem. O único código que muda é o texto do prompt: o parágrafo que mandava "usar a
ferramenta de cálculo" (instrução que nem a geração do `agentic` nem o `chat` podem cumprir) dá lugar a um parágrafo
neutro quanto ao flow sobre resultados de ferramentas (FR-008). A US2 é provada no core, no perfil `test` e sem rede:
pack e MCP no mesmo catálogo do controller, e a geração recebendo o prompt do pack e o resultado cercado do MCP; com
Ollama disponível, uma integração opcional prova que o modelo usa o resultado.

## Technical Context (Fase 3)

**Dependências**: nenhuma nova. **Storage**: N/A. **Testing**: pytest; no pack, propriedades textuais do prompt
(`tests/test_pack.py`); no core, integração no perfil `test` com `ScriptedController`, `ScriptedProvider` e
`ScriptedMcpTransport` (R18) e integração opcional com Ollama, pulada sem `OLLAMA_BASE_URL` (R19).
**Constraints**: zero import do core no pack (SC-001) e nenhuma linha em `ai-core/packages/core/src/` (SC-002, R21);
versão `0.1.0` mantida (R17); nada de domínio no prompt (princípio I).
**Scale/Scope**: `prompts/general.py` (um parágrafo), `tests/test_pack.py`; no core, dois arquivos de teste e a
descrição da marca `us2`.

## Constitution Check (Fase 3)

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | O parágrafo novo fala de "ferramentas" e "resultados", sem domínio; o core não muda |
| II. Seams | ✅ | O pack só consome o contrato 001; o teste do core lê o prompt pelo seam `PackHooks` (002), não importa `ai_generic` (R18) |
| III. O core orquestra | ✅ | O pack não declara flow nem conhece MCP; o loop é do motor (005), o catálogo da 004 (R13, R15) |
| IV. Assistant é a fronteira | ✅ | Flow, MCP e modelos ficam na declaração do Assistant; o pack não amplia o que uma execução enxerga |
| V. Determinismo | ✅ | Prompt é constante; `calculate` e o validator não mudam |
| VI. Conteúdo externo | ✅ | "Dado, nunca instrução" permanece; o resultado do MCP chega cercado (004) e o prompt pede para apresentá-lo, não para obedecê-lo |
| VII. Falha fechada | ✅ | O prompt pede para dizer que a ferramenta falhou em vez de supor o valor; Assistant `agentic` sem `controller` continua indisponível (003) |
| VIII. Modelos por papel | ✅ | O exemplo declara `generation` e `controller` explicitamente (R15, R20) |
| XII. Simplicidade | ✅ | Sem flow preferido, sem arquivo de exemplo, sem dublê de eco, sem bump de versão (R15, R17, R18, R20) |
| XIII. Portas e adapters | ✅ | Nenhuma porta: o pack continua sem I/O |

**Module boundary gate (Fase 3)**: `ai-core/packages/generic/**` (prompt e testes do pack); fora dele, só testes do
core em `ai-core/packages/core/tests/bootstrap/integration/` (R18, R19) e a descrição da marca `us2` em
`ai-core/pyproject.toml` (R21). Nenhum seam muda; nenhuma spec consumidora muda; import-linter sem contrato novo.
**Resultado**: PASS.

**Ports & adapters gate (Fase 3)**: nenhuma porta nova (o pack não faz I/O); o teste do core monta a plataforma pela
composition root (`platform(profile="test", overrides=…)`), sem instanciar serviço de outro módulo à mão. **Resultado**:
PASS.

## Project Structure (Fase 3)

```text
ai-core/packages/generic/
├── src/ai_generic/prompts/general.py     # "Sobre cálculos" → "Sobre resultados de ferramentas" (FR-008, R16)
└── tests/test_pack.py                    # propriedades textuais da FR-008; manifest sem preferred_flow (R15, R16)

ai-core/packages/core/tests/bootstrap/integration/
├── test_generic_agentic_mcp.py           # NOVO: US2 no perfil test, sem rede (R18)
└── test_generic_agentic_real.py          # NOVO: US2 com Ollama, opcional (R19)

ai-core/pyproject.toml                    # marca us2 += "; 010 US2 — Assistant genérico com MCP" (R21)
specs/010-core-generic-pack/design.md     # nota fechando a "Questão em aberto" (R14)
```

## Seam Notes for Consumers (Fase 3)

| Consumidor | O que precisa saber |
|---|---|
| 003 | Nada a mudar: o pack continua sem `preferred_flow`, então `packs: [generic]` sem `flow` segue no `chat`; o Assistant genérico declara `flow: agentic` e `controller` |
| 005 | Nada a mudar: o prompt do pack continua indo só para a geração; o texto novo pressupõe isso (R16) |
| 011 | Nada a mudar: o perfil `test` já habilita `generic` e aceita trocas de `providers` e `mcp_transports` |
| Operador | O "agente genérico" é a declaração do quickstart, "Fase 3" §10; o pack não precisa de configuração |
| 1xx (Fase 4) | Continua o exemplo a copiar; prompt de pack não deve mandar chamar ferramentas — no `agentic`, ele só chega à geração |

## Complexity Tracking (Fase 3)

Nenhuma violação; nenhuma complexidade nova.

## Constitution Check — pós-design (Fase 3)

Reavaliado com a seção "Fase 3" de [data-model.md](data-model.md), de [contracts/generic-pack.md](contracts/generic-pack.md)
e de [quickstart.md](quickstart.md): **PASS**.

- I: o texto exato do parágrafo novo está no contrato e não tem termo de domínio, de organização nem de produto.
- II: a prova da US2 usa só seams e a composition root; o contrato da US2 nomeia o seam de onde vem o prompt.
- VI: o parágrafo novo pede para apresentar o resultado, e o seguinte, mantido, diz que o resultado é dado — as duas
  regras convivem sem conflito.
- XII: o data-model não ganhou entidade; a declaração do Assistant genérico é referência ao formato da 003.
