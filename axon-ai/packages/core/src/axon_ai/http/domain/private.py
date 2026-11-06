"""Formatos da superfície privada (US5, research R20): packs, chaves e saúde. Puro."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

from axon_ai.assistants.api import ApiKeyInfo
from axon_ai.http.domain.errors import InvalidRequest
from axon_ai.http.domain.records import HealthReport
from axon_ai.packs.api import PackEntry

ISSUE_FIELDS: Final = frozenset({"subject", "groups", "label", "scopes"})


def packs_json(entries: Sequence[PackEntry]) -> dict[str, Any]:
    return {
        "data": [
            {
                "name": entry.name,
                "version": entry.version,
                "contract_version": entry.contract_version,
                "status": str(entry.status),
                "error": entry.error,
            }
            for entry in entries
        ]
    }


def issue_request(body: Mapping[str, Any]) -> tuple[str, tuple[str, ...], str | None, tuple[str, ...] | None]:
    """`{"subject", "groups"?, "label"?, "scopes"?}` — nada além disso. Quem valida os nomes dos escopos e quem pode
    conceder cada um é a 003 (R70); aqui só a forma."""
    for key in sorted(str(k) for k in body if k not in ISSUE_FIELDS):
        raise InvalidRequest(f"campo '{key}' não é aceito na emissão de chave", field=key)
    subject = body.get("subject")
    if not isinstance(subject, str):
        raise InvalidRequest("campo 'subject' é obrigatório", field="subject")
    groups = body.get("groups", [])
    if not _texts(groups):
        raise InvalidRequest("campo 'groups' precisa ser uma lista de textos", field="groups")
    label = body.get("label")
    if label is not None and not isinstance(label, str):
        raise InvalidRequest("campo 'label' precisa ser um texto", field="label")
    scopes = body.get("scopes")
    if scopes is not None and not _texts(scopes):
        raise InvalidRequest("campo 'scopes' precisa ser uma lista de textos", field="scopes")
    return subject, tuple(groups), label, tuple(scopes) if scopes is not None else None


def _texts(value: Any) -> bool:
    return not isinstance(value, str) and isinstance(value, Sequence) and all(isinstance(v, str) for v in value)


def key_json(info: ApiKeyInfo) -> dict[str, Any]:
    """Nunca a chave nem o hash: só a emissão acrescenta `key`, uma vez."""
    return {
        "key_id": info.key_id,
        "subject": info.subject,
        "groups": sorted(info.groups),
        "scopes": sorted(info.scopes),
        "label": info.label,
        "created_at": info.created_at.isoformat(),
        "revoked_at": info.revoked_at.isoformat() if info.revoked_at is not None else None,
        "rotated_at": info.rotated_at.isoformat() if info.rotated_at is not None else None,
    }


def health_json(report: HealthReport) -> dict[str, Any]:
    return {
        "status": report.status,
        "items": [
            {"name": item.name, "ok": item.ok, "critical": item.critical, "detail": item.detail}
            for item in report.items
        ],
    }
