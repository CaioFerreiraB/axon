# Contrato — portas secundárias da 007 (`ai_core.mcp.ports`)

Cada porta existe por I/O, não-determinismo ou troca prevista (princípio XIII). Todas têm adapter em memória em
`adapters/memory.py` — na distribuição, para que o perfil `test` da 011 e a suíte de um pack montem a plataforma sem
rede — e uma suíte de conformidade que roda contra ele e contra o adapter real.

| Porta | Motivo | Em memória | Real | Conformidade |
|---|---|---|---|---|
| `McpServerStore` | banco | dicionário por `(owner, alias)` | `registry_postgres.py`, schema `mcp` (ADR-015) | `contract/test_store.py`, com Postgres por `AI_CORE_TEST_POSTGRES_DSN` |
| `McpConfigSource` | arquivo | configuração já carregada | `config_yaml.py` (`mcp.yaml`) | `contract/test_config_source.py` |
| `McpTransport` | rede e processo | servidores programados (tools, resultados, falhas, atraso) | `transport_http.py` (`http`, `sse`), `transport_stdio.py` | `contract/test_transport.py` contra o servidor MCP do SDK em `127.0.0.1` e um servidor `stdio` em script |
| `DnsResolver` | rede (DNS) | mapa nome → IPs | `dns_system.py` (`getaddrinfo`) | `contract/test_dns.py` |
| `SecretResolver` | segredos | dicionário | `secrets_env.py` (`AI_CORE_MCP_SECRET_<REF>`) | `contract/test_secrets.py` |
| `DiscoveryCache` | estado com TTL | dicionário + `Clock` | — (memória é o real nesta fase) | `contract/test_cache.py` com relógio fixo |
| `Clock` | tempo (ADR-013) | relógio fixo da 005 | relógio do sistema da 005 | — (o mesmo relógio da 011) |

## Formas

```python
class McpServerStore(Protocol):
    async def get(self, owner: str | None, alias: str) -> StoredServer | None: ...
    async def list(self, owner: str | None) -> Sequence[StoredServer]: ...      # owner=None: globais
    async def all(self) -> Sequence[StoredServer]: ...
    async def insert(self, record: StoredServer) -> bool: ...                    # False se (owner, alias) existe
    async def replace(self, record: StoredServer) -> bool: ...                   # False se não existe
    async def delete(self, owner: str | None, alias: str) -> bool: ...

class McpConfigSource(Protocol):
    def load(self) -> McpConfig: ...      # McpConfigError em erro de arquivo; erro de entrada vai para a entrada

class McpTransport(Protocol):
    async def list_tools(self, target: Target, *, limits: OperationLimits) -> Sequence[RemoteTool]: ...
    async def call_tool(
        self, target: Target, name: str, arguments: Mapping[str, JSONValue], *, limits: OperationLimits
    ) -> RemoteResult: ...

class DnsResolver(Protocol):
    async def resolve(self, host: str, port: int) -> Sequence[IPv4Address | IPv6Address]: ...

class SecretResolver(Protocol):
    def resolve(self, ref: str) -> str | None: ...

class DiscoveryCache(Protocol):
    def get(self, key: CacheKey) -> CachedDiscovery | None: ...                  # None se ausente ou vencida
    def put(self, key: CacheKey, value: CachedDiscovery, *, ttl: timedelta) -> None: ...
```

`Target` (interno): escopo, transporte, endpoint ou comando/args/ambiente, e cabeçalhos ou variáveis **já com o
segredo resolvido** — existe só durante a operação. `OperationLimits`: prazo e teto de bytes. As falhas do transporte
são uma exceção do módulo (`TransportFailure(reason)`) cuja mensagem nunca contém segredo nem cabeçalho.

## Regras de cada porta

| Porta | Regra | Verificada por |
|---|---|---|
| `McpServerStore` | `insert` duplicado devolve `False` sem alterar; `replace`/`delete` de inexistente devolvem `False`; `list(None)` só globais, `list(X)` só de X | `test_store.py` (memória × Postgres) |
| `McpServerStore` | só a referência da credencial é gravada; varredura do schema depois de operações não acha valor de segredo | `integration/test_secret_scan.py` |
| `McpConfigSource` | erro de arquivo → `McpConfigError` nomeando o caminho; erro de entrada → entrada indisponível com motivo | `test_config_source.py` |
| `McpTransport` | lista as tools e chama uma tool de um servidor de verdade, com cabeçalho `Authorization` quando `bearer` | `test_transport.py` |
| `McpTransport` | o prazo de `OperationLimits` vale para a operação inteira e é aplicado **pelo transporte** — o serviço não tem segunda camada; esgotado, vira `TransportFailure` com motivo | idem |
| `McpTransport` (`http`/`sse`) | teto de bytes lidos por sessão (`OperationLimits.max_bytes`); passou, `TransportFailure`. No `stdio` não há teto no transporte (R6) | idem |
| `McpTransport` (`http`/`sse`) | toda conexão passa pela política de rede, com o IP fixado; `localhost` sem a exceção de hosts internos é bloqueado | idem, `contract/test_guarded_backend.py` e `integration/test_ssrf.py` |
| `McpTransport` (`stdio`) | executa o comando do arquivo sem shell, com `env` e `secrets` no ambiente do filho | `test_transport.py` |
| `DnsResolver` | IP literal devolve ele mesmo; nome inexistente devolve vazio, não exceção | `test_dns.py` |
| `SecretResolver` | lê só `AI_CORE_MCP_SECRET_<REF>`; referência fora da gramática devolve `None`; `AI_CORE_DATABASE_URL` nunca é alcançável | `test_secrets.py` |
| `DiscoveryCache` | entrada vence no TTL do relógio; chave com versão diferente não acerta | `test_cache.py` |
