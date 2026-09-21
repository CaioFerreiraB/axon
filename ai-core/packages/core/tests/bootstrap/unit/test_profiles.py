"""T012 — conformidade dos perfis (contracts/profiles.md)."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_core.bootstrap.profiles import (
    PROFILES,
    REQUIRED_PORTS,
    Profile,
    profile_for,
    validate,
)
from ai_core.bootstrap.settings import ConfigurationError, Settings
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.llm.adapters.ollama import OllamaProvider
from ai_core.observability.adapters.jsonl import JsonlTraceBackend
from ai_core.observability.adapters.memory import InMemoryTraceBackend


@pytest.mark.parametrize("name", sorted(PROFILES))
def test_os_perfis_atendem_todas_as_portas_exigidas(name: str) -> None:
    profile = profile_for(name)
    assert set(REQUIRED_PORTS) <= set(profile.factories)


def test_perfil_incompleto_e_recusado_nomeando_a_porta() -> None:
    incompleto = Profile(name="furado", factories={"clock": lambda _s: object()})
    with pytest.raises(ConfigurationError) as error:
        validate(incompleto)
    assert "trace" in str(error.value)
    assert "providers" in str(error.value)


def test_perfil_desconhecido_e_recusado() -> None:
    with pytest.raises(ConfigurationError, match="producao"):
        profile_for("producao")


def test_no_perfil_de_teste_o_provider_e_simulado_e_o_trace_e_de_memoria() -> None:
    profile = profile_for("test")
    settings = Settings(profile="test")
    assert isinstance(profile.build("providers", settings)["ollama"], ScriptedProvider)
    assert isinstance(profile.build("trace", settings), InMemoryTraceBackend)


def test_no_perfil_de_memoria_o_provider_e_o_ollama() -> None:
    profile = profile_for("memory")
    providers = profile.build("providers", Settings(ollama_base_url="http://local/v1"))
    assert isinstance(providers["ollama"], OllamaProvider)


def test_trace_de_memoria_sem_diretorio_e_jsonl_com_diretorio(tmp_path: Path) -> None:
    profile = profile_for("memory")
    assert isinstance(profile.build("trace", Settings()), InMemoryTraceBackend)
    assert isinstance(profile.build("trace", Settings(trace_dir=tmp_path)), JsonlTraceBackend)


def test_o_relogio_do_perfil_de_teste_e_fixo() -> None:
    clock = profile_for("test").build("clock", Settings(profile="test"))
    assert clock.now() == clock.now()
    assert clock.now().tzinfo is not None


def test_os_dois_perfis_declaram_autenticacao_anonima_nesta_fase() -> None:
    """A autenticação real chega com a 003; até lá, o boot precisa avisar (princípio VII)."""
    for name in PROFILES:
        assert profile_for(name).anonymous_auth is True
