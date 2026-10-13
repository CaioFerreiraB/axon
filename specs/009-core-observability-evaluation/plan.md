# Implementation Plan: Trace por requisição (Trace Sink e consulta)

**Branch**: `009-core-observability-evaluation` | **Date**: 2026-09-17 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/009-core-observability-evaluation/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/009-core-observability-evaluation/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md) (atualizado em 2026-09-17), ADR-007, ADR-012, ADR-013; contratos da 001, Pack
Runtime da 002 e pack `ai-generic` da 010 já implementados; consumidores conferidos: 005 e 006 (emitem na Fase 1), 004
(Fase 3), 008 (consulta, Fase 2), 011 (monta e injeta). A candidata do ADR-013 — API do OpenTelemetry **como porta** —
foi rejeitada na clarificação e a linha correspondente do `design.md` foi atualizada com o motivo: o próprio ADR
autoriza outra forma desde que a semântica do seam se mantenha, então não há ADR novo
([research.md](research.md) R1). Nenhuma outra divergência.

## Summary

Entregar o lado de observabilidade da 009: o módulo `ai_core/observability/` com o seam **Trace Sink** (um método de
emissão que recebe eventos tipados, sem nenhum tipo de biblioteca de observabilidade) e o seam **Trace** (consulta por
identificador de requisição). Cinco tipos de evento — execução iniciada, chamada de modelo, execução de validator,
erro e execução concluída —, cada um gravado no momento da emissão, um registro por evento, com redação de credenciais
antes de sair do processo e instante estampado por uma porta de relógio. Backends da fase: memória (teste) e JSONL com
arquivo por dia. Falha do backend nunca interrompe a execução: é contada e registrada em log. Escopo da Fase 1:
**US1**. O harness de avaliação (`ai_core/eval/`, US2–US4) é Fase 6 e **não** nasce aqui.

## Technical Context

**Language/Version**: Python 3.14 (módulo da distribuição `ai-core`, `requires-python = ">=3.14"`)

**Primary Dependencies**: `ai-core-contracts` (só `JSONValue`); stdlib (`dataclasses`, `datetime`, `json`, `logging`,
`pathlib`, `re`). Nenhuma biblioteca de observabilidade — proibida no núcleo por contrato de import ([research.md](research.md) R12)

**Storage**: arquivo JSONL, um por dia, atrás da porta `TraceExporter`/`TraceReader`; memória no perfil de teste

**Testing**: pytest + pytest-asyncio (o seam é síncrono; a suíte segue o modo do workspace); testes puros de redação e
de serialização; suítes de conformidade dos dois seams e das três portas (memória × JSONL em `tmp_path`)

**Target Platform**: processo do core na imagem Linux ARM64

**Project Type**: módulo de biblioteca dentro do monolito modular (`ai-core`)

**Performance Goals**: emissão sem custo perceptível diante de uma chamada de modelo — uma serialização JSON e um
`write` bufferizado por evento, sem fila nem thread (R4); consulta de uma requisição por varredura do arquivo do dia

**Constraints**: nenhum tipo de biblioteca de observabilidade no seam (FR-013); credencial nunca sai do processo
(FR-002); falha do exporter nunca propaga (FR-011); nenhuma leitura de relógio fora da porta (ADR-013); nada de
domínio (princípio I); o módulo não conhece quem emite além do que chega pelo seam

**Scale/Scope**: 1 módulo (`api.py` com 2 Protocols + 5 eventos + 2 value objects de leitura, `domain/` com 2
arquivos, `ports.py` com 3 portas, `service.py`, 2 adapters); `ai_core/eval/` fora de escopo

