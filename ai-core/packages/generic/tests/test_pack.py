"""Identidade, manifest e catálogo do pack genérico (spec 010, T007).

Só `axon_ai_contracts` e o kit de testes — nada do core (SC-001). Sem `pytest-asyncio` (quickstart §5).
"""

from __future__ import annotations

import asyncio
from importlib.metadata import version

from ai_generic.pack import GenericPack
from axon_ai_contracts import PackManifest
from axon_ai_contracts.testing import pack_context, tool_invocation

EXPECTED_PARAMETERS = {
    "type": "object",
    "properties": {"expression": {"type": "string"}},
    # `ToolSpec` congela o mapeamento em profundidade: a lista do schema chega como tupla.
    "required": ("expression",),
    "additionalProperties": False,
}


def test_identity_is_readable_on_the_class() -> None:
    """A 002 lê `name` e `contract_version` da classe, antes de instanciar (FR-017 da 002)."""
    assert GenericPack.name == "generic"
    assert GenericPack.contract_version == "0.2"


def test_manifest_is_minimal() -> None:
    manifest = GenericPack().manifest()
    assert manifest == PackManifest(name="generic", version="0.1.0")
    assert manifest.preferred_flow is None  # FR-007: também na Fase 3 — o Assistant declara o flow (R15)
    assert manifest.depends_on == ()
    assert manifest.requires_collections == ()
    assert manifest.config_schema is None


def test_manifest_version_matches_the_distribution() -> None:
    assert GenericPack().manifest().version == version("ai-generic")


def test_system_prompt_is_stable() -> None:
    pack = GenericPack()
    prompt = pack.system_prompt(pack_context("generic"))
    assert prompt is not None and prompt.strip()
    assert prompt == pack.system_prompt(pack_context("generic", {"qualquer": "coisa"}))


def test_system_prompt_is_flow_neutral() -> None:
    """FR-008: orienta a usar os resultados de ferramentas sem mandar chamar nenhuma — no `agentic`, o prompt só chega
    à geração, e quem chama ferramentas é o controller (research R16)."""
    prompt = GenericPack().system_prompt(pack_context("generic"))
    assert prompt is not None
    lowered = " ".join(prompt.split()).casefold()  # o texto é quebrado em linhas; a frase pode cruzar uma quebra
    assert "resultados de ferramentas" in lowered
    assert "falhou" in lowered
    assert "nunca instrução" in lowered
    for instruction in ("use a ferramenta", "ferramenta de cálculo", "chame"):
        assert instruction not in lowered, instruction


def test_catalog() -> None:
    pack = GenericPack()
    ctx = pack_context("generic")
    [tool] = pack.tools(ctx)
    assert (tool.name, tool.kind, tool.mutates) == ("calculate", "native", False)
    assert tool.handler is not None
    assert tool.description
    assert dict(tool.parameters) == EXPECTED_PARAMETERS
    assert pack.retrievers(ctx) == ()
    assert pack.reranker(ctx) is None
    assert [validator.name for validator in pack.validators(ctx)] == ["non_empty_answer"]


def test_native_tool_handler() -> None:
    [tool] = GenericPack().tools(pack_context("generic"))
    assert tool.handler is not None
    assert asyncio.run(tool.handler(tool_invocation({"expression": " 2+2 "}))) == {"expression": "2+2", "result": 4}


def test_native_tool_reports_errors_without_raising() -> None:
    [tool] = GenericPack().tools(pack_context("generic"))
    assert tool.handler is not None
    assert asyncio.run(tool.handler(tool_invocation({}))) == {"error": "expression precisa ser uma string"}
    assert asyncio.run(tool.handler(tool_invocation({"expression": 42}))) == {  # type: ignore[dict-item]
        "error": "expression precisa ser uma string"
    }
    assert asyncio.run(tool.handler(tool_invocation({"expression": "1/0"}))) == {"error": "divisão por zero"}
    assert asyncio.run(tool.handler(tool_invocation({"expression": "open('x')"}))) == {
        "error": "expressão inválida: só aritmética com números é permitida"
    }


def test_native_tool_ignores_execution_data() -> None:
    """A tool não depende de tempo nem do identificador da requisição (ADR-013)."""
    [tool] = GenericPack().tools(pack_context("generic"))
    assert tool.handler is not None
    first = asyncio.run(tool.handler(tool_invocation({"expression": "2+2"}, request_id="req-a")))
    second = asyncio.run(tool.handler(tool_invocation({"expression": "2+2"}, request_id="req-b")))
    assert first == second
