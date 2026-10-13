# Implementation Plan: Conjunto dourado e calibração do domínio escoteiro (Fase 6 — infraestrutura e semente)

**Branch**: `105-scouting-evaluation` | **Date**: 2026-10-13 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/105-scouting-evaluation/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/105-scouting-evaluation/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-012, ADR-013, ADR-014, ADR-021, ADR-027; as três clarificações de
2026-10-13; o harness da 009 na tag `v0.3.0` (formato do conjunto, CLI `ai-core eval run|compare`, `EvalMetric` dos
contratos 0.1.2, perfil `test` com o provider `ollama` simulado); e, no `ai-scouting`, a derivação da 101
(`derive_context`, `reference_day`, léxico), os status da 102 (`ValidityStatus`), a flag `non_current_source` da 104, o
catálogo `corpus/corpus.yaml` e a CI. Nenhum ADR novo.

## Summary

Entregar, no `ai-scouting`, a infraestrutura de avaliação do domínio sobre um **conjunto semente provisório**: três
métricas de domínio puras (`context_accuracy`, `current_document_rate`, `validity_notice_rate`) publicadas pelo hook
`eval_metrics` (ADR-027); o conjunto semente de 8 a 12 perguntas tiradas do corpus, no formato da 009, validado contra
o catálogo do corpus e o léxico da 101; os arquivos de avaliação (`eval/packs.yaml`, `eval/assistants.yaml`) e a linha
de base da semente; e um workflow `eval` que, quando mudam corpus, RAG, prompt, derivação, pack ou dependências, ingere
o corpus real num Qdrant de serviço com o e5 em cache e roda `ai-core eval run` no perfil `test`, barrando só por
métrica determinística. O pack sobe para 0.3.0 (contratos `>=0.1.2`, tag `v0.3.0`). Calibração, embedding e modelo
local (US3–US5) esperam a curadoria (R11).

## Technical Context

**Language/Version**: Python 3.12+ no pacote (R3 da 101); a avaliação e a suíte `platform` em 3.14 (o core)

**Primary Dependencies**: `ai-core-contracts>=0.1.2,<0.2` (`ai_core_contracts.eval`); `pyyaml` (já dependência, só nos
testes que leem o conjunto); no grupo `platform`, `ai-core` da tag `v0.3.0` (harness e CLI). Nada novo

**Storage**: arquivos versionados em `ai-scouting/eval/` (YAML e o relatório JSON da linha de base); Qdrant de serviço
na CI, efêmero

**Testing**: pytest — unitários das métricas com `EvalItem`/`EvalObservation` construídos à mão; validação do
conjunto contra `corpus/corpus.yaml` e o léxico na suíte padrão; no grupo `platform`, rodadas de `ai-core eval run` (o
comando, em subprocesso) sobre o Qdrant embutido com o embedder de teste, inclusive com a semente (nenhum item inválido)

**Target Platform**: a CI do `ai-scouting` (GitHub Actions) e a máquina do mantenedor; a imagem do `agentic-deploy`
passa a ter o core `v0.3.0` (R9)

**Project Type**: submódulo de um pack de domínio (métricas puras) + dados e CI

**Performance Goals**: o job `eval` em até 10 minutos por execução — ingestão do corpus (413 trechos, e5 na CPU) e 8–12 itens com o
gerador simulado; sem modelo pago nem juiz

**Constraints**: métricas puras e determinísticas onde declaram ser (sem relógio, sem I/O); o pack continua sem
importar o core; nenhuma calibração sobre a semente (FR-001); só métricas determinísticas barram (FR-005)

