"""D03/D04: superfície, descoberta e canal confidencial HTTP→motor."""

import asyncio
from dataclasses import replace

from fastapi.testclient import TestClient
from http_testkit import MODEL_ID, StaticGrants, app, body
from mcp_testkit import FINANCEIRO_URL, build, global_draft

from axon_ai.assistants.api import AssistantSummary
from axon_ai.llm.api import ModelRef


class DelegatedGrants(StaticGrants):
    async def resolve(self, **kwargs):
        value = await super().resolve(**kwargs)
        return replace(value, mcp_aliases=frozenset({"financeiro"}))


def test_delegated_http_admission_and_metadata():
    kit = build()
    asyncio.run(kit.service.create_global(global_draft(auth_type="delegated")))

    class Directory:
        async def discover(self, principal):
            return [
                AssistantSummary(
                    name=MODEL_ID,
                    origin="system",
                    description=None,
                    generation=ModelRef(provider="ollama", model="m"),
                    allow=(),
                )
            ]

    application = app(grants=DelegatedGrants(), mcp=kit.service, directory=Directory())
    observed = []
    original = application.state.chat_service._engine.run

    def run(grant, request):
        observed.append(request)
        return original(grant, request)

    application.state.chat_service._engine.run = run
    with TestClient(application) as client:
        models = client.get("/private/v1/models")
        assert models.status_code == 200
        entries = models.json()["data"]
        assert entries[0]["x_axon"]["mcp_delegation"] == {
            "version": 1,
            "alias": "financeiro",
            "endpoint": FINANCEIRO_URL,
        }
        headers = {"X-Axon-MCP-Authorization": "Bearer per-run-secret", "x-axon-store": "false"}
        for path, hdr in [
            ("/v1/chat/completions", headers),
            ("/private/v1/chat/completions", {}),
            ("/private/v1/chat", headers),
        ]:
            response = client.post(path, json=body(), headers=hdr)
            assert response.status_code == 400
            assert "per-run-secret" not in response.text
        response = client.post("/private/v1/chat/completions", json=body(), headers=headers)
        assert response.status_code == 200, response.text
        assert observed[-1].mcp_delegation.authorization == "Bearer per-run-secret"
        assert "per-run-secret" not in repr(observed[-1]) + response.text
        assert response.headers.get("X-Conversation-Id") is None
