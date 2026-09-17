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
```

No último exemplo, `reason` é `None` e por isso não aparece.

## Redação no registro

A redação acontece **na serialização**, antes de o registro existir — nenhum backend recebe credencial. Exemplo com
mensagem de erro que ecoa cabeçalho:

```text
emitido:  message="401 Unauthorized: {'Authorization': 'Bearer sk-abc123'}"
gravado:  "message": "401 Unauthorized: {'Authorization': 'Bearer «redigido»'}"
```

Regras completas na tabela de redação do [data-model.md](../data-model.md). Texto acima de 2000 caracteres é gravado
truncado, com a marca `… [truncado: N caracteres]`.
