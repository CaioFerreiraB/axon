"""T035 — 006 US3 e FR-011 ponta a ponta no perfil `test`, sem rede (research R16, R21, R23; ADR-020).

Roteamento automático recusado na declaração (Assistant indisponível, 424) e na escolha por requisição (400, mesmo com
`openrouter/*` na allowlist); provider remoto sem credencial indisponível na saúde e explícito na conversa, sem que uma
única requisição saia para a rede.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx2
import pytest
from bootstrap_testkit import CHAVE, MODEL, OIDC, PUBLICO, USER_ASSISTANTS_E_ADMIN, MemoryConfig, body, write_config
from fastapi.testclient import TestClient

from axon_ai.bootstrap.wiring import Platform, platform
from axon_ai.llm.adapters.fake import ScriptedProvider
from axon_ai.llm.adapters.openai import OpenAIProvider
from axon_ai.llm.adapters.secrets import InMemorySecretResolver

pytestmark = pytest.mark.us3

ASSISTANTS = f"""
assistants:
  automatico:{PUBLICO}
    flow: agentic
    packs: [generic]
    models:
      generation: ollama/{MODEL}
      controller: openrouter/auto
      allow: ["ollama/*", "openrouter/*"]
  aberto:{PUBLICO}
    flow: chat
    packs: [generic]
    models:
      generation: ollama/{MODEL}
      allow: ["ollama/*", "openrouter/*"]
  remoto:{PUBLICO}
    flow: chat
    packs: [generic]
    models:
      generation: openai/gpt-4o-mini
      allow: ["openai/*"]
{USER_ASSISTANTS_E_ADMIN}"""


def _plataforma(tmp_path: Path, **overrides: Any) -> Platform:
    settings = write_config(tmp_path, assistants=ASSISTANTS)
    plataforma = platform(config=MemoryConfig(settings), overrides=overrides or None)
    assert plataforma.ok, plataforma.report.render()
    return plataforma


def test_assistant_com_roteamento_automatico_fica_indisponivel(tmp_path: Path) -> None:
    with TestClient(_plataforma(tmp_path).app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(model="automatico"))

    assert response.status_code == 424, response.text
    corpo = response.json()
    assert corpo["error"]["code"] == "assistant_unavailable"
    motivos = corpo["x_axon"]["reasons"]
    assert any("models.controller" in motivo and "roteamento automático" in motivo for motivo in motivos), motivos


def test_modelo_automatico_pedido_na_requisicao_e_recusado(tmp_path: Path) -> None:
    with TestClient(_plataforma(tmp_path).app) as client:
        response = client.post(
            "/v1/chat/completions", headers=OIDC, json=body(model="aberto/openrouter/openrouter/auto")
        )

    assert response.status_code == 400, response.text
    error = response.json()["error"]
    assert error["param"] == "model"
    assert "roteamento automático" in error["message"]


def test_remoto_sem_credencial_na_saude_e_na_conversa(tmp_path: Path) -> None:
    requests: list[httpx2.Request] = []

    def handler(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return httpx2.Response(500)

    openai = OpenAIProvider(
        secrets=InMemorySecretResolver(),
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)),
    )
    plataforma = _plataforma(
        tmp_path, providers={"ollama": ScriptedProvider(name="ollama", deltas=("Pronto.",)), "openai": openai}
    )

    with TestClient(plataforma.app) as client:
        saude = client.get("/private/v1/health", headers=CHAVE)
        conversa = client.post("/v1/chat/completions", headers=OIDC, json=body(model="remoto"))

    assert saude.status_code == 200, saude.text
    item = next(item for item in saude.json()["items"] if item["name"] == "model:openai/gpt-4o-mini")
    assert item["ok"] is False
    assert "sem credencial: defina AXON_OPENAI_API_KEY" in (item["detail"] or "")

    assert conversa.status_code == 502, conversa.text
    assert "sem credencial: defina AXON_OPENAI_API_KEY" in conversa.text
    assert requests == []