Nenhum `NEEDS CLARIFICATION` no escopo da Fase 1. Retenção por política configurável fica em aberto por decisão
explícita (R11): a rotação diária prepara o terreno e a política entra com a configuração do operador (011).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Eventos descrevem execução, modelo e validação; nenhum termo de domínio. Métricas de domínio são do harness (Fase 6) |
| II. Seams | ✅ | Expõe Trace Sink e Trace, ambos com suíte de conformidade; não conhece flows, catálogo, HTTP nem quem emite — só o evento que chega |
| III. O core orquestra | N/A | — |
| IV. Assistant é a fronteira | ✅ | O trace registra o assistant resolvido como dado; não decide nada sobre capacidade |
| V. Determinismo | ✅ | Redação e serialização puras; nenhuma chamada de LLM (julgamento por LLM é do harness offline, ADR-007) |
| VI. Conteúdo externo | ✅ | Texto livre que chega de fora (mensagem de erro de provider) é redigido e truncado com marca antes de ser gravado |
| VII. Falha fechada | ✅ | Falha do exporter é contada e registrada, nunca propagada (FR-011); consulta sem backend de leitura responde explicitamente, em vez de vazio |
| VIII. Modelos por papel | ✅ | `ModelCall` registra papel, provider e modelo — é o que torna auditável a regra da 006 |
| IX. Proveniência | N/A | Sem retrieval na Fase 1 |
| X. Medir antes de calibrar | ✅ | Este módulo é o pré-requisito: sem trace e sem harness não há medição. O harness entra na Fase 6 |
| XI. Streaming | ✅ | Escrita por evento (R4) é compatível com execução em streaming: o trace acompanha a execução em curso |
| XII. Simplicidade | ✅ | Sem fila assíncrona, sem índice, sem expurgo, sem reconstrução de tipos na leitura — cada um adiado com motivo (R4, R6, R9, R11) |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/observability/**` e
  `ai-core/packages/core/tests/observability/**`; fora dele apenas os contratos de import-linter em
  `ai-core/pyproject.toml` e o gatilho do `core.yml` (já cobre `packages/core/**`)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — consome apenas
  `JSONValue` de `ai_core_contracts` (001). **Não** importa 002, 005 nem 006: os emissores chamam o seam
- [x] Every seam this module exposes has a conformance test planned — `test_trace_sink_seam.py` (emissão) e
  `test_trace_query_seam.py` (consulta)
- [x] No seam changes — Trace Sink e Trace nascem aqui, na forma que o ADR-013 descreve; a forma concreta (contrato
  próprio em vez da API do OpenTelemetry) está na clarificação e no design.md
- [x] Import boundaries (import-linter) cover the new code — contratos novos do R12

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/`
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — só stdlib e
  `ai_core_contracts`; `json` aparece **apenas no adapter** (`domain/records.py` monta a estrutura de valores JSON,
  não texto); contrato de import proíbe `opentelemetry`, `logfire` e `sentry_sdk` nas quatro camadas
- [x] Other modules are imported only through their `api.py` — este módulo não importa nenhum outro módulo do core
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — `TraceExporter`
  e `TraceReader` (I/O de arquivo) e `Clock` (tempo, ADR-013); `domain/` é puro
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — as três: arquivo, leitura do backend e
  relógio. A troca de backend está no roadmap (arquivo → Postgres ou ferramenta)
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter —
  memória × JSONL em `tmp_path`; relógio fixo × relógio de sistema
- [x] Services and adapters of other modules are instantiated only in the composition root — a 009 não instancia nada
  de outro módulo; quem monta `TraceService` com seus adapters é a 011 (e os testes)

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/009-core-observability-evaluation/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── trace-api.md          # seams Trace Sink e Trace: eventos, emissão, consulta
│   ├── ports.md              # TraceExporter, TraceReader, Clock e suas conformidades
│   └── record-format.md      # formato do registro JSONL (o que o arquivo contém)
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                    # contratos novos de import-linter (R12)
└── packages/core/
    ├── src/ai_core/observability/
    │   ├── __init__.py               # docstring: consumidores importam observability.api
    │   ├── api.py                    # seams: TraceSink, TraceQuery + eventos e value objects de leitura
    │   ├── domain/
    │   │   ├── __init__.py
    │   │   ├── redaction.py          # redação de nomes sensíveis e de padrões em texto livre; truncamento (R7)
    │   │   └── records.py            # evento + instante → registro JSON (R10)
    │   ├── ports.py                  # TraceExporter, TraceReader, Clock
    │   ├── service.py                # TraceService: implementa TraceSink e TraceQuery; conta descartes (R8)
    │   └── adapters/
    │       ├── __init__.py
    │       ├── memory.py             # InMemoryTraceBackend (escrita e leitura) + FixedClock
    │       └── jsonl.py              # JsonlTraceBackend: trace-YYYY-MM-DD.jsonl (R6) + SystemClock
    └── tests/observability/
        ├── conftest.py               # eventos de exemplo e fábricas
        ├── unit/                     # redaction, records, service com adapters em memória
        ├── contract/                 # conformidade dos dois seams e das três portas
        └── integration/              # JSONL em tmp_path: escrita, leitura, rotação por dia
```

**Structure Decision**: layout hexagonal do ADR-012 no caminho do design.md. `ai_core/eval/` (harness, US2–US4) não é
criado nesta fase — nasce na Fase 6, e a divisão da spec em duas continua opcional (Assumptions da spec). O
`SystemClock` mora aqui porque é este módulo que precisa dele agora; quando a 005 declarar a própria porta de tempo, a
011 injeta o mesmo adapter nos dois (011 FR-008), e um adapter compartilhado pode migrar para a 011 sem mudar seam.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 005 (Fase 1) | Receber `TraceSink` no construtor e emitir `ExecutionStarted` no início (com o `reference_time` que fixou), `ValidationRun` por validator, `ExecutionError` em falha e `ExecutionFinished` no fim. Emissão é síncrona e nunca levanta |
| 006 (Fase 1) | Emitir `ModelCall` por chamada de provider, com papel, provider, modelo, tokens e duração medidos pelo próprio módulo |
| 004 (Fase 3) | Acrescentar um tipo de evento de tool no `api.py` da 009 — não muda o seam nem exige ADR (R1) |
| 008 (Fase 2) | Consulta pelo seam Trace: `trace(request_id)`; quando o perfil não tem backend de leitura, a resposta diz isso explicitamente, e a superfície privada deve traduzir em erro claro, não em 404 vazio |
| 011 (Fase 1) | Montar `TraceService(exporter, reader, clock)` pelo perfil (memória no teste; JSONL no real), injetar o mesmo `Clock` em todo módulo com porta de tempo (FR-008 da 011), configurar handlers do logger `ai_core.observability` e expor `dropped_events()` na saúde agregada (US5, Fase 2) |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- II: o `api.py` só tem Protocols, dataclasses congeladas e tipos de `ai_core_contracts`; nenhum evento carrega objeto
  de outro módulo (o assistant e o flow entram como texto, os packs como nomes).
- VI: `contracts/record-format.md` fixa que todo campo de texto livre é redigido e truncado antes de ir para o
  registro — a regra é do módulo, não do emissor.
- VII: a tabela de falhas do data-model cobre exporter que levanta, reader ausente e requisição sem trace, cada um com
  resposta explícita.
- XIII: nenhuma porta nova além das três; `Clock` existe por não-determinismo, as outras duas por I/O e troca prevista.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Duas portas de backend (`TraceExporter` e `TraceReader`, R5) | um exporter para ferramenta externa escreve mas não lê | porta única obrigaria adapters de escrita a implementar uma leitura falsa, e o seam de consulta mentiria |
| Redação por padrões em texto livre (R7) | mensagem de exceção de provider HTTP carrega `Authorization` | confiar em quem emite transfere um requisito duro (FR-002) para cada módulo futuro |
| Contador de descartes (R8) | "dados perdidos são sinalizados" não pode depender do backend que falhou | registrar a perda no trace é impossível quando o destino é justamente o que quebrou |

## Fase 6 (US2, US3, US4: harness de avaliação) — 2026-10-13

Insumos lidos: [design.md](design.md) ("Harness de avaliação", "Julgamento por LLM", "Benchmark de modelos", "Portas e
adapters"), ADR-007, ADR-012, ADR-013, ADR-017 e o [ADR-027](../../docs/adr/ADR-027-metricas-de-dominio-pelo-contrato-de-pack.md)
(criado por esta passada, da clarificação 3); as cinco clarificações de 2026-10-13; o código do motor (005), da consulta
de trace, do `GrantResolver` (003), do Pack Runtime (002), do Model Router (006) e da CLI da 011. Pesquisa em
[research.md](research.md) R13–R27. **Mudanças de seam**: o contrato 001 ganha `ai_core_contracts.eval` e o hook
opcional `eval_metrics` (ADR-027, contratos `0.1.2`); a 002 ganha o seam `PackEvalMetrics` (ADR-027); a 009 ganha o
evento `Retrieval` (aditivo, ADR-017), emitido pela 005; o harness nasce com os seams **Eval Harness**, **formato de
conjunto dourado** e **formato de relatório**.

### Summary — Fase 6

O módulo `ai_core/eval/` executa um conjunto dourado YAML contra um Assistant, item a item, pelo seam Execution Engine
com a data de referência do item, e lê o trace da requisição para medir recuperação (recall@k, MRR, recall do que foi
entregue), rerank (ganho), citação (resolvível, inventada, esperada), geração (fidelidade e cobertura por juiz, três
julgamentos com média e variância) e operação (latência e tempo até o primeiro token p50/p95, tokens, chamadas,
tokens/s, ações inválidas do controller, rotas do portão, erros, flags). Métricas de domínio vêm dos packs pelo contrato
001. Linha de base em JSON com tolerância por métrica; só as determinísticas barram o CI. O benchmark de modelos é o
mesmo harness sobre Assistants que diferem no modelo, com `eval compare`.

### Technical Context — o que muda

- **Dependências**: nenhuma nova (`pyyaml` e `jsonschema` já estão no core; o juiz usa o Model Router).
- **Storage**: conjunto dourado YAML e relatório/linha de base JSON, em arquivos do operador (versionados no pack).
- **Testing**: domínio por tabela (casamento, métricas, comparação, validação do conjunto); serviço com o motor real no
  perfil `test`, um pack de teste com retriever, reranker e métrica de domínio, e juiz simulado; conformidade das portas
  (memória × arquivo); CLI ponta a ponta.
- **Performance**: SC-002 — 50 perguntas em até 30 min, em sequência (R22).

### Constitution Check — Fase 6

| Princípio | Resultado | Evidência |
|---|---|---|
| I | ✅ | O core mede sem domínio: evidência por documento, flags contadas sem interpretação, métricas de domínio do pack (ADR-027) |
| II | ✅ | O harness só usa seams (005, 009, 003, 002, 006); mudanças de seam com ADR-027 e ADR-017 |
| IV | ✅ | O grant vem da 003 com um `Principal` da rodada, sujeito à ACL e ao orçamento (R21) |
| V | ✅ | Juiz só offline (FR-006, ADR-007); nada muda no caminho da requisição além de um evento de trace |
| VI | ✅ | O evento `Retrieval` não carrega texto; o juiz recebe os trechos como dado, com instrução própria |
| VII | ✅ | Item inválido, juiz ausente, métrica de domínio que levanta e trace sem leitura: explícitos, sem derrubar a rodada |
| IX | ✅ | Citação medida por `chunk_id` contra o que foi entregue (ADR-007) |
| X | ✅ | É o instrumento do princípio: linha de base e relatório antes/depois (SC-004) |
| XII | ✅ | Sequencial, arquivos simples, benchmark = mesmo harness |
| XIII | ✅ | `api.py`/`domain/`/`ports.py`/`service.py`/`adapters/`; quatro portas, cada uma por I/O ou não-determinismo |

**Module boundary gate (Fase 6)**: `ai_core/eval/**` e `tests/eval/**`; toques declarados em `ai_core_contracts`
(`eval.py`, `PackBase`, conformidade), `ai_core/packs/` (hook e seam), `ai_core/observability/api.py` (`Retrieval`),
`ai_core/graph/adapters/langgraph/nodes/common.py` (emissão), `ai_core/bootstrap/` (CLI e composição), com testes de
cada um; import-linter com os contratos do `eval` (R26).

**Ports & adapters gate (Fase 6)**: `GoldenSetSource` (arquivo), `BaselineStore` (arquivo), `Judge` (modelo) e `Clock`
(tempo), cada uma com adapter em memória e suíte de conformidade.

**Resultado do gate (antes da Phase 0)**: PASS.

### Project Structure — Fase 6

```text
ai-core/packages/contracts/src/ai_core_contracts/
├── eval.py                         # EvalEvidence, EvalItem, EvalChunk, EvalObservation, EvalMetric, ProvidesEvalMetrics
└── pack.py                         # PackBase.eval_metrics -> ()
ai-core/packages/core/src/ai_core/
├── observability/api.py            # Retrieval, RetrievedChunk (ADR-017)
├── graph/adapters/langgraph/nodes/common.py   # emite Retrieval na validação
├── packs/{api.py,service.py}       # hook eval_metrics na carga; seam PackEvalMetrics
├── eval/
│   ├── api.py                      # EvalHarness, GoldenSet, GoldenItem, Evidence, EvalReport, MetricValue, Comparison
│   ├── domain/{golden,matching,metrics,judging,compare}.py
│   ├── ports.py                    # GoldenSetSource, BaselineStore, Judge, Clock
│   ├── service.py                  # EvalService
│   └── adapters/{golden_yaml,report_json,judge,memory,cli}.py
└── bootstrap/{cli.py,wiring.py}    # eval run, eval compare
```

### Seam Notes for Consumers — Fase 6

| Consumidor | O que precisa saber |
|---|---|
| 105 | Conjunto dourado no formato de [contracts/eval-harness.md](contracts/eval-harness.md); métricas de domínio pelo hook `eval_metrics` (contratos `>=0.1.2`); roda com `ai-core eval run` na imagem de instalação; o Assistant precisa admitir o `Principal` da rodada |
| 005 | Emite `Retrieval` na validação a partir da Turn View; nenhum seam do motor muda |
| 011 | Registra `eval run` e `eval compare`; compõe o `EvalService` com o motor, a consulta de trace, a 003, a 002 e o juiz pelo Model Router |
| CI de packs | `ai-core eval run … --baseline` sai 1 em regressão determinística |

### Constitution Check — pós-design (Fase 6)

Reavaliado com a seção "Fase 6" de [data-model.md](data-model.md), [contracts/eval-harness.md](contracts/eval-harness.md)
e [quickstart.md](quickstart.md): **PASS** — cada edge case da spec tem comportamento definido (item inválido, juiz
ausente); só métricas determinísticas barram (SC-003); as mudanças de seam têm ADR.

### Complexity Tracking — Fase 6

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Protocolo de métrica no contrato 001 (ADR-027) | métrica de domínio no mesmo relatório e na mesma barreira, sem o pack importar o core | cálculo fora do harness duplicaria linha de base e CI |
| Evento `Retrieval` com proveniência | recall por documento precisa de documento e seção dos trechos | ids sozinhos não casam com evidência por documento (clarificação 2) |
| Três julgamentos por item | variância visível; juiz não barra sozinho | um julgamento esconderia a instabilidade do juiz |
