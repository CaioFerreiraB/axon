"""T035 — mensagens do controller e da geração (`domain/transcript.py`, R19): formato nativo de tool e cerca."""

from __future__ import annotations

import json

import pytest
from graph_testkit import MESSAGES, catalog_tool, fenced

from axon_ai.capabilities.api import FENCE_INSTRUCTION, FencedToolResult, ToolCall
from axon_ai.graph.domain.actions import CONTROLLER_INSTRUCTION, catalog_text
from axon_ai.graph.domain.transcript import (
    InvalidStep,
    ToolStep,
    controller_messages,
    generation_messages,
)

pytestmark = pytest.mark.us2

PROMPTS = ("Responda em português.", "Seja breve.")


def tool_step(iteration: int, content: str = "4", name: str = "generic.calculate") -> ToolStep:
    return ToolStep(
        iteration=iteration,
        call=ToolCall(name=name, arguments={"expression": "2+2"}),
        result=FencedToolResult(name=name, kind="native", status="ok", text=fenced(name, content)),
    )


def test_controller_sem_passos() -> None:
    tools = [catalog_tool()]
    messages = controller_messages(tools, MESSAGES, ())
    system = messages[0]
    assert system["role"] == "system"
    assert system["content"] == f"{CONTROLLER_INSTRUCTION}\n\n{catalog_text(tools)}\n\n{FENCE_INSTRUCTION}"
    assert messages[1:] == [{"role": m["role"], "content": m["content"]} for m in MESSAGES]


def test_controller_nao_recebe_prompts_de_pack() -> None:
    texto = json.dumps(controller_messages([catalog_tool()], MESSAGES, ()), ensure_ascii=False)
    assert PROMPTS[0] not in texto


def test_transcricao_de_tool_no_formato_nativo() -> None:
    step = tool_step(1)
    messages = controller_messages([catalog_tool()], MESSAGES, (step,))
    call, result = messages[-2], messages[-1]
    assert call == {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "call-1", "name": "generic.calculate", "arguments": '{"expression": "2+2"}'}],
    }
    assert result == {"role": "tool", "content": step.result.text, "tool_call_id": "call-1"}


def test_acao_invalida_vira_aviso_do_motor_sem_a_saida_do_modelo() -> None:
    messages = controller_messages([catalog_tool()], MESSAGES, (InvalidStep(iteration=1, reason="JSON malformado"),))
    assert messages[-1] == {
        "role": "user",
        "content": "A ação anterior era inválida: JSON malformado. Responda com uma ação válida.",
    }


def test_passos_entram_na_ordem() -> None:
    steps = (tool_step(1, "a"), InvalidStep(iteration=2, reason="JSON malformado"), tool_step(3, "b"))
    roles = [m["role"] for m in controller_messages([catalog_tool()], MESSAGES, steps)[len(MESSAGES) + 1 :]]
    assert roles == ["assistant", "tool", "user", "assistant", "tool"]


def test_geracao_sem_passos_e_exatamente_a_do_chat() -> None:
    assert generation_messages(PROMPTS, MESSAGES, ()) == [
        {"role": "system", "content": PROMPTS[0]},
        {"role": "system", "content": PROMPTS[1]},
        *({"role": m["role"], "content": m["content"]} for m in MESSAGES),
    ]


def test_geracao_com_resultado_recebe_a_cerca_depois_dos_prompts_e_a_transcricao_no_fim() -> None:
    step = tool_step(1)
    messages = generation_messages(PROMPTS, MESSAGES, (step,))
    assert messages[2] == {"role": "system", "content": FENCE_INSTRUCTION}
    assert messages[3 : 3 + len(MESSAGES)] == [{"role": m["role"], "content": m["content"]} for m in MESSAGES]
    assert messages[-1] == {"role": "tool", "content": step.result.text, "tool_call_id": "call-1"}


def test_geracao_nao_recebe_os_avisos_de_acao_invalida() -> None:
    steps = (InvalidStep(iteration=1, reason="JSON malformado"), tool_step(2))
    messages = generation_messages(PROMPTS, MESSAGES, steps)
    assert not any("inválida" in (m["content"] or "") for m in messages)


def test_geracao_so_com_acoes_invalidas_nao_recebe_a_cerca() -> None:
    messages = generation_messages(PROMPTS, MESSAGES, (InvalidStep(iteration=1, reason="JSON malformado"),))
    assert {"role": "system", "content": FENCE_INSTRUCTION} not in messages


# --- Fase 5: o passo que o portão grava (T068; research R41, R43) ----------------------------------------------------


@pytest.mark.us3
def test_passo_sintetico_entra_na_geracao_como_um_passo_executado() -> None:
    executado = tool_step(1, name="docs.search")
    sintetico = ToolStep(iteration=1, call=executado.call, result=executado.result, synthetic=True)
    assert not executado.synthetic and sintetico.synthetic
    assert generation_messages(PROMPTS, MESSAGES, (sintetico,)) == generation_messages(PROMPTS, MESSAGES, (executado,))
    assert generation_messages(PROMPTS, MESSAGES, (sintetico,))[len(PROMPTS)]["content"] == FENCE_INSTRUCTION
