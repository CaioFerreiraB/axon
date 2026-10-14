"""T018 — `IdentitySecrets`: nomes fixos de variável (ADR-020); erros nomeiam a variável, nunca um valor."""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_core.identity.adapters.secrets_env import EnvironmentIdentitySecrets
from ai_core.identity.ports import SecretsError


def test_segredo_de_cliente_pela_referencia() -> None:
    secrets = EnvironmentIdentitySecrets({"AI_CORE_IDENTITY_SECRET_OPEN_WEBUI": "s3gredo", "OUTRA": "x"})
    assert secrets.client_secret("open_webui") == "s3gredo"
    assert secrets.client_secret("console") is None
    assert secrets.client_secret("../OUTRA") is None


def test_cliente_google_completo_ou_nada() -> None:
    assert EnvironmentIdentitySecrets({}).google() is None
    google = EnvironmentIdentitySecrets(
        {
            "AI_CORE_GOOGLE_CLIENT_ID": "id.apps.googleusercontent.com",
            "AI_CORE_GOOGLE_CLIENT_SECRET": "segredo-google",
            "AI_CORE_GOOGLE_HOSTED_DOMAIN": "Exemplo.org",
        }
    ).google()
    assert google is not None and google.hosted_domain == "exemplo.org"
    assert "segredo-google" not in repr(google)
    with pytest.raises(SecretsError, match="AI_CORE_GOOGLE_CLIENT_SECRET") as caught:
        EnvironmentIdentitySecrets({"AI_CORE_GOOGLE_CLIENT_ID": "valor-do-id"}).google()
    assert "valor-do-id" not in str(caught.value)


@pytest.mark.parametrize(("value", "expected"), [(None, None), ("true", True), ("0", False), ("Sim", True)])
def test_ajuste_do_google_pela_instalacao(value: str | None, expected: bool | None) -> None:
    environ = {} if value is None else {"AI_CORE_GOOGLE_LOGIN": value}
    assert EnvironmentIdentitySecrets(environ).google_login() is expected


def test_ajuste_invalido_nomeia_a_variavel() -> None:
    with pytest.raises(SecretsError, match="AI_CORE_GOOGLE_LOGIN"):
        EnvironmentIdentitySecrets({"AI_CORE_GOOGLE_LOGIN": "talvez"}).google_login()


def test_admin_inicial_com_a_senha_no_arquivo(tmp_path: Path) -> None:
    password = tmp_path / "admin"
    password.write_text("senha-do-admin-inicial\n", encoding="utf-8")
    admin = EnvironmentIdentitySecrets(
        {
            "AI_CORE_BOOTSTRAP_ADMIN_USERNAME": "Admin",
            "AI_CORE_BOOTSTRAP_ADMIN_EMAIL": " Admin@Exemplo.org ",
            "AI_CORE_BOOTSTRAP_ADMIN_PASSWORD_FILE": str(password),
        }
    ).bootstrap_admin()
    assert admin is not None
    assert (admin.username, admin.email, admin.password) == ("admin", "admin@exemplo.org", "senha-do-admin-inicial")
    assert "senha-do-admin-inicial" not in repr(admin)
    assert EnvironmentIdentitySecrets({}).bootstrap_admin() is None


@pytest.mark.parametrize(
    ("environ", "variable"),
    [
        ({"AI_CORE_BOOTSTRAP_ADMIN_USERNAME": "admin"}, "AI_CORE_BOOTSTRAP_ADMIN_EMAIL"),
        (
            {"AI_CORE_BOOTSTRAP_ADMIN_USERNAME": "admin", "AI_CORE_BOOTSTRAP_ADMIN_EMAIL": "a@x.org"},
            "AI_CORE_BOOTSTRAP_ADMIN_PASSWORD_FILE",
        ),
        (
            {
                "AI_CORE_BOOTSTRAP_ADMIN_USERNAME": "admin",
                "AI_CORE_BOOTSTRAP_ADMIN_EMAIL": "a@x.org",
                "AI_CORE_BOOTSTRAP_ADMIN_PASSWORD_FILE": "/nao/existe",
            },
            "AI_CORE_BOOTSTRAP_ADMIN_PASSWORD_FILE",
        ),
        (
            {
                "AI_CORE_BOOTSTRAP_ADMIN_USERNAME": "a b",
                "AI_CORE_BOOTSTRAP_ADMIN_EMAIL": "a@x.org",
                "AI_CORE_BOOTSTRAP_ADMIN_PASSWORD_FILE": "/x",
            },
            "AI_CORE_BOOTSTRAP_ADMIN_USERNAME",
        ),
    ],
)
def test_admin_inicial_incompleto_nomeia_a_variavel(environ: dict[str, str], variable: str) -> None:
    with pytest.raises(SecretsError, match=variable):
        EnvironmentIdentitySecrets(environ).bootstrap_admin()


def test_senha_curta_no_arquivo(tmp_path: Path) -> None:
    password = tmp_path / "admin"
    password.write_text("curta", encoding="utf-8")
    environ = {
        "AI_CORE_BOOTSTRAP_ADMIN_USERNAME": "admin",
        "AI_CORE_BOOTSTRAP_ADMIN_EMAIL": "a@x.org",
        "AI_CORE_BOOTSTRAP_ADMIN_PASSWORD_FILE": str(password),
    }
    with pytest.raises(SecretsError, match="pelo menos 12") as caught:
        EnvironmentIdentitySecrets(environ).bootstrap_admin()
    assert "curta" not in str(caught.value)
