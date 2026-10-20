"""T056 — as três regras de referência da Fase 3 (research R19 a R21), com as mensagens do contrato."""

from __future__ import annotations

from typing import Any

import pytest

from axon_ai.assistants.domain.definitions import AssistantDefinition
from axon_ai.assistants.domain.validation import collision_reasons, role_reasons, tool_reasons
from axon_ai.llm.api import ModelRef

pytestmark = pytest.mark.us8

QWEN = ModelRef(provider="ollama", model="qwen3:1.7b")
FLOW_ROLES: dict[str, tuple[Any, ...]] = {"chat": ("generation",), "agentic": ("controller", "generation")}
PACK_TOOLS = {"generic": frozenset({"calculate", "buscar"})}


def definition(**overrides: Any) -> AssistantDefinition:
    fields: dict[str, Any] = {
        "name": "a",
        "origin": "system",
        "packs": ("generic",),
        "roles": {"generation": QWEN},
    }
    return AssistantDefinition(**(fields | overrides))


# --- papéis por flow (R19) ------------------------------------------------------------------------------------------


def test_agentic_sem_controller() -> None:
    assert role_reasons(definition(), flow="agentic", flow_roles=FLOW_ROLES) == (
        "models: o flow 'agentic' exige o papel 'controller', que o Assistant não declara",
    )


def test_agentic_com_controller() -> None:
    roles = {"generation": QWEN, "controller": QWEN}
    assert role_reasons(definition(roles=roles), flow="agentic", flow_roles=FLOW_ROLES) == ()


@pytest.mark.parametrize(("flow", "flow_roles"), [("rag_first", FLOW_ROLES), ("agentic", None), (None, FLOW_ROLES)])
def test_sem_exigencia_conhecida_nao_ha_motivo(flow: str | None, flow_roles: Any) -> None:
    assert role_reasons(definition(), flow=flow, flow_roles=flow_roles) == ()


# --- entradas de allowed_tools e write_tools (R20) ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entry", "reason"),
    [
        ("calculate", "'calculate' precisa de namespace: <pack>.<tool> ou <alias>.<tool>"),
        ("outro.x", "'outro.x': 'outro' não é pack nem MCP deste Assistant"),
        ("generic.nao_existe", "'generic.nao_existe': o pack 'generic' não oferece 'nao_existe'"),
        (" generic.calculate", "' generic.calculate': ' generic' não é pack nem MCP deste Assistant"),
        ("Generic.calculate", "'Generic.calculate': 'Generic' não é pack nem MCP deste Assistant"),
    ],
)
@pytest.mark.parametrize("field", ["allowed_tools", "write_tools"])
def test_entrada_morta(entry: str, reason: str, field: str) -> None:
    assert tool_reasons(definition(**{field: (entry,)}), pack_tools=PACK_TOOLS) == (f"{field}: {reason}",)


@pytest.mark.parametrize("entry", ["generic.calculate", "generic.buscar", "financeiro.qualquer", "demo.files.read"])
def test_entrada_que_pode_casar(entry: str) -> None:
    assistant = definition(mcp=("financeiro", "demo"), allowed_tools=(entry,), write_tools=(entry,))
    assert tool_reasons(assistant, pack_tools=PACK_TOOLS) == ()


def test_pack_sem_capacidades_nao_gera_motivo_de_tool() -> None:
    """O pack em erro já aparece no erro de composição; repetir a falha em cada tool só polui o relatório."""
    assistant = definition(packs=("quebrado",), allowed_tools=("quebrado.x",))
    assert tool_reasons(assistant, pack_tools={}) == ()


def test_sem_allowed_tools_nao_ha_motivo() -> None:
    assert tool_reasons(definition(allowed_tools=None), pack_tools=PACK_TOOLS) == ()


# --- colisão alias x pack (R21) -------------------------------------------------------------------------------------


def test_alias_igual_a_pack() -> None:
    assert collision_reasons(definition(mcp=("generic",))) == (
        "mcp: o alias 'generic' colide com o pack 'generic': as tools 'generic.<tool>' seriam ambíguas",
    )


def test_sem_colisao() -> None:
    assert collision_reasons(definition(mcp=("financeiro",))) == ()
