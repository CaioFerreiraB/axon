# Implementation Plan: Citações, proveniência e aviso de vigência (Fase 4 — esqueleto)

**Branch**: `104-scouting-citations` | **Date**: 2026-10-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/104-scouting-citations/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/104-scouting-citations/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-007, ADR-012, ADR-021; as três clarificações de 2026-10-07; o contrato de
validator da 001 na tag `contracts-v0.1.0`; o `ai-scouting` da 101 (Fase 4); e, no core, como o resultado é aplicado —
`PackRuntime.validate` encadeia resposta e citações, o motor transforma `issues` em `notice` e soma `flags`, e a API
devolve a resposta reescrita só sem streaming (research R11). A sintaxe `[[id]]`, que o design.md deixou como
proposta, é adotada (R3). Nenhum ADR novo.

## Summary

Implementar, no `ai-scouting`, os validators `citation_integrity` e `validity_notice` como núcleo funcional puro: o
primeiro extrai `[[id]]` da resposta, mantém só o que esteve no `generation_context`, renumera as válidas como `[n]`,
devolve a proveniência de cada uma e marca a resposta como não fundamentada quando nada sobra; o segundo garante o
aviso para toda citação não vigente ou de vigência não confirmada, sem duplicar o que o modelo já disse. Na Fase 4 eles
são testados com Turn Views sintéticas e **não** são publicados pelo pack — a publicação é da Fase 5, com o retriever e
a sintaxe nas instruções.

## Technical Context

**Language/Version**: Python 3.12+ (o pacote do `ai-scouting`, R3 da 101); testes em 3.12 e 3.14

**Primary Dependencies**: nenhuma nova — só stdlib (`re`, `unicodedata`, `dataclasses`) e `ai-core-contracts`

**Storage**: N/A

**Testing**: pytest com `turn_view`, `chunk` e `validator_context` do kit da 001; `asyncio.run` para os hooks

**Target Platform**: o processo do core, quando publicado (Fase 5); na Fase 4, só a suíte do pack

**Project Type**: submódulo de um pack de domínio (validators puros)

**Performance Goals**: regex e dicionário sobre uma resposta e algumas dezenas de trechos — desprezível diante da
geração (SC-003)

**Constraints**: determinístico, sem modelo (FR-006); fonte da verdade `generation_context` (ADR-007); não publicado na
Fase 4 (FR-008)

**Scale/Scope**: `validators/` com 4 módulos; 4 arquivos de teste novos; dois ajustes no `pyproject.toml` e um em
`tests/test_purity.py`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Tudo no `ai-scouting`; nenhuma linha do core |
| II. Seams | ✅ | Só o contrato 001 (`AnswerValidator`, `TurnView`, `Chunk`, `Citation`) |
| V. Determinismo | ✅ | Citação verificada mecanicamente no caminho da requisição; julgamento por LLM fica no harness (ADR-007) |
| VI. Conteúdo externo | ✅ | O texto do modelo é tratado como dado: só marcadores que casam com o contexto viram citação |
| VII. Falha fechada | ✅ | Vigência desconhecida avisa; nenhuma citação válida marca a resposta (R5, R6) |
| IX. Proveniência e vigência | ✅ | Cada citação traz os seis campos; fonte não vigente sempre avisada |
| XII. Simplicidade | ✅ | Sem porta, sem configuração; não publicado antes de ter efeito (R1) |
| XIII. Portas e adapters | ✅ | Núcleo funcional puro (design.md "Portas e adapters") |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-scouting/src/ai_scouting/validators/**` e testes novos;
  toques declarados: `[tool.importlinter]` do `ai-scouting/pyproject.toml` e `tests/test_purity.py` (R8); o `pack.py`
  (101) não muda na Fase 4
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — contrato 001:
  `AnswerValidator`, `ValidationResult`, `ValidatorContext`, `TurnView`, `Chunk`, `Citation`, kit de testes
- [x] Every seam this module exposes has a conformance test planned — os dois validators (contrato
  [validators.md](contracts/validators.md)) e a sintaxe para a 101 ([citation-syntax.md](contracts/citation-syntax.md))
- [x] No seam changes — nenhum
- [x] Import boundaries (import-linter) cover the new code — `validators` na camada independente e no contrato de
  modelo e MCP (R8)

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` (any collapsed part is
  justified) — núcleo funcional puro, sem I/O: só as políticas (design.md); a superfície são as duas classes
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — stdlib e contratos
- [x] Other modules are imported only through their `api.py` — só `ai_core_contracts`; nada de `context/` (R8)
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — não há
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — nenhuma porta
- [x] Every secondary port has an in-memory adapter and a conformance suite — N/A
- [x] Services and adapters of other modules are instantiated only in the composition root — os validators serão
  instanciados pelo `pack.py` (Fase 5)

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/104-scouting-citations/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── validators.md          # comportamento, textos, registros e casos de aceite
│   └── citation-syntax.md     # o que as instruções da 101 ensinam na Fase 5
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-scouting/
├── pyproject.toml                         # [tool.importlinter]: validators na camada e no contrato de modelo/MCP (R8)
├── src/ai_scouting/validators/
│   ├── __init__.py                        # reexporta os dois validators; ordem documentada
│   ├── _text.py                           # fold: minúsculas, sem acento (comparações)
│   ├── citations.py                       # MARKER, key, extract, rewrite (numeração e remoção) — puro
│   ├── integrity.py                       # CitationIntegrityValidator + UNGROUNDED_NOTICE
│   └── notice.py                          # ValidityNoticeValidator + NON_CURRENT_NOTICE, UNCONFIRMED_NOTICE
└── tests/
    ├── test_citations.py
    ├── test_integrity.py
    ├── test_notice.py
    ├── test_validators_chain.py
    └── test_purity.py                     # passa a varrer validators/
```

**Structure Decision**: `validators/` como no design.md, independente de `context/` e `prompts/`; sem porta.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 101 (Fase 5) | Publicar em `validators()` na ordem `CitationIntegrityValidator()`, `ValidityNoticeValidator()`; ensinar a sintaxe de [citation-syntax.md](contracts/citation-syntax.md) nas instruções |
| Flow `rag_first` (005, Fase 5) | Rotular cada trecho entregue à geração com o `chunk_id`; **pendência**: com streaming, a resposta reescrita pelos validators não chega ao cliente (R11) |
| 102 (Fase 5) | Os status de vigência são lidos dobrados (`vigente`, `revogado`, `substituido`, `rascunho`); qualquer outro conta como não confirmado |
| 105 (Fase 6) | SC-001 e SC-002 são medidos no harness com estes validators publicados |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- V e IX: as tabelas de resultado cobrem toda combinação de validade e status, sem chamada de modelo.
- VII: vigência desconhecida e resposta sem citação têm resultado explícito, nunca silêncio.
- XII: nenhuma configuração, nenhuma porta; textos fixos.

## Complexity Tracking

> Nenhuma violação.

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Detecção de aviso já presente por frase com `[n]` e marca de status (R6) | US3 cen. 2: não duplicar o aviso que o modelo já deu | só a linha padrão exata duplicaria; procurar o nome do documento em qualquer frase esconderia faltas |
