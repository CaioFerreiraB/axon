"""Backend de trace em arquivo JSONL (spec 009, research R6; contracts/record-format.md).

Um arquivo por dia (`trace-YYYY-MM-DD.jsonl`, pela data de `at` em UTC), uma linha JSON por registro, gravada no
momento da emissão. Linha ilegível é ignorada na leitura: arquivo truncado por queda de processo não impede consultar
o resto. Este é o único lugar do módulo que fala JSON em texto e que toca disco.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from axon_ai.observability.api import TraceRecord
from axon_ai_contracts import JSONValue

logger: Final = logging.getLogger("axon_ai.observability")

_PREFIX: Final = "trace-"
_SUFFIX: Final = ".jsonl"


class JsonlTraceBackend:
    """Escrita e leitura de trace em arquivos JSONL num diretório."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def _path(self, at: datetime) -> Path:
        return self._directory / f"{_PREFIX}{at.astimezone(UTC).date().isoformat()}{_SUFFIX}"

    def export(self, record: TraceRecord) -> None:
        payload: dict[str, JSONValue] = {
            "at": record.at.isoformat(),
            "type": record.type,
            "request_id": record.request_id,
            **record.attributes,
        }
        path = self._path(record.at)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
            handle.flush()

    def read(self, request_id: str) -> tuple[TraceRecord, ...]:
        records: list[TraceRecord] = []
        for path in sorted(self._directory.glob(f"{_PREFIX}*{_SUFFIX}")):
            records.extend(self._read_file(path, request_id))
        return tuple(records)

    def _read_file(self, path: Path, request_id: str) -> list[TraceRecord]:
        found: list[TraceRecord] = []
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            record = self._parse(line, path, number)
            if record is not None and record.request_id == request_id:
                found.append(record)
        return found

    def _parse(self, line: str, path: Path, number: int) -> TraceRecord | None:
        try:
            payload = json.loads(line)
            if not isinstance(payload, Mapping):
                raise ValueError("registro não é um objeto")
            attributes = {key: value for key, value in payload.items() if key not in ("at", "type", "request_id")}
            return TraceRecord(
                at=datetime.fromisoformat(str(payload["at"])),
                type=str(payload["type"]),
                request_id=str(payload["request_id"]),
                attributes=attributes,
            )
        except (ValueError, KeyError, TypeError) as error:
            logger.warning("linha %d ilegível em %s: %s", number, path.name, error)
            return None


class SystemClock:
    """Relógio do processo. Único lugar do módulo que lê a hora (ADR-013)."""

    def now(self) -> datetime:
        return datetime.now(UTC)
