"""T017 — `ClientSource` e as regras do `identity.yaml` (FR-005; contracts/identity-yaml.md)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
from identity_testkit import CONSOLE, OPEN_WEBUI, harness

from axon_ai.identity.adapters.clients_yaml import YamlClientSource
from axon_ai.identity.domain.clients import ClientsFileError, read_clients, redirect_origins

VALID = """
version: 1
clients:
  open-webui:
    type: confidential
    secret: open_webui
    audience: ai-core
    redirect_uris: [http://localhost:3000/oauth/oidc/callback]
    post_logout_redirect_uris: [http://localhost:3000/auth]
  console:
    type: public
    audience: ai-core-admin
    redirect_uris: [https://agentic.exemplo.org/callback, http://axon-ai-console:8080/callback]
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "identity.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_le_o_arquivo_do_operador(tmp_path: Path) -> None:
    clients = YamlClientSource(_write(tmp_path, VALID)).load()
    assert [client.id for client in clients] == ["open-webui", "console"]
    webui, console = clients
    assert webui.type == "confidential" and webui.secret_ref == "open_webui" and webui.audience == "ai-core"
    assert console.type == "public" and console.secret_ref is None and console.post_logout_redirect_uris == ()
    assert redirect_origins(clients) == (
        "http://localhost:3000",
        "https://agentic.exemplo.org",
        "http://axon-ai-console:8080",
    )


def _clients(**entries: Any) -> dict[str, Any]:
    return {"version": 1, "clients": entries}


_CONSOLE = {"type": "public", "audience": "ai-core-admin", "redirect_uris": ["http://localhost:8080/callback"]}


@pytest.mark.parametrize(
    ("data", "field"),
    [
        ({"version": 2, "clients": {"c": _CONSOLE}}, "version"),
        ({"version": 1}, "clients"),
        ({"version": 1, "clients": {"c": _CONSOLE}, "extra": 1}, "extra"),
        (_clients(Console=_CONSOLE), "clients.Console"),
        (_clients(c={**_CONSOLE, "type": "outro"}), "clients.c.type"),
        (_clients(c={**_CONSOLE, "type": "confidential"}), "clients.c.secret"),
        (_clients(c={**_CONSOLE, "type": "confidential", "secret": "Com-Maiuscula"}), "clients.c.secret"),
        (_clients(c={**_CONSOLE, "secret": "s"}), "clients.c.secret"),
        (_clients(c={**_CONSOLE, "audience": ""}), "clients.c.audience"),
        (_clients(c={**_CONSOLE, "redirect_uris": []}), "clients.c.redirect_uris"),
        (_clients(c={**_CONSOLE, "redirect_uris": ["/relativo"]}), "clients.c.redirect_uris[0]"),
        (_clients(c={**_CONSOLE, "redirect_uris": ["http://agentic.exemplo.org/cb"]}), "clients.c.redirect_uris[0]"),
        (_clients(c={**_CONSOLE, "redirect_uris": ["https://x.org/cb#frag"]}), "clients.c.redirect_uris[0]"),
        (_clients(c={**_CONSOLE, "post_logout_redirect_uris": "http://x"}), "clients.c.post_logout_redirect_uris"),
        (_clients(c={**_CONSOLE, "outra": 1}), "clients.c.outra"),
        (_clients(c={**_CONSOLE, "audience": "d"}, d=_CONSOLE), "clients.c.audience"),
    ],
)
def test_erros_nomeiam_o_campo(data: dict[str, Any], field: str) -> None:
    with pytest.raises(ClientsFileError) as caught:
        read_clients(data)
    assert field in str(caught.value)


def test_arquivo_ausente_ou_yaml_invalido(tmp_path: Path) -> None:
    with pytest.raises(ClientsFileError, match="não foi possível ler"):
        YamlClientSource(tmp_path / "nada.yaml").load()
    with pytest.raises(ClientsFileError, match="YAML inválido"):
        YamlClientSource(_write(tmp_path, "clients: [")).load()


async def test_cliente_confidencial_sem_segredo_fica_indisponivel(caplog: pytest.LogCaptureFixture) -> None:
    parts = harness(client_secrets={})
    with caplog.at_level(logging.WARNING, logger="axon_ai.identity"):
        await parts.service.start()
    assert parts.service.unavailable_clients() == ("open-webui",)
    assert "AXON_IDENTITY_SECRET_OPEN_WEBUI" in caplog.text
    form = {"grant_type": "authorization_code", "code": "x", "redirect_uri": OPEN_WEBUI.redirect_uris[0]}
    response = await parts.service.token(form, ("open-webui", ""))
    assert response.status == 401 and response.body["error"] == "invalid_client"
    assert CONSOLE.id in parts.service.clients
