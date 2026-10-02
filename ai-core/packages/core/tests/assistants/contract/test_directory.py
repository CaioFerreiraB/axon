"""T036 / T040 — conformidade do `AssistantDirectory` (contracts/assistants-api.md): descoberta igual ao conjunto
resolvível, e gestão dos Assistants de usuário isolada por dono."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from assistants_testkit import (
    ANA,
    BIA,
    CAIO_KEY,
    POLICIES,
    PRINCIPALS,
    T0,
    MutableClock,
    assistant,
    assistants_service,
    config,
    draft,
    policy,
    private,
)

from ai_core.assistants.adapters.memory import InMemoryMcpDirectory
from ai_core.assistants.api import (
    AssistantNotFound,
    AssistantUnavailable,
    Conflict,
    NoApplicablePolicy,
    PolicyViolation,
    Principal,
    RequestRejected,
)
from ai_core.llm.api import ModelRef

# --- US5: descoberta filtrada ----------------------------------------------------------------------------------------

DESCOBERTA = config(
    {
        "publico": assistant(description="para todos"),
        "so-chave": assistant(auth={"schemes": ["api_key"], "allow": ["*"]}),
        "privado": private(allow=["user:caio"], schemes=["api_key"]),
        "chefia": private(allow=["group:chefia"], schemes=["oidc"]),
        "quebrado": assistant(packs=["financeiro"]),
    }
)


async def _names(service: Any, principal: Any) -> list[str]:
    return [summary.name for summary in await service.discover(principal)]


async def _resolvable(service: Any, principal: Any, names: list[str]) -> list[str]:
    result = []
    for name in names:
        try:
            await service.resolve(model=name, principal=principal)
        except (AssistantNotFound, AssistantUnavailable, RequestRejected):
            continue
        result.append(name)
    return sorted(result)


async def test_discover_publico_ve_so_os_publicos_do_seu_esquema() -> None:
    """US5 cen. 1."""
    assert await _names(assistants_service(DESCOBERTA), ANA) == ["publico"]


async def test_discover_privado_de_grupo_aparece_para_o_membro() -> None:
    """US5 cen. 2."""
    service = assistants_service(DESCOBERTA)
    assert await _names(service, BIA) == ["chefia", "publico"]
    assert await _names(service, CAIO_KEY) == ["privado", "publico", "so-chave"]


async def test_discover_e_exatamente_o_conjunto_resolvivel() -> None:
    service = assistants_service(DESCOBERTA)
    todos = sorted(DESCOBERTA["assistants"])
    for principal in PRINCIPALS:
        assert await _names(service, principal) == await _resolvable(service, principal, todos), principal


async def test_discover_nao_mostra_indisponivel() -> None:
    assert "quebrado" not in await _names(assistants_service(DESCOBERTA), CAIO_KEY)


async def test_discover_traz_modelo_de_geracao_e_allowlist() -> None:
    (resumo,) = await assistants_service(DESCOBERTA).discover(ANA)
    assert resumo.origin == "system" and resumo.description == "para todos"
    assert resumo.generation == ModelRef(provider="ollama", model="qwen3:1.7b")
    assert resumo.allow == ("ollama/*",)


# --- US6: Assistants de usuário ---------------------------------------------------------------------------------------


def _service(users: Any = None, **kwargs: Any) -> Any:
    return assistants_service(
        config({"geral": assistant()}, policies=POLICIES),
        users=users,
        mcp=InMemoryMcpDirectory(by_owner={"user:ana": {"agenda"}, "user:caio": {"agenda-do-caio"}}),
        **kwargs,
    )


async def test_criado_dentro_da_politica_resolve_so_para_o_dono_sem_restart(user_assistant_store: Any) -> None:
    """US6 cen. 1 e Independent Test: MCP próprio; outro usuário não o vê nem o resolve."""
    service = _service(users=user_assistant_store)
    criado = await service.create(ANA, draft(mcp=("agenda",)))

    assert criado.name == "~meu-rag" and criado.owner == "user:ana" and criado.status.available
    grant = await service.resolve(model="~meu-rag", principal=ANA)
    assert grant.assistant == "~meu-rag" and grant.mcp_aliases == frozenset({"agenda"})
    assert grant.models.allow == ("ollama/*",)
    with pytest.raises(AssistantNotFound):
        await service.resolve(model="~meu-rag", principal=BIA)
    assert "~meu-rag" not in await _names(service, BIA)


async def test_mesmo_nome_em_donos_diferentes_cada_um_resolve_o_seu(user_assistant_store: Any) -> None:
    """US6 cen. 4."""
    service = _service(users=user_assistant_store)
    await service.create(ANA, draft(description="da ana"))
    await service.create(BIA, draft(description="da bia", packs=("rag",)))

    assert (await service.get(ANA, "~meu-rag")).draft.description == "da ana"
    assert (await service.get(BIA, "meu-rag")).draft.description == "da bia"
    assert (await service.resolve(model="~meu-rag", principal=BIA)).packs == ("rag",)


async def test_mcp_de_outro_usuario_tem_a_mensagem_de_inexistente() -> None:
    """US6 cen. 2."""
    service = _service()
    mensagens = []
    for alias in ("agenda-do-caio", "nao-existe"):
        with pytest.raises(PolicyViolation) as caught:
            await service.create(ANA, draft(name=f"x{len(mensagens)}", mcp=(alias,)))
        assert caught.value.field == "mcp"
        mensagens.append(str(caught.value).replace(alias, "X"))
    assert mensagens[0] == mensagens[1]


@pytest.mark.parametrize(
    ("overrides", "field"),
    [({"models": {"generation": "openai/gpt-4o"}}, "models.generation"), ({"limits": {"rpm": 50}}, "limits.rpm")],
)
async def test_fora_da_politica_e_recusado_nomeando_o_campo(overrides: dict[str, Any], field: str) -> None:
    """US6 cen. 5."""
    with pytest.raises(PolicyViolation) as caught:
        await _service().create(ANA, draft(**overrides))
    assert caught.value.field == field


async def test_sem_politica_aplicavel_nao_cria() -> None:
    """US6 cen. 6."""
    service = assistants_service(config(policies=[policy(match="group:chefia")]))
    with pytest.raises(NoApplicablePolicy):
        await service.create(ANA, draft())


async def test_nome_repetido_do_mesmo_dono_e_conflito() -> None:
    service = _service()
    await service.create(ANA, draft())
    with pytest.raises(Conflict):
        await service.create(ANA, draft(description="outro"))


async def test_nome_alheio_ou_de_sistema_e_inexistente_na_gestao() -> None:
    service = _service()
    await service.create(ANA, draft())
    for principal, name in ((BIA, "~meu-rag"), (ANA, "~outro"), (ANA, "geral"), (ANA, "~Nome Invalido")):
        with pytest.raises(AssistantNotFound):
            await service.get(principal, name)
        with pytest.raises(AssistantNotFound):
            await service.update(principal, name, draft(name=name.removeprefix("~").lower().replace(" ", "-")))
        with pytest.raises(AssistantNotFound):
            await service.delete(principal, name)
    assert (await service.resolve(model="geral", principal=ANA)).assistant == "geral"


async def test_atualizacao_substitui_e_preserva_a_criacao(clock: MutableClock) -> None:
    service = _service(clock=clock)
    criado = await service.create(ANA, draft())
    clock.advance(60)
    atualizado = await service.update(ANA, "~meu-rag", draft(description="v2"))

    assert atualizado.draft.description == "v2"
    assert atualizado.created_at == criado.created_at and atualizado.updated_at == T0 + timedelta(seconds=60)
    with pytest.raises(RequestRejected) as caught:
        await service.update(ANA, "~meu-rag", draft(name="outro-nome"))
    assert caught.value.field == "name"


async def test_remocao_e_definitiva() -> None:
    service = _service()
    await service.create(ANA, draft())
    await service.delete(ANA, "~meu-rag")
    assert await service.mine(ANA) == []
    with pytest.raises(AssistantNotFound):
        await service.resolve(model="~meu-rag", principal=ANA)


async def test_dono_que_sai_do_grupo_ve_indisponivel_e_nao_resolve() -> None:
    """Edge case: nunca resolvido com permissões que a política atual não concede."""
    service = _service()
    await service.create(BIA, draft(models={"generation": "openai/gpt-4o"}))
    assert (await service.resolve(model="~meu-rag", principal=BIA)).models.roles["generation"].provider == "openai"

    fora_do_grupo = Principal(subject="user:bia", scheme="oidc")
    (meu,) = await service.mine(fora_do_grupo)
    assert not meu.status.available
    assert any("models.generation" in reason for reason in meu.status.reasons)
    with pytest.raises(AssistantUnavailable) as caught:
        await service.resolve(model="~meu-rag", principal=fora_do_grupo)
    assert any("models.generation" in reason for reason in caught.value.reasons)
    assert "~meu-rag" not in await _names(service, fora_do_grupo)


def _com_pack_em_erro(users: Any = None) -> Any:
    """Política que permite o pack `financeiro`, que está em erro: o Assistant é criado e fica indisponível."""
    return assistants_service(
        config({"geral": assistant()}, policies=[policy(packs=["generic", "financeiro"])]), users=users
    )


async def test_discover_inclui_os_proprios_disponiveis(user_assistant_store: Any) -> None:
    service = _com_pack_em_erro(users=user_assistant_store)
    await service.create(ANA, draft())
    await service.create(ANA, draft(name="quebrado", packs=("financeiro",)))

    nomes = await _names(service, ANA)
    assert nomes == ["geral", "~meu-rag"]
    (proprio,) = [s for s in await service.discover(ANA) if s.origin == "user"]
    assert proprio.allow == ("ollama/*",)


async def test_mine_mostra_indisponiveis_com_motivo() -> None:
    service = _com_pack_em_erro()
    await service.create(ANA, draft(name="quebrado", packs=("financeiro",)))
    (meu,) = await service.mine(ANA)
    assert not meu.status.available and any("financeiro" in r for r in meu.status.reasons)


async def test_servico_novo_sobre_o_mesmo_armazenamento_continua_resolvendo(user_assistant_store: Any) -> None:
    """US6 cen. 3: novo deploy não apaga Assistant de usuário — ele vive no armazenamento."""
    await _service(users=user_assistant_store).create(ANA, draft())
    novo = _service(users=user_assistant_store)
    assert (await novo.resolve(model="~meu-rag/qwen3:8b", principal=ANA)).models.roles["generation"] == ModelRef(
        provider="ollama", model="qwen3:8b"
    )


# --- Fase 3 (T060; research R22): as regras novas na criação e na atualização ----------------------------------------

FLOW_ROLES = {"chat": ("generation",), "agentic": ("controller", "generation")}
def _regras() -> Any:
    return assistants_service(
        config(policies=[policy(match="*", flows=["chat", "agentic"], write_tools=True)]),
        mcp=InMemoryMcpDirectory(by_owner={"user:ana": {"generic", "agenda"}}),
        flow_roles=FLOW_ROLES,
    )


VIOLACOES = [
    ({"flow": "agentic"}, "models"),
    ({"allowed_tools": ("calculate",)}, "allowed_tools"),
    ({"write_tools": ("outro.x",)}, "write_tools"),
    ({"mcp": ("generic",)}, "mcp"),
]


@pytest.mark.us6
@pytest.mark.parametrize(("overrides", "field"), VIOLACOES)
async def test_regra_da_fase_3_recusa_a_criacao_nomeando_o_campo(overrides: dict[str, Any], field: str) -> None:
    with pytest.raises(RequestRejected) as recusa:
        await _regras().create(ANA, draft(**overrides))
    assert recusa.value.field == field


@pytest.mark.us6
@pytest.mark.parametrize(("overrides", "field"), VIOLACOES)
async def test_regra_da_fase_3_recusa_a_atualizacao_nomeando_o_campo(overrides: dict[str, Any], field: str) -> None:
    service = _regras()
    await service.create(ANA, draft())
    with pytest.raises(RequestRejected) as recusa:
        await service.update(ANA, "~meu-rag", draft(**overrides))
    assert recusa.value.field == field


@pytest.mark.us6
async def test_regra_da_fase_3_aceita_o_rascunho_valido() -> None:
    criado = await _regras().create(
        ANA,
        draft(
            flow="agentic",
            models={"generation": "ollama/qwen3:1.7b", "controller": "ollama/qwen3:1.7b"},
            mcp=("agenda",),
            allowed_tools=("generic.calculate", "agenda.marcar"),
        ),
    )
    assert criado.status.available, criado.status.reasons
