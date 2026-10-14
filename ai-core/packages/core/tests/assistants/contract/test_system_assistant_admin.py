"""T077 — o seam `SystemAssistantAdmin` (US10, ADR-032; SC-006 adversarial): os oito cenários, quem não administra, a
efetiva na resolução seguinte sem recriar o serviço, e o histórico. Roda sobre o armazenamento das duas versões."""

from __future__ import annotations

from typing import Any

import pytest
from assistants_testkit import ANA, CAIO_KEY, assistant, assistants_service, config

from ai_core.assistants.api import (
    AssistantUnavailable,
    Conflict,
    McpOverride,
    ModelsOverride,
    NotFound,
    Principal,
    RequestRejected,
)
from ai_core.assistants.domain.overrides import NOT_ALLOWED, SECTION_CHANGED
from ai_core.llm.api import ModelRef

pytestmark = pytest.mark.us10

ADMIN_OIDC = Principal(subject="user:root", scheme="oidc", groups=frozenset({"operadores"}))
FLOW_ROLES = {"chat": ("generation",), "agentic": ("generation", "controller")}
MINI = ModelRef.parse("openrouter/openai/gpt-4.1-mini")


class Directory:
    """MCPs globais que a suíte apaga no meio do teste (cenário 5)."""

    def __init__(self, *aliases: str) -> None:
        self.globals = set(aliases)

    async def aliases(self, *, owner: str | None) -> frozenset[str]:
        return frozenset(self.globals) if owner is None else frozenset()


def _geral(**fields: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "flow": "chat",
        "overrides": ["models", "mcp"],
        "models": {"generation": "openrouter/nvidia/nemotron", "allow": ["openrouter/*"]},
        "allowed_tools": ["generic.calculate"],
    }
    body.update(fields)
    return assistant(**body)


def _yaml(geral: dict[str, Any] | None = None) -> dict[str, Any]:
    return config({"geral": geral or _geral(), "fixo": assistant(flow="chat")})


def _service(store: Any, data: dict[str, Any] | None = None, directory: Directory | None = None) -> Any:
    return assistants_service(
        data or _yaml(),
        overrides=store,
        mcp=directory or Directory("arquivos", "agenda"),
        flow_roles=FLOW_ROLES,
    )


async def _generation(service: Any) -> ModelRef:
    grant = await service.resolve(model="geral", principal=ANA)
    return ModelRef.parse(str(grant.models.roles["generation"]))


async def test_cenario_1_sobrepor_generation_vale_na_resolucao_seguinte(override_store: Any) -> None:
    service = _service(override_store)
    assert str(await _generation(service)) == "openrouter/nvidia/nemotron"
    view = await service.override_models(
        "geral", ModelsOverride(roles={"generation": MINI}), actor=ADMIN_OIDC, version=None
    )
    assert view.effective_models["generation"] == MINI and view.yaml_models["generation"] != MINI
    (override,) = view.overrides
    assert (override.section, override.state, override.version, override.updated_by) == (
        "models",
        "active",
        1,
        "user:root",
    )
    assert await _generation(service) == MINI
    assert MINI in await service.declared_models()


async def test_cenario_2_modelo_fora_da_allowlist(override_store: Any) -> None:
    service = _service(override_store)
    with pytest.raises(RequestRejected) as caught:
        await service.override_models(
            "geral",
            ModelsOverride(roles={"generation": ModelRef.parse("openai/gpt-4.1")}),
            actor=CAIO_KEY,
            version=None,
        )
    assert caught.value.field == "models.generation" and "openrouter/*" in str(caught.value)


async def test_cenario_3_secao_nao_liberada(override_store: Any) -> None:
    service = _service(override_store)
    with pytest.raises(RequestRejected) as caught:
        await service.override_models("fixo", ModelsOverride(roles={"generation": MINI}), actor=CAIO_KEY, version=None)
    assert caught.value.field == "models" and "só muda por novo deploy" in str(caught.value)


