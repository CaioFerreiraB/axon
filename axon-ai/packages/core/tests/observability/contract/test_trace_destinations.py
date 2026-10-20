"""T063 — conformidade do seam `TraceDestinations` (memória e Postgres): segredo só de escrita, instalação somente
leitura, chave mestra, versão e recarga do destino (ADR-033, R33)."""

from __future__ import annotations

import pytest
from conftest import Stores
from trace_testkit import MASTER_KEY, MovingClock

from axon_ai.observability.adapters.cipher import AesGcmCipher
from axon_ai.observability.adapters.langfuse import LangfuseDestination
from axon_ai.observability.adapters.memory import RecordingLangfuseTransport
from axon_ai.observability.api import (
    Conflict,
    ConnectionCheck,
    InstallationDefined,
    InvalidField,
    MasterKeyMissing,
)
from axon_ai.observability.domain.settings import InstallationDestinations, LangfuseCredentials
from axon_ai.observability.service import DestinationService

pytestmark = pytest.mark.us6


async def _service(
    stores: Stores,
    *,
    installation: InstallationDestinations | None = None,
    cipher: bool = True,
    check: ConnectionCheck | None = None,
) -> tuple[DestinationService, RecordingLangfuseTransport, LangfuseDestination]:
    transport = RecordingLangfuseTransport(check=check)
    clock = MovingClock()
    destination = LangfuseDestination(transport, clock=clock.now)
    service = DestinationService(
        store=stores.settings,
        cipher=AesGcmCipher(MASTER_KEY) if cipher else None,
        installation=installation or InstallationDestinations(),
        transport=transport,
        langfuse=destination,
        usage=None,
        clock=clock,
    )
    await service.start()
    return service, transport, destination


async def test_gravar_liga_o_destino_e_o_segredo_nunca_volta(stores: Stores) -> None:
    service, transport, destination = await _service(stores)
    view = await service.settings()
    assert not view.langfuse_enabled and view.version == 0 and not destination.enabled
    view = await service.set_langfuse(
        enabled=True,
        host="https://lf.exemplo.org/",
        public_key="pk-1",
        secret_key="sk-segredo",
        actor="user:root",
        version=0,
    )
    assert view.langfuse_enabled and view.langfuse_secret_set and view.langfuse_host == "https://lf.exemplo.org"
    assert "sk-segredo" not in repr(view) and view.version == 1
    assert (
        destination.enabled and transport.credentials is not None and transport.credentials.secret_key == "sk-segredo"
    )
    stored = await stores.settings.get()
    assert stored.langfuse_secret_sealed is not None and b"sk-segredo" not in stored.langfuse_secret_sealed
    # um serviço novo (outro processo) abre o segredo com a mesma chave mestra
    _, other_transport, _ = await _service(stores)
    assert other_transport.credentials is not None and other_transport.credentials.secret_key == "sk-segredo"
    view = await service.set_langfuse(enabled=False, actor="user:root", version=1)
    assert not destination.enabled and view.langfuse_secret_set


async def test_versao_desatualizada_e_conflito(stores: Stores) -> None:
    service, _, _ = await _service(stores)
    await service.set_capture(enabled=True, actor="user:root", version=0)
    with pytest.raises(Conflict) as caught:
        await service.set_capture(enabled=False, actor="user:bia", version=0)
    assert caught.value.current_version == 1
    assert service.capture_enabled()


async def test_sem_chave_mestra_o_segredo_nao_grava(stores: Stores) -> None:
    service, _, _ = await _service(stores, cipher=False)
    with pytest.raises(MasterKeyMissing):
        await service.set_langfuse(host="https://lf.exemplo.org", secret_key="sk", actor="user:root", version=0)
    assert (await stores.settings.get()).version == 0  # nada do pedido gravou
    view = await service.set_langfuse(host="https://lf.exemplo.org", public_key="pk", actor="user:root", version=0)
    assert view.langfuse_host == "https://lf.exemplo.org" and not view.langfuse_secret_set


async def test_instalacao_somente_leitura(stores: Stores) -> None:
    env = LangfuseCredentials(host="https://cloud.langfuse.com", public_key="pk-env", secret_key="sk-env")
    service, transport, destination = await _service(
        stores, installation=InstallationDestinations(langfuse=env, capture=True)
    )
    assert destination.enabled and transport.credentials == env and service.capture_enabled()
    with pytest.raises(InstallationDefined) as caught:
        await service.set_langfuse(host="https://outro.org", actor="user:root", version=0)
    assert caught.value.field == "langfuse_host"
    with pytest.raises(InstallationDefined):
        await service.set_capture(enabled=False, actor="user:root", version=0)


async def test_endereco_invalido(stores: Stores) -> None:
    service, _, _ = await _service(stores)
    with pytest.raises(InvalidField):
        await service.set_langfuse(host="http://langfuse.exemplo.org", actor="user:root", version=0)


async def test_testar_conexao_com_o_digitado_ou_o_gravado(stores: Stores) -> None:
    service, transport, _ = await _service(stores, check=ConnectionCheck(ok=True, detail="projeto x"))
    missing = await service.test_langfuse()
    assert not missing.ok and "host" in missing.detail
    typed = await service.test_langfuse(host="https://lf.exemplo.org", public_key="pk", secret_key="sk-digitado")
    assert typed.ok and transport.checked[-1].secret_key == "sk-digitado"
    await service.set_langfuse(
        host="https://lf.exemplo.org", public_key="pk", secret_key="sk-gravado", actor="user:root", version=0
    )
    assert (await service.test_langfuse()).ok and transport.checked[-1].secret_key == "sk-gravado"


async def test_saude_dos_destinos(stores: Stores) -> None:
    service, _, _ = await _service(stores)
    (langfuse,) = service.health()
    assert (langfuse.name, langfuse.state) == ("langfuse", "off")
    await service.set_langfuse(
        enabled=True, host="https://lf.exemplo.org", public_key="pk", secret_key="sk", actor="user:root", version=0
    )
    (langfuse,) = service.health()
    assert langfuse.state == "ok"


# --- Identidade Axon (US8; ADR-037, research R40 a R42) ---------------------------------------------------------------


def test_o_rotulo_da_subchave_e_o_da_marca() -> None:
    from axon_ai.observability.adapters.cipher import INFO

    assert INFO == b"axon-ai/observability/v1"


@pytest.mark.us8
async def test_segredo_selado_com_o_rotulo_antigo_nao_abre_e_regravar_devolve_o_destino(stores: Stores) -> None:
    antigo = DestinationService(
        store=stores.settings,
        cipher=AesGcmCipher(MASTER_KEY, info=b"ai-core/observability/v1"),
        installation=InstallationDestinations(),
        transport=RecordingLangfuseTransport(),
        langfuse=None,
        usage=None,
        clock=MovingClock(),
    )
    await antigo.start()
    await antigo.set_langfuse(
        enabled=True,
        host="https://lf.exemplo.org",
        public_key="pk",
        secret_key="sk-antigo",
        actor="user:root",
        version=0,
    )
    service, transport, destination = await _service(stores)
    assert not destination.enabled and transport.credentials is None
    (langfuse,) = service.health()
    assert langfuse.last_error is not None and "não abre" in langfuse.last_error
    view = await service.settings()
    await service.set_langfuse(secret_key="sk-novo", actor="user:root", version=view.version)
    assert destination.enabled and transport.credentials is not None and transport.credentials.secret_key == "sk-novo"
    (langfuse,) = service.health()
    assert langfuse.last_error is None
