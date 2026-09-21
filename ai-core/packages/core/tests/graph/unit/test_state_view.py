"""T012 — projeção do estado interno na Turn View (ADR-011) e o trânsito das fatias de pack.

Este é o único teste fora de `integration/` que conhece o interior do adapter: ele acompanha a troca do grafo, e os
demais não (SC-001).
"""

from __future__ import annotations

from typing import Any

from graph_testkit import ASSISTANT, MESSAGES, REFERENCE_TIME, REQUEST_ID, Grant, ScriptedHooks, engine, request

from ai_core.graph.adapters.langgraph.view import turn_view


def state(**overrides: Any) -> Any:
    base: dict[str, Any] = {
        "request_id": REQUEST_ID,
        "assistant": ASSISTANT,
        "flow": "chat",
        "reference_time": REFERENCE_TIME,
        "question": "qual é a capital?",
        "messages": MESSAGES,
    }
    return base | overrides


def test_projecao_leva_identidade_pergunta_e_mensagens() -> None:
    view = turn_view(state())
    assert (view.request_id, view.assistant) == (REQUEST_ID, ASSISTANT)
    assert view.question == "qual é a capital?"
    assert view.reference_time == REFERENCE_TIME
    assert tuple(view.messages) == MESSAGES


def test_contexto_de_geracao_e_vazio_no_chat() -> None:
    """O `chat` não entrega chunk nenhum à geração — vazio é a resposta correta para o validator (ADR-007)."""
    view = turn_view(state())
    assert tuple(view.generation_context) == ()
    assert tuple(view.retrieved) == ()
    assert tuple(view.tool_results) == ()


def test_resposta_e_citacoes_aparecem_quando_ja_existem() -> None:
    view = turn_view(state(answer="Brasília", citations=[{"chunk_id": "c1"}]))
    assert view.answer == "Brasília"
    assert tuple(view.citations) == ({"chunk_id": "c1"},)


async def test_a_mesma_data_de_referencia_chega_a_todos_os_hooks(grant: Grant) -> None:
    hooks = ScriptedHooks()
    async for _ in engine(hooks=hooks).run(grant, request()):
        pass
    datas = {view.reference_time for view in (*hooks.prepare_views, *hooks.validate_views)}
    assert len(datas) == 1


async def test_fatias_devolvidas_por_prepare_chegam_a_validate(grant: Grant) -> None:
    hooks = ScriptedHooks(slice_update={"preparado": True})
    async for _ in engine(hooks=hooks).run(grant, request()):
        pass
    assert hooks.validate_slices[0]["generic"] == {"preparado": True}


async def test_validate_recebe_a_resposta_gerada(grant: Grant) -> None:
    hooks = ScriptedHooks()
    async for _ in engine(hooks=hooks).run(grant, request()):
        pass
    assert hooks.validate_views[0].answer == "Brasília"
    assert hooks.prepare_views[0].answer is None
