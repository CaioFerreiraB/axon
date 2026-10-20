# Contrato — operação pela superfície privada (US5, research R20)

| Rota | Quem | Seam / porta | Sucesso |
|---|---|---|---|
| `GET /private/v1/packs` | grupo de administração | `PackRegistry.entries()` (002), `AdminGate` | 200 |
| `POST /private/v1/admin/keys` | grupo de administração | `ApiKeyAdmin.issue` (003) | 201, com `key` em claro **uma vez** |
| `GET /private/v1/admin/keys` | grupo de administração | `ApiKeyAdmin.keys` | 200, sem chave nem hash |
| `DELETE /private/v1/admin/keys/{key_id}` | grupo de administração | `ApiKeyAdmin.revoke` | 200, com `revoked_at` |
| `GET /private/v1/health` | qualquer chave válida | `HealthProvider` | 200 se saudável, 503 se não |

Quem não é do grupo recebe 404 nas rotas de administração, como recurso inexistente (clarificação 5; 003 FR-015).

```json
GET /private/v1/packs
{"data": [{"name": "generic", "version": "0.1.0", "contract_version": "0.1", "status": "enabled", "error": null}]}

POST /private/v1/admin/keys   {"subject": "svc:ingestor", "groups": ["leitores"], "label": "pipeline"}
201 {"key_id": "…", "subject": "svc:ingestor", "groups": ["leitores"], "label": "pipeline",
     "created_at": "…", "revoked_at": null, "key": "axn_…"}

GET /private/v1/health
200 {"status": "ok", "items": [{"name": "packs", "ok": true, "detail": null}]}
```

Conformidade (`tests/http/contract/test_private_routes.py`): pack em erro aparece com status e mensagem para o admin
(US5 cen. 1) e 404 para os demais; ciclo emitir → autenticar com a chave → listar sem a chave → revogar → recusada
(US5 cen. 2); saúde com qualquer chave e 503 quando um item não está saudável.
