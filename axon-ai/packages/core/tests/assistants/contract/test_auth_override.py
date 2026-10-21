"""T107 — US13: sobreposição de `auth` de Assistants de sistema (ADR-040; R41 a R43; SC-010 adversarial). Roda sobre o
armazenamento das duas versões."""

from __future__ import annotations

from typing import Any

import pytest
from assistants_testkit import ANA, CAIO_KEY, assistant, assistants_service, config

from axon_ai.assistants.api import (
    AssistantNotFound,
    AssistantUnavailable,
    AuthOverride,
    Conflict,
    NotFound,
    Principal,
    RequestRejected,
)
from axon_ai.assistants.domain.overrides import NOT_ALLOWED, SECTION_CHANGED

pytestmark = pytest.mark.us13

EVA = Principal(subject="user:eva", scheme="oidc", groups=frozenset({"equipe"}))
RELATORIOS = Principal(subject="svc:relatorios", scheme="api_key")
SO_RELATORIOS = AuthOverride(schemes=frozenset({"oidc", "api_key"}), allow=("svc:relatorios",))


def _geral(**fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "flow": "chat",
        "overrides": ["auth"],
        "auth": {"schemes": ["oidc"], "allow": ["group:equipe"]},
    }
    body.update(fields)
    return assistant(**body)


def _privado(**fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "flow": "chat",
        "visibility": "private",
        "overrides": ["auth"],
        "auth": {"schemes": ["api_key"], "allow": ["user:caio"]},
    }
    body.update(fields)
    return assistant(**body)


def _yaml(geral: dict[str, Any] | None = None, privado: dict[str, Any] | None = None) -> dict[str, Any]:
    return config({"geral": geral or _geral(), "privado": privado or _privado(), "fixo": assistant(flow="chat")})


def _service(store: Any, data: dict[str, Any] | None = None) -> Any:
    return assistants_service(data or _yaml(), overrides=store, flow_roles={"chat": ("generation",)})


async def _names(service: Any, principal: Principal) -> set[str]:
    return {summary.name for summary in await service.discover(principal)}


async def test_cenario_1_sobrepor_acesso_vale_na_resolucao_seguinte(override_store: Any) -> None:
    service = _service(override_store)
    assert (await service.resolve(model="geral", principal=EVA)).assistant == "geral"
    with pytest.raises(AssistantNotFound):
        await service.resolve(model="geral", principal=RELATORIOS)

    view = await service.override_auth("geral", SO_RELATORIOS, actor=CAIO_KEY, version=None)

    assert view.effective_auth == SO_RELATORIOS
    assert view.yaml_auth == AuthOverride(schemes=frozenset({"oidc"}), allow=("group:equipe",))
    (override,) = view.overrides
    assert (override.section, override.state, override.version) == ("auth", "active", 1)
    assert (await service.resolve(model="geral", principal=RELATORIOS)).assistant == "geral"
    with pytest.raises(AssistantNotFound):
        await service.resolve(model="geral", principal=EVA)
    assert "geral" in await _names(service, RELATORIOS)
    assert "geral" not in await _names(service, EVA)


async def test_cenario_2_secao_nao_liberada(override_store: Any) -> None:
    with pytest.raises(RequestRejected, match="novo deploy") as caught:
        await _service(override_store).override_auth("fixo", SO_RELATORIOS, actor=CAIO_KEY, version=None)
    assert caught.value.field == "auth"


async def test_cenario_3_asterisco_em_privado(override_store: Any) -> None:
    star = AuthOverride(schemes=frozenset({"oidc"}), allow=("*",))
    service = _service(override_store)
    with pytest.raises(RequestRejected) as caught:
        await service.override_auth("privado", star, actor=CAIO_KEY, version=None)
    assert caught.value.field == "auth.allow"
    # No público, `*` é permitido.
    view = await service.override_auth("geral", star, actor=CAIO_KEY, version=None)
    assert view.effective_auth.allow == ("*",)


@pytest.mark.parametrize(
    ("override", "field"),
    [
        (AuthOverride(schemes=frozenset(), allow=("svc:relatorios",)), "auth.schemes"),
        (AuthOverride(schemes=frozenset({"oidc", "saml"}), allow=("svc:relatorios",)), "auth.schemes"),  # type: ignore[arg-type]
        (AuthOverride(schemes=frozenset({"oidc"}), allow=()), "auth.allow"),
        (AuthOverride(schemes=frozenset({"oidc"}), allow=("caio",)), "auth.allow"),
        (AuthOverride(schemes=frozenset({"oidc"}), allow=("group:",)), "auth.allow"),
    ],
)
async def test_cenario_4_conteudo_invalido_nomeia_o_campo(
    override_store: Any, override: AuthOverride, field: str
) -> None:
    service = _service(override_store)
    with pytest.raises(RequestRejected) as caught:
        await service.override_auth("geral", override, actor=CAIO_KEY, version=None)
    assert caught.value.field == field
    assert (await service.system_assistant("geral", actor=CAIO_KEY)).overrides == ()


