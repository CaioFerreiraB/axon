"""T008 — precedência instalação > runtime > padrão no login Google (FR-009, ADR-033)."""

from __future__ import annotations

import pytest

from axon_ai.identity.domain.settings import google_login


@pytest.mark.parametrize(
    ("installation", "runtime", "configured", "expected"),
    [
        (None, None, True, (True, "default")),
        (None, None, False, (False, "default")),
        (None, False, True, (False, "runtime")),
        (None, True, True, (True, "runtime")),
        (False, True, True, (False, "installation")),
        (True, False, True, (True, "installation")),
        # sem cliente Google, nada liga — nem a instalação
        (True, None, False, (False, "installation")),
        (None, True, False, (False, "runtime")),
    ],
)
def test_precedencia_e_origem(
    installation: bool | None, runtime: bool | None, configured: bool, expected: tuple[bool, str]
) -> None:
    assert google_login(installation=installation, runtime=runtime, configured=configured) == expected
