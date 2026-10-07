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

---

# Fase 3 (2026-10-02): US2–US5 — providers remotos, roteamento automático e saída estruturada

Insumos: as três clarificações de 2026-10-02 (FR-004, FR-005, FR-011); [design.md](design.md) (porta `SecretResolver`,
`openai.py` e `openrouter.py`), ADR-008, ADR-012, ADR-013, ADR-016; os consumidores conferidos no código — 003 (trata o
`ValueError` do `ModelRef` no YAML e na requisição), 008 (idem no corpo de Assistant), 005 (o nó do controller captura
`ModelCallFailed` e envia `response_format` sem `strict`) e 011 (monta providers e saúde). Decisões em
[research.md](research.md) R15–R26. **Sem divergência do `design.md`** e **sem mudança de seam**: a regra de roteamento
automático é invariante do `ModelRef` que a nota da Fase 1 para a 003 já anunciava (R16), e a guarda e a falta de
credencial usam o `ModelCallFailed` existente (R17, R21). **ADR novo**:
[ADR-020](../../docs/adr/ADR-020-segredos-uma-fonte-por-perfil-uma-porta-por-modulo.md) — refina a FR-009 e o caso de
borda de segredo ausente da 011 (uma fonte por perfil, uma porta por módulo; credencial ausente degrada, não derruba),
achado I1 da análise.

## Summary (Fase 3)

Os providers OpenAI e OpenRouter entram como arquivos finos sobre a camada compatível, com credencial por variável
(`AI_CORE_OPENAI_API_KEY`, `AI_CORE_OPENROUTER_API_KEY`) lida pela porta `SecretResolver`: sem ela, o provider fica
registrado, a saúde diz "sem credencial" e toda chamada falha antes da rede. O `ModelRef` passa a recusar roteamento
automático do OpenRouter (`openrouter/auto` e o namespace `openrouter/…`), o que cobre declaração, escolha por
requisição e saúde de uma vez. O papel `controller` ganha a garantia de formato em três camadas: o roteador recusa
chamada sem `response_format` de esquema, o adapter envia `strict: true` (e `require_parameters` no OpenRouter), e a
recusa do provider é erro explícito sem reenvio. US2 e US5 ganham a prova com providers diferentes. Toque declarado na
011: porta `llm_secrets` e os remotos nos perfis `memory` e `persistent`.

## Technical Context (Fase 3)

**Dependências**: nenhuma nova — o SDK `openai` da Fase 1 já fala com os três endpoints.
**Storage**: N/A. **Testing**: transporte HTTP falso para os remotos (Fase 1, R10); integração paga opcional, pulada sem
as variáveis de credencial (R25).
**Constraints**: nenhum valor de credencial em erro, log ou trace (FR-011); nenhuma chamada do `controller` sem
restrição (SC-003); nenhum reenvio nem fallback (FR-005, FR-007); seams inalterados.
**Scale/Scope**: `api.py` (invariante do `ModelRef`), `domain/output.py` (novo), `ports.py` (+`SecretResolver`),
`service.py` (guarda no `TracedModel`), `adapters/` (+`secrets.py`, `remote.py`, `openai.py`, `openrouter.py`;
`openai_compat.py` com `strict` e lista truncada); 011: `profiles.py`.

## Constitution Check (Fase 3)

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Providers, modelos e formato de saída; nenhum termo de domínio |
| II. Seams | ✅ | Assinaturas inalteradas; a invariante nova do `ModelRef` era anunciada desde a Fase 1 (R16) e os consumidores já tratam o `ValueError`; guarda e credencial usam `ModelCallFailed` (R17, R21) |
| IV. Assistant é a fronteira | ✅ | A allowlist não libera roteamento automático (R16); o modelo escolhido na requisição continua conferido (US5, R24) |
| V. Determinismo | ✅ | Nenhum modelo escolhido por terceiros: roteamento automático é recusado na construção da referência |
| VI. Conteúdo externo | ✅ | Corpo do provider continua truncado; o valor da chave é trocado por `***` em todo motivo de erro (R21) |
| VII. Falha fechada | ✅ | Sem credencial → erro antes da rede, nomeando a variável; controller sem esquema → recusado; recusa do provider → erro sem reenvio (R17–R21) |
| VIII. Modelos por papel | ✅ | US2 provada com providers diferentes por papel (R24) |
| XI. Streaming | ✅ | Os remotos herdam o streaming da camada compatível (FR-006) |
| XII. Simplicidade | ✅ | Remotos como arquivos finos; sem URL base configurável, sem cabeçalhos de atribuição, sem resolução de segredo por chamada (R20, R21) |
| XIII. Portas e adapters | ✅ | `SecretResolver` existe por I/O (ambiente) e troca prevista (secret store), com adapter em memória e conformidade (R21) |

