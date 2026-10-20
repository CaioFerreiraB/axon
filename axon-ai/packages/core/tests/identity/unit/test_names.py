"""T006 — nomes, e-mail, senha e identificador de login (FR-001, FR-002, FR-003; R10)."""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from axon_ai.identity.domain.names import (
    is_email,
    is_username,
    normalize_email,
    password_problem,
    read_identifier,
)

_LEGAL_FIRST = "abcdefghijklmnopqrstuvwxyz0123456789"
_LEGAL = _LEGAL_FIRST + "._-"


@given(st.text(_LEGAL_FIRST, min_size=1, max_size=1), st.text(_LEGAL, max_size=63))
def test_nomes_no_padrao_sao_aceitos(first: str, rest: str) -> None:
    assert is_username(first + rest)


@pytest.mark.parametrize(
    "name",
    ["", "Ana", "ana@x", ".ana", "-ana", "_ana", "ana silva", "a" * 65, "anã", "ana\n"],
)
def test_nomes_fora_do_padrao_sao_recusados(name: str) -> None:
    assert not is_username(name)


@given(st.text(_LEGAL, max_size=30), st.text(_LEGAL, max_size=30))
def test_nome_com_arroba_nunca_e_usuario(before: str, after: str) -> None:
    assert not is_username(f"{before}@{after}")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("  Ana@Exemplo.ORG ", "ana@exemplo.org"), ("bia@x.io", "bia@x.io")],
)
def test_email_normalizado_e_valido(raw: str, expected: str) -> None:
    assert normalize_email(raw) == expected
    assert is_email(normalize_email(raw))


@pytest.mark.parametrize("value", ["ana", "ana@", "@x.org", "ana@x", "a b@x.org", "a@b@c.org", "x" * 250 + "@x.org"])
def test_emails_invalidos(value: str) -> None:
    assert not is_email(value)


@given(st.text(min_size=12, max_size=128))
def test_senha_de_12_a_128_codigos_unicode_serve(password: str) -> None:
    assert password_problem(password) is None


@pytest.mark.parametrize(
    ("password", "fragment"),
    [("curta", "pelo menos 12"), ("x" * 11, "pelo menos 12"), ("x" * 129, "no máximo 128")],
)
def test_senha_fora_do_tamanho(password: str, fragment: str) -> None:
    problem = password_problem(password)
    assert problem is not None and fragment in problem


def test_senha_conta_codigos_e_nao_bytes() -> None:
    assert password_problem("ção" * 4) is None  # 12 códigos, 20 bytes
    assert password_problem("🔒" * 128) is None
    assert password_problem("🔒" * 129) is not None


def test_senha_sem_regra_de_composicao() -> None:
    assert password_problem("aaaaaaaaaaaa") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ana", ("username", "ana")),
        ("  Ana ", ("username", "ana")),
        ("Ana@Exemplo.org", ("email", "ana@exemplo.org")),
        (" bia@x.io ", ("email", "bia@x.io")),
    ],
)
def test_identificador_decide_pelo_arroba(raw: str, expected: tuple[str, str]) -> None:
    assert read_identifier(raw) == expected
