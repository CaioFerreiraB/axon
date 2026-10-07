"""O filtro da geração: sessões de streaming dos validators encadeadas (ADR-024). Puro — sem I/O.

Cada pedaço passa pelas sessões em ordem, como a resposta passa pelos validators em lote: a saída de uma é a entrada da
seguinte. No fim, cada sessão fecha depois de receber o que a anterior ainda tinha a entregar. Erro de um validator vira
`PackHookError` nomeando pack e validator.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ai_core.packs.api import PackHookError, StreamedValidation, ValidatorRun
from ai_core_contracts import AnswerStream, ValidationResult


@dataclass(frozen=True, slots=True)
class StreamSession:
    pack: str
    validator: str
    session: AnswerStream


class ChainedFilter:
    """Implementa `AnswerFilter` (002 api) sobre as sessões do prefixo de validators."""

    def __init__(self, sessions: Sequence[StreamSession]) -> None:
        self._sessions = list(sessions)
        self._released = ["" for _ in self._sessions]
        self._emitted = ""

    def feed(self, delta: str) -> str:
        text = delta
        for index, item in enumerate(self._sessions):
            text = _feed(item, text)
            self._released[index] += text
        self._emitted += text
        return text

    def finish(self) -> StreamedValidation:
        runs: list[ValidatorRun] = []
        carry = ""
        for index, item in enumerate(self._sessions):
            out = _feed(item, carry) if carry else ""
            self._released[index] += out
            result = _finish(item)
            final = result.answer if result.answer is not None else self._released[index]
            if not final.startswith(self._released[index]):
                raise _error(item, "finish", "devolveu uma resposta que não começa com o texto já liberado")
            carry = out + final[len(self._released[index]) :]
            runs.append(ValidatorRun(pack=item.pack, validator=item.validator, result=result))
        return StreamedValidation(tail=carry, answer=self._emitted + carry, runs=tuple(runs))


def _feed(item: StreamSession, text: str) -> str:
    try:
        released = item.session.feed(text)
    except Exception as error:
        raise _error(item, "feed", f"levantou {type(error).__name__}: {error}") from error
    if not isinstance(released, str):
        raise _error(item, "feed", f"devolveu {type(released).__name__}; esperado str")
    return released


def _finish(item: StreamSession) -> ValidationResult:
    try:
        result = item.session.finish()
    except Exception as error:
        raise _error(item, "finish", f"levantou {type(error).__name__}: {error}") from error
    if not isinstance(result, ValidationResult):
        raise _error(item, "finish", f"devolveu {type(result).__name__}; esperado ValidationResult")
    return result


def _error(item: StreamSession, step: str, detail: str) -> PackHookError:
    return PackHookError(
        f"validator '{item.validator}' do pack '{item.pack}' ({step}) {detail}",
        pack=item.pack,
        hook=f"stream:{item.validator}",
    )
