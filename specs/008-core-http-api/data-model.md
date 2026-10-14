# Data model — 008 HTTP API (Fase 1)

Este módulo não publica seam Python: o que ele expõe é a superfície HTTP. Os tipos abaixo são internos — ou formas
que ele **exige** de outro módulo, declaradas como `Protocol` para que a 003 as satisfaça na Fase 2 sem import.

## O que chega

### Corpo aceito em `POST /{surface}/chat/completions`

| Campo | Tipo | Regra |
|---|---|---|
| `model` | `str` | obrigatório; `"<assistant>"` ou `"<assistant>/<modelo>"` — a parte do modelo é opcional e, ausente, usa o default do Assistant |
| `messages` | lista de `{role, content}` | obrigatória, não vazia; ao menos uma de papel `user` |
| `stream` | `bool` | default `false`, como na OpenAI |

Campos de amostragem (`temperature`, `top_p`, `max_tokens`) são aceitos e **ignorados** nesta fase: entram com os
limites do Assistant, na Fase 2. Qualquer campo de ampliação de capacidade é rejeitado — ver "Rejeições".

### Rejeições (antes de qualquer execução)

| Campo na requisição | Resposta | Origem |
|---|---|---|
| `tools`, `functions`, `tool_choice`, `function_call` | 400 nomeando o campo | princípio IV, edge case da spec |
| `reference_time` (ou qualquer nome de data de referência) | 400 nomeando o campo | FR-012, ADR-013 |
| `messages` vazio ou sem mensagem de usuário | 400 | 005 FR-013 |
| `model` ausente ou vazio | 400 | — |

## O que este módulo exige de fora (`ports.py`)

```python
class Principal(Protocol):
    @property
    def id(self) -> str: ...

class Authenticator(Protocol):
    async def authenticate(self, *, surface: str, credential: str | None) -> Principal | None: ...

class GrantResolver(Protocol):
    async def resolve(self, *, model: str, principal: Principal) -> ExecutionGrant: ...   # levanta AssistantNotFound

class RequestIds(Protocol):
    def next(self) -> str: ...
```

`ExecutionGrant` é o `Protocol` da 005. `surface` é `"public"` ou `"private"`. `authenticate` devolvendo `None`
significa credencial inválida → 401. `AssistantNotFound` → **404**, igual para inexistente e para não autorizado
(FR-009, regra 404-não-403 da 003).

**Adapters desta fase** (`adapters/development.py`): `AnonymousAuthenticator`, que devolve sempre o mesmo Principal de
desenvolvimento e diz isso no nome, e `Uuid4RequestIds`; nos testes, `SequentialRequestIds`.

## O que sai

### Sem streaming — objeto `chat.completion`

| Campo | Valor |
|---|---|
| `id` | `chatcmpl-<request_id>` |
| `object` | `"chat.completion"` |
| `created` | instante, em segundos |
| `model` | o id pedido, como veio |
| `choices[0].message` | `{"role": "assistant", "content": <resposta final>}` |
| `choices[0].finish_reason` | `"stop"`, ou `"error"` quando o evento final traz erro de execução |
| `x_ai_core` | campo extra: citações, marcações e erros do evento final |

Cabeçalho `X-Request-Id` com o identificador do trace, sempre (FR-010).

### Com streaming — sequência de `chat.completion.chunk`

1. **primeiro chunk**: `delta = {"role": "assistant"}`, sem conteúdo — é o que os clientes esperam para abrir a
   mensagem;
2. **progresso**: `delta = {}` e `x_ai_core.progress = {"stage": …}` — clientes padrão ignoram (R5);
3. **token**: `delta = {"content": <pedaço>}`, um chunk por pedaço, escrito na hora;
4. **chunk final**: `delta = {}`, `finish_reason` e `x_ai_core` com citações, marcações e erros;
5. `data: [DONE]`.

Todo chunk repete `id`, `object`, `created` e `model`.

## Modos de falha

