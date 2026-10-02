# Contrato — `POST /{v1|private/v1}/chat/completions`

Dono: spec 008. Consumidores: clientes externos (Open WebUI, SDKs da OpenAI, scripts). É o seam deste módulo — não há
seam Python. **Mudar o formato exige ADR**, porque a compatibilidade é o ponto (SC-004).

## Requisição

```json
{
  "model": "geral/qwen3:1.7b",
  "messages": [{"role": "user", "content": "qual é a capital?"}],
  "stream": true
}
```

- `model` aceita `"<assistant>"` ou `"<assistant>/<modelo>"`; sem a parte do modelo, usa o default do Assistant.
- `messages` precisa de ao menos uma mensagem de papel `user`.
- `temperature`, `top_p` e `max_tokens` são aceitos e ignorados nesta fase (entram com os limites do Assistant na
  Fase 2).

## Regras da rota

| Regra | Origem | Verificada por |
|---|---|---|
| `tools`, `functions`, `tool_choice` e `function_call` são rejeitados com 400 que nomeia o campo | princípio IV | conformidade |
| Campo de data de referência é rejeitado com 400 que o nomeia, em qualquer superfície | FR-012, ADR-013 | conformidade |
| Assistant inexistente e Assistant não autorizado respondem 404 idênticos | FR-009 | conformidade |
| Credencial inválida responde 401 | FR-001 | conformidade |
| Toda resposta carrega `X-Request-Id`, o mesmo identificador do trace | FR-010 | conformidade |
| Nenhuma chamada de modelo acontece antes de a requisição ser aceita | princípio VII | conformidade |
| A rota existe, idêntica, nas duas superfícies | FR-001, US1 | conformidade |

## Resposta sem streaming

```json
{
  "id": "chatcmpl-req-1",
  "object": "chat.completion",
  "created": 1790000000,
  "model": "geral/qwen3:1.7b",
  "choices": [{
    "index": 0,
    "message": {"role": "assistant", "content": "Brasília"},
    "finish_reason": "stop"
  }],
  "x_ai_core": {"request_id": "req-1", "citations": [], "flags": [], "errors": []}
}
```

## Resposta em streaming

`Content-Type: text/event-stream`. Ver [sse-format.md](sse-format.md) para a sequência exata.

## Suíte de conformidade

`packages/core/tests/http/contract/test_chat_completions.py`, contra a app montada em processo com o motor real e o
provider simulado (research R10):

1. `stream: false` devolve um `chat.completion` com a resposta completa e `finish_reason: "stop"`;
2. `stream: true` devolve `text/event-stream`, com papel no primeiro chunk, um chunk por pedaço e `[DONE]` no fim;
3. a resposta traz `X-Request-Id`, e ele é o mesmo identificador que aparece no trace da requisição;
4. `id` da resposta é `chatcmpl-<request_id>`;
5. `tools`, `functions`, `tool_choice` e `function_call` → 400 nomeando o campo, sem tocar o provider;
6. campo de data de referência → 400 nomeando o campo, sem tocar o provider;
7. `messages` vazio, sem mensagem de usuário, ou `model` ausente → 400;
8. Assistant desconhecido → 404, com corpo idêntico ao de um Assistant não autorizado;
9. credencial recusada pelo autenticador → 401;
10. a rota responde igual em `/v1` e em `/private/v1`;
11. falha de execução depois do stream aberto → chunk final com `finish_reason: "error"`, motivos no campo extra e
    `[DONE]`, sem exceção vazando e sem conexão pendurada;
12. falha de execução sem streaming → **502** com os motivos e o texto parcial no corpo e o cabeçalho
    `x-should-retry: false`, nunca 200 com marcador de erro (princípio VII). Falha = algum registro com gravidade
    `error`; só `notice` (limite de iterações, ação inválida, corte de contexto, apontamento de validator) é sucesso,
    200 com `finish_reason: "stop"` (ADR-018, FR-022);
13. um cliente OpenAI padrão, apontado para a app em processo, conversa em streaming sem nenhuma adaptação — é a
    prova direta da SC-004.

## O que esta rota **não** faz nesta fase

- Não lista modelos (US2), não cria nem continua conversa (US7), não faz CRUD (US4) e não reporta saúde (US5).
- Não enfileira nem limita concorrência (US6, Fase 7).
- Não interpreta o conteúdo das mensagens, não escolhe modelo e não conhece pack nem flow.
