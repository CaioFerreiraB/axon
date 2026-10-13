"""Conversão do conjunto dourado — pura (research R16; contracts/eval-harness.md). Recebe o mapeamento já lido do YAML.

Item com problema de formato vira `InvalidItem` nomeando o campo, e o resto segue; só o que torna o arquivo inútil
(não é mapeamento, `version` desconhecida, sem `name` ou `items`, `k` ou tolerâncias inválidos) levanta.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, Final

from ai_core.eval.api import DEFAULT_K, Evidence, GoldenItem, GoldenSet, GoldenSetError, InvalidItem

VERSION: Final = 1


class _ItemError(ValueError):
    pass


def parse_golden(data: object) -> GoldenSet:
    if not isinstance(data, Mapping):
        raise GoldenSetError("o conjunto dourado precisa ser um mapeamento YAML")
    if data.get("version") != VERSION:
        raise GoldenSetError(f"version do conjunto dourado precisa ser {VERSION}: {data.get('version')!r}")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise GoldenSetError("o conjunto dourado precisa de name")
    raw_items = data.get("items")
    if not isinstance(raw_items, list):
        raise GoldenSetError("o conjunto dourado precisa de items (uma lista)")
    assistant = data.get("assistant")
    if assistant is not None and (not isinstance(assistant, str) or not assistant.strip()):
        raise GoldenSetError("assistant precisa ser texto")
    items: list[GoldenItem] = []
    invalid: list[InvalidItem] = []
    seen: set[str] = set()
    for raw in raw_items:
        raw_id = raw.get("id") if isinstance(raw, Mapping) else None
        item_id = raw_id if isinstance(raw_id, str) else None
        try:
            item = _item(raw)
        except (_ItemError, ValueError) as error:
            invalid.append(InvalidItem(id=item_id, reason=str(error)))
            continue
        if item.id in seen:
            invalid.append(InvalidItem(id=item.id, reason="id repetido no conjunto"))
            continue
        seen.add(item.id)
        items.append(item)
    try:
        return GoldenSet(
            name=name,
            assistant=assistant,
            k=_k(data.get("k", DEFAULT_K)),
            tolerances=_tolerances(data.get("tolerances", {})),
            items=items,
            invalid=invalid,
        )
    except ValueError as error:
        raise GoldenSetError(str(error)) from error


def _k(value: object) -> tuple[int, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise GoldenSetError("k precisa ser uma lista de inteiros")
    return tuple(value)  # o GoldenSet valida os valores


def _tolerances(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise GoldenSetError("tolerances precisa ser um mapeamento métrica → número")
    tolerances: dict[str, float] = {}
    for name, number in value.items():
        if not isinstance(name, str) or isinstance(number, bool) or not isinstance(number, int | float):
            raise GoldenSetError(f"tolerância inválida: {name!r}: {number!r}")
        tolerances[name] = float(number)
    return tolerances


def _item(raw: object) -> GoldenItem:
    if not isinstance(raw, Mapping):
        raise _ItemError("item precisa ser um mapeamento")
    question = raw.get("question")
    if not isinstance(question, str) or not question.strip():
        raise _ItemError("question vazia ou ausente")
    reference_answer = raw.get("reference_answer")
    if reference_answer is not None and not isinstance(reference_answer, str):
        raise _ItemError("reference_answer precisa ser texto")
    extra = raw.get("extra", {})
    if not isinstance(extra, Mapping):
        raise _ItemError("extra precisa ser um mapeamento")
    try:
        return GoldenItem(
            id=raw.get("id"),  # type: ignore[arg-type]
            question=question,
            reference_time=_reference_time(raw.get("reference_time")),
            expected_documents=_evidences(raw.get("expected_documents", []), "expected_documents"),
            reference_answer=reference_answer,
            expected_citations=_evidences(raw.get("expected_citations", []), "expected_citations"),
            extra=dict(extra),
        )
    except ValueError as error:
        raise _ItemError(str(error)) from error


def _reference_time(value: object) -> datetime:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        try:
            moment = datetime.fromisoformat(value)
        except ValueError as error:
            raise _ItemError(f"reference_time não é ISO 8601: {value!r}") from error
    else:
        raise _ItemError("reference_time ausente (ISO 8601 com fuso)")
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise _ItemError("reference_time precisa ter fuso")
    return moment


def _evidences(value: object, field_name: str) -> tuple[Evidence, ...]:
    if not isinstance(value, list):
        raise _ItemError(f"{field_name} precisa ser uma lista")
    evidences: list[Evidence] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise _ItemError(f"{field_name}: cada evidência é um mapeamento com document")
        document, section, chunk_id = raw.get("document"), raw.get("section"), raw.get("chunk_id")
        if not isinstance(document, str) or not document.strip():
            raise _ItemError(f"{field_name}: evidência sem document")
        if (section is not None and not isinstance(section, str)) or (
            chunk_id is not None and not isinstance(chunk_id, str)
        ):
            raise _ItemError(f"{field_name}: section e chunk_id precisam ser texto")
        evidences.append(_evidence(document, section, chunk_id, field_name))
    return tuple(evidences)


def _evidence(document: str, section: Any, chunk_id: Any, field_name: str) -> Evidence:
    try:
        return Evidence(document=document, section=section, chunk_id=chunk_id)
    except ValueError as error:
        raise _ItemError(f"{field_name}: {error}") from error