**SC-004 nesta passada**: nenhum seam nem regra de outra spec muda para acrescentar OpenAI e OpenRouter; o que muda na
011 é o registro dos adapters, que só a composition root faz (princípio XIII), e o contrato `profiles.md` passa a
descrever a porta de forma genérica ("os providers da 006"), para o próximo provider não exigir edição.

**Module boundary gate (Fase 3)**: `ai_core/llm/**` e `tests/llm/**`; toque declarado na 011 —
`bootstrap/profiles.py` (porta `llm_secrets` e providers remotos), seus testes e `specs/011-core-bootstrap/contracts/profiles.md`
(linha da porta). Nenhum outro módulo muda: 003, 005 e 008 continuam como estão (R16, R17). import-linter sem contrato
novo (R26). **Resultado**: PASS.

**Ports & adapters gate (Fase 3)**: porta nova `SecretResolver` — I/O (ambiente) e troca prevista (secret store do
operador) —, com `EnvSecretResolver` e `InMemorySecretResolver` e suíte de conformidade contra os dois; a regra do
controller é pura (`domain/output.py`); o SDK continua só em `adapters/`; só a 011 instancia os adapters. **Resultado**:
PASS.

## Project Structure (Fase 3)

```text
ai-core/packages/core/src/ai_core/llm/
├── api.py                    # ModelRef: recusa roteamento automático do OpenRouter (R16); docstring de ModelCallFailed
├── domain/output.py          # NOVO: constraint_problem — o controller exige response_format de esquema (R17)
├── ports.py                  # + SecretResolver (R21)
├── service.py                # TracedModel aplica a guarda dentro do bloco instrumentado (R17)
└── adapters/
    ├── openai_compat.py      # strict: true forçado; lista de disponíveis truncada na sondagem (R18, R22)
    ├── secrets.py            # NOVO: EnvSecretResolver, InMemorySecretResolver (R21)
    ├── remote.py             # NOVO: RemoteProvider — credencial resolvida no boot, falta guardada, chave limpa (R20, R21)
    ├── openai.py             # NOVO: OpenAIProvider (R20)
    └── openrouter.py         # NOVO: OpenRouterProvider — require_parameters, sondagem por variante (R18, R20, R22)

ai-core/packages/core/src/ai_core/bootstrap/profiles.py   # toque: llm_secrets + remotos nos perfis (R23)
specs/006-core-llm-providers/contracts/remote-adapters.md  # NOVO
specs/011-core-bootstrap/contracts/profiles.md             # linha da porta llm_secrets
```

## Seam Notes for Consumers (Fase 3)

| Consumidor | O que precisa saber |
|---|---|
| 003 | Nada a mudar: `ModelRef` agora recusa `openrouter/auto` e `openrouter/openrouter/…` com `ValueError`, que a validação do YAML, a criação de Assistant de usuário e a escolha por requisição já relatam |
| 005 | Nada a mudar para Ollama e OpenRouter. Chamada do `controller` sem `response_format` de esquema vira `ModelCallFailed` (o nó já o captura). **Pendência**: o esquema de ação com `anyOf` na raiz não cabe no modo estrito da OpenAI; OpenAI como controller do `agentic` falha explicitamente até a 005 publicar um esquema de raiz objeto (R19) |
| 008 | Nada a mudar: `ModelCallFailed` (inclusive "sem credencial") continua sendo falha de execução |
| 011 | Porta `llm_secrets` antes de `providers`; `memory`/`persistent` registram `ollama`, `openai` e `openrouter`; `test` inalterado nos providers (R23) |
| Operador | `AI_CORE_OPENAI_API_KEY` e `AI_CORE_OPENROUTER_API_KEY`; sem elas, `ai-core health` mostra o modelo declarado como indisponível, "sem credencial" (ADR-020: degrada, não derruba) |

