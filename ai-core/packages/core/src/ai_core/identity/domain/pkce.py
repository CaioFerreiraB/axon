"""PKCE S256 (RFC 7636). `plain` não existe aqui: o desafio sempre é o SHA-256 do verificador (FR-004)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from typing import Final

VERIFIER_PATTERN: Final = re.compile(r"[A-Za-z0-9\-._~]{43,128}")
CHALLENGE_PATTERN: Final = re.compile(r"[A-Za-z0-9_-]{43}")


def s256(verifier: str) -> str:
    raw = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def is_challenge(value: str) -> bool:
    return bool(CHALLENGE_PATTERN.fullmatch(value))


def verifies(verifier: str | None, challenge: str) -> bool:
    if verifier is None or not VERIFIER_PATTERN.fullmatch(verifier):
        return False
    return hmac.compare_digest(s256(verifier).encode("ascii"), challenge.encode("ascii"))
