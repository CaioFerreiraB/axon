"""T046 — conformidade do seam `LoginSettings` (memória e Postgres; FR-009, ADR-033)."""

from __future__ import annotations

import pytest
from identity_testkit import GOOGLE, ISSUER, Harness, harness

from axon_ai.identity.api import Conflict, GoogleNotConfigured, InstallationDefined


async def test_padrao_e_ligado_quando_configurado(seam: Harness) -> None:
    view = await seam.service.view()
    assert view.google_enabled and view.google_source == "default" and view.google_configured
    assert view.google_redirect_uri == f"{ISSUER}/oauth2/google/callback"
    assert view.google_client_id == GOOGLE.client_id and view.version == 0
    assert GOOGLE.client_secret not in repr(view)


async def test_desligar_e_religar_com_versao(seam: Harness) -> None:
    off = await seam.service.set_google(False, actor="user:root", version=0)
    assert not off.google_enabled and off.google_source == "runtime" and off.version == 1
    assert not await seam.service.google_available()
    with pytest.raises(Conflict) as caught:
        await seam.service.set_google(True, actor="user:root", version=0)
    assert caught.value.field == "version" and caught.value.current_version == 1
    on = await seam.service.set_google(True, actor="user:root", version=1)
    assert on.google_enabled and on.version == 2


async def test_sem_cliente_google_nao_liga() -> None:
    parts = harness()
    await parts.service.start()
    view = await parts.service.view()
    assert not view.google_enabled and not view.google_configured and view.google_client_id is None
    with pytest.raises(GoogleNotConfigured):
        await parts.service.set_google(True, actor="user:root", version=0)
    # desligar explicitamente é permitido
    assert (await parts.service.set_google(False, actor="user:root", version=0)).google_source == "runtime"


@pytest.mark.parametrize("installation", [True, False])
async def test_instalacao_define_e_a_administracao_so_le(installation: bool) -> None:
    parts = harness(google=True, google_login=installation)
    await parts.service.start()
    view = await parts.service.view()
    assert view.google_enabled is installation and view.google_source == "installation"
    with pytest.raises(InstallationDefined) as caught:
        await parts.service.set_google(not installation, actor="user:root", version=0)
    assert caught.value.field == "google_enabled"
