"""T122 — US14: escopos no Principal, as regras de admin e de inferência e a validação da emissão (ADR-057; research
R46, R47, R49)."""

from __future__ import annotations

import pytest

from axon_ai.assistants.api import DEFAULT_SCOPES, SCOPES, Principal, RequestRejected
from axon_ai.assistants.domain.access import can_infer, is_admin
from axon_ai.assistants.domain.keys import key_scopes

pytestmark = pytest.mark.us14

ADMIN = "operadores"


def test_vocabulario_fechado() -> None:
    assert SCOPES == ("inference", "users", "admin")
    assert frozenset({"inference"}) == DEFAULT_SCOPES


def test_principal_oidc_nao_tem_escopos() -> None:
    assert Principal(subject="user:ana", scheme="oidc").scopes is None
    with pytest.raises(ValueError, match="OIDC"):
        Principal(subject="user:ana", scheme="oidc", scopes=frozenset({"inference"}))


def test_principal_de_chave_sem_escopos_vira_inference() -> None:
    assert Principal(subject="svc:x", scheme="api_key").scopes == frozenset({"inference"})


@pytest.mark.parametrize("scopes", [frozenset(), frozenset({"root"}), frozenset({"inference", "tudo"})])
def test_principal_recusa_escopos_invalidos(scopes: frozenset[str]) -> None:
    with pytest.raises(ValueError, match="escopo"):
        Principal(subject="svc:x", scheme="api_key", scopes=scopes)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("groups", "scopes", "esperado"),
    [
        ({ADMIN}, {"admin"}, True),
        ({ADMIN}, {"inference", "admin"}, True),
        ({ADMIN}, {"inference"}, False),
        ({ADMIN}, {"users"}, False),
        (set(), {"admin"}, False),
    ],
)
def test_is_admin_com_chave_exige_grupo_e_escopo(groups: set[str], scopes: set[str], esperado: bool) -> None:
    principal = Principal(subject="svc:x", scheme="api_key", groups=frozenset(groups), scopes=frozenset(scopes))  # type: ignore[arg-type]
    assert is_admin(principal, ADMIN) is esperado


def test_is_admin_oidc_so_pelo_grupo() -> None:
    assert is_admin(Principal(subject="user:caio", scheme="oidc", groups=frozenset({ADMIN})), ADMIN)
    assert not is_admin(Principal(subject="user:ana", scheme="oidc"), ADMIN)
    assert not is_admin(Principal(subject="user:caio", scheme="oidc", groups=frozenset({ADMIN})), None)


@pytest.mark.parametrize(
    ("scopes", "esperado"),
    [({"inference"}, True), ({"users"}, False), ({"admin"}, False), ({"inference", "users"}, True)],
)
def test_can_infer(scopes: set[str], esperado: bool) -> None:
    assert can_infer(Principal(subject="svc:x", scheme="api_key", scopes=frozenset(scopes))) is esperado  # type: ignore[arg-type]
    assert can_infer(Principal(subject="user:ana", scheme="oidc"))


def test_key_scopes_default_e_conjuntos_validos() -> None:
    assert key_scopes(None, groups=(), admin_group=ADMIN, by_operator=False) == frozenset({"inference"})
    assert key_scopes(["users", "inference", "users"], groups=(), admin_group=ADMIN, by_operator=False) == frozenset(
        {"inference", "users"}
    )
    assert key_scopes(["admin"], groups=[ADMIN], admin_group=ADMIN, by_operator=True) == frozenset({"admin"})


@pytest.mark.parametrize(
    ("scopes", "groups", "by_operator", "mensagem"),
    [
        ([], (), True, "ao menos um escopo"),
        (["root"], (), True, "escopo desconhecido: root"),
        (["admin"], (), True, "exige o grupo de administração"),
        (["admin"], [ADMIN], False, "só é concedido pela linha de comando"),
    ],
)
def test_key_scopes_recusas(scopes: list[str], groups: tuple[str, ...], by_operator: bool, mensagem: str) -> None:
    with pytest.raises(RequestRejected, match=mensagem) as error:
        key_scopes(scopes, groups=groups, admin_group=ADMIN, by_operator=by_operator)
    assert error.value.field == "scopes"


def test_key_scopes_admin_sem_grupo_configurado() -> None:
    with pytest.raises(RequestRejected) as error:
        key_scopes(["admin"], groups=["admin"], admin_group=None, by_operator=True)
    assert error.value.field == "scopes"
