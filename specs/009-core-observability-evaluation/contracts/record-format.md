# Contrato — formato do registro de trace

O que um backend guarda e o que a consulta devolve. É o formato que o adapter JSONL grava e que a 008 (Fase 2) vai
renderizar; mudá-lo quebra traces já gravados, então vale como contrato.

## Um registro

```json
{
  "at": "2026-09-17T14:03:11.412000+00:00",
  "type": "model_call",
  "request_id": "req-7f3a",
  "role": "generation",
  "provider": "ollama",
  "model": "qwen3:1.7b",
  "input_tokens": 412,
  "output_tokens": 87,
  "duration_ms": 8321.5
}
```

| Chave | Regra |
|---|---|
| `at` | ISO 8601 com deslocamento de timezone; estampado pelo serviço (nunca pelo emissor) |
| `type` | nome do evento em `snake_case`, derivado do nome da classe |
| `request_id` | identificador da requisição |
| demais chaves | campos do evento, já redigidos; `None` é **omitido**; `frozenset` vira lista ordenada; `tuple` vira lista; `datetime` vira ISO 8601 |

As três chaves `at`, `type` e `request_id` estão sempre presentes. `request_id` é o único campo de evento que sobe
para esse nível; nenhum evento pode ter campo chamado `at` ou `type` (colisão é erro de programação, verificada em
teste).

## Um arquivo

```text
<diretório de trace>/trace-2026-09-17.jsonl
```

Uma linha JSON por registro, na ordem de emissão, sem vírgula nem envelope. O arquivo é escolhido pela data de `at`,
em UTC; a leitura de uma requisição varre os arquivos do diretório. Linha ilegível é ignorada com aviso em log — um
arquivo truncado por queda de processo não impede consultar o resto ([research.md](../research.md) R6).

## Exemplos dos outros tipos

```json
{"at": "…", "type": "execution_started", "request_id": "req-7f3a", "assistant": "geral", "flow": "chat",
 "packs": ["generic"], "reference_time": "2026-09-17T00:00:00+00:00"}
{"at": "…", "type": "validation_run", "request_id": "req-7f3a", "pack": "generic",
 "validator": "non_empty_answer", "ok": true, "issues": [], "flags": []}
{"at": "…", "type": "execution_error", "request_id": "req-7f3a", "stage": "generation",
 "kind": "ProviderTimeout", "message": "timeout após 30s chamando POST /v1/chat/completions"}
{"at": "…", "type": "execution_finished", "request_id": "req-7f3a", "ok": true, "duration_ms": 9102.7}
{"at": "…", "type": "tool_call", "request_id": "req-7f3a", "tool": "financeiro.saldo", "kind": "mcp",
 "status": "ok", "duration_ms": 182.4, "size_bytes": 340, "truncated": false}
{"at": "…", "type": "controller_decision", "request_id": "req-7f3a", "iteration": 1, "action": "tool",
 "tool": "financeiro.saldo"}
{"at": "…", "type": "controller_decision", "request_id": "req-7f3a", "iteration": 3, "action": "limit",
 "reason": "iterations"}
{"at": "…", "type": "controller_decision", "request_id": "req-c4d0", "iteration": 1, "action": "view_image",
 "images": ["img-3f9a0c1b2d4e"]}
{"at": "…", "type": "coverage_gate", "request_id": "req-9b21", "candidates": 20, "passages": 5,
 "best_score": 0.88, "covered": true, "route": "generate"}
{"at": "…", "type": "retrieval", "request_id": "req-9b21",
 "retrieved": [{"chunk_id": "por#r31@p37", "score": 0.88, "document": "POR", "status": "vigente", "page": 37}, …],
 "reranked": […], "delivered": […]}
```

No exemplo de `execution_finished`, `reason` é `None` e por isso não aparece; o mesmo vale para `tool` e `reason` do
`controller_decision` quando a ação não os tem, e para `threshold` do `coverage_gate` sem limiar. `tool_call` (004) e
`controller_decision` (005) entraram na Fase 3, `coverage_gate` (005) na Fase 5 e `retrieval` (005) na Fase 6 — trechos sem texto —, sob o
[ADR-017](../../../docs/adr/ADR-017-trace-sink-cresce-por-eventos-aditivos.md).

## Redação no registro

A redação acontece **na serialização**, antes de o registro existir — nenhum backend recebe credencial. Exemplo com
mensagem de erro que ecoa cabeçalho:

```text
emitido:  message="401 Unauthorized: {'Authorization': 'Bearer sk-abc123'}"
gravado:  "message": "401 Unauthorized: {'Authorization': 'Bearer «redigido»'}"
```

Regras completas na tabela de redação do [data-model.md](../data-model.md). Texto acima de 2000 caracteres é gravado
truncado, com a marca `… [truncado: N caracteres]`.

## Fase 9 (2026-10-14): `model_exchange`

| Campo | Tipo | Nota |
|---|---|---|
| `role` | `str` | papel de modelo |
| `provider`, `model` | `str` | |
| `messages` | lista de `{role, content}` | redigido; cada `content` cortado em 16 KiB com `«… cortado»` |
| `output` | `str` | redigido e cortado igual |

Nunca aparece no JSONL nem na memória (backends primários).

## Gráficos (2026-10-28, [ADR-052](../../../docs/adr/ADR-052-graficos-na-conversa.md))

- `tool_call` ganha `charts`: lista de `{id, kind, series, points}` dos gráficos do resultado (vazia sem gráfico);
  nunca os dados nem os textos.

## Imagens (2026-10-22, [ADR-044](../../../docs/adr/ADR-044-imagens-na-conversa.md))

- `tool_call` ganha `attachments`: lista de `{id, mime, size_bytes}` das imagens do resultado (vazia sem imagem);
  `size_bytes` do evento continua sendo o do texto.
- `controller_decision` ganha a ação `view_image` e o campo `images`, só nela: os ids escolhidos — um por iteração no
  loop; os da etapa `image_gate`, de uma vez, possivelmente nenhum.
- `model_exchange` leva `[imagem <id>]` no lugar de cada imagem de uma mensagem, nunca o data URI.

Nenhum registro leva os bytes de uma imagem.
