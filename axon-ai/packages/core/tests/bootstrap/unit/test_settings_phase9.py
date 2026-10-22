"""T053 — variáveis da Fase 9 na configuração (research R36; contracts/configuration.md, Fase 9).

Identidade (incremento 9.1) e, no incremento 9.2, o grupo do Langfuse da instalação e o uso (009).
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from axon_ai.bootstrap.settings import ConfigurationError, EnvConfigSource, Settings

KEY = base64.b64encode(bytes(range(32))).decode()


def _env(**values: str) -> Settings:
    return EnvConfigSource({f"AXON_{name}": value for name, value in values.items()}).load()


def test_padroes_sem_identidade() -> None:
    settings = _env()
    assert not settings.identity_enabled and settings.public_url is None and settings.master_key is None
    assert settings.display_name == "Axon" and settings.trusted_proxies == () and settings.cookie_secure is None


def test_identidade_completa_pelo_ambiente(tmp_path: Path) -> None:
    settings = _env(
        PROFILE="persistent",
        DATABASE_URL="postgresql://x",
        IDENTITY_ENABLED="true",
        PUBLIC_URL="https://agentic.exemplo.org",
        IDENTITY_CLIENTS_FILE=str(tmp_path / "identity.yaml"),
        MASTER_KEY=KEY,
        DISPLAY_NAME="Tropa Azul",
        LOGO_FILE=str(tmp_path / "logo.svg"),
        TRUSTED_PROXIES="10.0.0.0/8, 172.18.0.1",
    )
    assert settings.identity_enabled and settings.master_key == bytes(range(32))
    assert settings.trusted_proxies == ("10.0.0.0/8", "172.18.0.1")
    assert settings.secure_cookie is True
    assert KEY not in repr(settings) and "master_key" not in repr(settings)


def test_cookie_seguro_segue_o_endereco_publico_e_pode_ser_forcado() -> None:
    assert Settings(public_url="http://localhost:8000").secure_cookie is False
    assert Settings(public_url="http://localhost:8000", cookie_secure=True).secure_cookie is True
    assert _env(COOKIE_SECURE="false", PUBLIC_URL="https://x.org").secure_cookie is False


@pytest.mark.parametrize(
    ("values", "variable"),
    [
        (
            {
                "IDENTITY_ENABLED": "true",
                "OIDC_ISSUER": "https://idp",
                "OIDC_AUDIENCE": "a",
                "PUBLIC_URL": "https://x.org",
            },
            "IDENTITY_ENABLED",
        ),
        ({"IDENTITY_ENABLED": "true"}, "PUBLIC_URL"),
        ({"IDENTITY_ENABLED": "true", "PUBLIC_URL": "https://x.org"}, "IDENTITY_CLIENTS_FILE"),
        (
            {
                "PROFILE": "persistent",
                "DATABASE_URL": "postgresql://x",
                "IDENTITY_ENABLED": "true",
                "PUBLIC_URL": "https://x.org",
                "IDENTITY_CLIENTS_FILE": "/x.yaml",
            },
            "MASTER_KEY",
        ),
        ({"PUBLIC_URL": "http://agentic.exemplo.org"}, "PUBLIC_URL"),
        ({"PUBLIC_URL": "agentic.exemplo.org"}, "PUBLIC_URL"),
        ({"TRUSTED_PROXIES": "proxy.interno"}, "TRUSTED_PROXIES"),
        ({"IDENTITY_ENABLED": "talvez"}, "IDENTITY_ENABLED"),
        ({"DISPLAY_NAME": "  "}, "DISPLAY_NAME"),
    ],
)
def test_erros_param_o_boot_nomeando_a_variavel(values: dict[str, str], variable: str) -> None:
    with pytest.raises(ConfigurationError, match=f"AXON_{variable}"):
        _env(**values)


@pytest.mark.parametrize("raw", ["não é base64!", base64.b64encode(b"curta").decode()])
def test_chave_mestra_malformada_nunca_aparece_na_mensagem(raw: str) -> None:
    with pytest.raises(ConfigurationError, match="AXON_MASTER_KEY") as caught:
        _env(MASTER_KEY=raw)
    assert raw not in str(caught.value)


def test_perfil_de_teste_dispensa_o_arquivo_de_clientes() -> None:
    settings = _env(PROFILE="test", IDENTITY_ENABLED="1", PUBLIC_URL="http://localhost:8000")
    assert settings.identity_enabled and settings.identity_clients_file is None


# --- incremento 9.2: Langfuse da instalação e uso (009) --------------------------------------------------------------

LANGFUSE = {"LANGFUSE_HOST": "https://lf.exemplo.org/", "LANGFUSE_PUBLIC_KEY": "pk-1", "LANGFUSE_SECRET_KEY": "sk-x"}


def test_padroes_do_uso_e_sem_langfuse() -> None:
    settings = _env()
    assert (settings.usage_timezone, settings.usage_retention_days) == ("UTC", 400)
    assert settings.timezone == "UTC"
    assert settings.langfuse_host is None and settings.langfuse_capture_content is None


def test_langfuse_e_uso_pelo_ambiente() -> None:
    settings = _env(
        **LANGFUSE,
        LANGFUSE_CAPTURE_CONTENT="false",
        USAGE_TIMEZONE="America/Sao_Paulo",
        USAGE_RETENTION_DAYS="90",
    )
    assert (settings.langfuse_host, settings.langfuse_public_key) == ("https://lf.exemplo.org/", "pk-1")
    assert settings.langfuse_capture_content is False
    assert (settings.usage_timezone, settings.usage_retention_days) == ("America/Sao_Paulo", 90)
    assert "sk-x" not in repr(settings)


@pytest.mark.parametrize(
    ("values", "variable"),
    [
        ({"LANGFUSE_HOST": "https://lf.exemplo.org"}, "LANGFUSE_PUBLIC_KEY"),
        ({"LANGFUSE_PUBLIC_KEY": "pk", "LANGFUSE_SECRET_KEY": "sk-x"}, "LANGFUSE_HOST"),
        (LANGFUSE | {"LANGFUSE_HOST": "http://lf.exemplo.org"}, "LANGFUSE_HOST"),
        ({"LANGFUSE_CAPTURE_CONTENT": "sim"}, "LANGFUSE_CAPTURE_CONTENT"),
        ({"USAGE_TIMEZONE": "Lua/Base"}, "USAGE_TIMEZONE"),
        ({"TIMEZONE": "Lua/Base"}, "TIMEZONE"),
        ({"USAGE_RETENTION_DAYS": "29"}, "USAGE_RETENTION_DAYS"),
        ({"USAGE_RETENTION_DAYS": "um ano"}, "USAGE_RETENTION_DAYS"),
    ],
)
def test_erros_do_langfuse_e_do_uso_nomeiam_a_variavel(values: dict[str, str], variable: str) -> None:
    with pytest.raises(ConfigurationError, match=f"AXON_{variable}") as caught:
        _env(**values)
    assert "sk-x" not in str(caught.value)


def test_langfuse_interno_do_compose_aceita_http() -> None:
    """Nome sem ponto é a rede interna do compose (009 `check_host`)."""
    settings = _env(**LANGFUSE | {"LANGFUSE_HOST": "http://langfuse:3000"})
    assert settings.langfuse_host == "http://langfuse:3000"


def test_fuso_do_motor_pelo_ambiente() -> None:
    """`AXON_TIMEZONE`: o fuso da data de referência do `agentic` (005 R50), independente do fuso do uso."""
    assert _env(TIMEZONE="America/Sao_Paulo").timezone == "America/Sao_Paulo"
