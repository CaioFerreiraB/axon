"""Imagens na execução (ADR-044, itens 4, 5 e 8; FR-019 a FR-023; research R51).

As imagens das tools vão ao usuário e não ao modelo; a do usuário vai à geração; as da resposta anterior só quando a
pergunta é sobre elas — pelo `view_image` no loop, pela etapa `image_gate` no `chat` e no `rag_first` coberto, e todas
quando não há `controller`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from graph_testkit import (
    ANSWER,
    FakeCapabilities,
    FakeSession,
    Grant,
    RecordingTraceSink,
    ScriptedController,
    agentic,
    catalog_tool,
    controller_down,
    docs_session,
    engine,
    models,
    provider,
    rag,
    request,
    tool_action,
)

from axon_ai.graph.api import (
    AttachmentEvent,
    ControllerOutcome,
    ExecutionRequestInvalid,
    FinalEvent,
    ImageGateOutcome,
    ProgressEvent,
    StepFinished,
)
from axon_ai.graph.domain.images import IMAGES_INSTRUCTION
from axon_ai.llm.api import image_part
from axon_ai.observability.api import ControllerDecision
from axon_ai_contracts import Attachment, Chunk, Message

GRAFICO = Attachment(mime="image/png", data=b"\x89PNG\r\n\x1a\n" + b"g" * 50, alt="Gastos")
OUTRO = Attachment(mime="image/webp", data=b"RIFF" + b"w" * 30)
FOTO = Attachment(mime="image/jpeg", data=b"\xff\xd8\xff" + b"f" * 40)

COM_VISAO = frozenset({"generation"})


def historico(*, pergunta: str = "o que é aquele pico?", fotos: tuple[Attachment, ...] = ()) -> tuple[Message, ...]:
    """Turno anterior com duas imagens mostradas e a pergunta de agora."""
    ultima: Message = {"role": "user", "content": pergunta}
    if fotos:
        ultima = {"role": "user", "content": pergunta, "attachments": fotos}
    return (
        {"role": "user", "content": "gastos de outubro"},
        {
            "role": "assistant",
            "content": (
                f"Aqui está.\n[imagem {GRAFICO.id} mostrada ao usuário]\n[imagem {OUTRO.id} mostrada ao usuário]"
            ),
            "attachments": (GRAFICO, OUTRO),
        },
        ultima,
    )


async def coletar(stream: Any) -> list[Any]:
    return [event async for event in stream]


def enviadas(llm: Any) -> list[Any]:
    return list(llm.calls[-1]["messages"])


def imagens_na_ultima(messages: list[Any]) -> list[str]:
    """As imagens da última mensagem do usuário — no `rag_first`, depois dela vem o passo de tool sintético."""
    content = next(message for message in reversed(messages) if message["role"] == "user")["content"]
    if isinstance(content, str):
        return []
    return [part["image_url"]["url"] for part in content if part["type"] == "image_url"]


def url(attachment: Attachment) -> str:
    return image_part(attachment.mime, attachment.data)["image_url"]["url"]


# --- imagens das tools (item 4) ------------------------------------------------------------------------------------


async def test_imagem_da_tool_vai_ao_usuario_depois_do_desfecho_e_nao_ao_modelo() -> None:
    session = FakeSession((catalog_tool("mango.grafico"),), attachments={"mango.grafico": (GRAFICO, OUTRO)})
    llm = provider(deltas=("Pronto.",))
    controller = ScriptedController((tool_action("mango.grafico", expression="x"), ANSWER))
    motor = engine(capabilities=FakeCapabilities(session), controller=controller, llm=llm)

    events = await coletar(motor.run(agentic(), request()))

    executed = next(i for i, e in enumerate(events) if isinstance(e, StepFinished) and e.stage == "execute_tool")
    images = [(i, e) for i, e in enumerate(events) if isinstance(e, AttachmentEvent)]
    assert [e.attachment for _, e in images] == [GRAFICO, OUTRO]
    assert all(i == executed + n + 1 for n, (i, _) in enumerate(images)), "logo depois do desfecho da tool"
    assert {e.tool for _, e in images} == {"mango.grafico"}
    final = events[-1]
    assert isinstance(final, FinalEvent) and final.attachments == (GRAFICO, OUTRO)
    sent = enviadas(llm)
    assert {"role": "system", "content": IMAGES_INSTRUCTION} in sent
    assert all(isinstance(message["content"], str | None) for message in sent), "nenhum byte vai ao modelo"
    assert all(isinstance(m["content"], str | None) for call in controller.calls for m in call["messages"])


async def test_a_mesma_imagem_de_duas_chamadas_sai_uma_vez() -> None:
    session = FakeSession((catalog_tool("mango.grafico"),), attachments={"mango.grafico": (GRAFICO,)})
    script = (tool_action("mango.grafico", expression="a"), tool_action("mango.grafico", expression="b"), ANSWER)
    motor = engine(capabilities=FakeCapabilities(session), controller=ScriptedController(script))

    events = await coletar(motor.run(agentic(), request()))

    assert [e.attachment for e in events if isinstance(e, AttachmentEvent)] == [GRAFICO]
    assert events[-1].attachments == (GRAFICO,)


async def test_sem_imagem_de_tool_a_geracao_nao_recebe_o_aviso() -> None:
    llm = provider()
    controller = ScriptedController((tool_action("generic.calculate", expression="1+1"), ANSWER))
    motor = engine(capabilities=FakeCapabilities(), controller=controller, llm=llm)
    events = await coletar(motor.run(agentic(), request()))
    assert events[-1].attachments == ()
    assert all(message["content"] != IMAGES_INSTRUCTION for message in enviadas(llm))


# --- imagem do usuário (item 5) ------------------------------------------------------------------------------------


async def test_imagem_do_usuario_vai_a_geracao_sem_decisao() -> None:
    llm = provider()
    motor = engine(llm=llm)
    grant = Grant(models=models(controller=False, vision=COM_VISAO))
    pedido = request(messages=({"role": "user", "content": "o que é isto?", "attachments": (FOTO,)},))

    events = await coletar(motor.run(grant, pedido))

    assert not any(isinstance(e, ProgressEvent) and e.stage == "image_gate" for e in events)
    last = enviadas(llm)[-1]
    assert last["content"][0] == {"type": "text", "text": "o que é isto?"}
    assert imagens_na_ultima(enviadas(llm)) == [url(FOTO)]


async def test_so_imagem_vale_como_pergunta() -> None:
    llm = provider()
    motor = engine(llm=llm)
    grant = Grant(models=models(controller=False, vision=COM_VISAO))
    pedido = request(messages=({"role": "user", "content": "", "attachments": (FOTO,)},))
    events = await coletar(motor.run(grant, pedido))
    assert isinstance(events[-1], FinalEvent)
    assert imagens_na_ultima(enviadas(llm)) == [url(FOTO)]


def test_imagem_do_usuario_sem_vision_na_geracao_e_recusada_antes_de_qualquer_custo() -> None:
    llm = provider()
    motor = engine(llm=llm)
    pedido = request(messages=({"role": "user", "content": "e isto?", "attachments": (FOTO,)},))
    with pytest.raises(ExecutionRequestInvalid, match="vision"):
        motor.run(Grant(models=models(controller=False)), pedido)
    assert llm.calls == []


@pytest.mark.parametrize("controller_vision", [False, True])
async def test_o_controller_so_ve_a_imagem_do_usuario_com_vision(controller_vision: bool) -> None:
    controller = ScriptedController((ANSWER,))
    motor = engine(capabilities=FakeCapabilities(), controller=controller)
    vision = COM_VISAO | ({"controller"} if controller_vision else set())
    pedido = request(messages=({"role": "user", "content": "calcule o total", "attachments": (FOTO,)},))

    await coletar(motor.run(agentic(models=models(vision=frozenset(vision))), pedido))

    last = controller.calls[0]["messages"][-1]
    if controller_vision:
        assert imagens_na_ultima(controller.calls[0]["messages"]) == [url(FOTO)]
    else:
        assert last["content"] == f"calcule o total\n[imagem {FOTO.id} enviada pelo usuário]"


# --- imagens da resposta anterior no loop (item 8) -----------------------------------------------------------------


async def test_no_loop_o_controller_ve_so_os_ids_e_marca_a_imagem_para_a_geracao() -> None:
    trace = RecordingTraceSink()
    llm = provider()
    controller = ScriptedController((json.dumps({"action": "view_image", "id": GRAFICO.id}), ANSWER))
    motor = engine(capabilities=FakeCapabilities(), controller=controller, llm=llm, trace=trace)

    events = await coletar(motor.run(agentic(models=models(vision=COM_VISAO)), request(messages=historico())))

    first = controller.calls[0]
    system = first["messages"][0]["content"]
    assert GRAFICO.id in system and OUTRO.id in system
    assert all(isinstance(m["content"], str | None) for m in first["messages"]), (
        "as candidatas não voltam ao controller"
    )
    branch = first["response_format"]["json_schema"]["schema"]["anyOf"][1]
    assert branch["properties"]["id"]["enum"] == [GRAFICO.id, OUTRO.id]
    assert f"A imagem {GRAFICO.id} foi marcada para a resposta." in [
        m["content"] for m in controller.calls[1]["messages"]
    ]

    sent = enviadas(llm)
    assert imagens_na_ultima(sent) == [url(GRAFICO)]
    assert {"type": "text", "text": f"[imagem {GRAFICO.id} mostrada ao usuário]"} in sent[-1]["content"]
    outcomes = [e.outcome for e in events if isinstance(e, StepFinished) and isinstance(e.outcome, ControllerOutcome)]
    assert outcomes[0].action == "view_image" and outcomes[0].image == GRAFICO.id
    decisions = trace.of_type(ControllerDecision)
    assert (decisions[0].action, decisions[0].images, decisions[0].tool) == ("view_image", (GRAFICO.id,), None)


async def test_pedir_a_mesma_imagem_de_novo_segue_a_regra_da_acao_repetida() -> None:
    llm = provider()
    view = json.dumps({"action": "view_image", "id": OUTRO.id})
    controller = ScriptedController((view, view))
    motor = engine(capabilities=FakeCapabilities(), controller=controller, llm=llm)

    events = await coletar(motor.run(agentic(models=models(vision=COM_VISAO)), request(messages=historico())))

    assert len(controller.calls) == 2
    assert any(issue.kind == "RepeatedAction" and issue.severity == "notice" for issue in events[-1].errors)
    assert imagens_na_ultima(enviadas(llm)) == [url(OUTRO)]


async def test_id_fora_das_candidatas_e_acao_invalida() -> None:
    controller = ScriptedController((json.dumps({"action": "view_image", "id": "img-000000000000"}), ANSWER))
    motor = engine(capabilities=FakeCapabilities(), controller=controller)
    events = await coletar(motor.run(agentic(models=models(vision=COM_VISAO)), request(messages=historico())))
    assert any(issue.kind == "InvalidAction" for issue in events[-1].errors)


async def test_sem_vision_na_geracao_nao_ha_candidata() -> None:
    llm = provider()
    controller = ScriptedController((ANSWER,))
    motor = engine(capabilities=FakeCapabilities(), controller=controller, llm=llm)
    await coletar(motor.run(agentic(), request(messages=historico())))
    schema = controller.calls[0]["response_format"]["json_schema"]["schema"]
    assert all(branch["properties"]["action"].get("const") != "view_image" for branch in schema["anyOf"])
    assert GRAFICO.id not in controller.calls[0]["messages"][0]["content"]
    assert imagens_na_ultima(enviadas(llm)) == []


async def test_catalogo_vazio_com_candidata_ainda_chama_o_controller() -> None:
    controller = ScriptedController((json.dumps({"action": "view_image", "id": GRAFICO.id}), ANSWER))
    llm = provider()
    motor = engine(capabilities=FakeCapabilities(FakeSession(())), controller=controller, llm=llm)
    await coletar(motor.run(agentic(models=models(vision=COM_VISAO)), request(messages=historico())))
    assert len(controller.calls) == 2
    assert imagens_na_ultima(enviadas(llm)) == [url(GRAFICO)]


# --- etapa `image_gate` no `chat` (item 8) -------------------------------------------------------------------------


async def test_chat_com_controller_decide_na_etapa_image_gate() -> None:
    trace = RecordingTraceSink()
    llm = provider()
    controller = ScriptedController((json.dumps({"view": [OUTRO.id]}),))
    motor = engine(controller=controller, llm=llm, trace=trace)

    events = await coletar(motor.run(Grant(models=models(vision=COM_VISAO)), request(messages=historico())))

    stages = [e.stage for e in events if isinstance(e, ProgressEvent)]
    assert stages == ["prepare_context", "image_gate", "generate", "validate_answer"]
    call = controller.calls[0]
    assert call["response_format"]["json_schema"]["schema"]["properties"]["view"]["items"]["enum"] == [
        GRAFICO.id,
        OUTRO.id,
    ]
    assert all(isinstance(m["content"], str | None) for m in call["messages"])
    assert imagens_na_ultima(enviadas(llm)) == [url(OUTRO)]
    [gate] = [e.outcome for e in events if isinstance(e, StepFinished) and e.stage == "image_gate"]
    assert gate == ImageGateOutcome(model="ctrl/controlador", candidates=2, viewed=(OUTRO.id,))
    [decision] = trace.of_type(ControllerDecision)
    assert (decision.iteration, decision.action, decision.images) == (1, "view_image", (OUTRO.id,))


async def test_chat_image_gate_que_nao_escolhe_nenhuma() -> None:
    llm = provider()
    motor = engine(controller=ScriptedController((json.dumps({"view": []}),)), llm=llm)
    events = await coletar(motor.run(Grant(models=models(vision=COM_VISAO)), request(messages=historico())))
    assert imagens_na_ultima(enviadas(llm)) == []
    assert all(issue.severity == "notice" for issue in events[-1].errors)


@pytest.mark.parametrize(
    ("line", "kind"),
    [
        (controller_down(), "ModelCallFailed"),
        ('{"view": ["img-falsa"]}', "ImageGateInvalid"),
        ("nada", "ImageGateInvalid"),
    ],
)
async def test_falha_da_image_gate_segue_sem_imagem_com_aviso(line: Any, kind: str) -> None:
    llm = provider()
    motor = engine(controller=ScriptedController((line,)), llm=llm)
    events = await coletar(motor.run(Grant(models=models(vision=COM_VISAO)), request(messages=historico())))
    final = events[-1]
    assert final.answer and imagens_na_ultima(enviadas(llm)) == []
    [issue] = [issue for issue in final.errors if issue.stage == "image_gate"]
    assert (issue.kind, issue.severity) == (kind, "notice")
    [gate] = [e.outcome for e in events if isinstance(e, StepFinished) and e.stage == "image_gate"]
    assert isinstance(gate, ImageGateOutcome) and gate.failed


async def test_chat_sem_controller_manda_todas_as_candidatas() -> None:
    llm = provider()
    motor = engine(llm=llm)
    grant = Grant(models=models(controller=False, vision=COM_VISAO))
    events = await coletar(motor.run(grant, request(messages=historico())))
    assert "image_gate" not in [e.stage for e in events if isinstance(e, ProgressEvent)]
    assert imagens_na_ultima(enviadas(llm)) == [url(GRAFICO), url(OUTRO)]


async def test_chat_sem_imagem_nao_resolve_nem_chama_o_controller() -> None:
    controller = ScriptedController(())
    motor = engine(controller=controller)
    events = await coletar(motor.run(Grant(models=models(vision=COM_VISAO)), request()))
    assert [e.stage for e in events if isinstance(e, ProgressEvent)] == [
        "prepare_context",
        "generate",
        "validate_answer",
    ]
    assert controller.calls == []


async def test_imagem_do_usuario_e_candidatas_juntas() -> None:
    llm = provider()
    motor = engine(controller=ScriptedController((json.dumps({"view": [GRAFICO.id]}),)), llm=llm)
    grant = Grant(models=models(vision=COM_VISAO))
    await coletar(motor.run(grant, request(messages=historico(pergunta="compare", fotos=(FOTO,)))))
    assert imagens_na_ultima(enviadas(llm)) == [url(FOTO), url(GRAFICO)]


# --- `rag_first` (item 8) ------------------------------------------------------------------------------------------


def _chunk() -> Chunk:
    return Chunk(chunk_id="c1", text="trecho", score=0.9, document="doc")


async def test_rag_first_coberto_com_controller_passa_pela_image_gate_depois_do_portao() -> None:
    generation = provider()
    controller = ScriptedController((json.dumps({"view": [GRAFICO.id]}),))
    motor = engine(capabilities=FakeCapabilities(docs_session((_chunk(),))), controller=controller, llm=generation)

    events = await coletar(motor.run(rag(models=models(vision=COM_VISAO)), request(messages=historico())))

    stages = [e.stage for e in events if isinstance(e, ProgressEvent)]
    assert stages.index("gate") < stages.index("image_gate") < stages.index("generate")
    assert imagens_na_ultima(enviadas(generation)) == [url(GRAFICO)]


async def test_rag_first_sem_controller_manda_as_candidatas() -> None:
    generation = provider()
    motor = engine(capabilities=FakeCapabilities(docs_session((_chunk(),))), llm=generation)
    grant = rag(models=models(controller=False, vision=COM_VISAO))
    events = await coletar(motor.run(grant, request(messages=historico())))
    assert "image_gate" not in [e.stage for e in events if isinstance(e, ProgressEvent)]
    assert imagens_na_ultima(enviadas(generation)) == [url(GRAFICO), url(OUTRO)]
