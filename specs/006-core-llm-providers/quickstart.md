# Quickstart — 006 LLM Providers (Fase 1, US1)

Guia de validação. Todos os comandos rodam a partir de `ai-core/`. Nesta máquina, prefixe `uv` com
`XDG_DATA_HOME=$HOME/.local/share` (ver CLAUDE.md).

## Pré-requisitos

```bash
uv sync                      # traz openai>=3.15,<4 (nova dependência da distribuição ai-core)
```

Nada mais: a suíte padrão **não** fala com rede — o adapter do Ollama é exercitado com transporte HTTP falso
([research.md](research.md) R10).

## Verificação completa

```bash
uv run pytest                                  # inclui packages/core/tests/llm
uv run mypy
uv run ruff check packages
uv run lint-imports                            # contratos de camada da 006 e proibição do SDK fora de adapters/
```

`lint-imports` é o que prova, de forma executável, que `openai` e `httpx2` não aparecem em `api.py`, `domain/`,
`ports.py` nem `service.py` (princípio XIII).

## Cenários da US1

### 1. Geração local em streaming (cenário 1)

Sem Ollama, pela suíte:

```bash
uv run pytest packages/core/tests/llm/contract/test_model_router_seam.py -k streaming -v
```

Esperado: o teste observa mais de um pedaço, com `delta` incremental, e `finish_reason` só no último — é a prova de que
o primeiro token chega antes do fim da geração.

### 2. Provider fora do ar (cenário 2)

```bash
uv run pytest packages/core/tests/llm/contract/test_model_router_seam.py -k indisponivel -v
```

Esperado: `ModelCallFailed` cuja mensagem contém `ollama` e o nome do modelo, sem repetição de chamada e sem fallback.

### 3. Trace da chamada

```bash
uv run pytest packages/core/tests/llm/unit/test_instrumentation.py -v
```

Esperado: um `ModelCall` por chamada — no sucesso, com papel, provider, modelo, duração e tokens; na falha, com
`finish_reason="error"`. Dois eventos para duas chamadas; nenhum evento para resolução que falha antes da rede.

## Com um Ollama de verdade (opcional)

```bash
ollama serve &
ollama pull qwen3:1.7b
OLLAMA_BASE_URL=http://localhost:11434/v1 uv run pytest packages/core/tests/llm/integration -v
```

Esperado: tokens chegando incrementalmente de um modelo real, `probe` confirmando `qwen3:1.7b` e negando um modelo
inexistente. Sem a variável, esses testes são pulados.

Para medir o que o `design.md` manda medir antes de escolher modelo (tokens/s e tempo até o primeiro token), use o
trace: com o perfil JSONL da 009, cada chamada vira um registro `ModelCall` com duração e tokens.

## Verificação de saúde (FR-009)

Enquanto a linha de comando do operador não existe (011 US4, Fase 2), a verificação é exercitada pela suíte:

```bash
uv run pytest packages/core/tests/llm/contract/test_model_router_seam.py -k saude -v
```

Esperado: um `ModelHealth` por papel configurado; modelo ausente no provider devolve `available=False` com motivo, e
provider fora do ar **não** levanta exceção.

## Como a 005 e a 011 consomem

```python
# 011, no boot: uma vez por processo
routing = ModelRoutingService(
    providers={"ollama": OllamaProvider(base_url=cfg.ollama_base_url)},
    trace=trace_service,          # seam Trace Sink da 009
    clock=MonotonicClock(),
)
policy = ModelPolicy(roles={"generation": ModelRef.parse("ollama/qwen3:1.7b")}, allow=("ollama/*",))

# 005, por execução
router = routing.for_execution(policy=policy, request_id=request_id)
async for chunk in router.for_role("generation").stream(messages):
    ...
```

No perfil de teste da 011, troque `OllamaProvider` por `ScriptedProvider`: nenhum módulo muda.

---

# Fase 3 (2026-10-02): US2–US5

Mesmos pré-requisitos: nenhuma dependência nova, e a suíte padrão continua sem rede (remotos com transporte HTTP falso,
[research.md](research.md) R25). Contratos em [contracts/remote-adapters.md](contracts/remote-adapters.md) e na seção
"Fase 3" de [contracts/model-router.md](contracts/model-router.md).

