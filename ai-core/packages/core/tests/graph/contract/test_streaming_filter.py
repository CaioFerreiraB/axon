"""A geração passa pelo filtro dos validators de streaming; o acréscimo final sai como token (ADR-024).

Com e sem streaming, o consumidor recebe o mesmo texto: o que o filtro libera, a cauda dele e o que os validators em
lote só acrescentam. Reescrita no meio, depois da geração, fica registrada como `notice`.
"""

from __future__ import annotations

from typing import Any

from graph_testkit import DropFilter, Grant, ScriptedHooks, engine, outcome, provider, request

from ai_core.graph.api import FinalEvent, TokenEvent


async def collect(events: Any) -> list[Any]:
    return [event async for event in events]


def tokens(events: list[Any]) -> str:
    return "".join(event.text for event in events if isinstance(event, TokenEvent))


async def test_o_filtro_segura_o_que_nao_pode_sair_e_solta_a_cauda() -> None:
    hooks = ScriptedHooks(answer_filter=DropFilter(drop="X", tail=" [fim]"))
    events = await collect(engine(hooks=hooks, llm=provider(deltas=("BraX", "sX", "ília"))).run(Grant(), request()))

    assert tokens(events) == "Brasília [fim]"
    assert all("X" not in event.text for event in events if isinstance(event, TokenEvent))
    assert events[-1].answer == "Brasília [fim]"


async def test_a_validacao_recebe_o_resultado_filtrado() -> None:
    hooks = ScriptedHooks(answer_filter=DropFilter(drop="X"))
    await collect(engine(hooks=hooks, llm=provider(deltas=("aXb",))).run(Grant(), request()))

    [streamed] = hooks.validate_streamed
    assert streamed is not None and streamed.answer == "ab"
    assert hooks.validate_views[0].answer == "ab"
    assert hooks.stream_views[0].answer is None  # o filtro abre antes da geração


async def test_acrescimo_dos_validators_em_lote_sai_como_token() -> None:
    hooks = ScriptedHooks(outcome=outcome(answer="Brasília\n\nAtenção: aviso."))
    events = await collect(engine(hooks=hooks).run(Grant(), request()))

    assert tokens(events) == "Brasília\n\nAtenção: aviso."
    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert final.answer == "Brasília\n\nAtenção: aviso."
    assert all(issue.kind != "AnswerRewritten" for issue in final.errors)


async def test_reescrita_no_meio_fica_registrada() -> None:
    hooks = ScriptedHooks(outcome=outcome(answer="Outra coisa."))
    events = await collect(engine(hooks=hooks).run(Grant(), request()))

    final = events[-1]
    assert final.answer == "Outra coisa."
    assert tokens(events) == "Brasília"
    [registro] = [issue for issue in final.errors if issue.kind == "AnswerRewritten"]
    assert registro.severity == "notice"


async def test_sem_streaming_o_texto_final_e_o_mesmo() -> None:
    hooks = ScriptedHooks(answer_filter=DropFilter(drop="X", tail=" [fim]"))
    run = engine(hooks=hooks, llm=provider(deltas=("BraX", "sília"))).run(Grant(), request(stream=False))
    [final] = await collect(run)
    assert final.answer == "Brasília [fim]"
