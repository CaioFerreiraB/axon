"""T123 — US14: escopos da chave de API (ADR-057; research R46 a R49; SC-011 adversarial)."""

from __future__ import annotations

from typing import Any

import pytest
from assistants_testkit import (
    CAIO_KEY,
    POLICIES,
    access_service,
    assistant,
    assistants_service,
    config,
    draft,
    private,
)

from axon_ai.assistants.api import (
    AssistantNotFound,
    AuthOverride,
    ModelsOverride,
    NotFound,
    Principal,
    RequestRejected,
)
from axon_ai.llm.api import ModelRef

pytestmark = pytest.mark.us14

ADMIN = "operadores"


def _key(subject: str = "svc:robo", *, scopes: set[str], groups: set[str] = frozenset()) -> Principal:  # type: ignore[assignment]
    return Principal(subject=subject, scheme="api_key", groups=frozenset(groups), scopes=frozenset(scopes))  # type: ignore[arg-type]


def _directory() -> Any:
    data = config(
        {
            "geral": assistant(flow="chat", overrides=["models", "auth"]),
            "equipe-admin": private(allow=[f"group:{ADMIN}"], schemes=["api_key"], flow="chat"),
        },
        policies=POLICIES,
    )
    return assistants_service(data, flow_roles={"chat": ("generation",)})


# --- cenário 1: default ----------------------------------------------------------------------------------------------


async def test_emissao_sem_escopos_sai_com_inference_e_a_listagem_os_mostra() -> None:
    service = access_service()
    issued = await service.issue(actor=CAIO_KEY, subject="svc:robo")

    assert issued.info.scopes == frozenset({"inference"})
    (listada,) = await service.keys(actor=CAIO_KEY)
    assert listada.scopes == frozenset({"inference"})
    principal = await service.authenticate(surface="private", credential=issued.plaintext)
    assert principal is not None and principal.scopes == frozenset({"inference"})


# --- cenário 2: sem inference, nenhum Assistant ----------------------------------------------------------------------


@pytest.mark.parametrize("scopes", [{"users"}, {"admin"}, {"users", "admin"}])
async def test_sem_inference_nada_resolve_nem_aparece(scopes: set[str]) -> None:
    directory = _directory()
    principal = _key(scopes=scopes, groups={ADMIN})

    with pytest.raises(AssistantNotFound):
        await directory.resolve(model="geral", principal=principal)
    with pytest.raises(AssistantNotFound):
        await directory.resolve(model="inexistente", principal=principal)
    assert list(await directory.discover(principal)) == []
    assert list(await directory.mine(principal)) == []
    for call in (
        directory.get(principal, "~meu-rag"),
        directory.update(principal, "~meu-rag", draft()),
        directory.delete(principal, "~meu-rag"),
        directory.create(principal, draft()),
    ):
        with pytest.raises(NotFound):
            await call


async def test_chave_users_do_dono_nao_alcanca_os_assistants_que_outra_chave_com_inference_alcanca() -> None:
    directory = _directory()
    conversa = _key("user:ana", scopes={"inference"})
    provisiona = _key("user:ana", scopes={"users"})
    await directory.create(conversa, draft())

    assert [item.name for item in await directory.mine(conversa)] == ["~meu-rag"]
    assert list(await directory.mine(provisiona)) == []
    with pytest.raises(AssistantNotFound):
        await directory.resolve(model="~meu-rag", principal=provisiona)
    assert (await directory.resolve(model="~meu-rag", principal=conversa)).assistant == "~meu-rag"


# --- cenários 3 e 4: administração exige grupo e escopo --------------------------------------------------------------


async def test_grupo_de_administracao_sem_escopo_admin_nao_administra_mas_conversa() -> None:
    access = access_service()
    directory = _directory()
    so_conversa = _key("user:caio", scopes={"inference"}, groups={ADMIN})
    alvo = await access.issue_as_operator(subject="svc:alvo")

    assert not access.is_admin(so_conversa)
    for call in (
        access.keys(actor=so_conversa),
        access.issue(actor=so_conversa, subject="svc:x"),
        access.revoke(actor=so_conversa, key_id=alvo.info.key_id),
        access.rotate(actor=so_conversa, key_id=alvo.info.key_id),
        directory.system_assistants(actor=so_conversa),
        directory.override_models(
            "geral", ModelsOverride(roles={"generation": ModelRef.parse("ollama/x")}), actor=so_conversa, version=None
        ),
        directory.override_auth(
            "geral", AuthOverride(schemes=frozenset({"oidc"}), allow=("*",)), actor=so_conversa, version=None
        ),
    ):
        with pytest.raises(NotFound):
            await call
    # Ainda conversa com o que a ACL concede, inclusive pelo grupo de administração em `allow`.
    assert (await directory.resolve(model="equipe-admin", principal=so_conversa)).assistant == "equipe-admin"


