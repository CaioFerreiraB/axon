"""T055 — cenários da US6 da 011 (Fase 9): o boot com identidade, chave mestra, Langfuse e origem do uso.

O cenário 3 (admin inicial uma vez, contra o Postgres) está em `test_platform_identity.py`.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import pytest
from bootstrap_testkit import ASSISTANTS_YAML, MODEL_ID, PACKS_YAML, MemoryConfig, write_config
from opentelemetry.sdk.trace.export import SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from axon_ai.bootstrap import profiles
from axon_ai.bootstrap.settings import EnvConfigSource
from axon_ai.bootstrap.wiring import STAGE_CONFIGURATION, Platform, platform
from axon_ai.graph.api import ExecutionRequest
from axon_ai.observability.adapters.langfuse import OtelLangfuseTransport
from axon_ai.observability.adapters.memory import RecordingLangfuseTransport
from axon_ai.observability.api import UsageQuery

LANGFUSE = {
    "LANGFUSE_HOST": "https://lf.exemplo.org",
    "LANGFUSE_PUBLIC_KEY": "pk-lf-1",
    "LANGFUSE_SECRET_KEY": "sk-lf-segredo-da-instalacao",
}


def _env_platform(tmp_path: Path, **values: str) -> Platform:
    settings = write_config(tmp_path)
    environ = {
        "AXON_PROFILE": "test",
        "AXON_PACKS_FILE": str(settings.packs_file),
        "AXON_ASSISTANTS_FILE": str(settings.assistants_file),
        **{f"AXON_{name}": value for name, value in values.items()},
    }
    return platform(config=EnvConfigSource(environ))


def _failed_at_configuration(plataforma: Platform, variable: str) -> None:
    failure = plataforma.report.failure()
    assert failure is not None and failure.name == STAGE_CONFIGURATION, plataforma.report.render()
    assert variable in (failure.detail or "")


def test_cenario_1_persistent_com_identidade_sem_chave_mestra(tmp_path: Path) -> None:
    plataforma = _env_platform(
        tmp_path,
        PROFILE="persistent",
        DATABASE_URL="postgresql://ninguem@localhost:1/nada",
        IDENTITY_ENABLED="true",
        PUBLIC_URL="https://agentic.exemplo.org",
        IDENTITY_CLIENTS_FILE=str(tmp_path / "identity.yaml"),
    )
    _failed_at_configuration(plataforma, "AXON_MASTER_KEY")


def test_cenario_2_identidade_e_emissor_externo_juntos(tmp_path: Path) -> None:
    plataforma = _env_platform(
        tmp_path,
        IDENTITY_ENABLED="true",
        PUBLIC_URL="http://localhost:8000",
        OIDC_ISSUER="https://idp.exemplo.org",
        OIDC_AUDIENCE="ai-core",
    )
    _failed_at_configuration(plataforma, "AXON_OIDC_ISSUER")


def test_grupo_do_langfuse_incompleto_para_o_boot_sem_mostrar_o_segredo(tmp_path: Path) -> None:
    plataforma = _env_platform(tmp_path, LANGFUSE_SECRET_KEY="sk-lf-segredo-da-instalacao")
    _failed_at_configuration(plataforma, "AXON_LANGFUSE_HOST")
    assert "sk-lf-segredo" not in plataforma.report.render()


class _Down(InMemorySpanExporter):
    def export(self, spans: Any) -> SpanExportResult:
        return SpanExportResult.FAILURE


async def _chat(plataforma: Platform) -> None:
    assert plataforma.engine is not None and plataforma.assistants is not None
    grant = await plataforma.assistants.resolve(model=MODEL_ID, principal=_principal())
    async for _ in plataforma.engine.run(grant, ExecutionRequest(request_id="r-1", messages=_messages())):
        pass


def _principal() -> Any:
    from axon_ai.assistants.api import Principal

    return Principal(subject="user:test", scheme="oidc")


def _messages() -> Any:
    from axon_ai_contracts import ChatMessage

    return (ChatMessage(role="user", content="qual é a capital?"),)


async def test_cenario_4_langfuse_fora_do_ar_nao_impede_o_boot_e_aparece_na_saude(tmp_path: Path) -> None:
    transport = OtelLangfuseTransport(exporter_factory=lambda _c: _Down(), delay_ms=10)
    settings = write_config(tmp_path, packs=PACKS_YAML, assistants=ASSISTANTS_YAML)
    environ = {
        "AXON_PROFILE": "test",
        "AXON_PACKS_FILE": str(settings.packs_file),
        "AXON_ASSISTANTS_FILE": str(settings.assistants_file),
        **{f"AXON_{name}": value for name, value in LANGFUSE.items()},
    }
    plataforma = platform(config=EnvConfigSource(environ), overrides={"langfuse_transport": transport})
    assert plataforma.ok, plataforma.report.render()
    assert plataforma.trace is not None and plataforma.destinations is not None
    view = await plataforma.destinations.settings()
    assert view.sources["langfuse_host"] == "installation" and view.langfuse_enabled
    await _chat(plataforma)
    await plataforma.trace.flush()
    (langfuse,) = [item for item in plataforma.destinations.health() if item.name == "langfuse"]
    assert langfuse.state == "degraded" and langfuse.last_error == "o Langfuse não aceitou o lote (OTLP)"
    health = plataforma.parts["health"]
    items = {item.name: item for item in (await health.health()).items}
    assert not items["trace:langfuse"].ok and not items["trace:langfuse"].critical
    assert (await health.health()).status == "degraded"
    plataforma.aclose()


def test_cenario_5_suite_de_pack_encontra_o_admin_semeado_e_a_chave() -> None:
    assert profiles.TEST_ADMIN_USERNAME == "admin-teste" and profiles.TEST_ADMIN_PASSWORD
    assert profiles.TEST_API_KEY.startswith("aic_")


async def test_o_test_nunca_sai_para_a_rede_no_langfuse(tmp_path: Path) -> None:
    plataforma = _env_platform(tmp_path, **LANGFUSE)
    assert plataforma.ok, plataforma.report.render()
    transport = plataforma.parts["langfuse_transport"]
    assert isinstance(transport, RecordingLangfuseTransport) and transport.credentials is not None
    await _chat(plataforma)
    assert transport.sent and transport.sent[0].type == "execution_started"
    plataforma.aclose()


@pytest.mark.parametrize(("origin", "seen"), [("production", "production"), ("evaluation", "evaluation")])
async def test_a_origem_do_processo_marca_o_uso(tmp_path: Path, origin: Any, seen: str) -> None:
    """`axon eval run` sobe com `origin="evaluation"`: as chamadas não entram no relatório de produção (R40)."""
    settings = write_config(tmp_path)
    plataforma = platform(config=MemoryConfig(settings), origin=origin)
    assert plataforma.ok and plataforma.trace is not None and plataforma.usage is not None
    await _chat(plataforma)
    await plataforma.trace.flush()
    day = profiles.FIXED_TIME.date()
    for queried in ("production", "evaluation"):
        report = await plataforma.usage.report(UsageQuery(start=day, end=day, tz="UTC", origin=queried))
        assert bool(report.totals) is (queried == seen), queried


def test_chave_mestra_do_memory_e_uma_so_por_processo(tmp_path: Path) -> None:
    """O `memory` sem `AXON_MASTER_KEY` sorteia uma chave para todos os módulos que selam segredos (ADR-033)."""
    clients = tmp_path / "identity.yaml"
    clients.write_text(
        "version: 1\nclients:\n  console:\n    type: public\n    audience: ai-core-admin\n"
        "    redirect_uris: [http://localhost:8080/callback]\n",
        encoding="utf-8",
    )
    settings = write_config(
        tmp_path, identity_enabled=True, public_url="http://localhost:8000", identity_clients_file=clients
    )
    plataforma = platform(config=MemoryConfig(settings), profile="memory")
    assert plataforma.ok, plataforma.report.render()
    key = plataforma.parts["master_key"]
    assert len(key) == 32 and base64.b64encode(key).decode() not in plataforma.report.render()
