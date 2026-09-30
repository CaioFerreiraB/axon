"""T012 / T046 — conformidade do `GrantResolver` (contracts/assistants-api.md): o grant tem exatamente o declarado."""

from __future__ import annotations

import pytest
from assistants_testkit import ANA, BIA, CAIO_KEY, MutableClock, assistant, assistants_service, config, private

from ai_core.assistants.adapters.memory import InMemoryCollectionCatalog, InMemoryMcpDirectory
from ai_core.assistants.api import (
    DEFAULT_RPM,
    AssistantNotFound,
    AssistantUnavailable,
    ExecutionGrant,
    Limits,
    RateLimited,
    RequestRejected,
)
from ai_core.llm.api import ModelPolicy, ModelRef
from ai_core.packs.api import Composition

# --- US1: Assistants de sistema --------------------------------------------------------------------------------------


async def test_us1_dois_assistants_resolvem_para_grants_diferentes_e_completos() -> None:
    """Independent Test da US1: um público só com pack, outro privado com pack + MCP."""
    service = assistants_service(
        config(
            {
                "publico": assistant(),
                "privado": private(allow=["user:caio"], mcp=["finance"], flow="agentic", packs=["rag", "generic"]),
            }
        ),
        mcp=InMemoryMcpDirectory(global_aliases={"finance"}),
    )

    publico = await service.resolve(model="publico", principal=ANA)
    privado = await service.resolve(model="privado", principal=CAIO_KEY)

    assert publico.mcp_aliases == frozenset() and publico.packs == ("generic",) and publico.flow == "chat"
    assert privado.mcp_aliases == frozenset({"finance"})
    assert privado.packs == ("rag", "generic") and privado.flow == "agentic"
    assert privado.principal == CAIO_KEY and privado.assistant == "privado"


async def test_us1_mcp_vazio_nao_deixa_nenhum_alias_entrar() -> None:
    service = assistants_service(
        config({"geral": assistant(mcp=[])}),
        mcp=InMemoryMcpDirectory(global_aliases={"finance", "drive"}),
    )
    grant = await service.resolve(model="geral", principal=ANA)
    assert grant.mcp_aliases == frozenset()


async def test_us1_composicao_mantem_a_ordem_declarada() -> None:
    service = assistants_service(config({"comp": assistant(packs=["rag", "generic"], flow="chat")}))
    grant = await service.resolve(model="comp", principal=ANA)
    assert grant.composition == Composition(packs=("rag", "generic"))


@pytest.mark.parametrize(("pack", "flow"), [("rag", "agentic"), ("generic", "chat")])
async def test_us1_um_pack_sem_flow_herda_o_preferido_ou_chat(pack: str, flow: str) -> None:
    service = assistants_service(config({"x": assistant(packs=[pack])}))
    assert (await service.resolve(model="x", principal=ANA)).flow == flow


async def test_us1_composicao_sem_flow_fica_indisponivel() -> None:
    service = assistants_service(config({"comp": assistant(packs=["rag", "generic"])}))
    with pytest.raises(AssistantUnavailable) as caught:
        await service.resolve(model="comp", principal=ANA)
    assert any("flow" in reason for reason in caught.value.reasons)


async def test_us1_pack_em_erro_deixa_so_aquele_assistant_indisponivel() -> None:
    service = assistants_service(config({"fin": assistant(packs=["financeiro"]), "geral": assistant()}))

    with pytest.raises(AssistantUnavailable) as caught:
        await service.resolve(model="fin", principal=ANA)
    assert any("financeiro" in reason for reason in caught.value.reasons)
    assert (await service.resolve(model="geral", principal=ANA)).packs == ("generic",)


async def test_us1_mcp_ou_colecao_fora_do_catalogo_deixa_indisponivel() -> None:
    """Clarificação 3: com os catálogos vazios da fase, referência nunca é ignorada."""
    service = assistants_service(config({"m": assistant(mcp=["finance"]), "c": assistant(collections=["docs"])}))
    for name, field in (("m", "mcp"), ("c", "collections")):
        with pytest.raises(AssistantUnavailable) as caught:
            await service.resolve(model=name, principal=ANA)
        assert any(reason.startswith(field) for reason in caught.value.reasons)


