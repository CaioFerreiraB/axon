"""005 T088 — o `rag_first` ponta a ponta pela API, no perfil `test` e sem rede (US3; R44; ADR-026).

Um pack de teste em memória (troca da porta `pack_source` na montagem) declara um retriever da coleção `docs` e um
reranker. O Assistant `leitor` declara `flow: rag_first` e só o papel `generation` — e é servido (ADR-019). A geração
recebe os trechos com `· id: <chunk_id>`; a falha do retriever é 502 sem reexecução; o limiar do operador
(`AI_CORE_RAG_MIN_SCORE`) leva à geração sem trechos quando o Assistant não tem `controller`.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from bootstrap_testkit import MODEL, OIDC, PUBLICO, USER_ASSISTANTS_E_ADMIN, MemoryConfig, body, write_config
from fastapi.testclient import TestClient

from ai_core.bootstrap.wiring import Platform, platform
from ai_core.llm.adapters.fake import ScriptedProvider
from ai_core.packs.adapters.memory import InMemoryPackSource
from ai_core_contracts import Chunk, JSONValue, NamedRetriever, PackBase, PackContext, PackManifest

pytestmark = pytest.mark.us3

CHUNKS = tuple(
    Chunk(chunk_id=f"manual#s{n}", text=f"conteúdo da seção {n}", score=0.9 - n * 0.1, document="Manual", page=n)
    for n in range(1, 4)
)

PACKS_YAML = """
packs:
  docs:
    enabled: true
"""

ASSISTANTS_YAML = f"""
assistants:
  leitor:{PUBLICO}
    flow: rag_first
    packs: [docs]
    collections: [docs]
    models:
      generation: ollama/{MODEL}
      allow: ["ollama/*"]
{USER_ASSISTANTS_E_ADMIN}"""


class Retriever:
    def __init__(self, *, error: Exception | None = None) -> None:
        self._error = error

    async def search(
        self, query: str, *, top_k: int | None = None, filters: Mapping[str, JSONValue] | None = None
    ) -> list[Chunk]:
        if self._error is not None:
            raise self._error
        return list(CHUNKS)


class KeepOrder:
    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]:
        return list(documents)[:top_k]


def docs_pack(retriever: Retriever) -> type[PackBase]:
    class DocsPack(PackBase):
        name = "docs"
        contract_version = "0.1"

        def manifest(self) -> PackManifest:
            return PackManifest(name="docs", version="0.1.0", preferred_flow="rag_first")

        def retrievers(self, ctx: PackContext) -> Sequence[NamedRetriever]:
            return (
                NamedRetriever(
                    name="search", description="Busca.", collections=frozenset({"docs"}), retriever=retriever
                ),
            )

        def reranker(self, ctx: PackContext) -> Any:
            return KeepOrder()

    return DocsPack


def _plataforma(tmp_path: Path, retriever: Retriever, geracao: ScriptedProvider, **settings: Any) -> Platform:
    config = write_config(tmp_path, packs=PACKS_YAML, assistants=ASSISTANTS_YAML, **settings)
    plataforma = platform(
        config=MemoryConfig(config),
        overrides={"pack_source": InMemoryPackSource.of(docs_pack(retriever)), "providers": {"ollama": geracao}},
    )
    assert plataforma.ok, plataforma.report.render()
    return plataforma


def test_o_assistant_rag_first_sem_controller_e_servido_e_ve_o_identificador(tmp_path: Path) -> None:
    geracao = ScriptedProvider(name="ollama", deltas=("Veja [[manual#s1]].",))
    plataforma = _plataforma(tmp_path, Retriever(), geracao)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(model="leitor"))

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["choices"][0]["finish_reason"] == "stop"
    mensagens = geracao.calls[-1]["messages"]
    (resultado,) = [m["content"] for m in mensagens if m["role"] == "tool"]
    for item in CHUNKS:
        assert f"[Manual, p. {item.page} · id: {item.chunk_id}]" in resultado
    assert plataforma.trace is not None
    tipos = [record.type for record in plataforma.trace.trace(payload["x_ai_core"]["request_id"]).records]
    assert "coverage_gate" in tipos and "tool_call" in tipos and "controller_decision" not in tipos
    assert tipos.count("model_call") == 1


def test_retriever_que_falha_e_502_sem_reexecucao(tmp_path: Path) -> None:
    geracao = ScriptedProvider(name="ollama", deltas=("não deveria gerar",))
    plataforma = _plataforma(tmp_path, Retriever(error=RuntimeError("índice fora do ar")), geracao)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(model="leitor"))

    assert response.status_code == 502, response.text
    assert response.headers.get("x-should-retry") == "false"
    assert [e["kind"] for e in response.json()["x_ai_core"]["errors"]] == ["RetrievalFailed"]
    assert geracao.calls == []


def test_limiar_do_operador_sem_controller_gera_sem_trechos(tmp_path: Path) -> None:
    geracao = ScriptedProvider(name="ollama", deltas=("Nenhum documento encontrado.",))
    plataforma = _plataforma(tmp_path, Retriever(), geracao, rag_min_score=0.99)
    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(model="leitor"))

    assert response.status_code == 200, response.text
    assert [e["kind"] for e in response.json()["x_ai_core"]["errors"]] == ["CoverageInsufficient"]
    assert [m for m in geracao.calls[-1]["messages"] if m["role"] == "tool"] == []


def test_timeline_de_status_nomeia_a_busca_os_documentos_e_o_portao(tmp_path: Path) -> None:
    """008 FR-005a com o motor real (ADR-028): o que o Open WebUI mostra numa conversa `rag_first`."""
    geracao = ScriptedProvider(name="ollama", deltas=("Veja [[manual#s1]].",))
    plataforma = _plataforma(tmp_path, Retriever(), geracao)
    with TestClient(plataforma.app) as client:
        response = client.post(
            "/v1/chat/completions",
            headers=OIDC | {"x-ai-core-progress": "status"},
            json=body(model="leitor", stream=True),
        )

    assert response.status_code == 200, response.text
    chunks = [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: {")]
    timeline = [c["event"]["data"]["description"] for c in chunks if "event" in c]
    assert "Consultando os documentos…" in timeline
    (busca,) = [line for line in timeline if line.startswith("docs.search(")]
    assert "→ ok: 3 trechos de 1 documento: Manual" in busca
    assert any(line.startswith("3 de 3 trechos: Manual, p. 1; Manual, p. 2; Manual, p. 3") for line in timeline)
    assert any(line.startswith("Coberto: melhor score 0,80, sem limiar → resposta com 3 trechos") for line in timeline)
    assert any(line.startswith(f"Resposta de ollama/{MODEL}") for line in timeline)
    assert timeline[-1].startswith("Concluído em ")
    assert "conteúdo da seção" not in response.text
