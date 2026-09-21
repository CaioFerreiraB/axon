# Implementation Plan: Providers de LLM e modelo por papel

**Branch**: `006-core-llm-providers` | **Date**: 2026-09-18 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/006-core-llm-providers/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/006-core-llm-providers/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-008, ADR-012, ADR-013; contratos da 001 (`LLMProvider`, `ChatMessage`,
`ChatChunk`, `ChatResponse`, `ChatTool`, `ChatUsage`), Trace Sink da 009 (`ai_core.observability.api`) e Pack Runtime da
002 já implementados. Consumidores conferidos: 005 (Fase 1, pede o papel `generation`), 011 (monta providers, política e
perfil de teste — US1/US3), 003 (Fase 2, passa a produzir a política), 008 (Fase 2, traduz os erros do módulo).
**Nenhuma divergência do `design.md`**: a assinatura `for_role(papel) → cliente de modelo` é preservada literalmente; o
que o plano acrescenta é a fábrica por execução ([research.md](research.md) R2), ausente do design porque ele não trata
de onde entram política e identificador de requisição. Nenhum ADR novo.

## Summary

Entregar o módulo `ai_core/llm/`: o seam **Model Router**, que resolve papel → (provider, modelo) a partir de uma
**Model Policy** e devolve um cliente já ligado ao modelo, com a chamada instrumentada no Trace Sink da 009; o adapter do
provider local (Ollama pela camada compatível com OpenAI, via SDK oficial); um provider simulado para o perfil de teste
da 011; e verificação de saúde sob demanda. Escopo da Fase 1: **US1** (geração local em streaming), mais as três
exigências que nascem com o seam — allowlist aplicada (FR-003), saúde (FR-009) e timeouts de conexão e de inatividade
(FR-010). Adapters de OpenAI e OpenRouter, papéis múltiplos, restrição de formato de saída no controller e tempo até o
primeiro token são Fase 3 ([research.md](research.md) R14).

## Technical Context

**Language/Version**: Python 3.14 (módulo da distribuição `ai-core`, `requires-python = ">=3.14"`)

**Primary Dependencies**: `ai-core-contracts` (contrato `LLMProvider` e tipos de chat); **nova** — `openai>=3.15,<4`,
confinada a `ai_core/llm/adapters/` por contrato de import (R4, R13); stdlib (`dataclasses`, `fnmatch`, `time`,
`typing`). O cliente HTTP (`httpx2`) vem com o SDK e só aparece na construção do cliente e nos testes do adapter

**Storage**: N/A — o módulo não persiste nada. Credenciais de providers remotos entram na Fase 3, pela porta de segredos
do `design.md`

**Testing**: pytest + pytest-asyncio (modo `auto` do workspace); `domain/` puro; conformidade do seam e da porta
`ModelProvider` rodando contra o provider simulado **e** contra o adapter do Ollama com transporte HTTP falso (R10);
integração opcional contra um Ollama real, marcada e pulada por default

**Target Platform**: processo do core na imagem Linux ARM64 (2 OCPU · 12 GB · sem GPU); Ollama no mesmo host

**Project Type**: módulo de biblioteca dentro do monolito modular (`ai-core`)

**Performance Goals**: o módulo não acrescenta latência perceptível à chamada do modelo — resolução de papel é
dicionário mais casamento de padrão; a instrumentação é uma leitura de relógio monotônico e uma emissão síncrona no
Trace Sink por chamada. Expectativa do provider local: 5–15 tok/s (design.md), com o primeiro pedaço chegando antes do
fim da geração (é o que a US1 verifica)

**Constraints**: nenhum tipo do SDK atravessa o seam (R6); nenhum teto de tempo total (R5); o contrato `LLMProvider`
(001) não muda — a exigência de sondagem é porta deste módulo (R8); nada de domínio (princípio I); nenhuma leitura de
relógio fora da porta (ADR-013); a Fase 1 não conhece 003 nem 008

**Scale/Scope**: 1 módulo — `api.py` (3 Protocols de seam + 4 value objects + 5 erros), `domain/policy.py`, `ports.py`
(2 portas), `service.py`, 3 adapters (`openai_compat.py`, `ollama.py`, `fake.py`); 3 papéis; 1 provider real na fase