async def test_us1_colecao_existente_entra_no_grant() -> None:
    service = assistants_service(
        config({"c": assistant(collections=["docs"])}), collections=InMemoryCollectionCatalog({"docs", "outra"})
    )
    assert (await service.resolve(model="c", principal=ANA)).collections == frozenset({"docs"})


async def test_us1_grant_tem_o_que_o_motor_le() -> None:
    service = assistants_service(
        config(
            {
                "geral": assistant(
                    models={"generation": "ollama/qwen3:1.7b", "controller": "ollama/qwen3:8b", "allow": ["ollama/*"]},
                    limits={"rpm": 20, "max_iterations": 4},
                    allowed_tools=["calculate"],
                )
            }
        )
    )
    grant = await service.resolve(model="geral", principal=BIA)

    assert isinstance(grant, ExecutionGrant)
    assert isinstance(grant.assistant, str) and isinstance(grant.flow, str)
    assert isinstance(grant.composition, Composition)
    assert grant.models == ModelPolicy(
        roles={
            "generation": ModelRef(provider="ollama", model="qwen3:1.7b"),
            "controller": ModelRef(provider="ollama", model="qwen3:8b"),
        },
        allow=("ollama/*",),
    )
    assert grant.limits == Limits(rpm=20, max_iterations=4)
    assert grant.allowed_tools == frozenset({"calculate"})
    assert grant.write_tools == frozenset()


async def test_us1_assistant_desconhecido_nao_existe() -> None:
    service = assistants_service(config({"geral": assistant()}))
    with pytest.raises(AssistantNotFound, match="assistant 'outro' não existe ou não é visível"):
        await service.resolve(model="outro", principal=ANA)


async def test_us1_assistant_com_problema_de_carga_fica_indisponivel() -> None:
    service = assistants_service(config({"x": assistant(mpc=["finance"])}))
    with pytest.raises(AssistantUnavailable) as caught:
        await service.resolve(model="x", principal=ANA)
    assert any("mpc" in reason for reason in caught.value.reasons)


# --- US7: orçamento por (Principal, Assistant) -----------------------------------------------------------------------


async def test_rate_a_21a_resolucao_do_par_e_recusada_e_outro_principal_nao_e_afetado(clock: MutableClock) -> None:
    """US7 cen. 1, com relógio fixo."""
    service = assistants_service(config({"geral": assistant(limits={"rpm": 20})}), clock=clock)
    for _ in range(20):
        await service.resolve(model="geral", principal=ANA)
    clock.advance(15)
    with pytest.raises(RateLimited) as caught:
        await service.resolve(model="geral", principal=ANA)
    assert caught.value.retry_after == 45.0
    assert (await service.resolve(model="geral", principal=BIA)).assistant == "geral"

    clock.advance(45)
    assert (await service.resolve(model="geral", principal=ANA)).assistant == "geral"


async def test_rate_pedido_recusado_antes_nao_consome_cota(clock: MutableClock) -> None:
    service = assistants_service(
        config(
            {
                "geral": assistant(limits={"rpm": 1}),
                "privado": private(limits={"rpm": 1}),
                "quebrado": assistant(packs=["financeiro"], limits={"rpm": 1}),
            }
        ),
        clock=clock,
    )
    for _ in range(3):
        with pytest.raises(RequestRejected):
            await service.resolve(model="geral/openai/gpt-x", principal=ANA)
        with pytest.raises(AssistantNotFound):
            await service.resolve(model="privado", principal=ANA)
        with pytest.raises(AssistantUnavailable):
            await service.resolve(model="quebrado", principal=ANA)
    assert (await service.resolve(model="geral", principal=ANA)).assistant == "geral"
    with pytest.raises(RateLimited):
        await service.resolve(model="geral", principal=ANA)


async def test_rate_sem_rpm_declarado_vale_o_default(clock: MutableClock) -> None:
    service = assistants_service(config({"geral": assistant()}), clock=clock)
    for _ in range(DEFAULT_RPM):
        await service.resolve(model="geral", principal=ANA)
    with pytest.raises(RateLimited):
        await service.resolve(model="geral", principal=ANA)


async def test_rate_limites_de_iteracao_e_contexto_viajam_no_grant() -> None:
    service = assistants_service(
        config({"geral": assistant(limits={"rpm": 5, "max_iterations": 3, "max_context_tokens": 4000})})
    )
    grant = await service.resolve(model="geral", principal=ANA)
    assert grant.limits == Limits(rpm=5, max_iterations=3, max_context_tokens=4000)
