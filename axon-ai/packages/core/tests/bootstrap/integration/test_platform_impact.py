"""ADR-056 ponta a ponta, no perfil `test` e sem rede (011 US8; 009 US9; 008 US12).

Uma conversa pelo modelo simulado `ollama/gpt-4.1-mini` — cujo nome casa exato com o `openai/gpt-4.1-mini` da base do
EcoLogits — é estimada quando o destino de uso esvazia; `GET /admin/v1/impact` por mês traz números maiores que zero; a
saúde tem o item informativo `impact`; e `axon usage impact-backfill` não acha nada a estimar.
"""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path

import pytest
from bootstrap_testkit import CHAVE, PACKS_YAML, PUBLICO, USER_ASSISTANTS_E_ADMIN, MemoryConfig, serving, write_config

from axon_ai.bootstrap.wiring import platform

pytestmark = pytest.mark.us8

ASSISTANTS = f"""
assistants:
  geral:{PUBLICO}
    flow: chat
    packs: [generic]
    models:
      generation: ollama/gpt-4.1-mini
      allow: ["ollama/*"]
{USER_ASSISTANTS_E_ADMIN}"""


async def test_conversa_estimada_e_relatorio_por_mes(tmp_path: Path) -> None:
    plataforma = platform(config=MemoryConfig(write_config(tmp_path, packs=PACKS_YAML, assistants=ASSISTANTS)))
    assert plataforma.ok, plataforma.report.render()
    assert plataforma.trace is not None and plataforma.impact is not None
    async with serving(plataforma) as client:
        answer = await client.post(
            "/private/v1/chat/completions",
            headers=CHAVE,
            json={"model": "geral", "messages": [{"role": "user", "content": "qual é a capital?"}]},
        )
        assert answer.status_code == 200, answer.text
        await plataforma.trace.flush()

        response = await client.get("/admin/v1/impact?grain=month&from=2025-12-01&to=2026-01-31", headers=CHAVE)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["enabled"] is True and body["method"]["ecologits_version"]
        (row,) = body["rows"]
        assert (row["key"], row["impact_model"], row["match"]) == (
            "ollama/gpt-4.1-mini",
            "openai/gpt-4.1-mini",
            "exact",
        )
        assert Decimal(body["totals"]["metrics"]["gwp_kgco2eq"]["mean"]) > 0
        assert Decimal(body["totals"]["metrics"]["energy_kwh"]["mean"]) > 0
        assert body["totals"]["coverage"]["estimated"] == 1
        assert [bucket["start"] for bucket in body["buckets"]] == ["2025-12-01", "2026-01-01"]

        health = await client.get("/private/v1/health", headers=CHAVE)
        items = {item["name"]: item for item in health.json()["items"]}
        assert items["impact"]["ok"] is True and items["impact"]["critical"] is False
        assert "EcoLogits" in items["impact"]["detail"]


async def test_desligado_pela_instalacao(tmp_path: Path) -> None:
    settings = write_config(tmp_path, packs=PACKS_YAML, assistants=ASSISTANTS, impact_enabled=False)
    plataforma = platform(config=MemoryConfig(settings))
    assert plataforma.ok, plataforma.report.render()
    async with serving(plataforma) as client:
        body = (await client.get("/admin/v1/impact", headers=CHAVE)).json()
        assert body["enabled"] is False and body["totals"] is None
        health = await client.get("/private/v1/health", headers=CHAVE)
        items = {item["name"]: item for item in health.json()["items"]}
        assert "desligada" in items["impact"]["detail"]


def test_backfill_pela_linha_de_comando(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from axon_ai.bootstrap.cli import main

    for name in ("AXON_DEV_API_KEY", "AXON_OIDC_ISSUER", "AXON_DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "packs.yaml").write_text(PACKS_YAML, encoding="utf-8")
    (tmp_path / "assistants.yaml").write_text(ASSISTANTS, encoding="utf-8")
    monkeypatch.setenv("AXON_PROFILE", "test")
    monkeypatch.setenv("AXON_PACKS_FILE", str(tmp_path / "packs.yaml"))
    monkeypatch.setenv("AXON_ASSISTANTS_FILE", str(tmp_path / "assistants.yaml"))
    out, err = io.StringIO(), io.StringIO()
    code = main(["usage", "impact-backfill", "--limit", "10"], out=out, err=err)
    assert code == 0, err.getvalue()
    assert out.getvalue().startswith("0 estimadas, 0 sem par")
