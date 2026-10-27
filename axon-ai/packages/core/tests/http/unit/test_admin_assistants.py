"""T084 — corpos e respostas dos Assistants de sistema na administração (contracts/admin-api.md; research R44, R45)."""

from __future__ import annotations

from typing import Any

import pytest

from axon_ai.assistants.api import AuthOverride, McpOverride, ModelsOverride
from axon_ai.http.domain.admin_assistants import (
    auth_body,
    auth_json,
    check_body,
    mcp_body,
    mcp_json,
    models_body,
    payload_json,
    version_param,
)
from axon_ai.http.domain.admin_common import AdminInvalid
from axon_ai.llm.api import ModelRef

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


# --- US11: seção `auth` (ADR-040; R58) -------------------------------------------------------------------------------


@pytest.mark.us11
def test_auth_body_le_esquemas_allow_e_versao() -> None:
    override, version = auth_body({"schemes": ["oidc", "api_key"], "allow": ["svc:a", "group:b"], "version": 2})
    assert override == AuthOverride(schemes=frozenset({"oidc", "api_key"}), allow=("svc:a", "group:b"))
    assert version == 2
    _, first = auth_body({"schemes": ["oidc"], "allow": ["*"], "version": None})
    assert first is None


@pytest.mark.us11
@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"schemes": ["oidc"], "allow": ["*"], "version": None, "visibility": "public"}, "visibility"),
        ({"schemes": "oidc", "allow": ["*"], "version": None}, "schemes"),
        ({"schemes": ["oidc"], "allow": [1], "version": None}, "allow"),
        ({"allow": ["*"], "version": None}, "schemes"),
    ],
)
def test_auth_body_recusa_forma_errada(body: dict[str, Any], field: str) -> None:
    assert _field(auth_body, body) == field


@pytest.mark.us11
def test_auth_json_ordena_esquemas_e_mantem_a_ordem_de_allow() -> None:
    override = AuthOverride(schemes=frozenset({"oidc", "api_key"}), allow=("svc:z", "group:a"))
    assert auth_json(override) == {"schemes": ["api_key", "oidc"], "allow": ["svc:z", "group:a"]}
    assert payload_json(override) == auth_json(override)


def test_models_com_vision_na_forma_do_yaml() -> None:
    """ADR-044, item 10: papel com `vision` vira `{model, vision}`; sem ele, continua o texto de antes."""
    from axon_ai.http.domain.admin_assistants import models_body, models_json
    from axon_ai.llm.api import ModelRef

    override, version = models_body(
        {
            "roles": {"generation": {"model": "openrouter/a/b", "vision": True}, "controller": "openrouter/a/c"},
            "version": 3,
        }
    )
    assert override.vision == {"generation"} and version == 3
    assert models_json(override.roles, override.vision) == {
        "controller": "openrouter/a/c",
        "generation": {"model": "openrouter/a/b", "vision": True},
    }
    assert models_json({"generation": ModelRef.parse("openrouter/a/b")}) == {"generation": "openrouter/a/b"}
    for ruim, campo in (
        ({"generation": {"model": "openrouter/a/b", "vision": "sim"}}, "roles.generation.vision"),
        ({"generation": {"model": "openrouter/a/b", "cor": 1}}, "roles.generation.cor"),
        ({"generation": {"vision": True}}, "roles.generation.model"),
    ):
        with pytest.raises(AdminInvalid) as caught:
            models_body({"roles": ruim})
        assert caught.value.field == campo
