# Contrato — tradução dos eventos do motor em SSE

A construção do chunk é pura (`domain/openai_chunks.py`); `adapters/sse.py` só serializa e escreve
([research.md](../research.md) R4). Cada evento vira um chunk **no instante em que chega** — nada é acumulado, que é o
que sustenta a SC-003.

## A sequência

```text
(abre)         → chunk com delta {"role": "assistant"}
ProgressEvent  → chunk com delta {} e x_axon.progress = {"stage": "..."}
TokenEvent     → chunk com delta {"content": "<pedaço>"}
FinalEvent     → chunk com delta {}, finish_reason e x_axon (citações, marcações, erros)
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

## Campo extra `x_axon`

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

## Fase 7 (2026-10-13): progresso como raciocínio e fila (research R34, R35)

```text
(abre)                      → delta {"role": "assistant"}
(na fila)                   → delta {"reasoning_content": "Aguardando uma vaga (posição 2 na fila)…\n"}, x_axon.progress {"stage": "queue", "detail": "2"}
ProgressEvent antes do texto → delta {"reasoning_content": "<linha>\n"}, x_axon.progress {"stage": …, "detail": …}
TokenEvent                  → delta {"content": "<pedaço>"}
ProgressEvent depois do texto → delta {}, x_axon.progress (como antes)
FinalEvent                  → como antes
```

| Regra | Motivo |
|---|---|
| Linha de raciocínio só antes do primeiro `delta.content` | o Open WebUI abriria um segundo bloco de "pensamento" abaixo da resposta |
| Cada linha termina em `\n` | o Open WebUI concatena os `reasoning_content` de um bloco |
| Nunca texto de progresso em `delta.content` | a resposta é só a resposta (FR-005) |
| Espera esgotada com o stream aberto → chunk final `finish_reason: "error"` + `QueueTimeout`, depois `[DONE]` | o status já foi enviado; nenhuma chamada de modelo aconteceu |

Suíte: `test_openai_chunks.py` ganha os casos de raciocínio (antes e depois do primeiro token);
`test_progress_text.py`, a tabela.

## Timeline de status (2026-10-13, FR-005a; research R42)

Com `x-axon-progress: status`:

```text
(abre)                      → delta {"role": "assistant"}
(na fila)                   → delta {}, event status {"description": "Aguardando uma vaga (posição 2 na fila)…", "done": false}, x_axon.progress
ProgressEvent               → delta {}, event status {"description": "<linha de início>", "done": false}, x_axon.progress
StepFinished                → delta {}, event status {"description": "<desfecho> · <tempo>", "done": true} (uma por linha)
TokenEvent                  → delta {"content": "<pedaço>"}
FinalEvent                  → delta {}, event status por registro e a linha de conclusão ("done": true); depois o chunk final de sempre
```

`event` = `{"type": "status", "data": {"description": …, "done": …}}`, no mesmo nível de `choices`.

| Regra | Motivo |
|---|---|
| Nenhum `reasoning_content` nesse modo | a timeline substitui o bloco de "pensamento" |
| Status também depois do primeiro texto | conferência, avisos e conclusão fazem parte da timeline |
| Status sempre com `delta: {}` | a resposta é só a resposta (FR-005) |
| A última linha antes do chunk final tem `done: true` | sem isso, o Open WebUI deixa a última linha animada |
| Sem o cabeçalho (ou `reasoning`), a seção "Fase 7" vale como antes, e `StepFinished` não gera chunk | FR-005 |

Suíte: `test_timeline.py` (as linhas), `test_openai_chunks.py` (`status_chunk`), `test_chat_request.py` (o cabeçalho),
`test_admission.py` (fila no modo `status`), `test_open_webui.py` (o pedido do v0.12 com o cabeçalho, o 400 nas duas
entradas e a requisição nativa).
