# Contrato — requisição nativa `POST /v1/chat` e `POST /private/v1/chat` (US3, research R17)

```json
{"assistant": "geral", "model": "ollama/qwen3:8b", "messages": [{"role": "user", "content": "…"}],
 "stream": true, "conversation_id": "conv_…"}
```

| Campo | Obrig. | Regra |
|---|---|---|
| `assistant` | sim | nome do Assistant (`geral`, `~meu-rag`) |
| `model` | não | só a parte que restringe: `qwen3:8b` ou `ollama/qwen3:8b` (003 R5) |
| `messages` | sim | como na compat |
| `stream` | não | booleano; default `false` |
| `conversation_id` | não | continua a conversa (US7) |

- Qualquer outro campo → 400 nomeando o campo. Campo de `WIDENING_FIELDS` (003) → 400 `widening_field`; data de
  referência → 400 `reference_time` (FR-012).
- A resposta é **a mesma** da compat: chunks SSE (`chat.completion.chunk`) ou `chat.completion`
  ([chat-completions.md](chat-completions.md), [sse-format.md](sse-format.md)).

Conformidade (`tests/http/contract/test_native_route.py`): cada campo de ampliação recusado nomeando o campo antes de
qualquer execução (US3 cen. 1); campo desconhecido recusado; `assistant` + `model` resolvem como o id completo; mesmo
formato de resposta da compat, com e sem streaming.