**Scale/Scope**: `eval/` no pacote com 2 módulos; 4 arquivos de dados; 1 workflow; ~4 arquivos de teste; toques no
`pack.py`, `pyproject.toml`, `.gitignore`, `tests/test_purity.py`; o `agentic-deploy` fica para a 002

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Tudo no `ai-scouting`; o core só vê `EvalMetric` e `extra` opaco (ADR-027) |
| II. Seams | ✅ | Consome o contrato 001 (`EvalMetric`, `EvalItem`, `EvalObservation`) e o formato e a CLI da 009 |
| V. Determinismo | ✅ | `context_accuracy` e `current_document_rate` não dependem do texto gerado; só elas e as de recuperação barram |
| VII. Falha fechada | ✅ | Status vazio conta como não vigente (como na 104); conjunto que referencia documento fora do corpus falha o teste |
| IX. Proveniência e vigência | ✅ | Todo item fixa `reference_time` (FR-006); vigência medida sobre o que chegou ao modelo |
| X. Medir antes de calibrar | ✅ | Linha de base antes de qualquer calibração (SC-001); nenhuma decisão sobre a semente (R1, R11) |
| XII. Simplicidade | ✅ | Sem porta, sem configuração nova; métricas que o design pede, nenhuma a mais |
| XIII. Portas e adapters | ✅ | Núcleo funcional puro; a execução é do harness da 009 (design.md "Portas e adapters") |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-scouting/src/ai_scouting/eval/**`, `ai-scouting/eval/**`,
  `ai-scouting/.github/workflows/eval.yml` e testes novos; toques declarados: `pack.py` (101: declara as métricas e
  sobe a versão), `pyproject.toml` (versão, faixa dos contratos, tag, import-linter), `.gitignore`,
  `tests/test_purity.py`; o `agentic-deploy` (`CORE_REF` e o pin do pack) muda numa passada de encaixe da 002, depois
  desta (R9)
- [x] Every consumed seam is listed with its owner spec — contrato 001 (`EvalMetric`, `EvalItem`, `EvalEvidence`,
  `EvalObservation`, `EvalChunk`, `PackContext`); 009: formato do conjunto e do relatório, `ai-core eval run`; 011: perfil
  `test`, `AI_CORE_PACKS_FILE`/`AI_CORE_ASSISTANTS_FILE`; dentro do pack, `derive_context`/`reference_day` (101) e
  `ValidityStatus` do `rag/index/api.py` (102)
- [x] Every seam this module exposes has a conformance test planned — as métricas
  ([domain-metrics.md](contracts/domain-metrics.md)) pela conformidade da 001 (`eval_metric.*`) e por testes de
  tabela; o conjunto semente ([golden-set.md](contracts/golden-set.md)) pela validação contra o corpus
- [x] No seam changes — nenhum; o hook `eval_metrics` e o formato já existem (ADR-027, 009)
- [x] Import boundaries (import-linter) cover the new code — `eval` como camada entre `pack` e os demais, e nas fontes
  dos contratos de modelo/MCP e do seam do índice (R10)

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` (any collapsed part is
  justified) — núcleo funcional puro, sem I/O: só as políticas (design.md "Portas e adapters"); a superfície são as
  três classes, compostas pelo `pack.py`
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — stdlib, contratos e o
  próprio pack
- [x] Other modules are imported only through their `api.py` — do índice, só `rag/index/api.py`; da derivação, a função
  pública de `context/`
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — não há; o dia
  vem do `reference_time` do item
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — nenhuma porta
- [x] Every secondary port has an in-memory adapter and a conformance suite — N/A
- [x] Services and adapters of other modules are instantiated only in the composition root — as métricas são
  instanciadas no `pack.py`; o harness e a plataforma, pela CLI da 011

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/105-scouting-evaluation/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── domain-metrics.md      # as três métricas: definição, casos de aceite
│   └── golden-set.md          # regras de domínio do conjunto e da validação contra o corpus
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-scouting/
├── pyproject.toml                         # 0.3.0; ai-core-contracts>=0.1.2,<0.2; tag v0.3.0; import-linter (R9, R10)
├── .gitignore                             # .cache/ (o e5 da avaliação)
├── .github/workflows/eval.yml             # job eval com filtro de caminhos (R7)
├── eval/
│   ├── golden.yaml                        # conjunto semente provisório (R4)
│   ├── packs.yaml                         # o scouting da avaliação (R6)
│   ├── assistants.yaml                    # o Assistant scouting, ACL com svc:eval (R6)
│   └── baseline.json                      # linha de base da semente (R8)
├── src/ai_scouting/
│   ├── pack.py                            # eval_metrics(ctx) → as três métricas
│   └── eval/
│       ├── __init__.py                    # reexporta as métricas
│       └── metrics.py                     # ContextAccuracy, CurrentDocumentRate, ValidityNoticeRate — puro
└── tests/
    ├── eval/
    │   ├── test_metrics.py                # tabela de casos por métrica
    │   └── test_golden.py                 # o conjunto contra corpus.yaml e o léxico (suíte padrão)
    ├── integration/test_eval.py           # grupo platform: `ai-core eval run` em subprocesso
    ├── test_conformance.py                # já roda a conformidade da 001, que passa a cobrir eval_metric.*
    └── test_purity.py                     # passa a varrer eval/

agentic-deploy/                            # depois, passada de encaixe da 002 (R9)
└── Dockerfile                             # CORE_REF v0.3.0; PACKS no commit novo do ai-scouting
```

**Structure Decision**: `src/ai_scouting/eval/` como no Module Boundary da spec, só com políticas puras; os dados de
avaliação em `ai-scouting/eval/`, fora do pacote (não são instalados); a execução é do harness da 009.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| Harness (009) | O pack declara `scouting:context_accuracy`, `scouting:current_document_rate` (determinísticas) e `scouting:validity_notice_rate`; `extra.context` e `extra.provisional` são opacos para o core |
| Curadoria (depois do desenvolvimento) | Troca o conteúdo de `eval/golden.yaml` (30–50 perguntas), tira `provisional`, regrava `eval/baseline.json` com `--update-baseline`; formato, validação e CI ficam |
| `agentic-deploy` (002) | Passada de encaixe: `CORE_REF=v0.3.0` e o pack 0.3.0, para `ai-core eval run` existir na imagem |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- V: as duas métricas que barram leem só a pergunta, a data e os trechos entregues — nunca o texto gerado.
- X: a linha de base da semente fica registrada; nenhum parâmetro do RAG muda nesta passada.
- XII: nenhuma porta, nenhuma variável de ambiente nova; o workflow reaproveita a CLI da 102 e da 009.

## Complexity Tracking

Nenhuma violação.
