"""T014 — a plataforma inteira montada por uma chamada, e a conversa acontecendo por HTTP (US3, SC-003).

Nenhuma rede, nenhum serviço externo, nenhum modelo de verdade: é o que a 011 entrega para que qualquer suíte — do
core ou de um pack externo — teste contra a plataforma real.
"""

from __future__ import annotations

import json
from pathlib import Path

from bootstrap_testkit import MODEL_ID, MemoryConfig, body, write_config
from fastapi.testclient import TestClient

from ai_core.bootstrap.profiles import FIXED_TIME
from ai_core.bootstrap.wiring import platform
from ai_core.observability.api import ExecutionFinished, ExecutionStarted, ModelCall, ValidationRun


def built(tmp_path: Path, **kwargs: str):  # type: ignore[no-untyped-def]
    return platform(config=MemoryConfig(write_config(tmp_path, **kwargs)))


def test_a_plataforma_sobe_inteira_no_perfil_de_teste(tmp_path: Path) -> None:
    plataforma = built(tmp_path)

    assert plataforma.ok
    assert [o.name for o in plataforma.report.stages] == [
        "configuration",
        "adapters",
        "packs",
        "engine",
        "api",
    ]
    assert plataforma.packs is not None
    assert plataforma.engine is not None
    assert plataforma.app is not None
    assert plataforma.engine.flows() == frozenset({"chat"})


def test_o_pack_de_referencia_e_carregado(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    assert plataforma.packs is not None
    entrada = plataforma.packs.entry("generic")
    assert entrada is not None
    assert entrada.status == "enabled"


def test_conversa_sem_streaming_pela_api(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", json=body())

    assert response.status_code == 200
    payload = response.json()
    assert payload["choices"][0]["message"]["content"] == "Brasília"
    assert payload["model"] == MODEL_ID
    assert payload["created"] == int(FIXED_TIME.timestamp()), "o relógio fixo torna `created` verificável"


def test_conversa_em_streaming_pela_api(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", json=body(stream=True))

    assert response.status_code == 200
    pedacos = [
        json.loads(bloco.removeprefix("data: "))
        for bloco in response.text.split("\n\n")
        if bloco.strip().startswith("data: ") and "[DONE]" not in bloco
    ]
    texto = "".join(p["choices"][0]["delta"].get("content", "") for p in pedacos)
    assert texto == "Brasília"
    assert response.text.rstrip().endswith("data: [DONE]")


def test_o_trace_da_requisicao_atravessa_a_plataforma(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", json=body())

    assert plataforma.trace is not None
    trace = plataforma.trace.trace(response.headers["x-request-id"])
    tipos = [registro.type for registro in trace.records]
    for esperado in (ExecutionStarted, ModelCall, ValidationRun, ExecutionFinished):
        nome = "".join("_" + c.lower() if c.isupper() else c for c in esperado.__name__).lstrip("_")
        assert nome in tipos, f"falta {nome} no trace: {tipos}"


def test_a_mesma_data_de_referencia_em_toda_a_execucao(tmp_path: Path) -> None:
    """ADR-013 e FR-008: um relógio só para motor, API e trace."""
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", json=body())

    assert plataforma.trace is not None
    trace = plataforma.trace.trace(response.headers["x-request-id"])
    inicio = next(r for r in trace.records if r.type == "execution_started")
    assert inicio.attributes["reference_time"] == FIXED_TIME.isoformat()


def test_assistant_desconhecido_responde_404(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        assert client.post("/v1/chat/completions", json=body(model="outro")).status_code == 404


def test_encerrar_a_plataforma_nao_levanta(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    plataforma.aclose()
    plataforma.aclose()
