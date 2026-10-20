"""T029 — 006 US2 ponta a ponta: controller num provider remoto e geração no local (research R24).

O `pesquisador` declara `controller: openrouter/qwen/qwen3-8b` e `generation: ollama/qwen3:1.7b`; a suíte troca a porta
`providers` por dois simulados com esses nomes. O trace da requisição prova que cada papel foi ao seu provider.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from bootstrap_testkit import AGENTIC_ASSISTANTS_YAML, MODEL, OIDC, MemoryConfig, body, write_config
from fastapi.testclient import TestClient

from axon_ai.bootstrap.wiring import platform
from axon_ai.llm.adapters.fake import ScriptedProvider

pytestmark = pytest.mark.us2

POR_PAPEL = AGENTIC_ASSISTANTS_YAML.replace("    mcp: [demo]\n", "", 1).replace(
    f'      controller: ollama/{MODEL}\n      allow: ["ollama/*"]\n  perdido:',
    '      controller: openrouter/qwen/qwen3-8b\n      allow: ["ollama/*", "openrouter/*"]\n  perdido:',
)
"""`pesquisador` sem MCP, com o controller no OpenRouter e a geração no Ollama."""


def test_providers_por_papel_no_trace(tmp_path: Path) -> None:
    assert "openrouter/qwen/qwen3-8b" in POR_PAPEL
    settings = write_config(tmp_path, assistants=POR_PAPEL)
    plataforma = platform(
        config=MemoryConfig(settings),
        overrides={
            "providers": {
                "ollama": ScriptedProvider(name="ollama", deltas=("Pronto.",)),
                "openrouter": ScriptedProvider(name="openrouter", content='{"action": "answer"}'),
            }
        },
    )
    assert plataforma.ok, plataforma.report.render()

    with TestClient(plataforma.app) as client:
        response = client.post("/v1/chat/completions", headers=OIDC, json=body(model="pesquisador"))

    assert response.status_code == 200, response.text
    request_id = response.json()["x_axon"]["request_id"]
    assert plataforma.trace is not None
    chamadas = [
        (record.attributes["role"], record.attributes["provider"])
        for record in plataforma.trace.trace(request_id).records
        if record.type == "model_call"
    ]
    assert ("controller", "openrouter") in chamadas
    assert ("generation", "ollama") in chamadas
    assert {provider for role, provider in chamadas if role == "controller"} == {"openrouter"}
    assert {provider for role, provider in chamadas if role == "generation"} == {"ollama"}
