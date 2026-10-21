"""T074 — regras puras das sobreposições (ADR-032; R28, R29): impressão digital, estados e definição efetiva."""

from __future__ import annotations

import dataclasses

import pytest
from assistants_testkit import T0, assistant, config

from axon_ai.assistants.api import AuthOverride, McpOverride, ModelsOverride
from axon_ai.assistants.domain.definitions import AssistantDefinition, read_config
from axon_ai.assistants.domain.overrides import (
    NOT_ALLOWED,
    SECTION_CHANGED,
    StoredOverride,
    apply_auth,
    apply_mcp,
    attribute,
    effective,
    payload_of,
    read_payload,
    section_fingerprint,
    yaml_auth,
    yaml_mcp,
)
from axon_ai.llm.api import ModelRef

pytestmark = pytest.mark.us10

PACK_TOOLS = {"generic": frozenset({"calculate", "buscar"})}


def _definition(**fields: object) -> AssistantDefinition:
    defaults: dict[str, object] = {
        "overrides": ["models", "mcp"],
        "mcp": ["arquivos", "agenda"],
        "allowed_tools": ["generic.calculate", "arquivos.listar"],
        "write_tools": ["arquivos.gravar"],
        "models": {"generation": "openrouter/a/b", "controller": "openrouter/a/c", "allow": ["openrouter/*"]},
        "visibility": "private",
        "auth": {"schemes": ["oidc"], "allow": ["group:equipe"]},
    }
    body = assistant(**(defaults | fields))
    return read_config(config({"x": body}), origin="t").assistants["x"]


def _stored(section: str, payload: object, definition: AssistantDefinition, **changes: object) -> StoredOverride:
    record = StoredOverride(
        assistant="x",
        section=section,  # type: ignore[arg-type]
        payload=payload_of(payload),  # type: ignore[arg-type]
        fingerprint=section_fingerprint(definition, section),  # type: ignore[arg-type]
        version=1,
        updated_by="user:root",
        updated_at=T0,
    )
    return dataclasses.replace(record, **changes)  # type: ignore[arg-type]


def test_impressao_digital_estavel_e_insensivel_a_ordem_dos_aliases() -> None:
    definition = _definition()
    reordered = dataclasses.replace(definition, mcp=("agenda", "arquivos"))
    assert section_fingerprint(definition, "mcp") == section_fingerprint(reordered, "mcp")
    assert section_fingerprint(definition, "models") == section_fingerprint(definition, "models")
    # a allowlist não entra: é o teto, não a seção
    assert section_fingerprint(dataclasses.replace(definition, allow=("x/*",)), "models") == section_fingerprint(
        definition, "models"
    )
    changed = dataclasses.replace(definition, roles={"generation": ModelRef.parse("openrouter/a/z")})
    assert section_fingerprint(changed, "models") != section_fingerprint(definition, "models")


def test_secao_mcp_do_yaml() -> None:
    assert yaml_mcp(_definition()) == McpOverride(
        aliases=("arquivos", "agenda"), allowed=frozenset({"arquivos.listar"}), write=frozenset({"arquivos.gravar"})
    )


def test_conteudo_ida_e_volta_e_ilegivel() -> None:
    models = ModelsOverride(roles={"generation": ModelRef.parse("openrouter/a/z")})
    mcp = McpOverride(aliases=("agenda",), allowed=frozenset({"agenda.ler"}))
    assert read_payload("models", payload_of(models)) == models
    assert read_payload("mcp", payload_of(mcp)) == mcp
    assert read_payload("models", {"roles": {"papel_novo": "a/b"}}) is None
    assert read_payload("models", {"roles": {"generation": "sem-barra"}}) is None
    assert read_payload("mcp", {"aliases": "x"}) is None


