"""Hash de segredos de protocolo e comparação em tempo constante.

Pedido pendente, código, sessão e renovação são valores aleatórios de 32 bytes: SHA-256 basta para guardá-los (não há
dicionário a atacar), e o armazenamento nunca vê o valor (FR-020, research R12).
"""

from __future__ import annotations

import hashlib
import hmac

_CSRF_CONTEXT = "ai-core/identity/csrf:"


def digest(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def same(left: str, right: str) -> bool:
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))


def session_csrf(session_token: str) -> str:
    """CSRF de "Minha conta", derivado do token da sessão: só quem tem o cookie o calcula, e nada é guardado (R5)."""
    return hashlib.sha256((_CSRF_CONTEXT + session_token).encode("utf-8")).hexdigest()
