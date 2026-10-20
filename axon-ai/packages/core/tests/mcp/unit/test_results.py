"""T029 e T038 — resultado remoto → `ToolResult` (research R9; FR-008; princípio VI)."""

from __future__ import annotations

import pytest

from axon_ai.mcp.domain.records import RemotePart, RemoteResult
from axon_ai.mcp.domain.results import cut, failure, to_tool_result

LIMITE = 65_536


def texto(*partes: str, **kwargs: object) -> RemoteResult:
    return RemoteResult(parts=tuple(RemotePart(kind="text", text=p) for p in partes), **kwargs)  # type: ignore[arg-type]


@pytest.mark.us3
def test_textos_concatenados() -> None:
    resultado = to_tool_result(texto("um", "dois"), max_bytes=LIMITE)
    assert resultado.content == "um\n\ndois" and resultado.untrusted and resultado.error is None


@pytest.mark.us3
def test_texto_vem_antes_do_estruturado() -> None:
    assert to_tool_result(texto("oi", structured={"result": "oi"}), max_bytes=LIMITE).content == "oi"


@pytest.mark.us3
def test_estruturado_so_quando_nao_ha_texto() -> None:
    resultado = to_tool_result(RemoteResult(structured={"b": 2, "a": 1}), max_bytes=LIMITE)
    assert resultado.content == '{"a": 1, "b": 2}'


@pytest.mark.us3
def test_parte_nao_textual_vira_marcador() -> None:
    remoto = RemoteResult(parts=(RemotePart(kind="text", text="veja"), RemotePart(kind="image")))
    assert to_tool_result(remoto, max_bytes=LIMITE).content == "veja\n\n[conteúdo image omitido]"


@pytest.mark.us3
def test_erro_do_servidor_vira_error() -> None:
    resultado = to_tool_result(texto("deu ruim", is_error=True), max_bytes=LIMITE)
    assert resultado.error == "deu ruim" and resultado.untrusted


@pytest.mark.us3
def test_falha_fora_do_servidor() -> None:
    resultado = failure("sem resposta em 1 s")
    assert resultado.error == "sem resposta em 1 s" and resultado.content == "" and resultado.untrusted


# --- corte (T038, US5) ------------------------------------------------------------------------------------------------


@pytest.mark.us5
def test_no_limite_exato_nao_corta() -> None:
    assert cut("x" * 1024, max_bytes=1024) == ("x" * 1024, False)


@pytest.mark.us5
def test_acima_do_limite_corta_com_marca_visivel() -> None:
    cortado, truncado = cut("x" * 5000, max_bytes=1024)
    assert truncado
    assert len(cortado.encode("utf-8")) <= 1024
    assert cortado.endswith("de 5000 bytes]") and "resposta cortada" in cortado


@pytest.mark.us5
def test_corte_em_fronteira_de_caractere() -> None:
    cortado, _ = cut("ação" * 1000, max_bytes=1024)
    cortado.encode("utf-8").decode("utf-8")
    assert "�" not in cortado and len(cortado.encode("utf-8")) <= 1024


@pytest.mark.us5
def test_estruturado_grande_e_cortado_como_texto() -> None:
    resultado = to_tool_result(RemoteResult(structured={"dados": "y" * 5000}), max_bytes=1024)
    assert resultado.truncated and isinstance(resultado.content, str)
    assert resultado.content.startswith('{"dados": "yyy')