| Situação | Resultado |
|---|---|
| Campo de ampliação ou data de referência no corpo | 400 nomeando o campo, antes de qualquer execução |
| Corpo malformado (sem `model`, sem mensagem de usuário) | 400 |
| Credencial inválida na superfície | 401 |
| Assistant inexistente **ou** não autorizado | 404, com o mesmo corpo nos dois casos (FR-009) |
| Motor levanta antes do primeiro evento (`ExecutionRequestInvalid`, `UnknownFlow`) | 400 nomeando o problema; nada foi executado |
| Execução falha depois do stream aberto | chunk final com `finish_reason="error"`, motivos em `x_ai_core.errors`, e `[DONE]`; conexão fecha limpa (R6) |
| Execução falha sem streaming | **502** com os motivos e o texto parcial no corpo. Sem streaming ainda dá para escolher o status, e 200 com marcador de erro seria degradação silenciosa, que o princípio VII proíbe — em streaming o 200 já foi enviado e o chunk com desfecho de erro é o melhor possível |
| Cliente desconecta no meio do stream | o iterador do motor é fechado e a execução cancelada (005) |

---

# Fase 2 (2026-09-30)

Os tipos de Principal, grant e erros de acesso agora são da 003 (`ai_core.assistants.api`, research R13). Os tipos
abaixo são desta spec: os de armazenamento em `ports.py`, os de formato em `domain/`.

## Conversa (US7)

### `Conversation`

| Campo | Tipo | Regra |
|---|---|---|
| `id` | `str` | `conv_<hex>`, gerado pela porta `RequestIds` (instância própria) |
| `owner` | `str` | subject do Principal (clarificação 3); o mesmo subject a alcança pelas duas superfícies |
| `assistant` | `str` | nome resolvido (`geral`, `~meu-rag`); a conversa só continua com o mesmo Assistant |
| `model` | `str` | o id pedido na abertura (`geral`, `geral/ollama/qwen3:8b`) |
| `created_at`, `last_activity_at` | `datetime` | da porta `Clock`; a expiração usa `last_activity_at` |
| `message_count` | `int` | mensagens gravadas |

### `StoredMessage`

| Campo | Tipo | Regra |
|---|---|---|
| `role` | `"user" \| "assistant"` | só esses dois são gravados |
| `content` | `str` | texto da mensagem |
| `at` | `datetime` | da porta `Clock` |
| `request_id` | `str` | a requisição que a produziu (liga a conversa ao trace, 009) |
| `citations` | `tuple[JSONValue, ...]` | nas respostas: as citações do `FinalEvent` |
| `flags` | `tuple[str, ...]` | nas respostas: as marcações do `FinalEvent` |

`ConversationPage(items: tuple[Conversation, ...], next_cursor: str | None)` — listagem por última atividade, mais
recente primeiro; o cursor é opaco.

**Ciclo de vida**: `aberta` (antes da primeira execução) → `com trocas` (a cada evento final sem erro) → `apagada`
(pelo dono, ou pela expiração após o prazo sem atividade). Apagada é terminal: listagem, leitura e continuação
respondem 404 (FR-018).

## Saúde (US5)

`HealthReport(ok: bool, items: tuple[HealthItem, ...])`, `HealthItem(name: str, ok: bool, detail: str | None)`. Montado
fora do módulo (011); a API só o serializa (200 se `ok`, 503 se não).

## Formatos de fio

- **Entrada da listagem de modelos** (R16): `{"id": "<assistant>", "object": "model", "created": <epoch>, "owned_by":
  "system" | "<subject>", "x_ai_core": {"generation": "ollama/qwen3:1.7b", "description": …, "origin": "system" |
  "user", "allow": […]}}`.
- **Requisição nativa** (R17): `{"assistant", "model"?, "messages", "stream"?, "conversation_id"?}` — nada além disso.
- **Rascunho de Assistant de usuário** (R19): os campos do `UserAssistantDraft` da 003, com `models` como
  `{"generation": "ollama/qwen3:1.7b", …}` e `limits` opcional.
- **Envelope de erro** (R14): `{"error": {"message", "type", "param", "code"}}`, com `x_ai_core.reasons` no 424.

---

## Fase 3 (2026-10-02): MCP e desfecho por gravidade (research R25–R32)

### `create_app` — parâmetro novo

`mcp: McpRegistry | None = None` — o seam da 007; sem ele, as rotas de MCP não são montadas.

### Corpo de servidor MCP (`domain/mcp_body.py`)

`draft_from_json(body, *, scope, alias=None) -> McpServerDraft`: a forma do `mcp.yaml` (007) — `alias`, `transport`,
`endpoint`, `description`, `auth: {type, credential}`, `enabled`, `user_access`, `policy: {allowed_tools, write_tools,
timeout_ms, max_response_bytes}`; chave desconhecida → `InvalidRequest` nomeando o campo; `alias` do caminho prevalece e,
no escopo de usuário, ganha `~` se vier sem. `server_json(McpServer)`, `summary_json(McpSummary)` e
`health_json(ServerHealth)` — nunca com valor de credencial, só o nome da referência. Formatos em
[contracts/mcp-routes.md](contracts/mcp-routes.md).

