# Contrato — `/v1/models` e `/private/v1/models` (US2, research R16)

```json
GET /v1/models
{"object": "list",
 "data": [
   {"id": "geral", "object": "model", "created": 1790000000, "owned_by": "system",
    "x_axon": {"generation": "ollama/qwen3:1.7b", "description": "Assistente de uso geral",
                  "origin": "system", "allow": ["ollama/*"]}},
   {"id": "~meu-rag", "object": "model", "created": 1790000000, "owned_by": "user:ana",
    "x_axon": {"generation": "ollama/qwen3:1.7b", "description": null, "origin": "user", "allow": ["ollama/*"]}}
 ]}
```

| Regra | Origem |
|---|---|
| exatamente os itens de `AssistantDirectory.discover(principal)` — o que o Principal resolve, disponíveis | FR-003, 003 FR-008 |
| uma entrada por Assistant, id = nome (curto) | clarificação 2 |
| `created` = instante da listagem (porta `Clock`) | princípio XIII |
| mesmo formato nas duas superfícies | FR-001 |

Conformidade (`tests/http/contract/test_models_route.py`): dois Principals veem listas diferentes exatamente pela ACL;
privado de grupo aparece para o membro; indisponível não aparece; Assistant de usuário aparece só para o dono; o id
listado resolve no chat completions.