def test_efetiva_de_models_ativa() -> None:
    definition = _definition()
    override = ModelsOverride(roles={"generation": ModelRef.parse("openrouter/a/z")})
    result, (status,) = effective(definition, [_stored("models", override, definition)], pack_tools=PACK_TOOLS)
    assert status.state == "active" and status.reason is None
    assert dict(result.roles) == {"generation": ModelRef.parse("openrouter/a/z")}
    assert result.overridden == frozenset({"models"}) and result.problems == ()


def test_efetiva_de_mcp_mantem_as_entradas_de_pack() -> None:
    definition = _definition()
    override = McpOverride(aliases=("agenda",), allowed=frozenset({"agenda.ler"}), write=frozenset())
    result, _ = effective(definition, [_stored("mcp", override, definition)], pack_tools=PACK_TOOLS)
    assert result.mcp == ("agenda",)
    assert result.allowed_tools == ("generic.calculate", "agenda.ler")
    assert result.write_tools == ()


def test_sem_allowed_tools_no_yaml_a_restricao_enumera_as_tools_dos_packs() -> None:
    definition = dataclasses.replace(_definition(), allowed_tools=None, write_tools=())
    restricted = apply_mcp(
        definition, McpOverride(aliases=("agenda",), allowed=frozenset({"agenda.ler"})), pack_tools=PACK_TOOLS
    )
    assert restricted.allowed_tools == ("generic.buscar", "generic.calculate", "agenda.ler")
    open_ = apply_mcp(definition, McpOverride(aliases=("agenda",)), pack_tools=PACK_TOOLS)
    assert open_.allowed_tools is None


def test_inativa_quando_o_deploy_tira_a_permissao_ou_muda_a_secao() -> None:
    definition = _definition()
    override = ModelsOverride(roles={"generation": ModelRef.parse("openrouter/a/z")})
    stored = _stored("models", override, definition)
    without_flag = dataclasses.replace(definition, overrides=frozenset({"mcp"}))
    result, (status,) = effective(without_flag, [stored], pack_tools=PACK_TOOLS)
    assert (status.state, status.reason) == ("inactive", NOT_ALLOWED)
    assert result.roles == definition.roles and result.overridden == frozenset()
    changed = dataclasses.replace(definition, roles={"generation": ModelRef.parse("openrouter/a/novo")})
    result, (status,) = effective(changed, [stored], pack_tools=PACK_TOOLS)
    assert (status.state, status.reason) == ("inactive", SECTION_CHANGED)
    assert dict(result.roles) == {"generation": ModelRef.parse("openrouter/a/novo")}


def test_modelo_fora_da_allowlist_atual_vira_problema_da_sobreposicao() -> None:
    definition = _definition()
    stored = _stored("models", ModelsOverride(roles={"generation": ModelRef.parse("openrouter/a/z")}), definition)
    narrowed = dataclasses.replace(definition, allow=("openrouter/outro/*",))
    result, (status,) = effective(narrowed, [stored], pack_tools=PACK_TOOLS)
    assert status.state == "active"
    assert result.problems and result.problems[0].startswith("override.models: models.generation:")


def test_conteudo_ilegivel_ativo_deixa_indisponivel() -> None:
    definition = _definition()
    stored = dataclasses.replace(_stored("models", ModelsOverride(roles={}), definition), payload={"roles": "x"})
    result, _ = effective(definition, [stored], pack_tools=PACK_TOOLS)
    assert result.problems == ("override.models: sobreposição ilegível",)


def test_motivos_dos_campos_sobrepostos_nomeiam_a_sobreposicao() -> None:
    reasons = ("mcp: MCP 'x' não existe ou não é visível", "packs: pack 'p' não está instalado", "models: falta x")
    assert attribute(reasons, frozenset({"mcp"})) == (
        "override.mcp: mcp: MCP 'x' não existe ou não é visível",
        "packs: pack 'p' não está instalado",
        "models: falta x",
    )
    assert attribute(reasons, frozenset())[0] == reasons[0]


# --- US13: seção `auth` (ADR-040; R41, R42) --------------------------------------------------------------------------

