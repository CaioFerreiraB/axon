"""T010 — interpretação do `assistants.yaml` (contracts/assistants-yaml.md): erro de arquivo para o boot, erro de um
Assistant fica só nele."""

from __future__ import annotations

from typing import Any

import pytest
import yaml
from assistants_testkit import assistant, config, policy, private

from axon_ai.assistants.api import DEFAULT_RPM, AssistantsConfigError, Limits
from axon_ai.assistants.domain.definitions import PHASE1_ALLOW_MESSAGE, read_config
from axon_ai.llm.api import ModelRef

EXEMPLO = """
assistants:
  geral:
    description: Assistente de uso geral
    visibility: public
    auth:
      schemes: [oidc, api_key]
      allow: ["*"]
    flow: chat
    packs: [generic]
    models:
      generation: ollama/qwen3:1.7b
      allow: ["ollama/*"]
    limits:
      rpm: 20
  interno:
    visibility: private
    auth:
      schemes: [api_key]
      allow: ["user:caio", "group:operadores"]
    flow: chat
    packs: [generic]
    mcp: []
    collections: []
    allowed_tools: [calculate]
    write_tools: []
    models:
      generation: ollama/qwen3:1.7b
      controller: ollama/qwen3:1.7b
      allow: ["ollama/*"]
    limits:
      rpm: 30
      max_iterations: 6
      max_context_tokens: 4000
user_assistants:
  policies:
    - match: group:operadores
      packs: [generic]
      flows: [chat]
      collections: []
      models:
        allow: ["ollama/*"]
      limits: { rpm: 30, max_iterations: 6, max_context_tokens: 8000 }
      write_tools: false
    - match: "*"
      packs: [generic]
      flows: [chat]
      models:
        allow: ["ollama/qwen3:1.7b"]
      limits: { rpm: 10, max_iterations: 3, max_context_tokens: 4000 }
api_keys:
  admin_group: operadores
"""


def _load(data: Any) -> Any:
    return read_config(data, origin="assistants.yaml")


def test_us1_exemplo_do_contrato_carrega_sem_problemas() -> None:
    cfg = _load(yaml.safe_load(EXEMPLO))

    geral, interno = cfg.assistants["geral"], cfg.assistants["interno"]
    assert geral.problems == () and interno.problems == ()
    assert geral.visibility == "public" and geral.access.allow == ("*",)
    assert geral.roles["generation"] == ModelRef(provider="ollama", model="qwen3:1.7b")
    assert geral.limits == Limits(rpm=20)
    assert interno.access.schemes == frozenset({"api_key"})
    assert interno.allowed_tools == ("calculate",)
    assert interno.limits == Limits(rpm=30, max_iterations=6, max_context_tokens=4000)
    assert set(interno.roles) == {"generation", "controller"}
    assert [p.match for p in cfg.policies] == ["group:operadores", "*"]
    assert cfg.policies[1].models_allow == ("ollama/qwen3:1.7b",)
    assert cfg.policies[0].limits == Limits(rpm=30, max_iterations=6, max_context_tokens=8000)
    assert cfg.admin_group == "operadores"


def test_us1_secoes_ausentes_sao_configuracao_valida() -> None:
    for data in (None, {}, {"assistants": None}):
        cfg = _load(data)
        assert dict(cfg.assistants) == {} and cfg.policies == () and cfg.admin_group is None


def test_us1_defaults_de_um_assistant() -> None:
    definition = _load(config({"geral": assistant()})).assistants["geral"]
    assert definition.problems == ()
    assert definition.limits == Limits(rpm=DEFAULT_RPM)
    assert definition.flow is None
    assert definition.mcp == () and definition.collections == () and definition.write_tools == ()
    assert definition.allowed_tools is None


def test_us1_grupo_de_administracao_aceita_o_prefixo_group() -> None:
    assert _load({"api_keys": {"admin_group": "group:operadores"}}).admin_group == "operadores"


@pytest.mark.parametrize(
    ("data", "path"),
    [
        (["assistants"], "raiz"),
        ({"assistentes": {}}, "assistentes"),
        ({"assistants": ["geral"]}, "assistants"),
        ({"user_assistants": {"politicas": []}}, "user_assistants.politicas"),
        ({"user_assistants": {"policies": {"match": "*"}}}, "user_assistants.policies"),
        (config(policies=[policy(match=None)]), "user_assistants.policies[0].match"),
        (config(policies=[policy(match="user:caio")]), "user_assistants.policies[0].match"),
        (config(policies=[policy(models={"allow": []})]), "user_assistants.policies[0].models.allow"),
        (config(policies=[policy(limits={"max_iterations": 3})]), "user_assistants.policies[0].limits.rpm"),
        (config(policies=[policy(), policy(extra=True)]), "user_assistants.policies[1].extra"),
        (config(policies=[policy(write_tools="sim")]), "user_assistants.policies[0].write_tools"),
        ({"api_keys": {"admin_group": ""}}, "api_keys.admin_group"),
        ({"api_keys": {"admins": "x"}}, "api_keys.admins"),
    ],
)
def test_us1_erro_de_arquivo_para_a_carga_nomeando_o_campo(data: Any, path: str) -> None:
    with pytest.raises(AssistantsConfigError) as caught:
        _load(data)
    assert path in str(caught.value)
    assert "assistants.yaml" in str(caught.value)


