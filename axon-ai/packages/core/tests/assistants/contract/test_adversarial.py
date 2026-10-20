"""T030 / T034 — suíte adversarial da fronteira de isolamento (SC-001, SC-002, SC-005).

`not_found`: um Principal não autorizado não distingue Assistant privado existente de inexistente — mesmo erro, mesma
mensagem, mesmo caminho, tempo na mesma ordem de grandeza.
"""

from __future__ import annotations

import asyncio
import contextlib
import statistics
import time
from typing import Any

import pytest
from assistants_testkit import (
    ANA,
    BIA,
    CAIO_KEY,
    CAIO_OIDC,
    POLICIES,
    assistant,
    assistants_service,
    config,
    draft,
    private,
)
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from axon_ai.assistants.adapters.memory import InMemoryCollectionCatalog, InMemoryMcpDirectory
from axon_ai.assistants.api import (
    WIDENING_FIELDS,
    AssistantNotFound,
    AssistantUnavailable,
    RequestRejected,
)
from axon_ai.assistants.domain.definitions import allowed_model
from axon_ai.llm.api import ModelRef

# --- US3: 404, nunca 403 ---------------------------------------------------------------------------------------------

SERVICE_CONFIG = config(
    {
        "privado": private(allow=["user:caio"], schemes=["api_key"]),
        "privado-quebrado": private(allow=["user:caio"], schemes=["api_key"], packs=["financeiro"]),
        "chefia": private(allow=["group:chefia"], schemes=["oidc"]),
        "publico": assistant(),
    }
)


async def _error(service: Any, model: str, principal: Any) -> AssistantNotFound:
    with pytest.raises(AssistantNotFound) as caught:
        await service.resolve(model=model, principal=principal)
    return caught.value


async def test_not_found_privado_pedido_por_oidc() -> None:
    """US3 cen. 1."""
    service = assistants_service(SERVICE_CONFIG)
    await _error(service, "privado", CAIO_OIDC)


async def test_not_found_nao_se_aplica_ao_dono_pela_chave() -> None:
    """US3 cen. 2."""
    service = assistants_service(SERVICE_CONFIG)
    assert (await service.resolve(model="privado", principal=CAIO_KEY)).assistant == "privado"


async def test_not_found_nao_se_aplica_a_publico_com_estrela() -> None:
    """US3 cen. 3."""
    service = assistants_service(SERVICE_CONFIG)
    for principal in (ANA, BIA, CAIO_KEY, CAIO_OIDC):
        assert (await service.resolve(model="publico", principal=principal)).assistant == "publico"


async def test_not_found_grupo_permitido_resolve_e_os_demais_nao() -> None:
    service = assistants_service(SERVICE_CONFIG)
    assert (await service.resolve(model="chefia", principal=BIA)).assistant == "chefia"
    await _error(service, "chefia", ANA)


async def test_not_found_privado_e_inexistente_sao_indistinguiveis() -> None:
    service = assistants_service(SERVICE_CONFIG)
    privado = await _error(service, "privado", ANA)
    inexistente = await _error(service, "inexistente", ANA)

    assert type(privado) is type(inexistente)
    assert str(privado).replace("privado", "X") == str(inexistente).replace("inexistente", "X")
    assert privado.args[0].replace("privado", "X") == inexistente.args[0].replace("inexistente", "X")


async def test_not_found_privado_indisponivel_nao_se_revela() -> None:
    """ACL antes da disponibilidade: um privado quebrado responde como inexistente a quem não pode."""
    service = assistants_service(SERVICE_CONFIG)
    await _error(service, "privado-quebrado", ANA)


async def test_not_found_assistant_de_usuario_alheio_e_inexistente_sao_indistinguiveis() -> None:
    """FR-017: `~x` de outro usuário e `~x` inexistente são a mesma leitura vazia, com o mesmo erro."""
    service = assistants_service(config(policies=POLICIES))
    await service.create(BIA, draft("so-da-bia"))

    alheio = await _error(service, "~so-da-bia", ANA)
    inexistente = await _error(service, "~nunca-existiu", ANA)
    assert type(alheio) is type(inexistente)
    assert str(alheio).replace("~so-da-bia", "X") == str(inexistente).replace("~nunca-existiu", "X")
    assert (await service.resolve(model="~so-da-bia", principal=BIA)).assistant == "~so-da-bia"


async def test_not_found_tempo_na_mesma_ordem_de_grandeza() -> None:
    service = assistants_service(SERVICE_CONFIG)

    async def mediana(model: str) -> float:
        tempos = []
        for _ in range(200):
            inicio = time.perf_counter()
            with contextlib.suppress(AssistantNotFound):
                await service.resolve(model=model, principal=ANA)
            tempos.append(time.perf_counter() - inicio)
        return statistics.median(tempos)

    privado, inexistente = await mediana("privado"), await mediana("inexistente")
    assert max(privado, inexistente) / min(privado, inexistente) < 10


# --- US4: a requisição só restringe (SC-002, SC-005) -----------------------------------------------------------------


