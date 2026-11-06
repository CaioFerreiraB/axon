"""T087 — US9 e US11: o pseudônimo de uma conta apagada e o que o ator que não administra não pode fazer (ADR-057,
ADR-059; research R28, R31)."""

from __future__ import annotations

import pytest

from axon_ai.identity.domain.accounts import (
    PSEUDONYM_PATTERN,
    escalation_create,
    escalation_groups,
    escalation_members,
    escalation_membership,
    escalation_target,
    pseudonym_of,
)

pytestmark = pytest.mark.us11

ADMIN = "admin"


@pytest.mark.us9
def test_pseudonimo_vem_do_uuid_e_nunca_e_um_nome() -> None:
    pseudonym = pseudonym_of("3F9A1C2E-7B60-4D18-9a1b-0123456789ab")
    assert pseudonym == "deleted:3f9a1c2e7b604d18"
    assert PSEUDONYM_PATTERN.fullmatch(pseudonym)
    assert pseudonym_of("3f9a1c2e-7b60-4d18-9a1b-0123456789ab") == pseudonym
    with pytest.raises(ValueError):
        pseudonym_of("curto")


def test_cadastro() -> None:
    assert escalation_create({ADMIN, "equipe"}, admin_group=ADMIN) == "groups"
    assert escalation_create({"equipe"}, admin_group=ADMIN) is None


def test_escrita_sobre_conta_do_grupo_de_administracao() -> None:
    assert escalation_target({ADMIN}, admin_group=ADMIN) == "username"
    assert escalation_target({"equipe"}, admin_group=ADMIN) is None


@pytest.mark.parametrize(
    ("before", "after", "esperado"),
    [
        (set(), {ADMIN}, "groups"),
        ({ADMIN}, set(), "groups"),
        ({"equipe"}, {"vendas"}, None),
        ({ADMIN}, {ADMIN, "equipe"}, None),
    ],
)
def test_mudar_grupos(before: set[str], after: set[str], esperado: str | None) -> None:
    assert escalation_groups(before, after, admin_group=ADMIN) == esperado


def test_um_grupo_de_cada_vez() -> None:
    assert escalation_membership(ADMIN, set(), admin_group=ADMIN) == "group"
    assert escalation_membership("equipe", {ADMIN}, admin_group=ADMIN) == "username"
    assert escalation_membership("equipe", {"vendas"}, admin_group=ADMIN) is None


def test_definir_membros() -> None:
    assert escalation_members(ADMIN, [], admin_group=ADMIN) == "name"
    assert escalation_members("equipe", [{"vendas"}, {ADMIN}], admin_group=ADMIN) == "members"
    assert escalation_members("equipe", [{"vendas"}, set()], admin_group=ADMIN) is None
