"""T061 — precedência dos ajustes dos destinos: instalação > runtime > padrão, com a origem por campo (ADR-033, R33)."""

from __future__ import annotations

import pytest

from axon_ai.observability.api import InvalidField
from axon_ai.observability.domain.settings import (
    DestinationSettings,
    InstallationDestinations,
    LangfuseCredentials,
    check_host,
    effective,
)

pytestmark = pytest.mark.us6

ENV = LangfuseCredentials(host="https://cloud.langfuse.com", public_key="pk-env", secret_key="sk-env")


def test_padrao_desligado() -> None:
    result = effective(InstallationDestinations(), DestinationSettings(), secret=None)
    assert result.langfuse is None and not result.capture
    assert set(result.view.sources.values()) == {"default"}


def test_runtime_completo_liga() -> None:
    stored = DestinationSettings(
        langfuse_enabled=True, langfuse_host="https://lf.exemplo.org", langfuse_public_key="pk", version=3
    )
    incomplete = effective(InstallationDestinations(), stored, secret=None)
    assert incomplete.langfuse is None and not incomplete.view.langfuse_secret_set
    complete = effective(InstallationDestinations(), stored, secret="sk")
    assert complete.langfuse == LangfuseCredentials(host="https://lf.exemplo.org", public_key="pk", secret_key="sk")
    assert complete.view.langfuse_secret_set and complete.view.version == 3
    assert complete.view.sources["langfuse_host"] == "runtime" and "sk" not in repr(complete.view)


def test_instalacao_vence_e_a_captura_tem_origem_propria() -> None:
    stored = DestinationSettings(langfuse_enabled=False, langfuse_host="https://outro.org", capture_content=True)
    result = effective(InstallationDestinations(langfuse=ENV, capture=False), stored, secret="sk-banco")
    assert result.langfuse == ENV and result.view.langfuse_host == ENV.host
    assert result.view.sources["langfuse_secret"] == "installation" and not result.capture
    assert result.view.sources["capture_content"] == "installation"
    captured = effective(InstallationDestinations(), stored, secret=None)
    assert captured.capture and captured.view.sources["capture_content"] == "runtime"


@pytest.mark.parametrize(
    ("host", "ok"),
    [
        ("https://cloud.langfuse.com/", True),
        ("http://localhost:3000", True),
        ("http://langfuse:3000", True),
        ("http://langfuse.exemplo.org", False),
        ("ftp://x", False),
        ("cloud.langfuse.com", False),
    ],
)
def test_endereco(host: str, ok: bool) -> None:
    if ok:
        assert not check_host(host).endswith("/")
    else:
        with pytest.raises(InvalidField):
            check_host(host)
