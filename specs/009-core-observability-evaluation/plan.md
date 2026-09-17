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