async def test_papel_exigido_pelo_flow_nao_some(override_store: Any) -> None:
    data = _yaml(
        _geral(
            flow="agentic",
            models={"generation": "openrouter/a/b", "controller": "openrouter/a/c", "allow": ["openrouter/*"]},
        )
    )
    service = _service(override_store, data)
    with pytest.raises(RequestRejected) as caught:
        await service.override_models("geral", ModelsOverride(roles={"generation": MINI}), actor=CAIO_KEY, version=None)
    assert caught.value.field == "models" and "controller" in str(caught.value)


async def test_cenario_4_escrita_em_assistant_publico(override_store: Any) -> None:
    service = _service(override_store)
    override = McpOverride(
        aliases=("arquivos",),
        allowed=frozenset({"arquivos.ler", "arquivos.gravar"}),
        write=frozenset({"arquivos.gravar"}),
    )
    with pytest.raises(RequestRejected) as caught:
        await service.override_mcp("geral", override, actor=CAIO_KEY, version=None)
    assert caught.value.field == "mcp.write" and "FR-012" in str(caught.value)


@pytest.mark.parametrize(
    ("override", "field"),
    [
        (McpOverride(aliases=("inexistente",)), "mcp.aliases"),
        (McpOverride(aliases=("arquivos",), allowed=frozenset({"agenda.ler"})), "mcp.allowed"),
        (McpOverride(aliases=("arquivos",), allowed=frozenset({"sem-namespace"})), "mcp.allowed"),
        (McpOverride(aliases=("generic",)), "mcp.aliases"),
    ],
)
async def test_entradas_de_mcp_invalidas(override_store: Any, override: McpOverride, field: str) -> None:
    service = _service(override_store, directory=Directory("arquivos", "generic"))
    with pytest.raises(RequestRejected) as caught:
        await service.override_mcp("geral", override, actor=CAIO_KEY, version=None)
    expected = "mcp" if override.aliases == ("generic",) else field  # alias com nome de pack: colisão (R21)
    assert caught.value.field == expected


async def test_cenario_5_servidor_apagado_deixa_indisponivel_com_motivo(override_store: Any) -> None:
    directory = Directory("arquivos", "agenda")
    service = _service(override_store, directory=directory)
    override = McpOverride(aliases=("agenda",), allowed=frozenset({"agenda.ler"}))
    view = await service.override_mcp("geral", override, actor=CAIO_KEY, version=None)
    assert view.effective_mcp.aliases == ("agenda",)
    grant = await service.resolve(model="geral", principal=ANA)
    assert grant.mcp_aliases == frozenset({"agenda"})
    assert grant.allowed_tools == frozenset({"generic.calculate", "agenda.ler"})
    directory.globals.discard("agenda")
    service = _service(override_store, directory=directory)
    with pytest.raises(AssistantUnavailable) as caught:
        await service.resolve(model="geral", principal=ANA)
    assert any(reason.startswith("override.mcp: mcp: MCP 'agenda'") for reason in caught.value.reasons)


async def test_cenario_6_deploy_tira_a_permissao(override_store: Any) -> None:
    await _service(override_store).override_models(
        "geral", ModelsOverride(roles={"generation": MINI}), actor=CAIO_KEY, version=None
    )
    redeploy = _service(override_store, _yaml(_geral(overrides=["mcp"])))
    assert str(await _generation(redeploy)) == "openrouter/nvidia/nemotron"
    view = await redeploy.system_assistant("geral", actor=CAIO_KEY)
    (override,) = view.overrides
    assert (override.state, override.reason) == ("inactive", NOT_ALLOWED)
    assert override.payload == ModelsOverride(roles={"generation": MINI})


