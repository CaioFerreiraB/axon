"""T013 — `assistants.yaml` e resolução de grant (contracts/configuration.md)."""

from __future__ import annotations

from pathlib import Path

import pytest
from bootstrap_testkit import ASSISTANTS_YAML, MODEL

from ai_core.bootstrap.grants import ConfiguredGrants, load_assistants, validate_flows
from ai_core.bootstrap.settings import ConfigurationError
from ai_core.http.adapters.development import DevelopmentPrincipal
from ai_core.http.ports import AssistantNotFound
from ai_core.packs.api import Composition, CompositionError

PRINCIPAL = DevelopmentPrincipal()


class FakeRegistry:
    """Pack Registry de teste: compõe o que conhece e recusa o resto, como o real."""

    def __init__(self, known: tuple[str, ...] = ("generic",)) -> None:
        self._known = known

    def compose(self, pack_names: list[str] | tuple[str, ...]) -> Composition:
        faltando = [name for name in pack_names if name not in self._known]
        if faltando:
            raise CompositionError(f"pack indisponível: {', '.join(faltando)}", packs=pack_names)
        return Composition(packs=tuple(pack_names))


def write(tmp_path: Path, content: str) -> Path:
    path = tmp_path / "assistants.yaml"
    path.write_text(content, encoding="utf-8")
    return path


def test_arquivo_valido_vira_assistants(tmp_path: Path) -> None:
    assistants = load_assistants(write(tmp_path, ASSISTANTS_YAML))
    geral = assistants["geral"]
    assert geral.flow == "chat"
    assert geral.packs == ("generic",)
    assert str(geral.models["generation"]) == f"ollama/{MODEL}"
    assert geral.allow == ("ollama/*",)


def test_sem_arquivo_nao_ha_assistants() -> None:
    assert load_assistants(None) == {}


def test_arquivo_inexistente_e_erro_de_configuracao(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="não encontrado"):
        load_assistants(tmp_path / "ausente.yaml")


def test_flow_ausente_usa_chat(tmp_path: Path) -> None:
    path = write(tmp_path, "assistants:\n  x:\n    models:\n      generation: ollama/m\n")
    assert load_assistants(path)["x"].flow == "chat"


def test_models_sem_generation_e_recusado(tmp_path: Path) -> None:
    path = write(tmp_path, "assistants:\n  x:\n    models:\n      controller: ollama/m\n")
    with pytest.raises(ConfigurationError, match="generation"):
        load_assistants(path)


def test_referencia_de_modelo_sem_barra_e_recusada(tmp_path: Path) -> None:
    path = write(tmp_path, "assistants:\n  x:\n    models:\n      generation: qwen3\n")
    with pytest.raises(ConfigurationError, match="generation"):
        load_assistants(path)


def test_chave_desconhecida_e_recusada(tmp_path: Path) -> None:
    path = write(tmp_path, "assistants:\n  x:\n    mcp_servers: [a]\n    models:\n      generation: ollama/m\n")
    with pytest.raises(ConfigurationError, match="mcp_servers"):
        load_assistants(path)


def test_raiz_invalida_e_recusada(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="assistants"):
        load_assistants(write(tmp_path, "outra_coisa: {}\n"))


def test_flow_inexistente_nomeia_o_flow_e_os_disponiveis(tmp_path: Path) -> None:
    path = write(tmp_path, "assistants:\n  x:\n    flow: agentic\n    models:\n      generation: ollama/m\n")
    with pytest.raises(ConfigurationError) as error:
        validate_flows(load_assistants(path), {"chat"})
    assert "agentic" in str(error.value)
    assert "chat" in str(error.value)


async def test_id_sem_modelo_usa_o_generation_declarado(tmp_path: Path) -> None:
    grants = ConfiguredGrants(load_assistants(write(tmp_path, ASSISTANTS_YAML)), FakeRegistry())
    grant = await grants.resolve(model="geral", principal=PRINCIPAL)
    assert grant.assistant == "geral"
    assert str(grant.models.roles["generation"]) == f"ollama/{MODEL}"
    assert grant.composition.packs == ("generic",)


async def test_id_com_modelo_troca_so_a_geracao_e_preserva_a_allowlist(tmp_path: Path) -> None:
    grants = ConfiguredGrants(load_assistants(write(tmp_path, ASSISTANTS_YAML)), FakeRegistry())
    grant = await grants.resolve(model="geral/outro:1b", principal=PRINCIPAL)
    assert str(grant.models.roles["generation"]) == "ollama/outro:1b"
    assert grant.models.allow == ("ollama/*",)


async def test_assistant_desconhecido_levanta_o_erro_que_a_api_traduz_em_404(tmp_path: Path) -> None:
    grants = ConfiguredGrants(load_assistants(write(tmp_path, ASSISTANTS_YAML)), FakeRegistry())
    with pytest.raises(AssistantNotFound):
        await grants.resolve(model="nao-existe", principal=PRINCIPAL)


async def test_assistant_com_pack_indisponivel_fica_indisponivel_e_os_demais_atendem(tmp_path: Path) -> None:
    from bootstrap_testkit import ASSISTANTS_YAML_SEM_PACK

    grants = ConfiguredGrants(load_assistants(write(tmp_path, ASSISTANTS_YAML_SEM_PACK)), FakeRegistry())
    with pytest.raises(AssistantNotFound, match="orfao"):
        await grants.resolve(model="orfao", principal=PRINCIPAL)
    assert (await grants.resolve(model="geral", principal=PRINCIPAL)).assistant == "geral"
