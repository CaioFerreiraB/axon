# Contrato — portas secundárias da 003

Internas do módulo (`ai_core/assistants/ports.py`): não são seams, e quem escolhe o adapter é a composition root (011).
Toda porta tem adapter em memória e suíte de conformidade que roda contra ele e contra o adapter real (princípio XIII).
Nenhum tipo de biblioteca de infraestrutura aparece nas assinaturas.

## Visão geral

| Porta | Existe por | Adapter real | Adapter em memória / teste |
|---|---|---|---|
| `AssistantConfigSource` | I/O (arquivo) | `YamlAssistantConfigSource` (`assistants_yaml.py`) | `InMemoryAssistantConfigSource` |
| `UserAssistantStore` | I/O, troca prevista (memória → Postgres) | `PostgresUserAssistantStore` (`assistants_postgres.py`) | `InMemoryUserAssistantStore` |
| `ApiKeyStore` | I/O | `PostgresApiKeyStore` (`api_keys_postgres.py`) | `InMemoryApiKeyStore` |
| `OidcVerifier` | I/O (JWKS), criptografia de biblioteca | `JwksOidcVerifier` (`oidc.py`) | `StaticOidcVerifier`, `DisabledOidcVerifier` |
| `RateCounterStore` | estado entre requisições, troca prevista (réplicas) | `InMemoryRateCounterStore` (`rate_memory.py`) | o mesmo |
| `TokenGenerator` | aleatoriedade | `SecretsTokenGenerator` (`tokens.py`) | `SequentialTokenGenerator` |
| `Clock` | tempo (ADR-013) | `SystemClock` (único, injetado pela 011) | `FixedClock` |
| `McpDirectory` | troca prevista (007, Fase 3) | `EmptyMcpDirectory` (`catalogs.py`) nesta fase | `InMemoryMcpDirectory` |
| `CollectionCatalog` | troca prevista (índice, Fase 5) | `EmptyCollectionCatalog` (`catalogs.py`) nesta fase | `InMemoryCollectionCatalog` |

## Assinaturas

```python
class AssistantConfigSource(Protocol):
    def load(self) -> AssistantsConfig: ...            # levanta AssistantsConfigError em erro de arquivo

class UserAssistantStore(Protocol):
    async def get(self, owner: str, name: str) -> StoredUserAssistant | None: ...
    async def list(self, owner: str) -> Sequence[StoredUserAssistant]: ...
    async def all(self) -> Sequence[StoredUserAssistant]: ...           # só para a validação (R14)
    async def insert(self, record: StoredUserAssistant) -> bool: ...    # False se (owner, name) já existe
    async def replace(self, record: StoredUserAssistant) -> bool: ...   # False se não existe
    async def delete(self, owner: str, name: str) -> bool: ...          # False se não existe

class ApiKeyStore(Protocol):
    async def add(self, record: ApiKeyRecord) -> None: ...
    async def get(self, key_id: str) -> ApiKeyRecord | None: ...
    async def list(self) -> Sequence[ApiKeyRecord]: ...
    async def revoke(self, key_id: str, *, at: datetime) -> ApiKeyRecord | None: ...  # idempotente

class OidcVerifier(Protocol):
    async def verify(self, token: str) -> Mapping[str, object] | None: ...
    # assinatura, algoritmo, iss e aud conferidos; exp/nbf/iat ficam para o domain/, com o Clock (R6)

class RateCounterStore(Protocol):
    async def acquire(self, key: tuple[str, str], *, now: datetime, limit: int,
                      window: timedelta) -> RateDecision: ...           # atômica (R9)

class TokenGenerator(Protocol):
    def token_hex(self, nbytes: int) -> str: ...
    def token_urlsafe(self, nbytes: int) -> str: ...

class Clock(Protocol):
    def now(self) -> datetime: ...                     # sempre com timezone

class McpDirectory(Protocol):
    async def aliases(self, *, owner: str | None) -> frozenset[str]: ...
    # owner=None: globais (Assistants de sistema); owner=subject: do dono + globais permitidos a usuários

class CollectionCatalog(Protocol):
    async def names(self) -> frozenset[str]: ...
```

`StoredUserAssistant` = dono, nome sem `~`, `UserAssistantDraft`, `created_at`, `updated_at`. `ApiKeyRecord`,
`RateDecision` e `AssistantsConfig`: [data-model.md](../data-model.md).

## Configuração dos adapters reais

A 011 lê e passa estes valores; os nomes de variável são decisão dela (sugestão entre parênteses).

| Adapter | Parâmetros |
|---|---|
| `YamlAssistantConfigSource` | caminho do arquivo (`AI_CORE_ASSISTANTS_FILE`, já existente) |
| `JwksOidcVerifier` | emissor (`AI_CORE_OIDC_ISSUER`), audiência (`AI_CORE_OIDC_AUDIENCE`), URL do JWKS opcional — sem ela, descoberta em `<emissor>/.well-known/openid-configuration` —, algoritmos (default `RS256`, `ES256`), cliente httpx |
| mapeamento de claims (domínio) | claim de subject (default `sub`), claim de grupos (default `groups`), tolerância de relógio (default 60 s) |
| `PostgresUserAssistantStore`, `PostgresApiKeyStore` | `AsyncConnectionPool` compartilhado (ADR-015); `migrate(pool)` do módulo roda no boot |

Sem emissor configurado, a composition root injeta `DisabledOidcVerifier`: a superfície pública recusa toda
credencial — falha fechada, anunciada no relatório de boot.

## Suítes de conformidade (`tests/assistants/contract/`)

| Suíte | Adapters | O que garante |
|---|---|---|
| `test_user_assistant_store.py` | memória, Postgres | unicidade (dono, nome); `insert` duplicado → `False`; isolamento entre donos; `replace`/`delete` de inexistente → `False`; `all` lista todos; ida e volta do rascunho sem perda |
| `test_api_key_store.py` | memória, Postgres | `get` por `key_id`; hash guardado, nunca a chave; `revoke` idempotente preserva o primeiro instante; `list` inclui revogadas |
| `test_oidc_verifier.py` | estático, JWKS (chaves geradas na suíte, JWKS por `httpx.MockTransport`) | token bom → claims; assinatura errada, `iss`/`aud` errados, `alg: none`, HS256 com a chave pública e `kid` desconhecido → `None`; rotação de chave busca o JWKS de novo, respeitando o intervalo mínimo |
| `test_rate_counter_store.py` | memória | janela deslizante: `limit` concessões por janela, a seguinte recusada com `retry_after` exato; pares independentes |
| `test_token_generator.py` | `secrets`, sequencial | tamanho e alfabeto; sequencial é determinístico |
| `test_catalogs.py` | vazios, em memória | vazio devolve conjunto vazio; em memória separa globais e do dono |
| `test_config_source.py` | YAML, memória | ver [assistants-yaml.md](assistants-yaml.md) |

O Postgres roda quando `AI_CORE_TEST_POSTGRES_DSN` está definida (a CI do core a define, com um serviço Postgres); sem
ela, os casos do adapter real são pulados com motivo explícito, como o Ollama da 006.
