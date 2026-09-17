# Quickstart — validar o trace por requisição (Fase 1, US1)

Comandos a partir de `ai-core/`. Nesta máquina, use `XDG_DATA_HOME=$HOME/.local/share` no `uv` (ver CLAUDE.md).

## 1. Suíte do módulo

```bash
uv run pytest packages/core/tests/observability -q
```

**Esperado**: verde — redação e serialização puras, os dois seams, as três portas (memória × JSONL) e o JSONL em
`tmp_path`.

## 2. Emitir e consultar em memória

```bash
uv run python - <<'PY'
from datetime import UTC, datetime

from ai_core.observability.adapters.memory import FixedClock, InMemoryTraceBackend
from ai_core.observability.api import ExecutionFinished, ExecutionStarted, ModelCall
from ai_core.observability.service import TraceService

backend = InMemoryTraceBackend()
service = TraceService(exporter=backend, reader=backend, clock=FixedClock(datetime(2026, 9, 17, 14, tzinfo=UTC)))

service.emit(ExecutionStarted(request_id="req-1", assistant="geral", flow="chat", packs=("generic",),
                              reference_time=datetime(2026, 9, 17, tzinfo=UTC)))
service.emit(ModelCall(request_id="req-1", role="generation", provider="ollama", model="qwen3:1.7b",
                       input_tokens=412, output_tokens=87, duration_ms=8321.5))
service.emit(ExecutionFinished(request_id="req-1", ok=True, duration_ms=9102.7))

for record in service.trace("req-1").records:
    print(record.type, dict(record.attributes))
print("descartados:", service.dropped_events())
PY
```

**Esperado**: três linhas na ordem `execution_started`, `model_call`, `execution_finished`; `reason` ausente no
último (`None` é omitido); `descartados: 0`.

## 3. Credencial não aparece

```bash
uv run python - <<'PY'
from datetime import UTC, datetime

from ai_core.observability.adapters.memory import FixedClock, InMemoryTraceBackend
from ai_core.observability.api import ExecutionError
from ai_core.observability.service import TraceService

backend = InMemoryTraceBackend()
service = TraceService(exporter=backend, reader=backend, clock=FixedClock(datetime.now(UTC)))
service.emit(ExecutionError(
    request_id="req-2", stage="generation", kind="ProviderError",
    message="401 Unauthorized: {'Authorization': 'Bearer sk-abc123'} em https://user:s3nha@api.exemplo/v1",
))
[record] = service.trace("req-2").records
print(record.attributes["message"])
PY
```

**Esperado**: a mensagem com `Bearer «redigido»` e `https://user:«redigido»@api.exemplo/v1` — nenhum `sk-abc123` nem
`s3nha` em lugar algum ([contracts/record-format.md](contracts/record-format.md)).

## 4. Falha do backend não interrompe

```bash
uv run python - <<'PY'
from datetime import UTC, datetime

from ai_core.observability.adapters.memory import FixedClock
from ai_core.observability.api import ExecutionFinished
from ai_core.observability.service import TraceService


class Broken:
    def export(self, record): raise OSError("disco cheio")


service = TraceService(exporter=Broken(), reader=None, clock=FixedClock(datetime.now(UTC)))
service.emit(ExecutionFinished(request_id="req-3", ok=True, duration_ms=1.0))   # não levanta
print("descartados:", service.dropped_events())
try:
    service.trace("req-3")
except Exception as error:
    print(type(error).__name__, error)
PY
```

**Esperado**: `descartados: 1` (mais um aviso no logger `ai_core.observability`) e, na consulta,
`TraceQueryUnavailable` nomeando o backend — o perfil não tem leitura (FR-011, [research.md](research.md) R5, R8).

## 5. Arquivo JSONL e rotação por dia

```bash
tmp=$(mktemp -d)
uv run python - "$tmp" <<'PY'
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from ai_core.observability.adapters.jsonl import JsonlTraceBackend
from ai_core.observability.adapters.memory import FixedClock
from ai_core.observability.api import ExecutionFinished
from ai_core.observability.service import TraceService

directory = Path(sys.argv[1])
backend = JsonlTraceBackend(directory)
hoje = datetime(2026, 9, 17, 23, 50, tzinfo=UTC)
for instante, request_id in ((hoje, "req-a"), (hoje + timedelta(minutes=20), "req-b")):
    service = TraceService(exporter=backend, reader=backend, clock=FixedClock(instante))
    service.emit(ExecutionFinished(request_id=request_id, ok=True, duration_ms=1.0))

print(sorted(path.name for path in directory.iterdir()))
print([record.request_id for record in TraceService(exporter=backend, reader=backend,
                                                    clock=FixedClock(hoje)).trace("req-b").records])
PY
cat "$tmp"/*.jsonl ; rm -rf "$tmp"
```

**Esperado**: dois arquivos, `trace-2026-09-17.jsonl` e `trace-2026-09-18.jsonl`; a consulta de `req-b` encontra o
registro no arquivo do dia seguinte; cada linha do `cat` é um JSON válido com `at`, `type` e `request_id`.

## 6. Fronteiras, tipos e formatação

```bash
uv run lint-imports
uv run mypy
uv run ruff check packages/core && uv run ruff format --check packages/core
```

**Esperado**: os contratos novos do módulo aparecem como `KEPT` — em especial "o núcleo do trace não importa
biblioteca de observabilidade", que é o que mantém a decisão de [research.md](research.md) R1 executável; mypy strict
e ruff limpos.

## 7. A suíte completa do workspace continua verde

```bash
uv run pytest
```

**Esperado**: contratos (001), Pack Runtime (002), pack genérico (010) e trace (009) verdes na mesma execução.
