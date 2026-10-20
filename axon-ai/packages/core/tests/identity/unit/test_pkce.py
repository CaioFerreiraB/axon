"""T040 — PKCE S256 (RFC 7636, apêndice B)."""

from __future__ import annotations

from axon_ai.identity.domain.pkce import is_challenge, s256, verifies

RFC_VERIFIER = "dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk"
RFC_CHALLENGE = "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


def test_vetor_da_rfc() -> None:
    assert s256(RFC_VERIFIER) == RFC_CHALLENGE
    assert is_challenge(RFC_CHALLENGE)
    assert verifies(RFC_VERIFIER, RFC_CHALLENGE)


def test_verificador_errado_ausente_ou_fora_do_formato() -> None:
    assert not verifies(RFC_VERIFIER[:-1] + "Y", RFC_CHALLENGE)
    assert not verifies(None, RFC_CHALLENGE)
    assert not verifies("curto", s256("curto"))
    assert not verifies("x" * 129, s256("x" * 129))
    assert not verifies("ç" * 43, RFC_CHALLENGE)


def test_desafio_fora_do_formato() -> None:
    assert not is_challenge("curto")
    assert not is_challenge(RFC_CHALLENGE + "=")