async def test_grupo_e_escopo_admin_administram_e_o_oidc_do_grupo_continua_admin() -> None:
    access = access_service()
    directory = _directory()
    admin = _key("user:caio", scopes={"admin"}, groups={ADMIN})
    oidc = Principal(subject="user:caio", scheme="oidc", groups=frozenset({ADMIN}))

    assert access.is_admin(admin) and access.is_admin(oidc)
    assert list(await access.keys(actor=admin)) == []
    assert {view.name for view in await directory.system_assistants(actor=admin)} == {"geral", "equipe-admin"}
    assert {view.name for view in await directory.system_assistants(actor=oidc)} == {"geral", "equipe-admin"}
    # `admin` não inclui `inference`.
    with pytest.raises(AssistantNotFound):
        await directory.resolve(model="geral", principal=admin)


# --- cenários 5 a 7: quem concede o quê ------------------------------------------------------------------------------


async def test_cli_concede_admin_so_com_o_grupo() -> None:
    access = access_service()
    with pytest.raises(RequestRejected) as error:
        await access.issue_as_operator(subject="svc:ops", scopes=["admin"])
    assert error.value.field == "scopes"

    issued = await access.issue_as_operator(subject="svc:ops", groups=[ADMIN], scopes=["inference", "admin"])
    principal = await access.authenticate(surface="admin", credential=issued.plaintext)
    assert principal is not None and principal.scopes == frozenset({"inference", "admin"})
    assert access.is_admin(principal)


async def test_cli_com_o_grupo_sem_escopo_admin_nao_administra() -> None:
    access = access_service()
    issued = await access.issue_as_operator(subject="svc:ops", groups=[ADMIN])
    principal = await access.authenticate(surface="admin", credential=issued.plaintext)
    assert principal is not None and not access.is_admin(principal)


async def test_administracao_concede_inference_e_users_e_recusa_admin() -> None:
    access = access_service()
    issued = await access.issue(actor=CAIO_KEY, subject="svc:prov", scopes=["inference", "users"])
    assert issued.info.scopes == frozenset({"inference", "users"})

    with pytest.raises(RequestRejected) as error:
        await access.issue(actor=CAIO_KEY, subject="svc:prov", scopes=["admin"])
    assert error.value.field == "scopes"


async def test_grupo_de_administracao_recusado_antes_dos_escopos() -> None:
    access = access_service()
    with pytest.raises(RequestRejected) as error:
        await access.issue(actor=CAIO_KEY, subject="svc:prov", groups=[ADMIN], scopes=["admin"])
    assert error.value.field == "groups"


@pytest.mark.parametrize("scopes", [[], ["root"], ["inference", "superuser"]])
async def test_escopo_desconhecido_ou_vazio_e_recusado(scopes: list[str]) -> None:
    access = access_service()
    for call in (
        access.issue(actor=CAIO_KEY, subject="svc:prov", scopes=scopes),
        access.issue_as_operator(subject="svc:prov", scopes=scopes),
    ):
        with pytest.raises(RequestRejected) as error:
            await call
        assert error.value.field == "scopes"
    assert list(await access.keys(actor=CAIO_KEY)) == []


# --- cenário 8: rotação preserva -------------------------------------------------------------------------------------


async def test_rotacao_preserva_os_escopos() -> None:
    access = access_service()
    issued = await access.issue(actor=CAIO_KEY, subject="svc:prov", scopes=["users"])
    rotated = await access.rotate(actor=CAIO_KEY, key_id=issued.info.key_id)

    assert rotated.info.scopes == frozenset({"users"})
    principal = await access.authenticate(surface="private", credential=rotated.plaintext)
    assert principal is not None and principal.scopes == frozenset({"users"})
