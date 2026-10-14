"""T053 — variáveis da identidade na configuração (research R36; contracts/configuration.md, Fase 9).

Só a parte da identidade (incremento 9.1); as do Langfuse e do uso entram com a passada da 009.
"""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from ai_core.bootstrap.settings import ConfigurationError, EnvConfigSource, Settings

KEY = base64.b64encode(bytes(range(32))).decode()


def _env(**values: str) -> Settings:
    return EnvConfigSource({f"AI_CORE_{name}": value for name, value in values.items()}).load()


def test_padroes_sem_identidade() -> None:
    settings = _env()
    assert not settings.identity_enabled and settings.public_url is None and settings.master_key is None
    assert settings.display_name == "Agentic" and settings.trusted_proxies == () and settings.cookie_secure is None


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
    with pytest.raises(ConfigurationError, match=f"AI_CORE_{variable}"):
        _env(**values)


@pytest.mark.parametrize("raw", ["não é base64!", base64.b64encode(b"curta").decode()])
def test_chave_mestra_malformada_nunca_aparece_na_mensagem(raw: str) -> None:
    with pytest.raises(ConfigurationError, match="AI_CORE_MASTER_KEY") as caught:
        _env(MASTER_KEY=raw)
    assert raw not in str(caught.value)


def test_perfil_de_teste_dispensa_o_arquivo_de_clientes() -> None:
    settings = _env(PROFILE="test", IDENTITY_ENABLED="1", PUBLIC_URL="http://localhost:8000")
    assert settings.identity_enabled and settings.identity_clients_file is None
