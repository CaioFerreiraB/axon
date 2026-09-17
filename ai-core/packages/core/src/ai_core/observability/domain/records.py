"""Evento + instante → registro de trace (spec 009, research R10; contracts/record-format.md).

Puro: monta a estrutura de valores JSON e aplica a redação. Quem transforma em texto é o adapter.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Final

from ai_core.observability.api import TraceEvent, TraceRecord
from ai_core.observability.domain.redaction import redact_value
from ai_core_contracts import JSONValue

_CAMEL_BOUNDARY: Final = re.compile(r"(?<!^)(?=[A-Z])")
_RESERVED: Final = frozenset({"at", "type", "request_id"})


def record_type(event: TraceEvent) -> str:
    """Nome do evento em `snake_case`: `ExecutionStarted` → `execution_started`."""
    return _CAMEL_BOUNDARY.sub("_", type(event).__name__).lower()


def _as_json(value: object) -> JSONValue:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, frozenset | set):
        return sorted(str(item) for item in value)
    if isinstance(value, Mapping):
        return {str(key): _as_json(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return [_as_json(item) for item in value]
    if isinstance(value, bool | int | float | str) or value is None:
        return value
    return str(value)


def to_record(event: TraceEvent, at: datetime) -> TraceRecord:
    """Registro pronto para o backend: `at`, `type` e `request_id` fora dos atributos, tudo já redigido."""
    attributes: dict[str, JSONValue] = {}
    for field in dataclasses.fields(event):
        if field.name in _RESERVED:
            continue
        value = getattr(event, field.name)
        if value is None:
            continue
        attributes[field.name] = redact_value(_as_json(value))
    return TraceRecord(at=at, type=record_type(event), request_id=event.request_id, attributes=attributes)
