# Contrato — Assistants de usuário na superfície pública (US4, research R19)

| Rota | Seam da 003 | Sucesso |
|---|---|---|
| `GET /v1/assistants` | `AssistantDirectory.mine` | 200, lista com estado |
| `POST /v1/assistants` | `create` | 201 |
| `GET /v1/assistants/{nome}` | `get` | 200 |
| `PUT /v1/assistants/{nome}` | `update` | 200 |
| `DELETE /v1/assistants/{nome}` | `delete` | 204 |

`{nome}` aceita com ou sem `~`. Só na superfície pública (FR-006).

```json
POST /v1/assistants
{"name": "meu-rag", "description": "…", "flow": "chat", "packs": ["generic"], "mcp": [], "collections": [],
 "models": {"generation": "ollama/qwen3:1.7b"}, "limits": {"rpm": 5}, "allowed_tools": null, "write_tools": []}

201
{"name": "~meu-rag", "owner": "user:ana", "created_at": "…", "updated_at": "…",
 "status": {"available": true, "reasons": []}, "draft": { …o que foi enviado, normalizado… }}
```

Erros (ver [errors.md](errors.md)): fora da política → 400 `policy_violation` com `param` = campo; sem política →
400 `no_applicable_policy`; nome repetido do dono → 409; nome alheio ou inexistente → 404; campo desconhecido no corpo
→ 400.

Conformidade (`tests/http/contract/test_user_assistants_routes.py`): ciclo completo criar → ler → atualizar →
listar → remover; isolamento entre donos; criado aparece em `/v1/models` do dono e resolve no chat.
