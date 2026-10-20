"""Depreciação de símbolos dos contratos, com versão de depreciação e de remoção (FR-016, ADR-014, research R16)."""

from __future__ import annotations

import contextlib
from collections.abc import Callable

from typing_extensions import deprecated

from axon_ai_contracts.compat import removal_version

_DEPRECATED_SINCE_ATTRIBUTE = "__contract_deprecated_since__"


class ContractDeprecationWarning(DeprecationWarning):
    """Uso de símbolo depreciado de `axon-ai-contracts`. A suíte de conformidade o reporta como `deprecation.used`."""


def contract_deprecated[T](since: str, *, use_instead: str | None = None) -> Callable[[T], T]:
    """Marca um símbolo como depreciado desde `since`; a remoção sai da política (0.N.x → 0.(N+1).0).

    Grava `__contract_deprecated_since__` no objeto, lido pelo snapshot de superfície para barrar remoção sem
    depreciação prévia.
    """
    removal = removal_version(since)

    def decorate(target: T) -> T:
        qualname = str(getattr(target, "__qualname__", getattr(target, "__name__", repr(target))))
        symbol = qualname.rsplit("<locals>.", 1)[-1]
        message = f"{symbol} está depreciado desde axon-ai-contracts {since} e será removido em {removal}"
        if use_instead:
            message += f"; use {use_instead}"
        decorated: T = deprecated(message, category=ContractDeprecationWarning, stacklevel=2)(target)
        with contextlib.suppress(AttributeError, TypeError):
            setattr(decorated, _DEPRECATED_SINCE_ATTRIBUTE, since)
        return decorated

    return decorate
