"""ADR-024 de ponta a ponta: `PackRuntime` real com um validator de streaming e o motor real (002 + 005).

O validator do pack tira o `#` da resposta — à medida que ela chega, pela sessão de streaming, e no lote, pelo
`validate` — e acrescenta um aviso no fim. Os tokens que saem nunca têm `#`, e o texto em streaming é o mesmo do evento
final.
"""

from __future__ import annotations

from typing import Any

from graph_testkit import Grant, engine, provider, request
from packs_testkit import load_runtime, make_pack_class

from ai_core.graph.api import FinalEvent, TokenEvent
from ai_core.packs.api import Composition
from ai_core.packs.ports import PackSettings
from axon_ai_contracts import TurnView, ValidationResult, ValidatorContext

AVISO = "\n\nAviso."


class _Sem:
    def __init__(self) -> None:
        self._raw = ""

    def feed(self, delta: str) -> str:
        self._raw += delta
        return delta.replace("#", "")

    def finish(self) -> ValidationResult:
        return ValidationResult(ok=True, answer=self._raw.replace("#", "") + AVISO, flags=frozenset({"limpo"}))


class TiraCerquilha:
    name = "tira_cerquilha"

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        return ValidationResult(
            ok=True, answer=(view.answer or "").replace("#", "") + AVISO, flags=frozenset({"limpo"})
        )

    def open_stream(self, view: TurnView, ctx: ValidatorContext) -> _Sem:
        return _Sem()


async def _run(stream: bool) -> list[Any]:
    pack = make_pack_class("limpo", validators=lambda self, ctx: (TiraCerquilha(),))
    runtime: Any = load_runtime(pack, settings={"limpo": PackSettings(enabled=True)})
    motor = engine(hooks=runtime, llm=provider(deltas=("Bra#s", "í#", "lia")))
    grant = Grant(composition=Composition(packs=("limpo",)))
    return [event async for event in motor.run(grant, request(stream=stream))]


async def test_tokens_saem_filtrados_e_o_aviso_vem_no_fim() -> None:
    events = await _run(stream=True)
    tokens = [event.text for event in events if isinstance(event, TokenEvent)]
    assert all("#" not in text for text in tokens)
    assert "".join(tokens) == "Brasília" + AVISO
    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert final.answer == "Brasília" + AVISO
    assert "limpo" in final.flags


async def test_sem_streaming_o_texto_e_o_mesmo() -> None:
    [final] = await _run(stream=False)
    assert final.answer == "Brasília" + AVISO
