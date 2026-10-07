"""T013 — conformidade do seam Execution Engine (contracts/execution-engine.md).

Roda o grafo de verdade com hooks programáveis e o provider simulado da 006: só o modelo é simulado (research R13).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from graph_testkit import Grant, RecordingTraceSink, ScriptedHooks, engine, outcome, provider, request

from ai_core.graph.api import (
    ExecutionGrant,
    ExecutionRequestInvalid,
    FinalEvent,
    ProgressEvent,
    TokenEvent,
    UnknownFlow,
)
from ai_core.llm.api import ModelCallFailed
from ai_core.observability.api import ExecutionError, ExecutionFinished, ExecutionStarted, ValidationRun
from ai_core.packs.api import PackHookError

CITATION = {"chunk_id": "c1", "document": "doc"}


async def collect(events: Any) -> list[Any]:
    return [event async for event in events]


# --- 1 e 2: ordem dos eventos e streaming -------------------------------------------------------------------


async def test_streaming_emite_progresso_tokens_e_final_nessa_ordem(trace: Any, grant: ExecutionGrant) -> None:
    events = await collect(engine(trace=trace).run(grant, request()))
    kinds = [type(event).__name__ for event in events]
    assert kinds[0] == "ProgressEvent"
    assert kinds[-1] == "FinalEvent"
    stages = [event.stage for event in events if isinstance(event, ProgressEvent)]
    assert stages == ["prepare_context", "generate", "validate_answer"]
    assert [event.text for event in events if isinstance(event, TokenEvent)] == ["Bras", "ília"]


async def test_streaming_entrega_o_primeiro_token_antes_do_fim_da_geracao(grant: ExecutionGrant) -> None:
    """Se o token só saísse no fim, a validação já teria rodado quando o consumidor o recebesse."""
    hooks = ScriptedHooks()
    iterator = engine(hooks=hooks).run(grant, request())
    async for event in iterator:
        if isinstance(event, TokenEvent):
            assert hooks.validate_views == []
            break
    await iterator.aclose()


async def test_evento_final_traz_a_resposta_completa(grant: ExecutionGrant) -> None:
    events = await collect(engine().run(grant, request()))
    assert events[-1].answer == "Brasília"


# --- 4: validator que altera --------------------------------------------------------------------------------


async def test_validator_que_altera_resposta_e_citacoes_prevalece(grant: ExecutionGrant) -> None:
    hooks = ScriptedHooks(
        outcome=outcome(
            ok=False,
            answer="Brasília (revisada)",
            citations=[CITATION],  # type: ignore[list-item]
            issues=["citação removida"],
            flags=frozenset({"revisada"}),
        )
    )
    final = (await collect(engine(hooks=hooks).run(grant, request())))[-1]
    assert isinstance(final, FinalEvent)
    assert final.answer == "Brasília (revisada)"
    assert final.citations == (CITATION,)
    assert final.flags == frozenset({"revisada"})
    assert [issue.kind for issue in final.errors] == ["ValidatorIssue"]


# --- 5 e 6: falhas antes do primeiro evento -----------------------------------------------------------------


async def test_requisicao_invalida_levanta_na_chamada_sem_emitir_nada(grant: ExecutionGrant, trace: Any) -> None:
    llm = provider()
    with pytest.raises(ExecutionRequestInvalid):
        engine(llm=llm, trace=trace).run(grant, request(messages=[{"role": "system", "content": "sem usuário"}]))
    assert llm.calls == []
    assert trace.events == []


async def test_flow_invalido_levanta_na_chamada_sem_emitir_nada(trace: Any) -> None:
    llm = provider()
    with pytest.raises(UnknownFlow) as error:
        engine(llm=llm, trace=trace).run(Grant(flow="agentic"), request())
    assert "agentic" in str(error.value)
    assert llm.calls == []
    assert trace.events == []


# --- 7 e 8: falhas depois do primeiro evento ----------------------------------------------------------------


async def test_provider_fora_do_ar_vira_evento_final_com_erro(grant: ExecutionGrant, trace: Any) -> None:
    falho = provider(error=ModelCallFailed(provider="ollama", model="qwen3:1.7b", reason="inalcançável"))
    events = await collect(engine(llm=falho, trace=trace).run(grant, request()))
    final = events[-1]
    assert isinstance(final, FinalEvent)
    assert [issue.kind for issue in final.errors] == ["ModelCallFailed"]
    assert "ollama/qwen3:1.7b" in final.errors[0].message
    assert trace.of_type(ExecutionError)


async def test_hook_de_pack_que_levanta_vira_evento_final_nomeando_o_pack(grant: ExecutionGrant, trace: Any) -> None:
    hooks = ScriptedHooks(prepare_error=PackHookError("explodiu", pack="generic", hook="prepare_context"))
    final = (await collect(engine(hooks=hooks, trace=trace).run(grant, request())))[-1]
    assert isinstance(final, FinalEvent)
    assert final.errors[0].kind == "PackHookError"
    assert "generic" in final.errors[0].message


async def test_falha_preserva_o_que_ja_foi_gerado(grant: ExecutionGrant) -> None:
    """A resposta parcial não se perde: o consumidor já viu os tokens."""
    hooks = ScriptedHooks(validate_error=PackHookError("caiu", pack="generic", hook="validate:checa"))
    events = await collect(engine(hooks=hooks).run(grant, request()))
    assert events[-1].answer == "Brasília"
    assert events[-1].errors[0].kind == "PackHookError"


# --- 9 e 10: modos de consumo -------------------------------------------------------------------------------


async def test_sem_streaming_o_consumidor_recebe_so_o_evento_final(grant: ExecutionGrant) -> None:
    events = await collect(engine().run(grant, request(stream=False)))
    assert len(events) == 1
    assert isinstance(events[0], FinalEvent)
    assert events[0].answer == "Brasília"


async def test_fechar_o_iterador_no_meio_nao_levanta(grant: ExecutionGrant, trace: Any) -> None:
    iterator = engine(trace=trace).run(grant, request())
    await anext(iterator)
    await iterator.aclose()
    finished = trace.of_type(ExecutionFinished)
    assert finished and finished[0].ok is False
    assert finished[0].reason == "cancelled"


# --- 11: trace ----------------------------------------------------------------------------------------------


async def test_trace_tem_comeco_validacao_e_fim(grant: ExecutionGrant, trace: RecordingTraceSink, clock: Any) -> None:
    hooks = ScriptedHooks(outcome=outcome(issues=["aviso"]))
    await collect(engine(hooks=hooks, trace=trace, clock=clock).run(grant, request()))

    started = trace.of_type(ExecutionStarted)
    assert started[0].assistant == "geral"
    assert started[0].flow == "chat"
    assert started[0].packs == ("generic",)
    assert started[0].reference_time.tzinfo is not None

    runs = trace.of_type(ValidationRun)
    assert [(run.pack, run.validator) for run in runs] == [("generic", "checa")]
    assert runs[0].issues == ("aviso",)

    finished = trace.of_type(ExecutionFinished)
    assert finished[0].ok is True
    assert finished[0].duration_ms == pytest.approx(250.0)


async def test_data_de_referencia_da_requisicao_prevalece_sobre_o_relogio(grant: ExecutionGrant, trace: Any) -> None:
    """ADR-013: o harness fixa a data; a API HTTP rejeita o campo (008 FR-012)."""
    from datetime import UTC, datetime

    fixada = datetime(2020, 1, 1, tzinfo=UTC)
    await collect(engine(trace=trace).run(grant, request(reference_time=fixada)))
    assert trace.of_type(ExecutionStarted)[0].reference_time == fixada


# --- 12: SC-001 ---------------------------------------------------------------------------------------------


def test_as_suites_do_seam_nao_importam_o_framework_de_grafo() -> None:
    """É o que torna verificável a promessa do SC-001: estas suítes sobrevivem à troca do adapter."""
    raiz = Path(__file__).resolve().parents[1]
    proibidos = {"langgraph", "langchain_core"}
    for arquivo in sorted((*raiz.glob("unit/*.py"), *raiz.glob("contract/*.py"))):
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        for node in ast.walk(arvore):
            if isinstance(node, ast.Import):
                nomes = {alias.name.split(".")[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                nomes = {(node.module or "").split(".")[0]}
            else:
                continue
            assert not (nomes & proibidos), f"{arquivo.name} importa o framework de grafo"
