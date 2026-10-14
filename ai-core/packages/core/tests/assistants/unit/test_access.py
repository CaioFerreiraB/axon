"""T019 / T029 — acesso puro: Principal a partir de claims OIDC, tempo do token, grupo de administração e ACL."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from assistants_testkit import ANA, BIA, CAIO_KEY, CAIO_OIDC, SVC, T0, claims

from ai_core.assistants.api import Principal
from ai_core.assistants.domain.access import OidcClaims, is_admin, principal_from_claims
from ai_core.assistants.domain.definitions import AccessRule

CONFIG = OidcClaims()


def _principal(data: dict[str, Any], *, now: Any = T0, config: OidcClaims = CONFIG) -> Principal | None:
    return principal_from_claims(data, now=now, config=config)


# --- claims → Principal (US2) ----------------------------------------------------------------------------------------


def test_claims_validas_viram_principal_oidc_com_grupos() -> None:
    principal = _principal(claims("ana", groups=["chefia", "leitores"]))
    assert principal == Principal(subject="user:ana", scheme="oidc", groups=frozenset({"chefia", "leitores"}))


def test_claims_de_subject_e_grupos_sao_configuraveis() -> None:
    config = OidcClaims(subject_claim="preferred_username", groups_claim="roles")
    principal = _principal(claims("uuid-1", preferred_username="ana", roles=["chefia"]), config=config)
    assert principal is not None
    assert principal.subject == "user:ana" and principal.groups == frozenset({"chefia"})


@pytest.mark.parametrize(
    ("groups", "expected"),
    [("chefia", {"chefia"}), (None, set()), (42, set()), (["a", 1, "", "b"], {"a", "b"})],
)
def test_grupos_em_formatos_variados(groups: Any, expected: set[str]) -> None:
    data = claims("ana")
    if groups is not None:
        data["groups"] = groups
    principal = _principal(data)
    assert principal is not None and principal.groups == frozenset(expected)


@pytest.mark.parametrize("sub", [None, "", "   ", "com espaço", 42])
def test_subject_ausente_ou_invalido_recusa(sub: Any) -> None:
    data = claims("ana")
    if sub is None:
        del data["sub"]
    else:
        data["sub"] = sub
    assert _principal(data) is None


def test_exp_e_obrigatorio() -> None:
    data = claims("ana")
    del data["exp"]
    assert _principal(data) is None


@pytest.mark.parametrize("valor", [True, "amanhã", None])
def test_exp_nao_numerico_recusa(valor: Any) -> None:
    data = claims("ana")
    data["exp"] = valor
    assert _principal(data) is None


def test_expirado_alem_da_tolerancia_recusa_e_dentro_dela_aceita() -> None:
    data = claims("ana", ttl=300)
    assert _principal(data, now=T0 + timedelta(seconds=359)) is not None
    assert _principal(data, now=T0 + timedelta(seconds=361)) is None


def test_nbf_no_futuro_alem_da_tolerancia_recusa() -> None:
    assert _principal(claims("ana", nbf=int((T0 + timedelta(seconds=120)).timestamp()))) is None
    assert _principal(claims("ana", nbf=int((T0 + timedelta(seconds=30)).timestamp()))) is not None


def test_iat_no_futuro_alem_da_tolerancia_recusa() -> None:
    data = claims("ana", ttl=600)
    data["iat"] = int((T0 + timedelta(seconds=120)).timestamp())
    assert _principal(data) is None


# --- grupo de administração (FR-015) ---------------------------------------------------------------------------------


def test_administracao_pelo_grupo_em_qualquer_esquema() -> None:
    """ADR-031 (research R27): até a Fase 8, só chave de API administrava; agora basta o grupo."""
    assert is_admin(CAIO_KEY, "operadores")
    assert not is_admin(CAIO_OIDC, "operadores")  # sem o grupo
    assert is_admin(Principal(subject="user:x", scheme="oidc", groups=frozenset({"operadores"})), "operadores")
    assert not is_admin(SVC, "operadores")
    assert not is_admin(CAIO_KEY, None)
    assert not is_admin(ANA, "operadores") and not is_admin(BIA, "operadores")


# --- ACL (US3) -------------------------------------------------------------------------------------------------------


def _rule(schemes: set[str], allow: list[str]) -> AccessRule:
    return AccessRule(schemes=frozenset(schemes), allow=tuple(allow))  # type: ignore[arg-type]


def test_acl_esquema_fora_da_lista_recusa_mesmo_com_estrela() -> None:
    assert not _rule({"api_key"}, ["*"]).permits(ANA)
    assert _rule({"api_key"}, ["*"]).permits(CAIO_KEY)


def test_acl_estrela_aceita_qualquer_principal_de_esquema_aceito() -> None:
    rule = _rule({"oidc", "api_key"}, ["*"])
    assert all(rule.permits(p) for p in (ANA, BIA, CAIO_KEY, CAIO_OIDC, SVC))


def test_acl_subject_casa_so_o_exato() -> None:
    rule = _rule({"oidc", "api_key"}, ["user:caio", "svc:ingestor"])
    assert rule.permits(CAIO_KEY) and rule.permits(CAIO_OIDC) and rule.permits(SVC)
    assert not rule.permits(ANA)
    assert not rule.permits(Principal(subject="user:caio2", scheme="oidc"))


def test_acl_grupo_casa_quem_tem_o_grupo() -> None:
    rule = _rule({"oidc"}, ["group:chefia"])
    assert rule.permits(BIA)
    assert not rule.permits(ANA)
    assert not rule.permits(Principal(subject="user:x", scheme="oidc", groups=frozenset({"chefia2"})))


def test_acl_vazia_recusa_todo_mundo() -> None:
    assert not AccessRule().permits(CAIO_KEY)
    assert not _rule({"oidc", "api_key"}, []).permits(ANA)
