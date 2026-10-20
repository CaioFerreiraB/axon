# Contrato — portas secundárias da 008 (Fase 1)

Internas do módulo (`axon_ai/http/ports.py`): não são seams, e quem escolhe o adapter é a composition root (011).
Três delas descrevem o que este módulo **exige** da 003 — declará-las aqui é o que permite à 003 chegar na Fase 2 sem
que nenhuma rota mude ([research.md](../research.md) R1, R2).

## `Principal` e `Authenticator` — quem está pedindo

```python
class Principal(Protocol):
    @property
    def id(self) -> str: ...

class Authenticator(Protocol):
    async def authenticate(self, *, surface: str, credential: str | None) -> Principal | None: ...
```

| Exigência | Detalhe |
|---|---|
| `surface` | `"public"` ou `"private"` — o mesmo verificador atende as duas, com regras próprias |
| Credencial recusada | devolve `None`; a rota responde 401 |
| Nunca levanta por credencial ausente | ausência é recusa, não erro de programa |

**Adapter da fase**: `AnonymousAuthenticator` (`adapters/development.py`), que aceita qualquer requisição e devolve
sempre o mesmo Principal de desenvolvimento. O nome diz o que ele é, e a 011 o anuncia no boot — não há como confundi-lo
com configuração de produção. Na Fase 2, a 003 fornece o verificador real.

## `GrantResolver` — o que a execução pode fazer

```python
class GrantResolver(Protocol):
    async def resolve(self, *, model: str, principal: Principal) -> ExecutionGrant: ...
```

| Exigência | Detalhe |
|---|---|
| `model` | o id pedido: `"<assistant>"` ou `"<assistant>/<modelo>"` |
| `ExecutionGrant` | o `Protocol` da 005 — assistant, flow, composição e política de modelos |
| Assistant inexistente **ou** não autorizado | levanta `AssistantNotFound`; a rota responde **404** nos dois casos (FR-009) |

A API nunca monta o grant: resolver Assistant é decidir a fronteira de isolamento (princípio IV), e isso pertence à
003. Na Fase 1 a 011 injeta um resolvedor montado da configuração do operador.

## `RequestIds` — identificador da requisição

```python
class RequestIds(Protocol):
    def next(self) -> str: ...
```

Existe por não-determinismo (princípio XIII) e porque o valor é observável: vai no cabeçalho `X-Request-Id`, no `id` da
resposta e é a chave do trace (009). Com a porta, a suíte confere o identificador exato em vez de casar formato.

**Adapters**: `Uuid4RequestIds` (produção) e `SequentialRequestIds` (testes, `req-1`, `req-2`, …).

### Conformidade (`tests/http/contract/test_http_ports.py`)

1. `AnonymousAuthenticator` devolve o mesmo Principal nas duas superfícies e nunca levanta;
2. um autenticador que recusa faz a rota responder 401;
3. `GrantResolver` que levanta `AssistantNotFound` faz a rota responder 404, com corpo idêntico para inexistente e
   para não autorizado;
4. `SequentialRequestIds` entrega identificadores distintos e crescentes, e o valor aparece no cabeçalho, no `id` da
   resposta e no trace da execução.

## `Clock` — o instante das respostas

```python
class Clock(Protocol):
    def now(self) -> datetime: ...   # sempre com timezone
```

O formato da OpenAI tem um campo `created` em toda resposta e em todo chunk, então **esta fase lê o relógio** — e o
princípio XIII manda que tempo passe por porta. Com ela, o teste de construção de chunk confere o valor exato em vez
de ignorar o campo.

**Adapters**: `SystemClock` e `FixedClock`. A 011 injeta o mesmo relógio nos módulos com porta de tempo (011 FR-008).

## Portas adiadas

`ConversationStore` e `HealthProvider` estão no `design.md` e entram na Fase 2, com conversas e saúde agregada:
declará-las agora seria porta sem consumidor (princípio XIII, [research.md](../research.md) R9).

---

## Fase 2 (2026-09-30) — portas que saem e que entram

**Saem** (research R13): `Principal`, `Authenticator`, `GrantResolver` e `AssistantNotFound`. A API passa a importá-los de
`axon_ai.assistants.api`, com `AssistantDirectory`, `ApiKeyAdmin` e os erros da 003. O `AnonymousAuthenticator` de
desenvolvimento continua aqui, agora produzindo o `Principal` da 003 (`user:anonymous`, esquema da superfície).

**Entram**:

```python
class ConversationStore(Protocol):
    async def create(self, conversation: Conversation) -> None: ...
    async def get(self, owner: str, conversation_id: str) -> Conversation | None: ...        # None → 404
    async def messages(self, owner: str, conversation_id: str) -> Sequence[StoredMessage] | None: ...
    async def append(self, owner: str, conversation_id: str, messages: Sequence[StoredMessage], *, at: datetime) -> bool: ...
    async def list(self, owner: str, *, limit: int, cursor: str | None) -> ConversationPage: ...
    async def delete(self, owner: str, conversation_id: str) -> bool: ...                      # False → 404
    async def delete_inactive(self, *, before: datetime) -> int: ...

class HealthProvider(Protocol):
    async def health(self) -> HealthReport: ...

class AdminGate(Protocol):
    def is_admin(self, principal: Principal) -> bool: ...     # satisfeita pelo AccessService da 003 (R20)
```

| Porta | Adapters | Conformidade |
|---|---|---|
| `ConversationStore` | `InMemoryConversationStore` (`adapters/conversations_memory.py`), `PostgresConversationStore` (`adapters/conversations_postgres.py`, schema `http`, ADR-015) | `tests/http/contract/test_conversation_store.py`, memória × Postgres: isolamento por dono, ordem das mensagens, `append` em conversa apagada devolve `False`, `delete_inactive` pelo instante, paginação estável, sobrevive a um armazenamento novo |
| `HealthProvider` | provedor mínimo da composition root (a partir do relatório de boot) até a 011 US5; `StaticHealthProvider` nos testes | a rota responde 200/503 conforme `ok` |
| `AdminGate` | `AccessService` da 003 | a rota de packs responde 404 a quem a porta recusa |
| `RequestIds` | uma instância para requisições, outra para conversas | ids distintos e previsíveis nos testes |