## Complexity Tracking (Fase 3)

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `RemoteProvider` entre `OpenAICompatProvider` e os dois remotos (R20) | credencial, falta e limpeza da chave são iguais nos dois remotos e não existem no Ollama | repetir nos dois arquivos; ou pôr credencial na base compartilhada com o Ollama, que não tem |
| Porta `llm_secrets` na 011 além de `mcp_secrets` (R21, R23; ADR-020) | cada módulo aplica a própria regra de nomes; o prefixo da 007 é controle de segurança | um adapter só mudaria o nome das variáveis da 006 para `AI_CORE_MCP_SECRET_…`, contra a clarificação |
| Registro dos remotos na composition root (T041, T042) frente ao SC-004 | instanciar adapters é papel exclusivo da 011 (princípio XIII, 011 FR-006); o SC-004 vale para seams e regras de outras specs, que não mudam | registrar o provider dentro da 006 faria o módulo instanciar a si mesmo, contra o princípio XIII |

## Constitution Check — pós-design (Fase 3)

Reavaliado com a seção "Fase 3" de [data-model.md](data-model.md), [contracts/remote-adapters.md](contracts/remote-adapters.md),
as seções "Fase 3" de [contracts/model-router.md](contracts/model-router.md) e [contracts/ports.md](contracts/ports.md) e
[quickstart.md](quickstart.md): **PASS**.

- II: nenhum Protocol, value object ou erro novo no `api.py`; a regra nova do `ModelRef` sai pelo `ValueError` que os
  três consumidores já tratam, e a guarda e a falta de credencial saem pelo `ModelCallFailed` que a 005 e a 008 já tratam.
- VII: a tabela de modos de falha da Fase 3 cobre roteamento automático, controller sem esquema, remoto sem credencial,
  recusa da restrição e chave inválida — cada um com erro nomeado e, quando houve invocação do cliente, um `ModelCall`.
- VIII: o único lugar onde um terceiro escolheria o modelo (roteador do OpenRouter) é recusado na construção da
  referência.
- XIII: uma porta nova, por I/O e troca prevista, com adapter em memória e conformidade; o SDK continua só em `adapters/`.

---

# Passada de 2026-10-07: subconjunto estrito da OpenAI (ADR-023)

O adapter da OpenAI (e o do OpenRouter para `openai/…`) converte o esquema de saída para o subconjunto estrito na ida e
desfaz na volta; a regra é pura, em `llm/domain/strict.py`. Supera a decisão da R19 de não reescrever o esquema e
retira a pendência da 005, que não muda. Decisões em [research.md](research.md) R27–R31; contrato em
[contracts/remote-adapters.md](contracts/remote-adapters.md), "Subconjunto estrito da OpenAI".

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | Nenhum seam muda: a conversão e a inversa ficam dentro do adapter; quem chama recebe a forma original |
| V. Determinismo | ✅ | Saída estruturada continua obrigatória; agora também no provider que exige o subconjunto |
| VII. Falha fechada | ✅ | Sem equivalente estrito → erro antes da rede, com caminho; nunca reenvio sem restrição |
| XIII. Portas e adapters | ✅ | Regra pura em `domain/`; o SDK só em `adapters/`; nenhuma porta nova |

**Module boundary gate**: `ai_core/llm/domain/strict.py` (novo), `ai_core/llm/adapters/remote.py`, `openai.py`,
`openrouter.py` e testes em `tests/llm/`; nenhum outro módulo. **Resultado**: PASS.

