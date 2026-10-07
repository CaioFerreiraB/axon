"""T008 — value objects e erros do seam (data-model.md)."""

from __future__ import annotations

import pytest

from ai_core.llm.api import (
    MODEL_ROLES,
    ModelCallFailed,
    ModelHealth,
    ModelNotAllowed,
    ModelPolicy,
    ModelRef,
    ModelRoutingError,
    RoleNotConfigured,
    UnknownProvider,
)


def test_parse_divide_no_primeiro_separador() -> None:
    ref = ModelRef.parse("ollama/qwen3:1.7b")
    assert (ref.provider, ref.model) == ("ollama", "qwen3:1.7b")


def test_parse_preserva_barra_no_nome_do_modelo() -> None:
    """Modelos do OpenRouter têm barra; dividir em todas quebraria a Fase 3 (research R12)."""
    ref = ModelRef.parse("openrouter/qwen/qwen3-8b")
    assert (ref.provider, ref.model) == ("openrouter", "qwen/qwen3-8b")


def test_str_volta_ao_texto_original() -> None:
    assert str(ModelRef.parse("openrouter/qwen/qwen3-8b")) == "openrouter/qwen/qwen3-8b"


@pytest.mark.parametrize("text", ["qwen3:1.7b", "ollama/", "/qwen3", ""])
def test_parse_rejeita_referencia_sem_provider_explicito(text: str) -> None:
    with pytest.raises(ValueError):
        ModelRef.parse(text)


def test_ref_rejeita_provider_com_separador() -> None:
    with pytest.raises(ValueError):
        ModelRef(provider="ollama/local", model="qwen3:1.7b")


def test_politica_sem_papel_e_rejeitada() -> None:
    with pytest.raises(ValueError):
        ModelPolicy(roles={})


def test_politica_rejeita_papel_desconhecido() -> None:
    with pytest.raises(ValueError, match="embedding"):
        ModelPolicy(roles={"embedding": ModelRef.parse("ollama/x")})  # type: ignore[dict-item]


def test_papeis_configurados_saem_na_ordem_canonica() -> None:
    policy = ModelPolicy(
        roles={"generation": ModelRef.parse("ollama/g"), "controller": ModelRef.parse("ollama/c")}
    )
    assert policy.configured_roles() == ("controller", "generation")
    assert policy.configured_roles() == tuple(r for r in MODEL_ROLES if r in policy.roles)


def test_politica_congela_o_mapa_de_papeis() -> None:
    roles = {"generation": ModelRef.parse("ollama/g")}
    policy = ModelPolicy(roles=roles)
    roles["controller"] = ModelRef.parse("ollama/c")
    assert policy.configured_roles() == ("generation",)
    with pytest.raises(TypeError):
        policy.roles["controller"] = ModelRef.parse("ollama/c")  # type: ignore[index]


def test_health_guarda_motivo_da_indisponibilidade() -> None:
    health = ModelHealth(
        role="generation", ref=ModelRef.parse("ollama/qwen3:1.7b"), available=False, detail="modelo não encontrado"
    )
    assert not health.available
    assert health.detail == "modelo não encontrado"


def test_erro_de_chamada_carrega_provider_modelo_e_motivo() -> None:
    """A 008 (Fase 2) traduz a hierarquia em status HTTP sem reparsear texto."""
    error = ModelCallFailed(provider="ollama", model="qwen3:1.7b", reason="provider inalcançável")
    assert (error.provider, error.model, error.reason) == ("ollama", "qwen3:1.7b", "provider inalcançável")
    assert "ollama/qwen3:1.7b" in str(error)


@pytest.mark.parametrize("error_type", [RoleNotConfigured, ModelNotAllowed, UnknownProvider])
def test_hierarquia_de_erro(error_type: type[ModelRoutingError]) -> None:
    assert issubclass(error_type, ModelRoutingError)
    assert issubclass(ModelCallFailed, ModelRoutingError)


# --- Fase 3, US3: roteamento automático recusado na construção da referência (T030, research R16) --------------------


@pytest.mark.us3
@pytest.mark.parametrize(
    "texto",
    [
        "openrouter/auto",
        "openrouter/AUTO",
        "openrouter/auto:free",
        "openrouter/openrouter/auto",
        "openrouter/OpenRouter/Auto",
        "openrouter/openrouter/qualquer",
    ],
)
def test_roteamento_automatico_recusado(texto: str) -> None:
    with pytest.raises(ValueError) as erro:
        ModelRef.parse(texto)
    assert "roteamento automático" in str(erro.value)
    assert "modelo explícito" in str(erro.value)
    assert texto in str(erro.value)


@pytest.mark.us3
def test_roteamento_automatico_recusado_na_construcao_direta() -> None:
    with pytest.raises(ValueError, match="roteamento automático"):
        ModelRef(provider="openrouter", model="auto")


@pytest.mark.us3
@pytest.mark.parametrize(
    "texto",
    [
        "openrouter/qwen/qwen3-8b",
        "openrouter/qwen/qwen3-8b:free",
        "openrouter/qwen/qwen3-8b:nitro",
        "openrouter/qwen/qwen3-8b:floor",
        "ollama/auto",
        "openai/gpt-4o-mini",
        "openai/openrouter/auto",
        "openrouter/~z-ai/glm-flash-latest",
    ],
)
def test_roteamento_automatico_nao_atinge_modelo_explicito(texto: str) -> None:
    assert str(ModelRef.parse(texto)) == texto