### Desfecho

| Registros do `FinalEvent` | Stream | Sem streaming |
|---|---|---|
| nenhum, ou só `notice` | `finish_reason: "stop"` | 200 |
| algum `error` | `finish_reason: "error"` | 502 + `x-should-retry: false` |

`VALIDATOR_ISSUE` sai de `domain/openai_chunks.py`: a API não conhece mais `kind` nenhum da 005.

## Fase 7 (2026-10-13): fila, progresso como raciocínio e pedido efêmero (research R33–R41)

### `AdmissionLimits` (`domain/admission.py`)

| Campo | Tipo | Regra |
|---|---|---|
| `max_executions` | `int` | 1–64 (`AI_CORE_MAX_EXECUTIONS`; provisório 2) |
| `queue_size` | `int` | 0–1000; 0 = sem fila (`AI_CORE_QUEUE_SIZE`; provisório 8) |
| `max_wait` | `timedelta` | 1 ms–600 s (`AI_CORE_QUEUE_WAIT_MS`; provisório 60 s); para não esperar, `queue_size = 0` |

`decide(running, queued, limits)` → `"run"` se `running < max_executions`; `"queue"` se `queued < queue_size`; senão
`"reject"`. `retry_after(limits)` → `max(1, ceil(max_wait em segundos))`.

### `ExecutionSlots` (`service.py`)

Estado em memória, por processo: execuções em andamento e uma fila FIFO de quem espera. Transições de um pedido:

```text
admitido ──────────────────────────────→ executando ──(evento final | iterador fechado)──→ liberado
   └─ na fila ──(vaga liberada, primeiro da fila)──↗
        ├─ espera esgotada ──→ recusado (503 sem streaming; finish_reason "error" + QueueTimeout no stream)
        └─ cliente desconectou ──→ fora da fila (não ocupa vaga)
recusado (vagas e fila cheias) ──→ 503 + Retry-After, antes de abrir o stream
```

### `ChatRequest` — campo novo

| Campo | Tipo | Regra |
|---|---|---|
| `store` | `bool` | default `True`; `False` com `x-ai-core-store: false` e sem `conversation_id` (FR-023) |

### Linhas de progresso (`domain/progress_text.py`)

`progress_line(stage, detail) -> str`: a tabela da R34 (estágios publicados pela 005), `Etapa {stage}…` para os demais;
`queue_line(position) -> str`. O chunk de progresso leva `delta.reasoning_content = linha + "\n"` só antes do primeiro
token; depois, `delta: {}` como antes.

### Erros novos

| Causa | Status | `type` | `code` | `param` |
|---|---|---|---|---|
| vagas e fila cheias, ou espera esgotada sem streaming | 503 + `Retry-After` | `server_error` | `overloaded` | — |
| `x-ai-core-store: false` com `conversation_id` | 400 | `invalid_request_error` | `store_conflict` | `x-ai-core-store` |
| `x-ai-core-store` com valor diferente de `true`/`false` | 400 | `invalid_request_error` | `invalid_header` | `x-ai-core-store` |

No stream já aberto, a espera esgotada vira o registro `{"stage": "admission", "kind": "QueueTimeout", "message": …}` no
`x_ai_core.errors` do chunk final, com `finish_reason: "error"`.

## Timeline de status (2026-10-13, FR-005a; research R42)

### `ChatRequest` — campo novo

| Campo | Tipo | Regra |
|---|---|---|
| `progress` | `"reasoning" \| "status"` | default `"reasoning"`; do cabeçalho `x-ai-core-progress`, nas duas entradas |

### `domain/timeline.py`

`Status(description, done)` e `Timeline(started_at)` com `queued(position)`, `started(event, at)`,
`finished(event, at)` e `final(event, at)`. O tempo vem de quem chama (o `Clock` do serviço). O início de etapa guardado
é retirado no fim, então um fim sem início sai sem tempo. As linhas estão na R42.

### Erro novo

| Causa | Status | `type` | `code` | `param` |
|---|---|---|---|---|
| `x-ai-core-progress` com valor diferente de `reasoning`/`status` | 400 | `invalid_request_error` | `invalid_header` | `x-ai-core-progress` |