@pytest.mark.parametrize(
    ("name", "body", "field"),
    [
        ("~geral", assistant(), "reservado"),
        ("Geral", assistant(), "nome"),
        ("geral/x", assistant(), "nome"),
        ("x", private(allow=["*"]), "auth.allow"),
        ("x", assistant(write_tools=["apagar"]), "write_tools"),
        ("x", assistant(models={"generation": "ollama/qwen3:1.7b", "allow": []}), "models.allow"),
        ("x", assistant(models={"generation": "ollama/qwen3:1.7b"}), "models.allow"),
        ("x", assistant(models={"generation": "openai/gpt-x", "allow": ["ollama/*"]}), "models.generation"),
        ("x", assistant(models={"generation": "qwen3", "allow": ["ollama/*"]}), "models.generation"),
        ("x", assistant(models={"allow": ["ollama/*"]}), "models.generation"),
        ("x", assistant(models={"generation": "ollama/a", "juiz": "ollama/b", "allow": ["ollama/*"]}), "models.juiz"),
        ("x", assistant(packs=["generic", "rag"]), "flow"),
        ("x", assistant(visibility=None), "visibility"),
        ("x", assistant(visibility="interno"), "visibility"),
        ("x", assistant(auth=None), "auth"),
        ("x", assistant(auth={"schemes": ["saml"], "allow": ["*"]}), "auth.schemes"),
        ("x", assistant(auth={"schemes": [], "allow": ["*"]}), "auth.schemes"),
        ("x", assistant(auth={"schemes": ["oidc"], "allow": ["caio"]}), "auth.allow"),
        ("x", assistant(auth={"schemes": ["oidc"], "allow": []}), "auth.allow"),
        ("x", assistant(mpc=["finance"]), "mpc"),
        ("x", assistant(limits={"rpm": 0}), "limits.rpm"),
        ("x", assistant(limits={"rpm": 10, "max_tokens": 5}), "limits.max_tokens"),
        ("x", assistant(description="a" * 501), "description"),
        ("x", assistant(packs="generic"), "packs"),
        ("x", "texto", "mapeamento"),
    ],
)
def test_us1_erro_de_um_assistant_fica_so_nele(name: str, body: Any, field: str) -> None:
    cfg = _load(config({name: body, "saudavel": assistant()}))

    assert cfg.assistants["saudavel"].problems == ()
    problems = cfg.assistants[name].problems
    assert problems, f"{name}: esperava ao menos um problema"
    assert any(field in problem for problem in problems), problems


def test_us1_arquivo_da_fase_1_diz_o_que_mudar() -> None:
    fase1 = {"flow": "chat", "packs": ["generic"], "models": {"generation": "ollama/qwen3:1.7b"}, "allow": ["ollama/*"]}
    problems = _load({"assistants": {"geral": fase1}}).assistants["geral"].problems

    assert PHASE1_ALLOW_MESSAGE in problems
    assert PHASE1_ALLOW_MESSAGE == (
        "`allow` saiu da raiz do Assistant: a allowlist de modelos vive em `models.allow`, e quem pode usar o "
        "Assistant, em `auth.allow`"
    )
    assert any("visibility" in p for p in problems)
    assert any(p.startswith("auth") for p in problems)
    assert any("models.allow" in p for p in problems)


def test_us1_assistant_sem_corpo_e_indisponivel_nao_erro_de_arquivo() -> None:
    cfg = _load({"assistants": {"vazio": None}})
    assert cfg.assistants["vazio"].problems


# --- Fase 9 (T075): `overrides` ---------------------------------------------------------------------------------------


def test_overrides_lido_e_ausente_e_vazio() -> None:
    data = config({"livre": assistant(overrides=["models", "mcp"]), "fixo": assistant()})
    parsed = read_config(data, origin="assistants.yaml")
    assert parsed.assistants["livre"].overrides == frozenset({"models", "mcp"})
    assert parsed.assistants["fixo"].overrides == frozenset()
    assert parsed.assistants["livre"].problems == ()


def test_overrides_com_valor_desconhecido_e_problema_do_assistant() -> None:
    parsed = read_config(config({"x": assistant(overrides=["models", "allow"])}), origin="assistants.yaml")
    definition = parsed.assistants["x"]
    assert definition.overrides == frozenset({"models"})
    assert any(problem.startswith("overrides: valor desconhecido: allow") for problem in definition.problems)


@pytest.mark.us13
def test_overrides_aceita_auth_e_recusa_visibility() -> None:
    parsed = read_config(
        config({"x": assistant(overrides=["auth"]), "y": assistant(overrides=["auth", "visibility"])}),
        origin="assistants.yaml",
    )
    assert parsed.assistants["x"].overrides == frozenset({"auth"}) and not parsed.assistants["x"].problems
    y = parsed.assistants["y"]
    assert y.overrides == frozenset({"auth"})
    assert any(problem.startswith("overrides: valor desconhecido: visibility") for problem in y.problems)
