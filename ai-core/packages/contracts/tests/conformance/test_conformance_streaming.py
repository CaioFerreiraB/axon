"""Conformidade: validators que filtram o streaming (ADR-024; contratos 0.1.1)."""

from __future__ import annotations

from typing import Any

from packs import make_pack

from axon_ai_contracts import AnswerStream, StreamingValidator, TurnView, ValidationResult, ValidatorContext
from axon_ai_contracts.testing import check_pack, turn_view

VIEWS = [turn_view(answer="aXbXc"), turn_view(answer=None), turn_view(answer="")]


class _Stream:
    """Tira o X à medida que chega; `finish` devolve a resposta sem X."""

    def __init__(self, *, emit_raw: bool = False, extra_flag: bool = False) -> None:
        self._raw = ""
        self._emit_raw = emit_raw
        self._extra_flag = extra_flag

    def feed(self, delta: str) -> str:
        self._raw += delta
        return delta if self._emit_raw else delta.replace("X", "")

    def finish(self) -> ValidationResult:
        flags = frozenset({"extra"}) if self._extra_flag else frozenset()
        return ValidationResult(ok=True, answer=self._raw.replace("X", ""), flags=flags)


class DropX:
    name = "drop_x"

    def __init__(self, **stream: bool) -> None:
        self._stream = stream

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        if view.answer is None:
            return ValidationResult(ok=True)
        return ValidationResult(ok=True, answer=view.answer.replace("X", ""))

    def open_stream(self, view: TurnView, ctx: ValidatorContext) -> AnswerStream:
        return _Stream(**self._stream)


def _codes(validator: Any) -> list[str]:
    pack = make_pack(validators=lambda self, ctx: (validator,))
    return [issue.code for issue in check_pack(pack, views=VIEWS, check_distribution=False).issues]


def test_os_protocolos_reconhecem_o_validator_e_a_sessao() -> None:
    assert isinstance(DropX(), StreamingValidator)
    assert isinstance(_Stream(), AnswerStream)


def test_validator_que_filtra_certo_conforma() -> None:
    assert _codes(DropX()) == []


def test_fim_que_nao_so_acrescenta_e_apontado() -> None:
    assert "validator.stream.not_append_only" in _codes(DropX(emit_raw=True))


def test_resultado_diferente_do_validate_e_apontado() -> None:
    assert "validator.stream.mismatch" in _codes(DropX(extra_flag=True))