Nenhum `NEEDS CLARIFICATION`: as cinco perguntas abertas foram resolvidas na sessão de clarificação de 2026-09-18 e
estão em [research.md](research.md) R1, R4, R5, R7 e R8.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Papéis, providers e modelos; nenhum termo de domínio. O módulo não vê prompt nem conteúdo — só mensagens que chegam prontas |
| II. Seams | ✅ | Expõe Model Router (com suíte de conformidade); consome só `ai_core_contracts` e o `api.py` da 009. Não conhece flows, packs nem HTTP |
| III. O core orquestra | ✅ | O módulo não decide topologia: devolve o cliente do papel que a 005 pediu |
| IV. Assistant é a fronteira | ✅ | A política vem de fora já resolvida (R1) e a allowlist é aplicada em toda resolução (R9, elo 6 da cadeia) |
| V. Determinismo | ✅ | Resolução de papel e allowlist são puras e sem LLM; nenhuma escolha de modelo é feita pelo módulo (FR-004 proíbe roteamento automático) |
| VI. Conteúdo externo | ✅ | Resposta do provider é dado: o módulo não a interpreta. Corpo de erro do provider é truncado antes de entrar na mensagem (R6) e redigido pela 009 antes de sair do processo |
| VII. Falha fechada | ✅ | Papel não configurado, modelo fora da allowlist, provider desconhecido, provider fora do ar e stream travado são erros explícitos que nomeiam provider e modelo; nenhum fallback (FR-007) |
| VIII. Modelos por papel | ✅ | É a spec que implementa o ADR-008: provider e modelo sempre explícitos, resolvidos por papel, conferidos contra a allowlist |
| IX. Proveniência | N/A | Sem retrieval |
| X. Medir antes de calibrar | ✅ | `ModelCall` por chamada (R7) é o insumo do benchmark do design.md; nenhum número de modelo é fixado aqui |
| XI. Streaming | ✅ | `stream()` faz parte do seam desde a Fase 1 e é o caminho que a US1 valida; o timeout de inatividade existe para protegê-lo (R5) |
| XII. Simplicidade | ✅ | Sem pool próprio, sem cache de cliente por requisição, sem retry, sem fila de trace; porta de segredos adiada para a fase que a usa (R8, R14) |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/llm/**` e
  `ai-core/packages/core/tests/llm/**`; fora dele, apenas `ai-core/packages/core/pyproject.toml` (dependência `openai`)
  e `ai-core/pyproject.toml` (contratos de import-linter)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — `LLMProvider` e tipos
  de chat de `ai_core_contracts` (001); `TraceSink` e `ModelCall` de `ai_core.observability.api` (009). Nenhum outro
  módulo do core é importado
- [x] Every seam this module exposes has a conformance test planned — `tests/llm/contract/test_model_router_seam.py`
  (resolução, papel não configurado, allowlist, cliente ligado, emissão de trace) e
  `test_model_provider_port.py` (conformidade da porta contra o provider simulado e contra o Ollama com transporte falso)
- [x] No seam changes — o Model Router nasce aqui, com a assinatura do `design.md`; o contrato `LLMProvider` (001) é
  consumido sem alteração, e a exigência de sondagem virou porta deste módulo em vez de mudança no contrato (R8)
- [x] Import boundaries (import-linter) cover the new code — contratos novos do R13

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/`
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — `api.py`, `domain/` e
  `ports.py` importam só stdlib e `ai_core_contracts`; o `service.py` acrescenta o `api.py` da 009 (Trace Sink).
  Contrato de import proíbe `openai` e `httpx2` nas quatro camadas (R13)
- [x] Other modules are imported only through their `api.py` — só `ai_core.observability.api`; o `api.py` da 006 não
  importa o resto do próprio módulo (`BoundModel` é Protocol aqui e implementação no `service.py`, R3)
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — I/O de rede pela
  porta `ModelProvider` (contrato 001 + sondagem, R8); tempo pela porta `Clock` (relógio monotônico, ADR-013); trace
  pelo seam da 009; `domain/policy.py` é puro. Segredos entram na Fase 3, com os providers remotos (R14)
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — `ModelProvider` (rede, e a troca de
  provider é o ponto do módulo) e `Clock` (não-determinismo). Nenhuma porta para regra pura: allowlist e resolução de
  papel ficam em `domain/`
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter —
  `fake.py` × `ollama.py` (com transporte HTTP falso na suíte padrão e Ollama real na integração opcional);
  `ScriptedClock` × `MonotonicClock`, ambos em `adapters/clock.py` para que a 011 use o programado no perfil de teste
  (011 US3 cenário 2)
- [x] Services and adapters of other modules are instantiated only in the composition root — a 006 não instancia nada de
  outro módulo; quem monta `ModelRoutingService(providers=…, trace=…, clock=…)` é a 011 (e os testes)

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/006-core-llm-providers/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── model-router.md       # seam: ModelRouting, ModelRouter, BoundModel, erros, Model Policy
│   ├── ports.md              # ModelProvider (contrato 001 + sondagem) e Clock, com suas conformidades
│   └── ollama-adapter.md     # tradução para a camada compatível: mensagens, streaming, tokens, erros, timeouts
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                       # contratos novos de import-linter (R13)
└── packages/core/
    ├── pyproject.toml                   # dependência openai>=3.15,<4 (R4)
    ├── src/ai_core/llm/
    │   ├── __init__.py                  # docstring: consumidores importam llm.api
    │   ├── api.py                       # seams ModelRouting/ModelRouter/BoundModel + ModelRef, ModelPolicy,
    │   │                                #   ModelRole, ModelHealth + os cinco erros
    │   ├── domain/
    │   │   ├── __init__.py
    │   │   └── policy.py                # resolução por papel, casamento de allowlist, leitura de "provider/modelo"
    │   ├── ports.py                     # ModelProvider (LLMProvider + probe), ProbeResult, Clock
    │   ├── service.py                   # ModelRoutingService, ExecutionRouter, TracedModel (instrumentação, R7)
    │   └── adapters/
    │       ├── __init__.py
    │       ├── clock.py                 # MonotonicClock (time.monotonic) + ScriptedClock (perfil de teste da 011)
    │       ├── openai_compat.py         # provider sobre qualquer endpoint compatível: tradução e mapeamento de erro
    │       ├── ollama.py                # OllamaProvider: base_url :11434/v1, sentinela de credencial, sondagem
    │       └── fake.py                  # ScriptedProvider: respostas, pedaços e falhas programados (011 US3, R11)
    └── tests/llm/
        ├── conftest.py                  # políticas de exemplo, transporte HTTP falso, relógio fixo
        ├── llm_testkit.py               # fábricas compartilhadas (padrão de tests/observability)
        ├── unit/                        # domain/policy.py; service com provider simulado; instrumentação
        ├── contract/                    # conformidade do seam e da porta (simulado × Ollama com transporte falso)
        └── integration/                 # Ollama real, marcado e pulado sem OLLAMA_BASE_URL
```

**Structure Decision**: layout hexagonal do ADR-012 no caminho do `design.md` (`ai_core/llm/`). `openai.py` e
`openrouter.py` do design não nascem nesta fase: `openai_compat.py` já é a parte comum dos três, e cada um deles vira um
arquivo fino na Fase 3 (R4). A porta `SecretResolver` do `design.md` também é da Fase 3, quando houver credencial a
resolver (R8, R14) — a Fase 1 declararia uma porta sem uso, contra o princípio XIII.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 005 (Fase 1) | Receber `ModelRouting` no construtor; por execução, `router = routing.for_execution(policy=…, request_id=…)` e depois `router.for_role("generation")`. Gerar com `stream()`; o trace da chamada já sai do módulo (não emitir `ModelCall` por conta própria). Erros chegam como `ModelRoutingError` — nada de `openai` |
| 011 (Fase 1) | Montar `ModelRoutingService(providers={"ollama": OllamaProvider(...)}, trace=trace_service, clock=MonotonicClock())`, injetar o mesmo relógio dos demais módulos (011 FR-008), montar a `ModelPolicy` a partir da configuração (R1) e usar `ScriptedProvider` no perfil de teste. Expor `await routing.check(policy)` na saúde e no comando de diagnóstico — nunca no caminho de boot (R8) |
| 003 (Fase 2) | Passa a produzir a `ModelPolicy` como parte do Execution Grant; o seam não muda. Validação de Assistant (roteamento automático, FR-004) usa o mesmo value object |
| 008 (Fase 2) | Traduzir a hierarquia de erro: `RoleNotConfigured`/`ModelNotAllowed`/`UnknownProvider` são configuração (4xx); `ModelCallFailed` é indisponibilidade do provider (5xx) |
| 009 | Recebe `ModelCall` por chamada, com `finish_reason="error"` quando a chamada falha. `ttft_ms` entra na Fase 3 (US6) como campo aditivo |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- II: o `api.py` só tem Protocols, dataclasses congeladas, erros e tipos de `ai_core_contracts`; nenhum tipo do SDK e
  nenhum objeto de outro módulo atravessa o seam.
- VII: a tabela de falhas do [data-model.md](data-model.md) cobre os seis modos (papel ausente, modelo bloqueado,
  provider desconhecido, provider fora do ar, erro de status, stream travado), cada um com erro nomeado e com o
  `ModelCall` correspondente emitido.
- VIII: `ModelRef` não tem default e não aceita texto vazio; não existe caminho em que o módulo escolha um modelo.
- XIII: duas portas, ambas por I/O ou não-determinismo; o SDK aparece só em `adapters/`, e o contrato de import-linter
  torna isso verificável.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Fábrica `for_execution` além de `for_role` (R2) | política e identificador de requisição são por execução; providers e trace são por processo | passar os dois em cada `for_role` obrigaria a 005 a repeti-los em cada papel de cada iteração, com risco de `request_id` trocado |
| `openai_compat.py` separado de `ollama.py` (R4) | a camada compatível é o que os três providers do design compartilham | um `ollama.py` monolítico faria a Fase 3 copiar tradução e mapeamento de erro duas vezes |
| Porta `ModelProvider` estendendo o contrato 001 (R8) | FR-009 exige sondagem, e o contrato 001 só tem `chat` | acrescentar saúde ao contrato 001 mudaria um seam de outra spec para atender a esta |
