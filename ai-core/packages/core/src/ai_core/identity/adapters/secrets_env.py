"""`IdentitySecrets` real: variáveis da instalação com nomes fixos (ADR-020; research R9, R14).

Só estes nomes existem — nada de variável arbitrária escolhida por configuração: `AI_CORE_IDENTITY_SECRET_<REF>` para
os clientes do `identity.yaml`, `AI_CORE_GOOGLE_*` para o cliente Google e o ajuste da instalação, e
`AI_CORE_BOOTSTRAP_ADMIN_*` para o admin inicial, com a senha num arquivo (nunca em variável: vazaria em `docker
inspect`). Erros nomeiam a variável, nunca um valor.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Final

from ai_core.identity.domain.clients import SECRET_REF_PATTERN, secret_variable
from ai_core.identity.domain.names import is_email, is_username, normalize_email, password_problem
from ai_core.identity.ports import BootstrapAdmin, GoogleClient, SecretsError

GOOGLE_CLIENT_ID: Final = "AI_CORE_GOOGLE_CLIENT_ID"
GOOGLE_CLIENT_SECRET: Final = "AI_CORE_GOOGLE_CLIENT_SECRET"
GOOGLE_HOSTED_DOMAIN: Final = "AI_CORE_GOOGLE_HOSTED_DOMAIN"
GOOGLE_LOGIN: Final = "AI_CORE_GOOGLE_LOGIN"
BOOTSTRAP_USERNAME: Final = "AI_CORE_BOOTSTRAP_ADMIN_USERNAME"
BOOTSTRAP_EMAIL: Final = "AI_CORE_BOOTSTRAP_ADMIN_EMAIL"
BOOTSTRAP_PASSWORD_FILE: Final = "AI_CORE_BOOTSTRAP_ADMIN_PASSWORD_FILE"

_TRUE: Final = frozenset({"1", "true", "yes", "on", "sim"})
_FALSE: Final = frozenset({"0", "false", "no", "off", "nao", "não"})


class EnvironmentIdentitySecrets:
    def __init__(self, environ: Mapping[str, str] | None = None) -> None:
        self._environ = os.environ if environ is None else environ

    def _get(self, name: str) -> str | None:
        value = self._environ.get(name, "").strip()
        return value or None

    def client_secret(self, ref: str) -> str | None:
        if not SECRET_REF_PATTERN.fullmatch(ref):
            return None
        return self._get(secret_variable(ref))

    def google(self) -> GoogleClient | None:
        client_id, client_secret = self._get(GOOGLE_CLIENT_ID), self._get(GOOGLE_CLIENT_SECRET)
        if client_id is None and client_secret is None:
            return None
        if client_id is None:
            raise SecretsError(f"{GOOGLE_CLIENT_SECRET} está definida, mas {GOOGLE_CLIENT_ID} não")
        if client_secret is None:
            raise SecretsError(f"{GOOGLE_CLIENT_ID} está definida, mas {GOOGLE_CLIENT_SECRET} não")
        domain = self._get(GOOGLE_HOSTED_DOMAIN)
        return GoogleClient(
            client_id=client_id, client_secret=client_secret, hosted_domain=domain.lower() if domain else None
        )

    def google_login(self) -> bool | None:
        value = self._get(GOOGLE_LOGIN)
        if value is None:
            return None
        if value.lower() in _TRUE:
            return True
        if value.lower() in _FALSE:
            return False
        raise SecretsError(f"{GOOGLE_LOGIN} precisa ser true ou false")

    def bootstrap_admin(self) -> BootstrapAdmin | None:
        names = (BOOTSTRAP_USERNAME, BOOTSTRAP_EMAIL, BOOTSTRAP_PASSWORD_FILE)
        values = {name: self._get(name) for name in names}
        if all(value is None for value in values.values()):
            return None
        missing = [name for name, value in values.items() if value is None]
        if missing:
            raise SecretsError(f"admin inicial incompleto: falta {missing[0]}")
        username = str(values[BOOTSTRAP_USERNAME]).lower()
        email = normalize_email(str(values[BOOTSTRAP_EMAIL]))
        if not is_username(username):
            raise SecretsError(f"{BOOTSTRAP_USERNAME}: usuário fora do padrão [a-z0-9][a-z0-9._-]{{0,63}}")
        if not is_email(email):
            raise SecretsError(f"{BOOTSTRAP_EMAIL}: e-mail inválido")
        path = Path(str(values[BOOTSTRAP_PASSWORD_FILE]))
        try:
            password = path.read_text(encoding="utf-8").rstrip("\r\n")
        except OSError as error:
            raise SecretsError(
                f"{BOOTSTRAP_PASSWORD_FILE}: não foi possível ler o arquivo ({error.strerror})"
            ) from None
        problem = password_problem(password)
        if problem is not None:
            raise SecretsError(f"{BOOTSTRAP_PASSWORD_FILE}: {problem}")
        return BootstrapAdmin(username=username, email=email, password=password)
