"""Perfis de adapters (specs/011-core-bootstrap/contracts/profiles.md).

Um perfil é o mapeamento porta → adapter de um ambiente. A lista de portas exigidas é **dado**: validar um perfil é
conferir que nenhuma ficou sem fábrica, e isso acontece antes da primeira etapa do boot (FR-004, research R6).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Final

from ai_core.bootstrap.settings import MEMORY_PROFILE, TEST_PROFILE, ConfigurationError, Settings
from ai_core.graph.adapters.clock import FixedClock, SystemClock
from ai_core.http.adapters.development import (
    AnonymousAuthenticator,
    SequentialRequestIds,
    Uuid4RequestIds,
)
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.llm.adapters.ollama import OllamaProvider
from ai_core.observability.adapters.jsonl import JsonlTraceBackend
from ai_core.observability.adapters.memory import InMemoryTraceBackend

REQUIRED_PORTS: Final = ("clock", "trace", "providers", "pack_source", "authenticator", "request_ids")
"""Portas secundárias que um perfil precisa atender. Acrescentar uma porta é acrescentar uma linha aqui."""

FIXED_TIME: Final = datetime(2026, 1, 1, 12, tzinfo=UTC)
"""Instante do relógio fixo do perfil de teste: torna verificáveis a data de referência e o campo `created`."""

ANONYMOUS_WARNING: Final = (
    "ATENÇÃO: autenticação anônima — qualquer requisição é aceita. "
    "A verificação real chega com a spec 003; não use este perfil exposto a terceiros."
)
"""O perfil `memory` é o que mais parece produção. Subir sem autenticação achando o contrário é o erro caro."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Profile:
    """Uma fábrica por porta exigida. O relógio é **um objeto só** para todos os módulos com porta de tempo."""

    name: str
    factories: Mapping[str, Callable[[Settings], Any]]
    anonymous_auth: bool = True

    def build(self, port: str, settings: Settings) -> Any:
        return self.factories[port](settings)


def _memory_profile() -> Profile:
    return Profile(
        name=MEMORY_PROFILE,
        factories={
            "clock": lambda _s: SystemClock(),
            "trace": lambda s: JsonlTraceBackend(s.trace_dir) if s.trace_dir else InMemoryTraceBackend(),
            "providers": lambda s: {"ollama": OllamaProvider(base_url=s.ollama_base_url)},
            "pack_source": lambda _s: _entry_point_source(),
            "authenticator": lambda _s: AnonymousAuthenticator(),
            "request_ids": lambda _s: Uuid4RequestIds(),
        },
    )


def _test_profile() -> Profile:
    return Profile(
        name=TEST_PROFILE,
        factories={
            "clock": lambda _s: FixedClock(FIXED_TIME, readings=[0.0, 0.25]),
            "trace": lambda _s: InMemoryTraceBackend(),
            "providers": lambda _s: {"ollama": ScriptedProvider(name="ollama", deltas=("Bras", "ília"))},
            "pack_source": lambda _s: _entry_point_source(),
            "authenticator": lambda _s: AnonymousAuthenticator(),
            "request_ids": lambda _s: SequentialRequestIds(),
        },
    )


def _entry_point_source() -> Any:
    from ai_core.packs.adapters.entry_points import EntryPointPackSource

    return EntryPointPackSource()


PROFILES: Final[Mapping[str, Callable[[], Profile]]] = {
    MEMORY_PROFILE: _memory_profile,
    TEST_PROFILE: _test_profile,
}


def profile_for(name: str) -> Profile:
    """Perfil pelo nome, já validado. Perfil desconhecido ou incompleto é recusado antes do boot."""
    try:
        build = PROFILES[name]
    except KeyError:
        known = ", ".join(sorted(PROFILES))
        raise ConfigurationError(f"perfil '{name}' não existe; disponíveis: {known}") from None
    return validate(build())


def validate(profile: Profile) -> Profile:
    """Recusa perfil a que falte fábrica para alguma porta exigida, nomeando a porta (FR-004)."""
    missing = [port for port in REQUIRED_PORTS if port not in profile.factories]
    if missing:
        raise ConfigurationError(
            f"perfil '{profile.name}' não atende a(s) porta(s): {', '.join(missing)}"
        )
    return profile
