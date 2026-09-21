# Quickstart — 005 Execution Engine (Fase 1, US1)

Guia de validação. Todos os comandos rodam a partir de `ai-core/`. Nesta máquina, prefixe `uv` com
`XDG_DATA_HOME=$HOME/.local/share` (ver CLAUDE.md).

## Pré-requisitos

```bash
uv sync                      # traz langgraph>=1.2,<2 (nova dependência da distribuição ai-core)
```

Nada mais: a suíte **não** fala com rede nem exige Ollama — só o modelo é simulado, e packs, hooks e grafo são os de
verdade ([research.md](research.md) R13).

## Verificação completa

```bash
uv run pytest                                  # inclui packages/core/tests/graph
uv run mypy
uv run ruff check packages
uv run lint-imports                            # prende o framework de grafo a adapters/langgraph/
```

O `lint-imports` é o que prova, de forma executável, a promessa do ADR-011: `langgraph` e `langchain_core` não
aparecem em `api.py`, `domain/`, `ports.py` nem `service.py` — nem em nenhum outro módulo do core.

## Cenários da US1

### 1. Conversa em streaming (cenário 1)

```bash
uv run pytest packages/core/tests/graph/contract/test_execution_engine_seam.py -k streaming -v
```

Esperado: os eventos saem em ordem — progresso de preparação, vários `TokenEvent` incrementais, progresso de validação
e um `FinalEvent` com a resposta. O teste verifica que o primeiro token é observado **antes** de o nó de geração
terminar: é isso que sustenta SC-004.

### 2. Requisição inválida e flow inexistente (cenário 2)

```bash
uv run pytest packages/core/tests/graph/contract/test_execution_engine_seam.py -k invalid -v
```

Esperado: `ExecutionRequestInvalid` e `UnknownFlow` levantados na **chamada** de `run`, sem nenhum evento emitido e sem
nenhuma chamada ao provider simulado — é o que permite à 008 responder 4xx antes de abrir o SSE.

### 3. Validator que altera a resposta (cenário 3)

```bash
uv run pytest packages/core/tests/graph/contract/test_execution_engine_seam.py -k validator -v
```

Esperado: o `FinalEvent` traz a resposta modificada pelo validator, as citações que ele encadeou e um `ExecutionIssue`
por `issue` reportada.

### 4. Caminho completo com o pack de referência

```bash
uv run pytest packages/core/tests/graph/integration -v
```

Esperado: o Pack Runtime real carrega o `ai-generic` pelo entry point, o `prompt` geral do pack entra como mensagem de
sistema, o validator `non_empty_answer` roda, e o trace da requisição tem começo, `ValidationRun` e fim. É o
"Independent Test" que a US1 descreve.

## Como a 008 e a 011 consomem

```python
# 011, no boot: uma vez por processo
engine = ExecutionService(
    flows=chat_registry(),          # nomes de flow → grafos compilados
    hooks=pack_runtime,             # seam Pack Hooks (002)
    routing=model_routing,          # seam Model Router (006)
    trace=trace_service,            # seam Trace Sink (009)
    clock=SystemClock(),
)

# 008, por requisição
try:
    events = engine.run(grant, ExecutionRequest(messages=messages))
except ExecutionRequestInvalid as error:
    return http_400(str(error))     # nada foi emitido, nada custou
async for event in events:
    ...                             # TokenEvent → delta SSE; FinalEvent → fecha o stream
```

O `grant` é qualquer objeto com `assistant`, `flow`, `composition` e `models`. Na Fase 1 quem o monta é a 011; na Fase
2, a 003 — sem mudar nada aqui.

## Trocar o grafo (SC-001)

Para provar que a promessa vale, o exercício é: apagar `adapters/langgraph/`, escrever outro adapter que produza os
mesmos eventos e rodar `uv run pytest packages/core/tests/graph/contract packages/core/tests/graph/unit`. As suítes do
seam e de `domain/` passam sem alteração; só os testes em `tests/graph/unit/test_state_view.py`, que são do adapter,
acompanham a troca.
