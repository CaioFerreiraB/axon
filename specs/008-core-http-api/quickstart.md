# Quickstart — 008 HTTP API (Fase 1, US1)

Guia de validação. Todos os comandos rodam a partir de `ai-core/`. Nesta máquina, prefixe `uv` com
`XDG_DATA_HOME=$HOME/.local/share` (ver CLAUDE.md).

## Pré-requisitos

```bash
uv sync                      # traz fastapi>=0.141,<1 e, no grupo de desenvolvimento, o cliente de teste
```

A suíte **não** abre porta TCP nem fala com rede: a app é montada em processo e exercitada pelo cliente de teste do
framework, com o motor real, o Pack Runtime real, o `ai-generic` e o provider simulado da 006
([research.md](research.md) R10).

## Verificação completa

```bash
uv run pytest                                  # inclui packages/core/tests/http
uv run mypy
uv run ruff check packages
uv run lint-imports                            # prende o framework HTTP a adapters/
```

## Cenários da US1

### 1. Streaming (cenário 1)

```bash
uv run pytest packages/core/tests/http/contract/test_chat_completions.py -k streaming -v
```

Esperado: `Content-Type: text/event-stream`; o primeiro chunk traz o papel, cada pedaço da resposta vira um chunk com
`delta.content`, o chunk final traz `finish_reason` e o stream termina com `data: [DONE]`.

### 2. Sem streaming (cenário 2)

```bash
uv run pytest packages/core/tests/http/contract/test_chat_completions.py -k complet -v
```

Esperado: um objeto `chat.completion` com a resposta inteira em `choices[0].message.content`.

### 3. Rejeições antes de qualquer execução

```bash
uv run pytest packages/core/tests/http/contract/test_chat_completions.py -k rejeit -v
```

Esperado: 400 nomeando o campo para `tools`, `functions` e para o campo de data de referência — e o provider simulado
sem nenhuma chamada registrada.

### 4. Conversa ponta a ponta só via HTTP (SC-002)

```bash
uv run pytest packages/core/tests/http/integration -v
```

Esperado: uma requisição HTTP atravessa API, motor, Pack Runtime e Model Router; o prompt do `ai-generic` entra como
mensagem de sistema, o validator do pack roda, e o trace da requisição — recuperado pelo identificador do cabeçalho —
tem começo, chamada de modelo, validação e fim.

## Conversando de verdade (opcional)

Com a composition root ainda por vir (011), o jeito de subir a app é montá-la em processo:

```python
from ai_core.http.adapters.app import create_app
app = create_app(engine=engine, authenticator=..., grants=..., request_ids=...)
# uvicorn app --port 8000
```

```bash
curl -N http://localhost:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model": "geral", "messages": [{"role": "user", "content": "oi"}], "stream": true}'
```

Esperado: os pedaços chegando um a um, e `data: [DONE]` no fim. Com um Ollama de verdade atrás do Model Router, é a
conversa ponta a ponta da Fase 1. A forma definitiva de subir o serviço (`ai-core serve`) é da 011.

## Compatibilidade (SC-004)

A prova de que clientes OpenAI padrão funcionam sem adaptação está na suíte — um `AsyncOpenAI` de verdade apontado
para a app em processo, pelo transporte ASGI do cliente HTTP do SDK:

```bash
uv run pytest packages/core/tests/http/integration/test_openai_sdk_client.py -v
```

Esperado: o SDK conversa com e sem streaming, lê o papel só no primeiro chunk, o desfecho só no último, e traduz 404
em erro de "não encontrado". Nenhuma porta aberta.

Com um servidor no ar, o mesmo exercício é manual:

```python
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="nao-usado")
for chunk in client.chat.completions.create(model="geral", messages=[...], stream=True):
    print(chunk.choices[0].delta.content or "", end="")
```

O SDK já está no ambiente (é o adapter da 006), o que torna esse exercício barato quando houver um servidor no ar.
