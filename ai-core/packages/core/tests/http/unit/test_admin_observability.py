"""T084 — ajustes do Langfuse e da captura na administração: versão e confirmação do aviso (contracts/admin-api.md)."""

from __future__ import annotations

import pytest

from ai_core.http.domain.admin_common import AdminInvalid
from ai_core.http.domain.admin_observability import capture_body, connection_body, langfuse_body, settings_json
from ai_core.observability.api import DestinationHealth, DestinationSettingsView

pytestmark = pytest.mark.us9


def test_langfuse_parcial_com_versao() -> None:
    assert langfuse_body({"secret_key": "sk-novo", "version": 4}) == {
        "enabled": None,
        "host": None,
        "public_key": None,
        "secret_key": "sk-novo",
        "version": 4,
    }
    for body, field in (({"enabled": True}, "version"), ({"segredo": "x", "version": 1}, "segredo")):
        with pytest.raises(AdminInvalid) as caught:
            langfuse_body(body)
        assert caught.value.field == field


def test_ligar_a_captura_exige_o_aviso_lido() -> None:
    assert capture_body({"enabled": True, "acknowledged": True, "version": 4}) == (True, 4)
    assert capture_body({"enabled": False, "version": 4}) == (False, 4)
    for body in ({"enabled": True, "version": 4}, {"enabled": True, "acknowledged": False, "version": 4}):
        with pytest.raises(AdminInvalid) as caught:
            capture_body(body)
        assert caught.value.field == "acknowledged"


def test_testar_conexao_aceita_so_os_tres_campos() -> None:
    assert connection_body({}) == {"host": None, "public_key": None, "secret_key": None}
    with pytest.raises(AdminInvalid):
        connection_body({"version": 1})


def test_visao_nunca_tem_o_segredo() -> None:
    view = DestinationSettingsView(
        langfuse_enabled=True,
        langfuse_host="https://lf.exemplo.org",
        langfuse_public_key="pk-1",
        langfuse_secret_set=True,
        capture_content=False,
        sources={"langfuse_host": "installation"},
        version=4,
    )
    body = settings_json(view, (DestinationHealth(name="langfuse", state="ok", dropped_24h=0),))
    assert body["langfuse"]["secret_set"] is True and "secret_key" not in body["langfuse"]
    assert body["langfuse"]["sources"]["host"] == "installation" and body["capture_source"] == "default"
    assert body["health"] == [
        {"name": "langfuse", "state": "ok", "dropped_24h": 0, "last_error": None, "last_sent_at": None}
    ]
