"""T056 — a prova da Fase 9 sem rede (011 US6, research R43, SC-007).

`platform(profile="test")` com a identidade ligada: o admin semeado entra pelo cliente do chat e pelo da console (PKCE);
o token do chat vale em `/v1` e não em `/admin/v1`; o da console administra. Uma sobreposição de `generation` vale na
conversa seguinte, sem restart, e a chamada aparece no relatório de uso — com custo depois de lançado o preço.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from bootstrap_testkit import (
    PACKS_YAML,
    PUBLIC_URL,
    PUBLICO,
    USER_ASSISTANTS_E_ADMIN,
    MemoryConfig,
    bearer,
    chat_token,
    console_token,
    serving,
    write_config,
)

from axon_ai.bootstrap.identity import TEST_ADMIN_USERNAME
from axon_ai.bootstrap.wiring import platform

ASSISTANTS = f"""
assistants:
  geral:{PUBLICO}
    flow: chat
    packs: [generic]
    overrides: [models]
    models:
      generation: ollama/qwen3:1.7b
      allow: ["ollama/*"]
{USER_ASSISTANTS_E_ADMIN}"""


async def test_login_sobreposicao_conversa_e_uso(tmp_path: Path) -> None:
    settings = write_config(
        tmp_path, packs=PACKS_YAML, assistants=ASSISTANTS, identity_enabled=True, public_url=PUBLIC_URL
    )
    plataforma = platform(config=MemoryConfig(settings))
    assert plataforma.ok, plataforma.report.render()
    assert plataforma.trace is not None
    async with serving(plataforma) as client:
        chat = await chat_token(client)
        console = await console_token(client)

        assert (await client.get("/v1/models", headers=bearer(chat))).status_code == 200
        assert (await client.get("/admin/v1/me", headers=bearer(chat))).status_code == 401
        me = await client.get("/admin/v1/me", headers=bearer(console))
        assert me.status_code == 200, me.text
        assert (me.json()["username"], me.json()["scheme"]) == (TEST_ADMIN_USERNAME, "oidc")
        assert me.json()["instance"] == {"name": "Axon", "logo_url": None}  # o nome padrão (ADR-038)

        saved = await client.put(
            "/admin/v1/assistants/geral/models",
            headers=bearer(console),
            json={"roles": {"generation": "ollama/gemma3:1b"}, "version": None},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["effective"]["models"]["generation"] == "ollama/gemma3:1b"

        answer = await client.post(
            "/v1/chat/completions",
            headers=bearer(chat),
            json={"model": "geral", "messages": [{"role": "user", "content": "qual é a capital?"}]},
        )
        assert answer.status_code == 200, answer.text

        await plataforma.trace.flush()
        usage = (await client.get("/admin/v1/usage", headers=bearer(console))).json()
        (row,) = usage["totals"]
        assert (row["key"], row["calls"], row["requests"], row["priced"]) == ("ollama/gemma3:1b", 1, 1, False)
        assert usage["incomplete"] is True

        price = await client.post(
            "/admin/v1/prices",
            headers=bearer(console),
            json={
                "provider": "ollama",
                "model": "gemma3:1b",
                "input": "0",
                "output": "0",
                "effective_from": "2025-12-01",
            },
        )
        assert price.status_code == 201, price.text
        priced = (await client.get("/admin/v1/usage", headers=bearer(console))).json()
        assert Decimal(priced["total_cost"]) == 0 and priced["incomplete"] is False

        health = await client.get("/admin/v1/health", headers=bearer(console))
        items = {item["name"]: item for item in health.json()["items"]}
        # o modelo da saúde é o efetivo, com a sobreposição (R41); os destinos aparecem como itens não críticos
        assert "model:ollama/gemma3:1b" in items and "model:ollama/qwen3:1.7b" not in items
        assert items["trace:usage"]["ok"] is True and items["trace:usage"]["critical"] is False
        assert items["trace:langfuse"]["detail"] == "desligado"