async def test_cenario_5_deploy_muda_a_secao_ou_tira_a_permissao(override_store: Any) -> None:
    await _service(override_store).override_auth("geral", SO_RELATORIOS, actor=CAIO_KEY, version=None)

    mudou = _service(override_store, _yaml(_geral(auth={"schemes": ["oidc"], "allow": ["group:outra"]})))
    (override,) = (await mudou.system_assistant("geral", actor=CAIO_KEY)).overrides
    assert (override.state, override.reason) == ("inactive", SECTION_CHANGED)
    assert override.payload == SO_RELATORIOS
    with pytest.raises(AssistantNotFound):
        await mudou.resolve(model="geral", principal=RELATORIOS)

    tirou = _service(override_store, _yaml(_geral(overrides=["models"])))
    (override,) = (await tirou.system_assistant("geral", actor=CAIO_KEY)).overrides
    assert (override.state, override.reason) == ("inactive", NOT_ALLOWED)
    assert (await tirou.resolve(model="geral", principal=EVA)).assistant == "geral"


async def test_cenario_6_acesso_nao_e_administracao(override_store: Any) -> None:
    service = _service(override_store)
    await service.override_auth("geral", SO_RELATORIOS, actor=CAIO_KEY, version=None)
    with pytest.raises(AssistantNotFound):
        await service.resolve(model="geral", principal=CAIO_KEY)

    view = await service.system_assistant("geral", actor=CAIO_KEY)
    assert view.effective_auth == SO_RELATORIOS
    back = await service.discard_override("geral", "auth", actor=CAIO_KEY, version=1)
    assert back.overrides == () and back.effective_auth == back.yaml_auth


async def test_cenario_7_entrada_sem_correspondencia_e_aceita_e_nao_concede_nada(override_store: Any) -> None:
    service = _service(override_store)
    pendente = AuthOverride(schemes=frozenset({"oidc", "api_key"}), allow=("group:inexistente", "svc:sem-chave"))
    view = await service.override_auth("geral", pendente, actor=CAIO_KEY, version=None)

    assert view.status.available
    for principal in (EVA, RELATORIOS, ANA):
        with pytest.raises(AssistantNotFound):
            await service.resolve(model="geral", principal=principal)


async def test_cenario_8_dois_admins_na_mesma_versao(override_store: Any) -> None:
    service = _service(override_store)
    await service.override_auth("geral", SO_RELATORIOS, actor=CAIO_KEY, version=None)
    outro = AuthOverride(schemes=frozenset({"oidc"}), allow=("group:equipe", "user:ana"))
    await service.override_auth("geral", outro, actor=CAIO_KEY, version=1)
    with pytest.raises(Conflict) as caught:
        await service.override_auth("geral", SO_RELATORIOS, actor=CAIO_KEY, version=1)
    assert caught.value.current_version == 2


async def test_cenario_9_visao_com_e_sem_auth_liberado(override_store: Any) -> None:
    service = _service(override_store)
    liberado = await service.system_assistant("geral", actor=CAIO_KEY)
    assert "auth" in liberado.overridable
    assert (
        liberado.yaml_auth
        == liberado.effective_auth
        == AuthOverride(schemes=frozenset({"oidc"}), allow=("group:equipe",))
    )

    fixo = await service.system_assistant("fixo", actor=CAIO_KEY)
    assert "auth" not in fixo.overridable
    assert fixo.yaml_auth == fixo.effective_auth == AuthOverride(schemes=frozenset({"oidc", "api_key"}), allow=("*",))


async def test_deploy_que_torna_privado_com_asterisco_sobreposto_falha_fechado(override_store: Any) -> None:
    star = AuthOverride(schemes=frozenset({"oidc"}), allow=("*",))
    await _service(override_store).override_auth("geral", star, actor=CAIO_KEY, version=None)

    privado = _service(override_store, _yaml(_geral(visibility="private")))
    with pytest.raises(AssistantUnavailable) as caught:
        await privado.resolve(model="geral", principal=ANA)
    assert any("override.auth" in reason for reason in caught.value.reasons)
    view = await privado.system_assistant("geral", actor=CAIO_KEY)
    assert not view.status.available and view.overrides[0].state == "active"


async def test_quem_nao_administra_recebe_not_found(override_store: Any) -> None:
    service = _service(override_store)
    for actor in (ANA, EVA, RELATORIOS):
        with pytest.raises(NotFound):
            await service.override_auth("geral", SO_RELATORIOS, actor=actor, version=None)


async def test_historico_registra_gravacao_e_descarte(override_store: Any) -> None:
    service = _service(override_store)
    await service.override_auth("geral", SO_RELATORIOS, actor=CAIO_KEY, version=None)
    await service.discard_override("geral", "auth", actor=CAIO_KEY, version=1)

    history = await service.history("geral", actor=CAIO_KEY)
    assert [(entry.section, entry.action, entry.version) for entry in history] == [
        ("auth", "discarded", 1),
        ("auth", "saved", 1),
    ]
    assert history[1].payload == SO_RELATORIOS and history[1].actor == CAIO_KEY.subject
