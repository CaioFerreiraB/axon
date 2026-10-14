"""T084 — corpos e respostas dos Assistants de sistema na administração (contracts/admin-api.md; research R44, R45)."""

from __future__ import annotations

from typing import Any

import pytest

from ai_core.assistants.api import McpOverride, ModelsOverride
from ai_core.http.domain.admin_assistants import check_body, mcp_body, mcp_json, models_body, version_param
from ai_core.http.domain.admin_common import AdminInvalid
from ai_core.llm.api import ModelRef

pytestmark = pytest.mark.us9


def _field(call: Any, *args: Any) -> str:
    with pytest.raises(AdminInvalid) as caught:
        call(*args)
    return caught.value.field


def test_modelos_por_papel_com_versao() -> None:
    override, version = models_body({"roles": {"generation": "openrouter/openai/gpt-4.1-mini"}, "version": 3})
    assert override == ModelsOverride(roles={"generation": ModelRef.parse("openrouter/openai/gpt-4.1-mini")})
    assert version == 3
    _, first = models_body({"roles": {"generation": "ollama/qwen3:1.7b"}, "version": None})
    assert first is None


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"roles": {"generation": "ollama/qwen3:1.7b"}}, "version"),
        ({"roles": {}, "version": 1}, "roles"),
        ({"roles": {"juiz": "ollama/qwen3:1.7b"}, "version": 1}, "roles.juiz"),
        ({"roles": {"generation": "sem-barra"}, "version": 1}, "roles.generation"),
        ({"roles": {"generation": "openrouter/auto"}, "version": 1}, "roles.generation"),
        ({"roles": {"generation": "ollama/qwen3:1.7b"}, "version": "3"}, "version"),
        ({"roles": {"generation": "ollama/qwen3:1.7b"}, "version": 1, "allow": ["*"]}, "allow"),
    ],
)
def test_modelos_invalidos_nomeiam_o_campo(body: dict[str, Any], field: str) -> None:
    assert _field(models_body, body) == field


def test_mcp_com_listas_e_ida_e_volta() -> None:
    override, version = mcp_body({"aliases": ["arquivos"], "allowed": ["arquivos.listar"], "version": None})
    assert override == McpOverride(aliases=("arquivos",), allowed=frozenset({"arquivos.listar"}), write=frozenset())
    assert version is None
    assert mcp_json(override) == {"aliases": ["arquivos"], "allowed": ["arquivos.listar"], "write": []}
    assert _field(mcp_body, {"aliases": "arquivos", "version": 1}) == "aliases"
    assert _field(mcp_body, {"aliases": [], "tools": [], "version": 1}) == "tools"


def test_testar_modelo_e_versao_na_query() -> None:
    role, ref = check_body({"role": "generation", "model": "openrouter/openai/gpt-4.1-mini"})
    assert (role, str(ref)) == ("generation", "openrouter/openai/gpt-4.1-mini")
    assert _field(check_body, {"role": "generation"}) == "model"
    assert version_param("3") == 3
    assert _field(version_param, None) == "version" and _field(version_param, "-1") == "version"