AUTH = AuthOverride(schemes=frozenset({"oidc", "api_key"}), allow=("svc:relatorios", "group:equipe"))


@pytest.mark.us13
def test_yaml_auth_le_a_secao_do_yaml() -> None:
    assert yaml_auth(_definition()) == AuthOverride(schemes=frozenset({"oidc"}), allow=("group:equipe",))


@pytest.mark.us13
def test_impressao_digital_de_auth_ignora_a_ordem_de_allow_e_ve_os_esquemas() -> None:
    definition = _definition(auth={"schemes": ["oidc"], "allow": ["group:equipe", "user:ana"]})
    reordered = _definition(auth={"schemes": ["oidc"], "allow": ["user:ana", "group:equipe"]})
    other_scheme = _definition(auth={"schemes": ["oidc", "api_key"], "allow": ["group:equipe", "user:ana"]})

    assert section_fingerprint(definition, "auth") == section_fingerprint(reordered, "auth")
    assert section_fingerprint(definition, "auth") != section_fingerprint(other_scheme, "auth")
    assert section_fingerprint(definition, "auth") != section_fingerprint(definition, "models")


@pytest.mark.us13
def test_conteudo_de_auth_vai_e_volta() -> None:
    payload = payload_of(AUTH)
    assert payload == {"schemes": ["api_key", "oidc"], "allow": ["svc:relatorios", "group:equipe"]}
    assert read_payload("auth", payload) == AUTH


@pytest.mark.us13
@pytest.mark.parametrize(
    "payload",
    [
        {"schemes": ["oidc", "saml"], "allow": ["*"]},
        {"schemes": "oidc", "allow": ["*"]},
        {"schemes": ["oidc"], "allow": "*"},
        {"allow": ["*"]},
    ],
)
def test_conteudo_de_auth_ilegivel_e_none(payload: dict[str, object]) -> None:
    assert read_payload("auth", payload) is None


@pytest.mark.us13
def test_apply_auth_troca_o_acesso() -> None:
    result = apply_auth(_definition(), AUTH)
    assert result.access.schemes == AUTH.schemes and result.access.allow == AUTH.allow
    assert not result.problems


@pytest.mark.us13
def test_apply_auth_com_asterisco_em_privado_e_problema() -> None:
    result = apply_auth(_definition(), AuthOverride(schemes=frozenset({"oidc"}), allow=("*",)))
    assert any(problem.startswith("override.auth: auth.allow") for problem in result.problems)


@pytest.mark.us13
def test_apply_auth_vazio_e_problema() -> None:
    result = apply_auth(_definition(), AuthOverride())
    assert any(problem.startswith("override.auth: auth") for problem in result.problems)


@pytest.mark.us13
def test_efetiva_com_auth_ativa_inativa_por_permissao_e_por_mudanca() -> None:
    definition = _definition(overrides=["auth"])
    stored = _stored("auth", AUTH, definition)

    active, (status,) = effective(definition, [stored], pack_tools=PACK_TOOLS)
    assert status.state == "active" and active.access.allow == AUTH.allow and "auth" in active.overridden

    not_allowed = _definition(overrides=["models"])
    kept, (status,) = effective(not_allowed, [stored], pack_tools=PACK_TOOLS)
    assert (status.state, status.reason) == ("inactive", NOT_ALLOWED) and kept.access.allow == ("group:equipe",)

    changed = _definition(overrides=["auth"], auth={"schemes": ["oidc"], "allow": ["group:outra"]})
    kept, (status,) = effective(changed, [stored], pack_tools=PACK_TOOLS)
    assert (status.state, status.reason) == ("inactive", SECTION_CHANGED) and kept.access.allow == ("group:outra",)


@pytest.mark.us13
def test_attribute_nomeia_a_sobreposicao_de_auth() -> None:
    assert attribute(["auth.allow: algo"], frozenset({"auth"})) == ("override.auth: auth.allow: algo",)
