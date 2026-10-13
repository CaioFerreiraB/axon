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

---

## Fase 2 (US2, US3, US4, US5, US7)

Comandos a partir de `ai-core/`. Para a conformidade da `ConversationStore` contra Postgres, defina
`AI_CORE_TEST_POSTGRES_DSN` como no quickstart da 003.

```bash
uv run pytest packages/core/tests/http -v
```

| Cenário | Suíte | Esperado |
|---|---|---|
| Listagem de modelos (US2) | `contract/test_models_route.py` | listas diferem exatamente pela ACL; id curto; o id listado resolve no chat |
| Requisição nativa (US3) | `contract/test_native_route.py` | `mcp_servers`, `packs`, `tools`, `provider` recusados nomeando o campo, antes de executar |
| Assistants de usuário (US4) | `contract/test_user_assistants_routes.py` | CRUD completo; outro usuário recebe 404; criado aparece em `/v1/models` |
| Superfície privada (US5) | `contract/test_private_routes.py` | packs e chaves só para o grupo de administração (404 para os demais); saúde com qualquer chave, 503 quando degradada |
| Conversas (US7) | `contract/test_conversation_routes.py`, `integration/test_conversation_restart.py`, `unit/test_conversation_expiry.py` | continuação pelo id nas duas superfícies; reinício preserva o histórico; mensagem de assistente do cliente nunca entra; exclusão e expiração tornam o id 404 |
| Erros (R14) | `unit/test_errors.py` e todas as rotas | envelope da OpenAI; 424 para indisponível; 429 com `Retry-After` |
| Plataforma inteira (011, perfil `test`) | `uv run pytest packages/core/tests/bootstrap` | a conversa ponta a ponta continua funcionando com os serviços da 003 e o autenticador anônimo |

## Fase 3 (2026-10-02): MCP e desfecho por gravidade

```bash
uv run pytest packages/core/tests/http -m "us4 or us5 or us6" -v
```

Esperado ([contracts/mcp-routes.md](contracts/mcp-routes.md), itens 1–7, e [contracts/errors.md](contracts/errors.md),
"Fase 3"): CRUD de MCP do usuário isolado por dono; globais só para o grupo de administração (404 para os demais); MCP
próprio + Assistant que o usa aparece em `/v1/models`; execução só com `notice` → 200 `stop`; com `error` → 502 e
`x-should-retry: false`; progresso de `execute_tool` com o nome da tool no stream.

Pela plataforma (perfil `test`), com a chave de teste do grupo de administração:

```bash
curl -s -X POST localhost:8000/private/v1/mcp -H "Authorization: Bearer $TEST_API_KEY" \
  -H 'content-type: application/json' \
  -d '{"alias":"demo","transport":"http","endpoint":"https://demo.test/mcp","policy":{"allowed_tools":["eco"]}}'
curl -s localhost:8000/private/v1/mcp -H "Authorization: Bearer $TEST_API_KEY" | jq '.data[].alias'
```

Esperado: 201 e depois `"demo"` na listagem; sem servidor programado, `GET /private/v1/mcp/demo/health` responde `ok:
false` com o motivo.

## Fase 7 (2026-10-13): progresso, fila e Open WebUI (US6, US8)

Contratos: [admission.md](contracts/admission.md), [open-webui.md](contracts/open-webui.md), as seções "Fase 7" de
[sse-format.md](contracts/sse-format.md), [errors.md](contracts/errors.md) e
[chat-completions.md](contracts/chat-completions.md). A partir de `ai-core/`:

```bash
uv run pytest packages/core/tests/http -m "us6 or us8"
```

**Raciocínio no stream.** Com `ai-core serve` no perfil `memory` e um Ollama local, um pedido em streaming a um
Assistant `rag_first` mostra, antes do texto, chunks com `delta.reasoning_content` ("Preparando o contexto da
pergunta…", "Consultando os documentos…", "Escrevendo a resposta…"); nenhum deles depois do primeiro `delta.content`.

**Fila.** Com `AI_CORE_MAX_EXECUTIONS=1 AI_CORE_QUEUE_SIZE=1 AI_CORE_QUEUE_WAIT_MS=30000`, três pedidos simultâneos em
streaming: o primeiro executa, o segundo recebe "Aguardando uma vaga (posição 1 na fila)…" no início e executa depois,
o terceiro recebe 503 `overloaded` com `Retry-After: 30`.

**Pedido efêmero.** O mesmo pedido com `-H 'x-ai-core-store: false'` responde sem `conversation_id`, e
`GET /v1/conversations` não muda.

**Medição (R36), 2026-10-13 — com OpenRouter, por decisão do mantenedor** (o suporte ao Ollama local fica para
depois). `ai-core serve` no perfil `memory` (Ryzen 7 7700, 16 threads, 14 GB), Assistant `conversa` (flow `chat`,
`ai-generic`), geração `openrouter/~z-ai/glm-flash-latest`, pergunta curta, streaming, `x-ai-core-store: false`, 3
rodadas por caso, `AI_CORE_MAX_EXECUTIONS=4`:

| Simultâneas | Primeiro texto (p50 / máx) | Total (p50 / máx) |
|---|---|---|
| 1 | 2,31 s / 2,43 s | 3,54 s / 3,59 s |
| 2 | 1,83 s / 2,54 s | 3,12 s / 3,49 s |
| 4 | 1,66 s / 2,09 s | 2,68 s / 3,14 s |

Com o modelo remoto, a concorrência não degrada nada: a plataforma não é o gargalo, o provider é. A primeira linha de
raciocínio sai em 0,01–0,02 s (SC-003). Os defaults ficam nos provisórios **2 / 8 / 60 s** — o que limita execuções é
o modelo local, e a medição com o Ollama no hardware alvo os confirma ou troca quando o suporte vier.

**Fila de verdade**, mesmo servidor com `AI_CORE_MAX_EXECUTIONS=1 AI_CORE_QUEUE_SIZE=1 AI_CORE_QUEUE_WAIT_MS=30000`,
três pedidos simultâneos: o 1º executou (primeiro texto em 2,1 s); o 2º recebeu "Aguardando uma vaga (posição 1 na
fila)…" em 0,01 s, ganhou a vaga em 3,35 s e terminou em 7,1 s; o 3º recebeu 503 `overloaded` com `Retry-After: 30`.

**Open WebUI.** A prova com a interface é da passada de encaixe da 002 ([open-webui.md](contracts/open-webui.md),
verificação 3): Keycloak de desenvolvimento com dois usuários de grupos diferentes, cada um vê só os próprios
Assistants e conversa em streaming; o trace mostra uma execução por mensagem.

*Resultado de 2026-10-13* (`agentic-deploy`, perfil `webui`, `scripts/check-webui.py`): login OIDC de verdade pelo
formulário do Keycloak; a `ana` vê `geral` e `scouting`, a `bia` (grupo `equipe`) vê também `interno`; uma mensagem pelo
Open WebUI virou exatamente um `POST /v1/chat/completions` na plataforma, sem tarefa auxiliar e sem conversa gravada. Em
streaming pelo próprio Open WebUI, a pergunta "Quando foi fundada a União dos Escoteiros do Brasil?" ao `scouting`
trouxe o raciocínio "Preparando o contexto da pergunta…", "Consultando os documentos…", "Ordenando os trechos
encontrados…", "Conferindo se os trechos cobrem a pergunta…", "Escrevendo a resposta…" e a resposta com citações do
Estatuto e do POR. A prova achou um defeito na 003 — a chave de cifragem do JWKS do Keycloak fazia o verificador
descartar todas as chaves — corrigido no core `v0.4.1` (003 research R24).
