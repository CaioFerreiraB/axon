# Contrato — tradução dos eventos do motor em SSE

A construção do chunk é pura (`domain/openai_chunks.py`); `adapters/sse.py` só serializa e escreve
([research.md](../research.md) R4). Cada evento vira um chunk **no instante em que chega** — nada é acumulado, que é o
que sustenta a SC-003.

## A sequência

```text
(abre)         → chunk com delta {"role": "assistant"}
ProgressEvent  → chunk com delta {} e x_ai_core.progress = {"stage": "..."}
TokenEvent     → chunk com delta {"content": "<pedaço>"}
FinalEvent     → chunk com delta {}, finish_reason e x_ai_core (citações, marcações, erros)
(fecha)        → data: [DONE]
```

## Formato de um chunk

```text
data: {"id": "chatcmpl-req-1", "object": "chat.completion.chunk", "created": 1790000000,
       "model": "geral/qwen3:1.7b", "choices": [{"index": 0, "delta": {"content": "Bras"}, "finish_reason": null}]}

```

Cada chunk é uma linha `data: ` com JSON e termina com linha em branco. `id`, `object`, `created` e `model` se repetem
em todos.

## Regras

| Regra | Motivo |
|---|---|
| O papel (`role`) aparece **só** no primeiro chunk | é o que os clientes usam para abrir a mensagem; repetir confunde alguns SDKs |
| `finish_reason` aparece **só** no chunk final | formato da OpenAI |
| Progresso vai com `delta` vazio e campo extra | cliente padrão ignora o campo extra e não vê texto espúrio (R5) |
| O stream sempre termina com `[DONE]`, inclusive em falha | evita cliente pendurado (R6) |
| `finish_reason` é `"error"` quando o evento final traz erro de execução | dá ao cliente um desfecho honesto |
| Apontamento de validator **não** vira `"error"` | reprovar é achado sobre a resposta, não falha de execução (005) |
| Nada é escrito depois de `[DONE]` | — |

## Campo extra `x_ai_core`

```json
{"request_id": "req-1", "citations": [{"chunk_id": "c1"}], "flags": ["nao_fundamentada"], "errors": []}
```

Presente no chunk final e na resposta sem streaming; nos chunks de progresso, só com `progress`. É ignorado por
clientes compatíveis e é onde a plataforma diz o que a OpenAI não tem onde dizer.

## Suíte

`packages/core/tests/http/unit/test_openai_chunks.py` — pura, sem servidor:

1. o primeiro chunk traz o papel e nenhum conteúdo;
2. um `TokenEvent` vira um chunk com o pedaço em `delta.content`, sem `finish_reason`;
3. um `ProgressEvent` vira chunk com `delta` vazio e a etapa no campo extra;
4. o `FinalEvent` vira chunk com `finish_reason`, citações, marcações e erros;
5. evento final com erro de execução produz `finish_reason: "error"`;
6. evento final só com apontamento de validator mantém `finish_reason: "stop"`;
7. a resposta sem streaming junta os pedaços e traz o mesmo campo extra;
8. `id`, `object`, `created` e `model` são iguais em todos os chunks de uma resposta.
