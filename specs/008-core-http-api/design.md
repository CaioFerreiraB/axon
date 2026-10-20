# Design — 008 HTTP API

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §25, §28; ADR-002, ADR-012, ADR-013.

## Localização

```text
axon-ai/packages/core/src/axon_ai/http/
├── ports.py          # ConversationStore, HealthProvider, Clock
├── service.py        # histórico de conversa (domínio da aplicação, não do motor)
└── adapters/         # a camada HTTP inteira é adapter primário
    ├── app.py                   # fábrica da app FastAPI, chamada pela composition root (011)
    ├── auth.py                  # dependências FastAPI → Authenticator (003)
    ├── public.py                # /v1 (OIDC)
    ├── private.py               # /private/v1 (API key)
    ├── openai_compat.py         # chat completions, models
    ├── sse.py                   # ExecutionEvent → chunk SSE OpenAI
    ├── conversations_memory.py  # ConversationStore — Fase 1 e testes
    └── conversations_postgres.py  # ConversationStore — Fase 2
```

O pacote era `axon_ai/api/`; virou `axon_ai/http/` para não colidir com a convenção `api.py` (ADR-012). Este módulo
não tem `api.py`: seu seam é a própria API HTTP, consumida por clientes externos.

## Duas superfícies

```http
# Pública — OIDC
GET  /v1/models                      # assistants visíveis ao Principal
POST /v1/chat/completions            # compat OpenAI, streaming SSE
GET    /v1/conversations             # conversas do próprio Principal
GET    /v1/conversations/{id}        # estado + mensagens
DELETE /v1/conversations/{id}        # exclusão definitiva
GET  /v1/assistants
POST /v1/assistants                  # assistants de usuário
GET  /v1/mcp-servers                 # MCPs do próprio usuário
POST /v1/mcp-servers

# Privada — API key
POST /private/v1/chat/completions
GET    /private/v1/conversations     # conversas do dono da chave
GET    /private/v1/conversations/{id}
DELETE /private/v1/conversations/{id}
GET  /private/v1/packs
POST /private/v1/admin/mcp-servers   # MCPs globais
GET  /private/v1/health
```

```python
# adapters/app.py e adapters/auth.py — a verificação em si é da 003 (Authenticator)
app.include_router(public,  prefix="/v1",         dependencies=[Depends(oidc)])      # oidc → authenticator.authenticate("public", token)
app.include_router(private, prefix="/private/v1", dependencies=[Depends(api_key)])   # api_key → authenticator.authenticate("private", key)
```

## Compatibilidade OpenAI e Open WebUI

Open WebUI fala o formato da API da OpenAI. O encaixe é expor **cada Assistant como um "model"**:

```json
GET /v1/models
{"data": [
  {"id": "scouting/qwen3:1.7b",         "object": "model"},
  {"id": "scouting_finance/qwen3:1.7b", "object": "model"}
]}
```

A listagem já vem filtrada pela ACL (spec 003) — assistants privados não aparecem.

## Streaming

Não é opcional e não é retrofit. O motor (005) emite eventos neutros; a API os traduz:

```text
TokenEvent    → chunk SSE OpenAI (delta.content)
ProgressEvent → chunk SSE com metadado extra (ignorado por clientes padrão)
FinalEvent    → chunk final + [DONE]
```

## Admissão e fila (clarificação 2026-09-14 — FR-016, FR-017)

```text
requisição autenticada e resolvida (003)
  ├─ vaga livre               → executa (ocupa a vaga até o FinalEvent)
  ├─ vagas cheias, fila livre → entra na fila; em streaming, evento "na fila" em ≤ 2 s
  │                               └─ espera > máximo → 503 + Retry-After
  └─ vagas e fila cheias      → 503 + Retry-After (antes de qualquer chamada de modelo)
```

- A decisão (executar, enfileirar, recusar) é função pura em `domain/`, a partir de vagas ocupadas, tamanho da fila e
  configuração. O semáforo e a fila ficam em memória, no `service.py` (processo único na v1; não há I/O, portanto não
  há porta).
