"""Portas secundárias da 003 (specs/003-core-assistants-access/contracts/ports.md).

Cada uma existe por I/O, não-determinismo ou troca prevista; nenhuma por regra pura (princípio XIII). Nenhum tipo de
biblioteca de infraestrutura aparece aqui.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from axon_ai.assistants.api import UserAssistantDraft
from axon_ai.assistants.domain.definitions import AssistantsConfig
from axon_ai.assistants.domain.keys import ApiKeyRecord
from axon_ai.assistants.domain.overrides import OverrideHistoryRecord, StoredOverride
from axon_ai.assistants.domain.rate import RateDecision


@dataclass(frozen=True, slots=True, kw_only=True)
class StoredUserAssistant:
    """Um Assistant de usuário como o armazenamento o guarda. O nome fica no rascunho, sem o `~`."""

    owner: str
    draft: UserAssistantDraft
    created_at: datetime
    updated_at: datetime

    @property
    def name(self) -> str:
        return self.draft.name


class AssistantConfigSource(Protocol):
    """Configuração do operador (`assistants.yaml`): lida uma vez, no boot."""

    def load(self) -> AssistantsConfig:
        """Levanta `AssistantsConfigError` em erro de arquivo; erro de um Assistant vai para `problems`."""
        ...


class UserAssistantStore(Protocol):
    """Assistants de usuário, por (dono, nome sem `~`)."""

    async def get(self, owner: str, name: str) -> StoredUserAssistant | None: ...

    async def list(self, owner: str) -> Sequence[StoredUserAssistant]: ...

    async def all(self) -> Sequence[StoredUserAssistant]:
        """Todos, de todos os donos — só para a validação (R14)."""
        ...

    async def insert(self, record: StoredUserAssistant) -> bool:
        """`False` se (dono, nome) já existe."""
        ...

    async def replace(self, record: StoredUserAssistant) -> bool:
        """`False` se não existe."""
        ...

    async def delete(self, owner: str, name: str) -> bool:
        """`False` se não existe."""
        ...


class ApiKeyStore(Protocol):
    """Chaves de API, só com o hash (FR-015)."""

    async def add(self, record: ApiKeyRecord) -> None: ...

    async def get(self, key_id: str) -> ApiKeyRecord | None: ...

    async def list(self) -> Sequence[ApiKeyRecord]: ...

    async def revoke(self, key_id: str, *, at: datetime) -> ApiKeyRecord | None:
        """Idempotente: revogar de novo preserva o primeiro instante. `None` se não existe."""
        ...


class OidcVerifier(Protocol):
    """Verificação do token OIDC: assinatura, algoritmo, emissor e audiência. O tempo fica no domínio (R6)."""

    async def verify(self, token: str, *, audience: str) -> Mapping[str, object] | None:
        """Claims do token se a audiência é a pedida — a da superfície (research R26); senão `None`. Nunca levanta."""
        ...


class RateCounterStore(Protocol):
    """Estado do orçamento entre requisições."""

    async def acquire(self, key: tuple[str, str], *, now: datetime, limit: int, window: timedelta) -> RateDecision:
        """Decide e registra numa operação só — sem a corrida "ler, decidir, gravar" (R9)."""
        ...


class TokenGenerator(Protocol):
    """Aleatoriedade (princípio XIII): de onde saem `key_id` e segredo das chaves."""

    def token_hex(self, nbytes: int) -> str: ...

    def token_urlsafe(self, nbytes: int) -> str: ...


class Clock(Protocol):
    """Tempo (ADR-013). A 011 injeta o mesmo relógio em todos os módulos."""

    def now(self) -> datetime:
        """Instante atual, sempre com timezone."""
        ...


class McpDirectory(Protocol):
    """Aliases MCP que um Assistant pode referenciar. A 007 (Fase 3) o satisfaz estruturalmente (R11)."""

    async def aliases(self, *, owner: str | None) -> frozenset[str]:
        """`owner=None`: globais (Assistants de sistema); `owner`: do dono e globais permitidos a usuários."""
        ...


class CollectionCatalog(Protocol):
    """Coleções existentes. O índice (Fase 5) o satisfaz estruturalmente (R11)."""

    async def names(self) -> frozenset[str]: ...


class SystemOverrideStore(Protocol):
    """Sobreposições de Assistants de sistema e o histórico delas (ADR-032, research R30). Gravar e descartar escrevem
    o histórico na mesma operação; versão desatualizada levanta `Conflict` com a guardada."""

    async def all(self) -> Sequence[StoredOverride]: ...

    async def get(self, assistant: str) -> Sequence[StoredOverride]: ...

    async def put(self, record: StoredOverride, *, expected_version: int | None) -> StoredOverride:
        """`expected_version=None` cria (e falha se já existe); senão substitui a dessa versão. A versão gravada é a
        seguinte; `record.version` é ignorada."""
        ...

    async def delete(self, assistant: str, section: str, *, expected_version: int, actor: str, at: datetime) -> bool:
        """`False` se não há sobreposição; `Conflict` se a versão não é a guardada."""
        ...

    async def history(self, assistant: str) -> Sequence[OverrideHistoryRecord]:
        """Mais recente primeiro."""
        ...
