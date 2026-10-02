# Contrato — rotas de MCP (Fase 3; US4, US5; research R26–R29)

Sobre o seam `McpRegistry` da 007 (`ai_core.mcp.api`), injetado em `create_app(mcp=…)` pela 011. Sem registry, as rotas
não existem (404).

## Do usuário — superfície pública (FR-006)

| Rota | Seam (007) | Sucesso |
|---|---|---|
| `GET /v1/mcp` | `mine(principal)` | 200 `{"data": [servidor…]}` |
| `POST /v1/mcp` | `create_mine` | 201 servidor |
| `GET /v1/mcp/available` | `available(principal)` | 200 `{"data": [{"alias", "scope", "description"}…]}` |
| `GET /v1/mcp/{alias}` | `get_mine` | 200 servidor |
| `PUT /v1/mcp/{alias}` | `update_mine` | 200 servidor |
| `DELETE /v1/mcp/{alias}` | `delete_mine` | 204 |
| `GET /v1/mcp/{alias}/health` | `check(alias, owner=subject)` | 200 saúde |

`{alias}` com ou sem `~`. MCP de outro usuário ou inexistente: 404 com a mesma mensagem (007 FR-006).

## Globais — superfície privada, só o grupo de administração (FR-007)

| Rota | Seam (007) | Sucesso |
|---|---|---|
| `GET /private/v1/mcp` | `globals()` | 200 `{"data": [servidor…]}` (arquivo do operador + API) |
| `POST /private/v1/mcp` | `create_global` | 201 |
| `GET /private/v1/mcp/{alias}` | `get_global` | 200 |
| `PUT /private/v1/mcp/{alias}` | `update_global` | 200 |
| `DELETE /private/v1/mcp/{alias}` | `delete_global` | 204 |
| `GET /private/v1/mcp/{alias}/health` | `check(alias)` | 200 saúde |

Chave fora do grupo de administração: 404 de recurso inexistente, antes de tocar o registry.

## Corpo (a forma do `mcp.yaml` da 007)

```json
POST /v1/mcp
{"alias": "~agenda", "transport": "http", "endpoint": "https://agenda.example/mcp", "description": "Minha agenda",
 "policy": {"allowed_tools": ["listar", "marcar"], "write_tools": ["marcar"]}}

POST /private/v1/mcp
{"alias": "financeiro", "transport": "http", "endpoint": "http://mcp-financeiro:8080/mcp",
 "auth": {"type": "bearer", "credential": "financeiro_token"}, "user_access": false, "enabled": true,
 "policy": {"allowed_tools": ["saldo"], "timeout_ms": 10000, "max_response_bytes": 65536}}
```

| Campo | Obrigatório | Regra |
|---|---|---|
| `alias` | sim | global sem `~`; de usuário com `~` (o `~` pode vir só no caminho) |
| `transport` | sim | `http` ou `sse` — `stdio` só no arquivo do operador (007 FR-013) |
| `endpoint` | sim | URL; de usuário sempre `https` |
| `description` | não | texto |
| `auth` | não | `{type: none \| bearer, credential: <ref>}`; só global; a referência vira `AI_CORE_MCP_SECRET_<REF>` |
| `enabled` | não | default `true` |
| `user_access` | não | só global; default `false` |
| `policy` | sim | `allowed_tools` obrigatória e não vazia; `write_tools` ⊆ `allowed_tools`; prazos e tamanhos da 007 |

Campo desconhecido → 400 nomeando o campo. As regras de escopo são da 007 (`McpRejected`).

## Resposta (servidor)

```json
{"alias": "~agenda", "scope": "user", "owner": "user:ana", "transport": "http",
 "endpoint": "https://agenda.example/mcp", "command": null, "description": "Minha agenda",
 "auth": {"type": "none", "credential": null}, "enabled": true, "user_access": false,
 "policy": {"allowed_tools": ["listar", "marcar"], "write_tools": ["marcar"], "timeout_ms": 30000,
            "max_response_bytes": 65536},
 "origin": "registry", "available": true, "reason": null, "created_at": "…", "updated_at": "…"}
```

Nunca contém o valor de uma credencial — só o nome da referência (007 FR-004).

## Saúde de um servidor

```json
{"alias": "financeiro", "ok": false, "detail": "sem resposta: conexão recusada", "tools": [], "missing": ["saldo"]}
```

## Erros

`McpNotFound` / `UnknownServer` → 404; `McpRejected` → 400 com `param` = campo; `McpConflict` → 409 com
`param: "alias"` (alias repetido; entrada do arquivo do operador, somente leitura). Formato em [errors.md](errors.md).

## Conformidade (`tests/http/contract/test_mcp_routes.py`)

1. usuário: criar → ler → atualizar → listar → saúde → remover; `~` opcional no caminho;
2. isolamento: MCP de A é 404 para B, com a mesma mensagem de inexistente; `GET /v1/mcp` de B não traz nada de A;
3. `available` lista próprios e globais liberados, sem endpoint nem política de global;
4. recusas da 007 com o campo: `http` em MCP de usuário, `stdio`, `policy.allowed_tools` vazia, campo desconhecido;
5. globais: chave fora do grupo → 404; administrador cria, lê, atualiza, lista e remove; entrada do arquivo → 409;
6. US4 cen. 1: MCP próprio criado pela API e Assistant de usuário que o declara → o Assistant aparece em `/v1/models`;
7. nenhum corpo de resposta contém valor de credencial.