- 429 continua sendo o limite por minuto da 003 para o par (Principal, Assistant); 503 é sobrecarga da plataforma.
- Cliente que desconecta na fila sai dela sem ocupar vaga. A ordem é de chegada.
- Limite, tamanho da fila e espera máxima vêm da configuração do operador (011); os valores iniciais são medidos no
  hardware alvo durante o plano.

## Requisição nativa

```json
{
  "assistant": "scouting",
  "messages": [
    {"role": "user", "content": "Quais competências do Ramo Pioneiro se relacionam à liderança?"}
  ],
  "stream": true
}
```

O que **não** está aqui: `mcp_servers`, `packs`, `provider`. Tudo isso vem do Assistant. A requisição pode, no máximo, restringir.

## Conversas no servidor (clarificação 2026-09-14 — FR-008, FR-013 a FR-015)

```json
{
  "assistant": "scouting",
  "conversation_id": "c_01J…",        // opcional; sem ele, abre conversa nova
  "messages": [{"role": "user", "content": "E para o Ramo Sênior?"}],
  "stream": true
}
```

- **Compat OpenAI**: o mesmo `conversation_id` vai como campo extra do corpo (os SDKs OpenAI o enviam por
  `extra_body`). A resposta devolve o id no cabeçalho `X-Conversation-Id` e num campo extra do objeto de resposta
  (no primeiro chunk, em streaming). Nomes finais fixados no plano.
- **Com `conversation_id`**: o histórico armazenado é a fonte de verdade. `service.py` carrega as mensagens da conversa
  pela porta `ConversationStore`, acrescenta a última mensagem de usuário da requisição e monta o `ExecutionRequest`.
  Mensagens de assistente ou de tool vindas do cliente são descartadas.
- **Sem `conversation_id`**: comportamento padrão OpenAI — a execução usa as mensagens da requisição, e o serviço cria
  uma conversa nova com essa troca.
- **Ao fim da execução**: grava a mensagem do usuário e a resposta (com citações, marcações e `request_id` do evento
  final) e atualiza a data de última atividade.
- **Isolamento**: conversa de outro Principal ou inexistente → 404 (mesma regra da 003); conversa usada com outro
  Assistant → erro explícito antes da execução.

```python
class ConversationStore(Protocol):     # ports.py
    async def create(self, principal: str, assistant: str, model: str) -> Conversation: ...
    async def get(self, principal: str, conversation_id: str) -> Conversation | None: ...   # None → 404
    async def append(self, conversation_id: str, messages: Sequence[Message]) -> None: ...
    async def list(self, principal: str, *, limit: int, cursor: str | None) -> Page[ConversationSummary]: ...
    async def delete(self, principal: str, conversation_id: str) -> bool: ...                # False → 404
    async def delete_inactive(self, before: datetime) -> int: ...                           # expiração
```

**Exclusão e retenção (clarificação 2026-09-14 — FR-018, FR-019):** a exclusão pelo usuário é definitiva (estado e
mensagens). A expiração roda periodicamente no próprio processo — agendada no boot pela composition root (011) — e
apaga conversas cuja última atividade é anterior a `agora − prazo`. `agora` vem da porta `Clock` (princípio XIII), o
que torna a expiração testável com relógio fixo. O prazo padrão é de 180 dias, configurável pelo operador. Os traces
(009) seguem a retenção própria.

## Superfície de administração (Fase 9, [ADR-031](../../docs/adr/ADR-031-superficie-de-administracao.md))

`/admin/v1`, montada por `adapters/admin.py`; a forma dos pedidos e respostas fica em `domain/admin_*.py` (puro). Cada
rota é uma tradução fina para um seam do módulo dono — nenhuma regra mora aqui (ADR-029).

