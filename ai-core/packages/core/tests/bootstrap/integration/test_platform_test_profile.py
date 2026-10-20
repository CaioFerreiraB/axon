"""T014 — a plataforma inteira montada por uma chamada, e a conversa acontecendo por HTTP (US3, SC-003).

Nenhuma rede, nenhum serviço externo, nenhum modelo de verdade: é o que a 011 entrega para que qualquer suíte — do
core ou de um pack externo — teste contra a plataforma real.
"""

from __future__ import annotations

import json
from pathlib import Path

from bootstrap_testkit import CHAVE, MODEL_ID, OIDC, MemoryConfig, body, write_config
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
        "identity",
        "packs",
        "mcp_registry",
        "engine",
        "assistants",
        "api",
    ]
    assert plataforma.packs is not None
    assert plataforma.engine is not None
    assert plataforma.app is not None
    assert plataforma.engine.flows() == frozenset({"chat", "agentic", "rag_first"})


def test_o_pack_de_referencia_e_carregado(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    assert plataforma.packs is not None
    entrada = plataforma.packs.entry("generic")
    assert entrada is not None
    assert entrada.status == "enabled"


def test_conversa_sem_streaming_pela_api(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body())

    assert response.status_code == 200
    payload = response.json()
    assert payload["choices"][0]["message"]["content"] == "Brasília"
    assert payload["model"] == MODEL_ID
    assert payload["created"] == int(FIXED_TIME.timestamp()), "o relógio fixo torna `created` verificável"


def test_conversa_em_streaming_pela_api(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(stream=True))

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
        response = client.post("/v1/chat/completions", headers=OIDC, json=body())

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
        response = client.post("/v1/chat/completions", headers=OIDC, json=body())

    assert plataforma.trace is not None
    trace = plataforma.trace.trace(response.headers["x-request-id"])
    inicio = next(r for r in trace.records if r.type == "execution_started")
    assert inicio.attributes["reference_time"] == FIXED_TIME.isoformat()


def test_assistant_desconhecido_responde_404(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        assert client.post("/v1/chat/completions", headers=OIDC, json=body(model="outro")).status_code == 404


def test_encerrar_a_plataforma_nao_levanta(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    plataforma.aclose()
    plataforma.aclose()


# --- Fase 2: autenticação real no perfil de teste (T026; FR-015, US2 cen. 5) -----------------------------------------


def test_sem_credencial_e_401_nas_duas_superficies(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        assert client.post("/v1/chat/completions", json=body()).status_code == 401
        assert client.post("/private/v1/chat/completions", json=body()).status_code == 401
        assert client.post("/v1/chat/completions", headers=CHAVE, json=body()).status_code == 401, (
            "a superfície pública aceita só OIDC"
        )
        assert client.post("/private/v1/chat/completions", headers=OIDC, json=body()).status_code == 401, (
            "a privada aceita só chave de API"
        )


def test_a_chave_exportada_conversa_pela_superficie_privada(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        response = client.post("/private/v1/chat/completions", headers=CHAVE, json=body())
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Brasília"


def test_a_chave_exportada_administra_quando_o_grupo_e_declarado(tmp_path: Path) -> None:
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        assert client.get("/private/v1/packs", headers=CHAVE).status_code == 200


def test_ids_de_conversa_do_perfil_de_teste(tmp_path: Path) -> None:
    """R19: `conv_t-1`, e não `conv_req-1`."""
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body())
    assert response.headers["x-conversation-id"] == "conv_t-1"
    assert response.headers["x-request-id"] == "req-1"


def test_saude_agregada_pela_superficie_privada(tmp_path: Path) -> None:
    """US5 cen. 2: todos os itens disponíveis → `ok`, e os itens saudáveis também aparecem (SC-005)."""
    plataforma = built(tmp_path)
    with TestClient(plataforma.app) as client:
        response = client.get("/private/v1/health", headers=CHAVE)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    nomes = {item["name"] for item in payload["items"]}
    assert {"boot:configuration", "boot:api", "pack:generic", "assistant:geral", "model:ollama/qwen3:1.7b"} <= nomes
    assert "database" not in nomes, "sem banco no perfil de teste"


# --- 008 Fase 7 (T073): o limite de execuções vem da configuração -----------------------------------------------


def test_limite_de_execucoes_simultaneas_pela_configuracao(tmp_path: Path) -> None:
    """Com `AI_CORE_MAX_EXECUTIONS=1` e `AI_CORE_QUEUE_SIZE=0`, o segundo pedido simultâneo recebe 503 (008 FR-016)."""
    import asyncio
    from collections.abc import AsyncIterator, Sequence
    from types import SimpleNamespace
    from typing import Any

    import httpx

    class Segurando:
        """`LLMProvider` (001) que só responde depois que o teste libera."""

        name = "ollama"

        def __init__(self) -> None:
            self.solta = asyncio.Event()
            self.entrou = asyncio.Event()

        async def chat(self, messages: Sequence[Any], model: str, **options: Any) -> Any:
            self.entrou.set()
            await self.solta.wait()
            if not options.get("stream"):
                return {"message": {"role": "assistant", "content": "Brasília"}, "finish_reason": "stop"}

            async def chunks() -> AsyncIterator[Any]:
                yield {"delta": "Brasília"}
                yield {"delta": "", "finish_reason": "stop"}

            return chunks()

        async def probe(self, model: str) -> Any:
            return SimpleNamespace(available=True, detail=None)

        async def ready(self) -> Any:
            return SimpleNamespace(available=True, detail=None)

        reports_cost = False

    async def cenario() -> None:
        provider = Segurando()
        plataforma = platform(
            config=MemoryConfig(write_config(tmp_path, max_executions=1, queue_size=0, queue_wait_ms=60_000)),
            overrides={"providers": {"ollama": provider}},
        )
        assert plataforma.ok, plataforma.report.render()
        transport = httpx.ASGITransport(app=plataforma.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://plataforma") as http:
            primeiro = asyncio.create_task(http.post("/v1/chat/completions", headers=OIDC, json=body()))
            await asyncio.wait_for(provider.entrou.wait(), 2)
            segundo = await http.post("/v1/chat/completions", headers=OIDC, json=body())
            provider.solta.set()
            resposta = await primeiro
        plataforma.aclose()

        assert segundo.status_code == 503
        assert segundo.json()["error"]["code"] == "overloaded"
        assert segundo.headers["Retry-After"] == "60"
        assert resposta.status_code == 200

    asyncio.run(cenario())