async def test_modelo_de_outro_provider_fora_da_allowlist_e_recusado() -> None:
    """US4 cen. 1: recusado na resolução, antes de qualquer chamada de modelo."""
    service = assistants_service(config({"geral": assistant()}))
    with pytest.raises(RequestRejected) as caught:
        await service.resolve(model="geral/openai/gpt-x", principal=ANA)
    assert caught.value.field == "model"
    assert "modelo não permitido" in str(caught.value)


async def test_outro_modelo_do_mesmo_provider_vai_para_geracao() -> None:
    """US4 cen. 3."""
    service = assistants_service(config({"geral": assistant()}))
    grant = await service.resolve(model="geral/ollama/qwen3:8b", principal=ANA)
    assert grant.models.roles["generation"] == ModelRef(provider="ollama", model="qwen3:8b")


def test_lista_de_campos_de_ampliacao() -> None:
    assert (
        frozenset(
            {
                "packs",
                "mcp",
                "mcp_servers",
                "collections",
                "provider",
                "flow",
                "limits",
                "allowed_tools",
                "write_tools",
                "tools",
                "functions",
                "tool_choice",
                "function_call",
            }
        )
        == WIDENING_FIELDS
    )


REFS = ["ollama/qwen3:1.7b", "ollama/qwen3:8b", "openai/gpt-4o", "openrouter/qwen/qwen3-8b"]
PATTERNS = ["ollama/*", "openai/gpt-*", "openrouter/*", "ollama/qwen3:1.7b"]


@st.composite
def assistants_e_pedidos(draw: st.DrawFn) -> tuple[dict[str, Any], str, Any]:
    visibility = draw(st.sampled_from(["public", "private"]))
    packs = draw(st.lists(st.sampled_from(["generic", "rag", "financeiro"]), unique=True, max_size=2))
    body: dict[str, Any] = {
        "visibility": visibility,
        "auth": {"schemes": ["oidc", "api_key"], "allow": ["*"] if visibility == "public" else ["user:ana"]},
        "packs": packs,
        "mcp": draw(st.lists(st.sampled_from(["finance", "drive", "fantasma"]), unique=True, max_size=3)),
        "collections": draw(st.lists(st.sampled_from(["docs", "normas", "sumida"]), unique=True, max_size=3)),
        "write_tools": draw(st.lists(st.sampled_from(["apagar", "enviar"]), unique=True, max_size=2)),
        "models": {
            "generation": draw(st.sampled_from(REFS)),
            "allow": draw(st.lists(st.sampled_from(PATTERNS), unique=True, min_size=1, max_size=3)),
        },
    }
    if draw(st.booleans()):
        body["models"]["controller"] = draw(st.sampled_from(REFS))
    if draw(st.booleans()):
        # Com namespace (003 Fase 3, R20): nome sem namespace deixaria o Assistant indisponível, e a propriedade não
        # chegaria ao grant.
        body["allowed_tools"] = draw(st.lists(st.sampled_from(["generic.calculate", "generic.buscar"]), unique=True))
    if draw(st.booleans()):
        body["flow"] = draw(st.sampled_from(["chat", "agentic", "inexistente"]))
    parte = draw(
        st.one_of(
            st.none(),
            st.sampled_from([*REFS, "qwen3:8b", "", "openai/", "x/y/z"]),
            st.text(min_size=0, max_size=12),
        )
    )
    model = "alvo" if parte is None else f"alvo/{parte}"
    principal = draw(st.sampled_from([ANA, BIA, CAIO_KEY]))
    return body, model, principal


@settings(max_examples=300, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(assistants_e_pedidos())
def test_nenhum_grant_excede_o_declarado(caso: tuple[dict[str, Any], str, Any]) -> None:
    """SC-002: para qualquer Assistant e qualquer pedido, o grant — quando sai — está contido no declarado."""
    body, model, principal = caso
    service = assistants_service(
        config({"alvo": body}),
        mcp=InMemoryMcpDirectory(global_aliases={"finance", "drive"}),
        collections=InMemoryCollectionCatalog({"docs", "normas"}),
    )
    try:
        grant = asyncio.run(service.resolve(model=model, principal=principal))
    except (AssistantNotFound, AssistantUnavailable, RequestRejected):
        return

    assert grant.mcp_aliases <= frozenset(body["mcp"])
    assert grant.collections <= frozenset(body["collections"])
    assert set(grant.packs) <= set(body["packs"]) and list(grant.packs) == body["packs"]
    assert grant.write_tools <= frozenset(body["write_tools"])
    if body["visibility"] == "public":
        assert grant.write_tools == frozenset()
    if grant.allowed_tools is not None:
        assert grant.allowed_tools <= frozenset(body.get("allowed_tools", []))
    declared_roles = {role for role in body["models"] if role != "allow"}
    assert set(grant.models.roles) == declared_roles
    assert grant.models.allow == tuple(body["models"]["allow"])
    assert allowed_model(grant.models.roles["generation"], grant.models.allow)
    if "controller" in declared_roles:
        assert grant.models.roles["controller"] == ModelRef.parse(body["models"]["controller"])
