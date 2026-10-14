"""Adapters em memória e de teste de todas as portas da 003 (contracts/ports.md).

São o adapter em memória que o princípio XIII exige de cada porta e o que o perfil de teste da composition root usa.
Moram na distribuição, não no kit de teste, pelo mesmo motivo do relógio fixo da 005: a suíte de um pack externo sobe a
plataforma de verdade com eles.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from types import MappingProxyType

from ai_core.assistants.api import Conflict
from ai_core.assistants.domain.definitions import AssistantsConfig, read_config
from ai_core.assistants.domain.keys import ApiKeyRecord
from ai_core.assistants.domain.overrides import OverrideHistoryRecord, StoredOverride
from ai_core.assistants.ports import StoredUserAssistant


class InMemoryAssistantConfigSource:
    """Configuração a partir de um mapeamento já carregado — a mesma interpretação do adapter YAML."""

    def __init__(self, data: Mapping[str, object] | None = None) -> None:
        self._data = dict(data or {})

    def load(self) -> AssistantsConfig:
        return read_config(self._data, origin="configuração em memória")


class InMemoryUserAssistantStore:
    """Assistants de usuário num dicionário por (dono, nome)."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], StoredUserAssistant] = {}

    async def get(self, owner: str, name: str) -> StoredUserAssistant | None:
        return self._records.get((owner, name))

    async def list(self, owner: str) -> Sequence[StoredUserAssistant]:
        return sorted((r for (o, _), r in self._records.items() if o == owner), key=lambda r: r.name)

    async def all(self) -> Sequence[StoredUserAssistant]:
        return sorted(self._records.values(), key=lambda r: (r.owner, r.name))

    async def insert(self, record: StoredUserAssistant) -> bool:
        key = (record.owner, record.name)
        if key in self._records:
            return False
        self._records[key] = record
        return True

    async def replace(self, record: StoredUserAssistant) -> bool:
        key = (record.owner, record.name)
        if key not in self._records:
            return False
        self._records[key] = record
        return True

    async def delete(self, owner: str, name: str) -> bool:
        return self._records.pop((owner, name), None) is not None


class InMemoryApiKeyStore:
    """Chaves num dicionário por `key_id`. Cada processo tem o próprio: chave da CLI só vale no perfil persistente."""

    def __init__(self) -> None:
        self._records: dict[str, ApiKeyRecord] = {}

    def seed(self, record: ApiKeyRecord) -> None:
        """Semeia uma chave conhecida — para as suítes e para o perfil de teste da 011."""
        self._records[record.info.key_id] = record

    async def add(self, record: ApiKeyRecord) -> None:
        self._records[record.info.key_id] = record

    async def get(self, key_id: str) -> ApiKeyRecord | None:
        return self._records.get(key_id)

    async def list(self) -> Sequence[ApiKeyRecord]:
        return sorted(self._records.values(), key=lambda r: (r.info.created_at, r.info.key_id))

    async def revoke(self, key_id: str, *, at: datetime) -> ApiKeyRecord | None:
        record = self._records.get(key_id)
        if record is None:
            return None
        if record.info.revoked_at is not None:
            return record
        revoked = dataclasses.replace(record, info=dataclasses.replace(record.info, revoked_at=at))
        self._records[key_id] = revoked
        return revoked


class StaticOidcVerifier:
    """Tokens conhecidos → claims. Não verifica assinatura: é o verificador do perfil de teste. Confere a audiência,
    como o real (research R26)."""

    def __init__(self, tokens: Mapping[str, Mapping[str, object]]) -> None:
        self._tokens = {token: MappingProxyType(dict(claims)) for token, claims in tokens.items()}

    async def verify(self, token: str, *, audience: str) -> Mapping[str, object] | None:
        claims = self._tokens.get(token)
        if claims is None:
            return None
        declared = claims.get("aud")
        audiences = declared if isinstance(declared, list | tuple) else [declared]
        return claims if audience in audiences else None


class DisabledOidcVerifier:
    """Sem emissor configurado, as superfícies com OIDC recusam todo token — falha fechada."""

    async def verify(self, token: str, *, audience: str) -> Mapping[str, object] | None:
        return None


class SequentialTokenGenerator:
    """Tokens previsíveis: a suíte confere a chave exata emitida, e não só o formato."""

    def __init__(self) -> None:
        self._count = 0

    def token_hex(self, nbytes: int) -> str:
        self._count += 1
        return f"{self._count:0{2 * nbytes}x}"[-2 * nbytes :]

    def token_urlsafe(self, nbytes: int) -> str:
        self._count += 1
        return f"segredo{self._count}"


class InMemoryMcpDirectory:
    """Aliases globais, globais permitidos a usuários e os de cada dono."""

    def __init__(
        self,
        *,
        global_aliases: Collection[str] = (),
        shared_with_users: Collection[str] = (),
        by_owner: Mapping[str, Collection[str]] | None = None,
    ) -> None:
        self._global = frozenset(global_aliases)
        self._shared = frozenset(shared_with_users)
        self._by_owner = {owner: frozenset(aliases) for owner, aliases in (by_owner or {}).items()}

    async def aliases(self, *, owner: str | None) -> frozenset[str]:
        if owner is None:
            return self._global
        return self._by_owner.get(owner, frozenset()) | self._shared


class InMemoryCollectionCatalog:
    """Nomes de coleção existentes."""

    def __init__(self, names: Collection[str] = ()) -> None:
        self._names = frozenset(names)

    async def names(self) -> frozenset[str]:
        return self._names


class InMemorySystemOverrideStore:
    """Sobreposições por (Assistant, seção) e o histórico, no processo (ADR-032)."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], StoredOverride] = {}
        self._history: list[OverrideHistoryRecord] = []

    async def all(self) -> Sequence[StoredOverride]:
        return sorted(self._records.values(), key=lambda r: (r.assistant, r.section))

    async def get(self, assistant: str) -> Sequence[StoredOverride]:
        return sorted((r for (a, _), r in self._records.items() if a == assistant), key=lambda r: r.section)

    async def put(self, record: StoredOverride, *, expected_version: int | None) -> StoredOverride:
        current = self._records.get((record.assistant, record.section))
        stored_version = current.version if current else None
        if stored_version != expected_version:
            raise Conflict("a sobreposição mudou desde a leitura", current_version=stored_version)
        saved = dataclasses.replace(record, version=(stored_version or 0) + 1)
        self._records[(record.assistant, record.section)] = saved
        self._history.append(
            OverrideHistoryRecord(
                assistant=saved.assistant,
                section=saved.section,
                action="saved",
                payload=saved.payload,
                version=saved.version,
                actor=saved.updated_by,
                at=saved.updated_at,
            )
        )
        return saved

    async def delete(self, assistant: str, section: str, *, expected_version: int, actor: str, at: datetime) -> bool:
        current = self._records.get((assistant, section))
        if current is None:
            return False
        if current.version != expected_version:
            raise Conflict("a sobreposição mudou desde a leitura", current_version=current.version)
        del self._records[(assistant, section)]
        self._history.append(
            OverrideHistoryRecord(
                assistant=assistant,
                section=current.section,
                action="discarded",
                payload=None,
                version=current.version,
                actor=actor,
                at=at,
            )
        )
        return True

    async def history(self, assistant: str) -> Sequence[OverrideHistoryRecord]:
        return [record for record in reversed(self._history) if record.assistant == assistant]
