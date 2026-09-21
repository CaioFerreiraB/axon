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