| Rota | Seam (dono) |
|---|---|
| `GET /me` | Principal (003) |
| `GET /assistants`, `GET /assistants/{nome}` | System Assistant Admin (003) |
| `PUT /assistants/{nome}/models`, `PUT /assistants/{nome}/mcp` (com `If-Match`), `DELETE /assistants/{nome}/overrides/{seção}` | System Assistant Admin (003) |
| `POST /assistants/{nome}/models/check` | Model Router `check(policy)` (006) |
| `GET/POST /mcp`, `GET/PUT/DELETE /mcp/{alias}`, `GET /mcp/{alias}/health` | MCP Registry (007) — o mesmo router da superfície privada, montado nas duas |
| `GET /usage?from&to&tz&by=model\|assistant&origin=production\|evaluation\|all` | Usage Report (009) |
| `GET /prices`, `PUT /prices` | Price Book (009) |
| `GET /observability`, `PUT /observability/langfuse`, `PUT /observability/capture`, `POST /observability/langfuse/test` | Trace Destinations (009) |
| `GET /prices/unpriced` | Price Book (009) |
| `GET /assistants/{nome}/history` | System Assistant Admin (003) |
| `GET/POST /users`, `PATCH /users/{nome}`, `POST /users/{nome}/password`, `POST /users/{nome}/disable`, `POST /users/{nome}/enable`, `DELETE /users/{nome}/google` | Account Admin (012) |
| `GET/POST /groups`, `DELETE /groups/{nome}`, `PUT /groups/{nome}/members` | Account Admin (012) |
| `GET/PUT /login-settings` | Login Settings (012) |
| `GET /keys`, `POST /keys`, `DELETE /keys/{id}` | API Key Admin (003) |
| `GET /health` | `HealthProvider` (011) |

- Autenticação por `authenticated(request, surface="admin")`; 401 para credencial inválida, 404 para não admin (porta
  `AdminGate`, agora `admin_group in groups`).
- Versão lida no corpo das escritas de recursos versionados (`version`; no `DELETE`, na query) — uma por seção de
  sobreposição (research R45); 409 com a versão atual.
- Sem CORS: a console chega pela mesma origem (o servidor estático repassa os prefixos sem reescrever — 013).
- O contrato `contracts/admin-api.md` (escrito no plano) é a fonte dos esquemas que a console espelha.

## Persistência

| Dado | Porta | Adapter | Quando |
|---|---|---|---|
| Histórico de conversa | `ConversationStore` | memória → Postgres | Fase 1 → Fase 2 |

## Portas e adapters **[ADR-012]**

| Porta | Tipo | Adapters por fase | Teste |
|---|---|---|---|
| API HTTP (`/v1`, `/private/v1`, `/admin/v1` na Fase 9) | primária (externa) | FastAPI em `adapters/` | suíte ponta a ponta via HTTP no perfil `test` da 011 (SC-002); suíte de administração: 404 para não admin, 401 para token do chat, 409/422, nenhum segredo nas respostas |
| `ConversationStore` | secundária | memória (Fase 1) → Postgres (Fase 2) | em memória + conformidade contra Postgres; isolamento entre Principals; continuação após reinício |
| `HealthProvider` | secundária | agregador da composition root (011) | provider fixo em memória |
| `Clock` | secundária | relógio do sistema (adapter único, injetado pela 011) | relógio fixo — expiração de conversas |

Consome por seam: Authenticator, GrantResolver e AssistantDirectory (003), Execution Engine (005), Pack Registry (002),
MCP Registry (007), identificador de trace (009); na Fase 9, System Assistant Admin (003), Model Router `check` (006),
Usage Report, Price Book e Trace Destinations (009), Account Admin e Login Settings (012). A saúde agregada entra pela porta `HealthProvider`, implementada pela
011 — a 008 não importa a 011, que é quem a monta. A rejeição de campos de ampliação é regra de `domain/` da 003; aqui
só se mapeia o formato OpenAI para a requisição nativa.

## Data de referência (ADR-013 — resolvido em 2026-09-14, FR-012)

A API não aceita data de referência em nenhuma superfície. O adapter HTTP nunca preenche o campo de data fixa do
`ExecutionRequest` (005), e um campo de data na requisição é rejeitado com erro que o nomeia. Execuções de avaliação
fixam a data pelo harness (009), em processo, montado pela composition root (011).
