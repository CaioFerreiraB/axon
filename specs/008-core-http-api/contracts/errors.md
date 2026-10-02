# Contrato — erros (Fase 2, research R14)

Todo erro sai no envelope da OpenAI. O identificador de requisição vai no cabeçalho `X-Request-Id` quando a requisição
chegou a ganhar um.

```json
{"error": {"message": "modelo não permitido: openai/gpt-x; allowlist: ollama/*", "type": "invalid_request_error", "param": "model", "code": "model_not_allowed"}}
```

| Causa | Status | `type` | `code` | `param` |
|---|---|---|---|---|
| credencial ausente ou recusada | 401 | `authentication_error` | `invalid_credential` | — |
| armazenamento de credenciais inacessível (FR-021, 2026-10-01) | 503 | `server_error` | `storage_unavailable` | — |
| inexistente **ou** não autorizado (Assistant, conversa, recurso administrativo) | 404 | `not_found_error` | `not_found` | — |
| corpo inválido, campo de ampliação, data de referência, modelo fora da allowlist, rascunho fora da política | 400 | `invalid_request_error` | `invalid_request`, `widening_field`, `reference_time`, `model_not_allowed`, `policy_violation`, `no_applicable_policy` | o campo |
| conversa de outro Assistant | 400 | `invalid_request_error` | `conversation_assistant_mismatch` | `conversation_id` |
| nome de Assistant de usuário já usado pelo dono | 409 | `conflict_error` | `conflict` | `name` |
| alias de MCP repetido, ou entrada do arquivo do operador alterada pela API (Fase 3) | 409 | `conflict_error` | `conflict` | `alias` |
| Assistant autorizado, mas indisponível | 424 | `dependency_error` | `assistant_unavailable` | — ; motivos em `x_ai_core.reasons` |
| cota do par (Principal, Assistant) | 429 + `Retry-After` | `rate_limit_error` | `rate_limit_exceeded` | — |
| execução com registro `error` sem streaming (ADR-018) | 502 + `x-should-retry: false` | `api_error` | `execution_failed` | — (Fase 1, R6; Fase 3, R30–R31) |

**Regras**: o 404 tem corpo **idêntico** para inexistente e para não autorizado — mensagem fixa (`assistant não encontrado`, ou `recurso não encontrado` para conversas e rotas administrativas), sem ecoar o nome pedido; o 424 só é
devolvido a quem resolveria o Assistant (FR-020); nenhum erro de pedido acontece depois de uma chamada de modelo.

Conformidade: `tests/http/unit/test_errors.py` (envelope e tabela) e as suítes de cada rota.

## Fase 3 (2026-10-02): desfecho por gravidade e não-retentativa (FR-022, research R30–R31)

- O desfecho é decidido pela **gravidade** dos registros do evento final (ADR-018): só `notice` → sucesso (200,
  `finish_reason: "stop"`); algum `error` → falha (stream: `finish_reason: "error"`; sem streaming: 502).
- A resposta 502 de falha de execução leva `x-should-retry: false`: o SDK oficial da OpenAI repete 5xx
  automaticamente, e cada repetição rodaria a execução de novo — inclusive tools de escrita.
- Erros anteriores à execução (4xx, 503 de armazenamento) não levam o cabeçalho: nada rodou, repetir é seguro.

