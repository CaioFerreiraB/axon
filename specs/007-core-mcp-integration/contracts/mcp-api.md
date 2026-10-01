# Contrato — seams da 007 (`ai_core.mcp.api`)

Três seams como `Protocol`, implementados por `McpService`. Value objects e regras em [data-model.md](../data-model.md).

## `McpRegistry` — CRUD por escopo

```python
class McpRegistry(Protocol):
    # globais — autoridade do operador; quem confere o grupo de administração é a borda (008)
    async def globals(self) -> Sequence[McpServer]: ...                 # arquivo + armazenamento, por alias
    async def get_global(self, alias: str) -> McpServer: ...
    async def create_global(self, draft: McpServerDraft) -> McpServer: ...
    async def update_global(self, alias: str, draft: McpServerDraft) -> McpServer: ...
    async def delete_global(self, alias: str) -> None: ...

    # do usuário — sempre no escopo do Principal
    async def mine(self, principal: Principal) -> Sequence[McpServer]: ...
    async def get_mine(self, principal: Principal, alias: str) -> McpServer: ...
    async def create_mine(self, principal: Principal, draft: McpServerDraft) -> McpServer: ...
    async def update_mine(self, principal: Principal, alias: str, draft: McpServerDraft) -> McpServer: ...
    async def delete_mine(self, principal: Principal, alias: str) -> None: ...

    async def available(self, principal: Principal) -> Sequence[McpSummary]: ...   # o que pode referenciar
    async def check(self, alias: str, *, owner: str | None = None) -> ServerHealth: ...  # FR-011
```

| Regra | Origem | Verificada por |
|---|---|---|
| `stdio` recusado em qualquer `create`/`update` | FR-013 | `test_registry.py` |
| Entrada do arquivo é somente leitura (`McpConflict`) | R3 | `test_registry.py` |
| Global com alias do arquivo: `create` recusa; armazenado e depois declarado no arquivo fica sombreado | R3 | `test_registry.py` |
| `~` obrigatório no de usuário, proibido no global | FR-015 | `test_registry.py` |
| Usuário: sem autenticação, sem referência, `https`, sem `user_access` | FR-014, R11 | `test_registry.py` |
| `get_mine`/`update_mine`/`delete_mine` de MCP alheio = inexistente, mesma mensagem | FR-006, SC-004 | `test_isolation.py` |
| `mine` de B não contém nada de A | US4 cen. 1 | `test_isolation.py` |
| `available` não mostra endpoint, credencial nem política de globais | data-model | `test_registry.py` |
| `check` ignora o cache e lista as tools anunciadas e as que faltam | R14 | `test_registry.py` |
| Adicionar, alterar e desabilitar valem na execução seguinte, sem restart | FR-002, SC-003 | `test_discovery.py` |

## `McpCatalog` — a forma de `McpDirectory` da 003

```python
class McpCatalog(Protocol):
    async def aliases(self, *, owner: str | None) -> frozenset[str]: ...
```

`owner=None`: globais habilitados e disponíveis. `owner=X`: `~` habilitados de X + globais habilitados com
`user_access` (R13). Conformidade: `test_catalog.py` — inclusive desabilitar some do conjunto (US1 cen. 2) e o
`McpService` passar no `isinstance`-estrutural contra a porta da 003 (checado por mypy no teste).

## `McpClients` e `RestrictedMcpClient`

```python
class McpClients(Protocol):
    def client_for(self, grant: ExecutionGrant) -> RestrictedMcpClient: ...

class RestrictedMcpClient(Protocol):            # cumpre MCPClient (001) e acrescenta discover
    async def discover(self, aliases: Sequence[str]) -> Discovery: ...
    async def discover_tools(self, aliases: Sequence[str]) -> Sequence[ToolSpec]: ...
    async def execute(self, alias: str, tool: str, arguments: Mapping[str, JSONValue]) -> ToolResult: ...
```

| Regra | Origem | Verificada por |
|---|---|---|
| Alias fora de `grant.mcp_aliases` → `UnknownServer`, sem I/O | US3, FR-005 | `test_restricted_client.py` |
| Alias do grant que deixou de ser visível (desabilitado, removido, `user_access` desligado) → `UnknownServer` | R9 | idem |
| Assistant de sistema não alcança `~`; de usuário alcança só os `~` do dono e globais liberados | FR-006, R9 | idem |
| `discover` devolve só a allowlist, com `mutates` de `write_tools`, nome local, `kind="mcp"`, sem handler | FR-007, US5 | `test_discovery.py`, `test_policy.py` |
| Tool anunciada fora da allowlist nunca aparece; tool da allowlist não anunciada também não | US5, Edge Cases | `test_discovery.py`, `test_policy.py` |
| Servidor com falha → `unavailable[alias]` com motivo; os outros atendem | Edge Cases; 004 | `test_discovery.py` |
| Segunda descoberta dentro do TTL não toca o servidor; mudar o registro invalida | FR-010, R8 | `test_discovery.py`, com relógio fixo |
| `execute` de tool fora da allowlist → `ToolResult(error=...)` sem tocar no servidor | FR-007 | `test_restricted_client.py` |
| Prazo esgotado, destino bloqueado, credencial ausente, erro do servidor → `ToolResult(error=...)`, nunca exceção | R9 | `test_restricted_client.py`, `test_credentials.py` |
| Resultado acima de `max_response_bytes` → cortado com marca, `truncated=True` | FR-008, princípio VI | `test_policy.py` |
| `ToolResult.untrusted` sempre verdadeiro | princípio VI | `test_restricted_client.py`, `unit/test_results.py` |
| Nenhum valor de segredo em `Discovery`, `ToolResult`, exceção ou log capturado | FR-004, SC-001 | `integration/test_secret_scan.py` |

## Erros

| Erro | Herda de (003) | Tradução na 008 |
|---|---|---|
| `McpNotFound` | `NotFound` | 404, mensagem fixa |
| `McpRejected(field=...)` | `RequestRejected` | 400 nomeando o campo |
| `McpConflict` | `Conflict` | 409 |
| `UnknownServer` | `LookupError` | — (interno à execução; a 004 o trata) |
| `McpConfigError` | `ValueError` | — (o boot para, 011) |
