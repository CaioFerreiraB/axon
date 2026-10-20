# Contrato — conversas no servidor (US7, research R21)

## No chat (compat e nativa)

| Pedido | O que acontece |
|---|---|
| sem `conversation_id` | executa com as mensagens do pedido; cria uma conversa antes de executar; grava só a última mensagem de usuário e a resposta |
| com `conversation_id` do subject e do mesmo Assistant | executa com o histórico armazenado + a **última** mensagem de usuário do pedido; descarta o resto do que o cliente mandou |
| com `conversation_id` de outro subject ou inexistente | 404, antes de qualquer execução |
| com `conversation_id` de outro Assistant | 400 `conversation_assistant_mismatch`, antes de qualquer execução |

A resposta devolve o id no cabeçalho `X-Conversation-Id` e em `x_axon.conversation_id` — no corpo do
`chat.completion`, ou no primeiro chunk em streaming (FR-014). Só evento final sem erro grava a troca; conversa apagada
durante a execução não recebe a troca (FR-018).

## Rotas (nas duas superfícies, para o mesmo subject)

| Rota | Sucesso |
|---|---|
| `GET /v1/conversations?limit=&cursor=` | 200 `{"data": [...], "next_cursor": …}`, mais recente primeiro |
| `GET /v1/conversations/{id}` | 200, estado e mensagens |
| `DELETE /v1/conversations/{id}` | 204 |

`limit` entre 1 e 100 (default 20). Conversa de outro subject ou inexistente → 404 nas três.

## Expiração

`ConversationService.expire()` apaga as conversas cuja última atividade é anterior a `agora − prazo` (prazo default de
180 dias, configurável pelo operador — FR-019), pelo relógio da porta. Quem agenda é a composition root (011).

Conformidade: `tests/http/contract/test_conversation_routes.py` (US7 cen. 1, 2, 4, 5, 6; mensagens de assistente do
cliente nunca entram numa execução com id — SC-005), `tests/http/integration/test_conversation_restart.py` (cen. 3:
serviço novo sobre o mesmo armazenamento, também contra Postgres), `tests/http/unit/test_conversation_expiry.py` (cen.
7 e SC-007, com relógio fixo).
