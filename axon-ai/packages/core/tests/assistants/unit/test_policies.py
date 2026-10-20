"""T038 — políticas de Assistants de usuário (FR-014): primeira que casa e conformidade do rascunho."""

from __future__ import annotations

from typing import Any

import pytest
from assistants_testkit import ANA, BIA, POLICIES, config, draft, policy

from axon_ai.assistants.api import Limits, PolicyViolation, Principal
from axon_ai.assistants.domain.definitions import UserAssistantPolicy, read_config
from axon_ai.assistants.domain.policies import applicable_policy, conform


def _policies(*raw: dict[str, Any]) -> tuple[UserAssistantPolicy, ...]:
    return read_config(config(policies=list(raw)), origin="teste").policies


PADRAO = _policies(*POLICIES)
PREFERIDO = {"generic": None, "rag": "agentic"}


def _conform(d: Any, principal: Principal = ANA, *, mcp: frozenset[str] = frozenset(), **kwargs: Any) -> Any:
    chosen = applicable_policy(PADRAO, principal)
    assert chosen is not None
    return conform(
        d,
        chosen,
        owner=principal.subject,
        mcp_aliases=mcp,
        preferred=PREFERIDO.get,
        **kwargs,
    )


def test_vale_a_primeira_politica_que_casa_na_ordem_declarada() -> None:
    assert applicable_policy(PADRAO, BIA) is PADRAO[0]
    assert applicable_policy(PADRAO, ANA) is PADRAO[1]
    invertidas = _policies(policy(match="*"), policy(match="group:chefia"))
    assert applicable_policy(invertidas, BIA) is invertidas[0]


def test_sem_politica_aplicavel_nao_ha_politica() -> None:
    so_chefia = _policies(policy(match="group:chefia"))
    assert applicable_policy(so_chefia, ANA) is None
    assert applicable_policy((), BIA) is None


def test_rascunho_dentro_da_politica_vira_definicao_privada_do_dono() -> None:
    definition = _conform(draft())
    assert definition.name == "~meu-rag" and definition.origin == "user" and definition.owner == "user:ana"
    assert definition.visibility == "private"
    assert definition.access.schemes == frozenset({"oidc", "api_key"}) and definition.access.allow == ("user:ana",)
    assert definition.allow == ("ollama/*",)
    assert definition.problems == ()


def test_limite_ausente_assume_o_teto() -> None:
    assert _conform(draft()).limits == Limits(rpm=10, max_iterations=3, max_context_tokens=4000)
    assert _conform(draft(limits={"rpm": 5})).limits == Limits(rpm=5, max_iterations=3, max_context_tokens=4000)


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"packs": ("rag",)}, "packs"),
        ({"flow": "agentic"}, "flow"),
        ({"packs": ("generic", "generic2")}, "packs"),
        ({"collections": ("docs",)}, "collections"),
        ({"models": {"generation": "openai/gpt-4o"}}, "models.generation"),
        ({"models": {"generation": "ollama/a", "controller": "openai/gpt-4o"}}, "models.controller"),
        ({"limits": {"rpm": 50}}, "limits.rpm"),
        ({"limits": {"max_iterations": 9}}, "limits.max_iterations"),
        ({"limits": {"max_context_tokens": 5000}}, "limits.max_context_tokens"),
        ({"write_tools": ("apagar",)}, "write_tools"),
        ({"mcp": ("agenda",)}, "mcp"),
    ],
)
def test_rascunho_fora_da_politica_e_recusado_nomeando_o_campo(overrides: dict[str, Any], field: str) -> None:
    with pytest.raises(PolicyViolation) as caught:
        _conform(draft(**overrides))
    assert caught.value.field == field


def test_flow_derivado_do_pack_tambem_precisa_estar_na_politica() -> None:
    """`rag` prefere `agentic`: sob a política de `chefia` passa, e o flow derivado é conferido."""
    assert _conform(draft(packs=("rag",)), BIA).problems == ()
    restrita = _policies(policy(match="*", packs=["rag"], flows=["chat"]))[0]
    with pytest.raises(PolicyViolation) as caught:
        conform(draft(packs=("rag",)), restrita, owner="user:ana", mcp_aliases=frozenset(), preferred=PREFERIDO.get)
    assert caught.value.field == "flow"


def test_composicao_sem_flow_e_recusada() -> None:
    with pytest.raises(PolicyViolation) as caught:
        _conform(draft(packs=("generic", "rag")), BIA)
    assert caught.value.field == "flow"


def test_mcp_alheio_e_inexistente_tem_a_mesma_mensagem() -> None:
    mensagens = []
    for alias in ("agenda-do-caio", "nao-existe"):
        with pytest.raises(PolicyViolation) as caught:
            _conform(draft(mcp=(alias,)), mcp=frozenset({"minha-agenda"}))
        mensagens.append(str(caught.value).replace(alias, "X"))
    assert mensagens[0] == mensagens[1]


def test_mcp_proprio_e_colecao_da_politica_passam() -> None:
    definition = _conform(draft(mcp=("minha-agenda",), collections=("docs",)), BIA, mcp=frozenset({"minha-agenda"}))
    assert definition.mcp == ("minha-agenda",) and definition.collections == ("docs",)


def test_escrita_permitida_pela_politica_de_chefia() -> None:
    assert _conform(draft(write_tools=("criar-evento",)), BIA).write_tools == ("criar-evento",)
