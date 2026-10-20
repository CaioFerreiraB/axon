"""T012 — projeção do estado interno na Turn View (ADR-011) e o trânsito das fatias de pack.

Este é o único teste fora de `integration/` que conhece o interior do adapter: ele acompanha a troca do grafo, e os
demais não (SC-001).
"""

from __future__ import annotations

from typing import Any

import pytest
from graph_testkit import ASSISTANT, MESSAGES, REFERENCE_TIME, REQUEST_ID, ScriptedHooks, engine, fenced, request

from ai_core.capabilities.api import FencedToolResult, ToolCall
from ai_core.graph.adapters.langgraph.view import turn_view
from ai_core.graph.api import ExecutionGrant
from ai_core.graph.domain.transcript import InvalidStep, ToolStep
from axon_ai_contracts import Chunk, ToolResult


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


async def test_a_mesma_data_de_referencia_chega_a_todos_os_hooks(grant: ExecutionGrant) -> None:
    hooks = ScriptedHooks()
    async for _ in engine(hooks=hooks).run(grant, request()):
        pass
    datas = {view.reference_time for view in (*hooks.prepare_views, *hooks.validate_views)}
    assert len(datas) == 1


async def test_fatias_devolvidas_por_prepare_chegam_a_validate(grant: ExecutionGrant) -> None:
    hooks = ScriptedHooks(slice_update={"preparado": True})
    async for _ in engine(hooks=hooks).run(grant, request()):
        pass
    assert hooks.validate_slices[0]["generic"] == {"preparado": True}


async def test_validate_recebe_a_resposta_gerada(grant: ExecutionGrant) -> None:
    hooks = ScriptedHooks()
    async for _ in engine(hooks=hooks).run(grant, request()):
        pass
    assert hooks.validate_views[0].answer == "Brasília"
    assert hooks.prepare_views[0].answer is None


# --- Fase 3 (T036; research R26): resultados de tool na Turn View --------------------------------------------------


def _chunk(n: int) -> Chunk:
    return Chunk(chunk_id=f"c{n}", text=f"trecho {n}", score=0.9, document=f"doc-{n}")


def _tool(iteration: int, name: str, *, chunks: tuple[Chunk, ...] = (), truncated: bool = False) -> ToolStep:
    result = FencedToolResult(
        name=name,
        kind="retrieval" if chunks else "native",
        status="ok",
        text=fenced(name, f"resultado {iteration}", truncated=truncated),
        truncated=truncated,
        chunks=chunks,
    )
    return ToolStep(iteration=iteration, call=ToolCall(name=name), result=result)


@pytest.mark.us2
def test_resultados_entregues_viram_tool_results_na_ordem() -> None:
    steps = [
        _tool(1, "generic.calculate"),
        InvalidStep(iteration=2, reason="JSON malformado"),
        _tool(3, "x.y", truncated=True),
    ]
    view = turn_view(state(flow="agentic", steps=steps))
    assert tuple(view.tool_results) == (
        ToolResult(content=steps[0].result.text, untrusted=True, truncated=False, error=None),  # type: ignore[union-attr]
        ToolResult(content=steps[2].result.text, untrusted=True, truncated=True, error=None),  # type: ignore[union-attr]
    )


@pytest.mark.us2
def test_omitidos_pelo_teto_nao_entram_na_turn_view() -> None:
    steps = [_tool(1, "docs.buscar", chunks=(_chunk(1),)), _tool(2, "docs.buscar", chunks=(_chunk(2), _chunk(3)))]
    view = turn_view(state(flow="agentic", steps=steps, omitted=1))
    assert [result.content for result in view.tool_results] == [steps[1].result.text]
    assert tuple(view.retrieved) == (_chunk(1), _chunk(2), _chunk(3))
    assert tuple(view.generation_context) == (_chunk(2), _chunk(3))
    assert tuple(view.reranked) == ()


@pytest.mark.us2
def test_sem_passos_nao_ha_resultados() -> None:
    view = turn_view(state(flow="agentic", steps=[]))
    assert (tuple(view.tool_results), tuple(view.retrieved), tuple(view.generation_context)) == ((), (), ())


# --- Fase 5: `rag_first` (T074; research R43; tabela "Turn View no `rag_first`" do data-model) ------------------------


def _passages(*ids: str, pack: str = "docs") -> tuple[Any, ...]:
    from ai_core.graph.domain.gate import Passage

    return tuple(
        Passage(pack=pack, tool=f"{pack}.search", chunk=Chunk(chunk_id=i, text=i, score=0.5, document="D")) for i in ids
    )


def _step(iteration: int, *ids: str, synthetic: bool) -> ToolStep:
    chunks = tuple(Chunk(chunk_id=i, text=i, score=0.5, document="D") for i in ids)
    return ToolStep(
        iteration=iteration,
        call=ToolCall(name="docs.search", arguments={"query": "q"}),
        result=FencedToolResult(
            name="docs.search", kind="retrieval", status="ok", text=fenced("docs.search", "x"), chunks=chunks
        ),
        synthetic=synthetic,
    )


@pytest.mark.us3
def test_rag_first_coberto() -> None:
    candidatos = _passages("c1", "c2", "c3", "c4")
    view = turn_view(
        state(
            flow="rag_first",
            retrieved=candidatos,
            reranked=candidatos[:3],
            steps=[_step(1, "c1", "c2", synthetic=True)],
        )
    )
    assert [c.chunk_id for c in view.retrieved] == ["c1", "c2", "c3", "c4"], "sem duplicar os do passo sintético"
    assert [c.chunk_id for c in view.reranked] == ["c1", "c2", "c3"]
    assert [c.chunk_id for c in view.generation_context] == ["c1", "c2"], "os que couberam"
    assert len(view.tool_results) == 1


@pytest.mark.us3
def test_rag_first_sem_trechos() -> None:
    candidatos = _passages("c1")
    view = turn_view(state(flow="rag_first", retrieved=candidatos, reranked=candidatos, steps=[]))
    assert [c.chunk_id for c in view.retrieved] == ["c1"] and [c.chunk_id for c in view.reranked] == ["c1"]
    assert tuple(view.generation_context) == () and tuple(view.tool_results) == ()


@pytest.mark.us3
def test_rag_first_escalado_soma_os_do_loop() -> None:
    candidatos = _passages("c1")
    view = turn_view(
        state(
            flow="rag_first", retrieved=candidatos, reranked=candidatos, steps=[_step(1, "l1", "l2", synthetic=False)]
        )
    )
    assert [c.chunk_id for c in view.retrieved] == ["c1", "l1", "l2"]
    assert [c.chunk_id for c in view.generation_context] == ["l1", "l2"]
    assert [c.chunk_id for c in view.reranked] == ["c1"]