async def test_cenario_7_deploy_muda_a_secao(override_store: Any) -> None:
    await _service(override_store).override_models(
        "geral", ModelsOverride(roles={"generation": MINI}), actor=CAIO_KEY, version=None
    )
    novo = _geral(models={"generation": "openrouter/meta/llama", "allow": ["openrouter/*"]})
    redeploy = _service(override_store, _yaml(novo))
    assert str(await _generation(redeploy)) == "openrouter/meta/llama"
    (override,) = (await redeploy.system_assistant("geral", actor=CAIO_KEY)).overrides
    assert (override.state, override.reason) == ("inactive", SECTION_CHANGED)


async def test_cenario_8_dois_admins_na_mesma_versao(override_store: Any) -> None:
    service = _service(override_store)
    await service.override_models("geral", ModelsOverride(roles={"generation": MINI}), actor=CAIO_KEY, version=None)
    other = ModelsOverride(roles={"generation": ModelRef.parse("openrouter/meta/llama")})
    await service.override_models("geral", other, actor=ADMIN_OIDC, version=1)
    with pytest.raises(Conflict) as caught:
        await service.override_models("geral", ModelsOverride(roles={"generation": MINI}), actor=CAIO_KEY, version=1)
    assert caught.value.current_version == 2
    assert str(await _generation(service)) == "openrouter/meta/llama"


async def test_quem_nao_administra_e_assistant_inexistente_ou_de_usuario(override_store: Any) -> None:
    service = _service(override_store)
    for call in (
        service.system_assistants(actor=ANA),
        service.system_assistant("geral", actor=ANA),
        service.override_models("geral", ModelsOverride(roles={"generation": MINI}), actor=ANA, version=None),
        service.history("geral", actor=ANA),
        service.system_assistant("nao-existe", actor=CAIO_KEY),
        service.system_assistant("~meu", actor=CAIO_KEY),
    ):
        with pytest.raises(NotFound):
            await call


async def test_lista_descartar_e_historico(override_store: Any) -> None:
    service = _service(override_store)
    views = await service.system_assistants(actor=ADMIN_OIDC)
    assert [view.name for view in views] == ["fixo", "geral"]
    geral = views[1]
    assert geral.overridable == frozenset({"models", "mcp"}) and geral.required_roles == ("generation",)
    assert geral.status.available and geral.allow == ("openrouter/*",)
    await service.override_models("geral", ModelsOverride(roles={"generation": MINI}), actor=CAIO_KEY, version=None)
    with pytest.raises(Conflict):
        await service.discard_override("geral", "models", actor=CAIO_KEY, version=7)
    view = await service.discard_override("geral", "models", actor=ADMIN_OIDC, version=1)
    assert view.overrides == () and str(view.effective_models["generation"]) == "openrouter/nvidia/nemotron"
    with pytest.raises(NotFound):
        await service.discard_override("geral", "models", actor=CAIO_KEY, version=1)
    history = await service.history("geral", actor=CAIO_KEY)
    assert [(entry.action, entry.version, entry.actor) for entry in history] == [
        ("discarded", 1, "user:root"),
        ("saved", 1, "user:caio"),
    ]
    assert history[1].payload == ModelsOverride(roles={"generation": MINI})


async def test_sem_armazenamento_a_efetiva_e_o_yaml() -> None:
    service = assistants_service(_yaml(), flow_roles=FLOW_ROLES)
    assert str(await _generation(service)) == "openrouter/nvidia/nemotron"
    with pytest.raises(RequestRejected):
        await service.override_models("geral", ModelsOverride(roles={"generation": MINI}), actor=CAIO_KEY, version=None)


async def test_assistants_validate_lista_a_sobreposicao_inativa(override_store: Any) -> None:
    """T082: o deploy desligou a seção; a sobreposição segue guardada e o comando diz por que não vale."""
    import io

    from ai_core.assistants.adapters.cli import validate_command

    await _service(override_store).override_models(
        "geral", ModelsOverride(roles={"generation": MINI}), actor=CAIO_KEY, version=None
    )
    out = io.StringIO()
    assert await validate_command(_service(override_store, _yaml(_geral(overrides=[]))), out) == 0
    assert f"sobreposição inativa: geral.models — {NOT_ALLOWED}" in out.getvalue()
