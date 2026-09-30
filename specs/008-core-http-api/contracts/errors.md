# Contrato — erros (Fase 2, research R14)

Todo erro sai no envelope da OpenAI. O identificador de requisição vai no cabeçalho `X-Request-Id` quando a requisição
chegou a ganhar um.

```json
{"error": {"message": "modelo não permitido: openai/gpt-x; allowlist: ollama/*", "type": "invalid_request_error", "param": "model", "code": "model_not_allowed"}}
```

| Causa | Status | `type` | `code` | `param` |
|---|---|---|---|---|
| credencial ausente ou recusada | 401 | `authentication_error` | `invalid_credential` | — |
| inexistente **ou** não autorizado (Assistant, conversa, recurso administrativo) | 404 | `not_found_error` | `not_found` | — |
| corpo inválido, campo de ampliação, data de referência, modelo fora da allowlist, rascunho fora da política | 400 | `invalid_request_error` | `invalid_request`, `widening_field`, `reference_time`, `model_not_allowed`, `policy_violation`, `no_applicable_policy` | o campo |
| conversa de outro Assistant | 400 | `invalid_request_error` | `conversation_assistant_mismatch` | `conversation_id` |
| nome de Assistant de usuário já usado pelo dono | 409 | `conflict_error` | `conflict` | `name` |
| Assistant autorizado, mas indisponível | 424 | `dependency_error` | `assistant_unavailable` | — ; motivos em `x_ai_core.reasons` |
| cota do par (Principal, Assistant) | 429 + `Retry-After` | `rate_limit_error` | `rate_limit_exceeded` | — |
| execução falhou sem streaming | 502 | `api_error` | `execution_failed` | — (Fase 1, R6) |

**Regras**: o 404 tem corpo **idêntico** para inexistente e para não autorizado — mensagem fixa (`assistant não encontrado`, ou `recurso não encontrado` para conversas e rotas administrativas), sem ecoar o nome pedido; o 424 só é
devolvido a quem resolveria o Assistant (FR-020); nenhum erro de pedido acontece depois de uma chamada de modelo.

Conformidade: `tests/http/unit/test_errors.py` (envelope e tabela) e as suítes de cada rota.