## US3 — roteamento automático recusado

```bash
uv run pytest packages/core/tests/llm/unit/test_llm_api.py -k automatico -v
uv run ai-core assistants validate            # com um Assistant que declara controller: openrouter/auto
```

Esperado: `openrouter/auto`, `openrouter/openrouter/auto` e `openrouter/AUTO` recusados com "é roteamento automático
… declare um modelo explícito"; `openrouter/qwen/qwen3-8b:free` aceito. No `assistants validate`, o Assistant aparece
indisponível com `models.controller: …` e o comando sai com código diferente de zero. Pela API, escolher
`<assistant>/openrouter/openrouter/auto` como `model` devolve 400 com `param: "model"`, mesmo com `openrouter/*` na
allowlist.

## US4 — saída estruturada no controller

```bash
uv run pytest packages/core/tests/llm -k "controller or strict or require_parameters or recusa" -v
```

Esperado: chamada do `controller` sem `response_format` de esquema falha antes do provider e deixa um `ModelCall` de
erro; o corpo enviado leva `"strict": true` (e, no OpenRouter, `"provider": {"require_parameters": true}`); um 400 do
provider vira `ModelCallFailed` com uma única requisição.

## FR-011 — provider remoto sem credencial

```bash
uv run pytest packages/core/tests/llm -k credencial -v
env -u AI_CORE_OPENAI_API_KEY uv run ai-core health   # com um Assistant de sistema em openai/gpt-4o-mini
```

Esperado: a plataforma sobe; o item `model:openai/gpt-4o-mini` aparece indisponível com "sem credencial: defina
AI_CORE_OPENAI_API_KEY"; nenhuma requisição sai para a rede; o valor de uma credencial nunca aparece na saída.

## US2 e US5 — papéis em providers diferentes e allowlist

```bash
uv run pytest packages/core/tests/llm/contract/test_model_router_seam.py -k "papeis or allowlist" -v
uv run pytest packages/core/tests/bootstrap/integration -k providers_por_papel -v
```

Esperado: com `controller: openrouter/qwen/qwen3-8b` e `generation: ollama/qwen3:1.7b`, o trace da execução `agentic`
tem a chamada de controller no `openrouter` e a de geração no `ollama`; `allow: ["ollama/*"]` com papel em `openai/…`
→ `ModelNotAllowed`.

## Com os providers reais (opcional, pago)

```bash
AI_CORE_OPENROUTER_API_KEY=… OPENROUTER_MODEL=~z-ai/glm-flash-latest \
  uv run pytest packages/core/tests/llm/integration/test_remote_real.py -v
AI_CORE_OPENAI_API_KEY=… OPENAI_MODEL=gpt-4o-mini \
  uv run pytest packages/core/tests/llm/integration/test_remote_real.py -k openai -v
```

Esperado: o controller com um esquema de ação de raiz objeto recebe JSON parseável segundo o esquema (Independent Test
da US4); `probe` confirma o modelo e nega um inexistente. Sem as variáveis, os testes são pulados.

O modelo precisa anunciar `structured_outputs` no OpenRouter (`GET https://openrouter.ai/api/v1/models`,
`supported_parameters`): com `require_parameters`, um modelo sem ele é recusado com 404 "No endpoints found that can
handle the requested parameters" — é a FR-005 funcionando. Em 2026-10-07, `qwen/qwen3-8b` (o default anterior) e as
variantes `:free` do Gemma 4 não o anunciavam; `~z-ai/glm-flash-latest` passou nos dois testes reais (este e o
`agentic` da 010). Em 2026-10-07, com o subconjunto estrito (ADR-023), `openai/gpt-4.1-nano` via OpenRouter também passou
nos dois — a OpenAI serve de controller do `agentic`.

## Como a 011 monta (perfis `memory` e `persistent`)

```python
secrets = EnvSecretResolver()                      # porta llm_secrets
providers = {
    "ollama": OllamaProvider(base_url=settings.ollama_base_url),
    "openai": OpenAIProvider(secrets=secrets),
    "openrouter": OpenRouterProvider(secrets=secrets),
}
```

No perfil `test`, `llm_secrets` é um `InMemorySecretResolver()` vazio e os providers continuam o simulado `ollama`; a
suíte que precisa de outros nomes troca a porta `providers`.
