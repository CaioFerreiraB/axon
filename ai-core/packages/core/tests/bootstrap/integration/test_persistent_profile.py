"""T025 — o perfil persistente contra um Postgres real (US2; research R13, R20).

Pulado sem `AI_CORE_TEST_POSTGRES_DSN`, exceto o banco inacessível, que não precisa de banco. A app roda com o ciclo de
vida no laço do próprio teste — é ali que o pool de serviço abre, como no servidor (R13).

O relógio, o provider e o verificador OIDC são trocados pelos do perfil de teste: o que está sob prova é o
armazenamento, e uma conversa precisa de modelo e a superfície pública, de emissor (o token de teste vale no instante do
relógio fixo). Trocar fábricas de um perfil não toca módulo nenhum.
"""

from __future__ import annotations

import asyncio
import dataclasses
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

import httpx
import pytest
from bootstrap_testkit import AGENTIC_ASSISTANTS_YAML, CHAVE, OIDC, MemoryConfig, body, write_config

from ai_core.bootstrap import profiles
from ai_core.bootstrap.profiles import TEST_SUBJECT, Profile
from ai_core.bootstrap.wiring import Platform, mcp_service, platform, storage
from ai_core.mcp.api import McpServerDraft, SecurityPolicy

PG_DSN = os.environ.get("AI_CORE_TEST_POSTGRES_DSN")
needs_pg = pytest.mark.skipif(PG_DSN is None, reason="defina AI_CORE_TEST_POSTGRES_DSN para rodar contra um Postgres")

UNREACHABLE: Final = "postgresql://ai:segredo-do-banco@127.0.0.1:1/ai"
"""Porta 1: conexão recusada na hora. A senha está aqui para provar que nunca aparece."""


def _persistent_for_tests() -> Profile:
    real = profiles._persistent_profile()
    test = profiles._test_profile()
    factories = dict(real.factories)
    for port in ("clock", "providers", "oidc"):
        factories[port] = test.factories[port]
    return dataclasses.replace(real, factories=factories)


@pytest.fixture
def persistent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(profiles.PROFILES, "persistent", _persistent_for_tests)  # type: ignore[index]


@pytest.fixture
async def banco_limpo() -> AsyncIterator[str]:
    if PG_DSN is None:
        pytest.skip("defina AI_CORE_TEST_POSTGRES_DSN")
    import psycopg

    async with await psycopg.AsyncConnection.connect(PG_DSN, autocommit=True) as connection:
        for schema in ("assistants", "http", "mcp", "capabilities"):
            await connection.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    yield PG_DSN


def _platform(tmp_path: Path, dsn: str, **kwargs: str) -> Platform:
    settings = dataclasses.replace(write_config(tmp_path, **kwargs), profile="persistent", database_url=dsn)
    return platform(config=MemoryConfig(settings))


@asynccontextmanager
async def serving(plataforma: Platform) -> AsyncIterator[httpx.AsyncClient]:
    """O ciclo de vida da app no laço do teste — abre o pool de serviço e agenda as tarefas, como o servidor faria."""
    app = plataforma.app
    assert app is not None, plataforma.report.render()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://ai-core") as client:
            yield client


@needs_pg
async def test_o_boot_migra_os_dois_schemas_e_conclui(persistent: None, banco_limpo: str, tmp_path: Path) -> None:
    import psycopg

    plataforma = _platform(tmp_path, banco_limpo)

    assert plataforma.ok, plataforma.report.render()
    assert plataforma.report.degraded == ()
    async with await psycopg.AsyncConnection.connect(banco_limpo) as connection:
        for schema in ("assistants", "http"):
            cursor = await connection.execute(f"SELECT count(*) FROM {schema}.schema_version")
            row = await cursor.fetchone()
            assert row is not None and row[0] >= 1, f"schema {schema} sem migração"


@needs_pg
async def test_o_boot_de_novo_sobre_o_mesmo_banco_nao_reaplica(
    persistent: None, banco_limpo: str, tmp_path: Path
) -> None:
    assert _platform(tmp_path, banco_limpo).ok
    assert _platform(tmp_path, banco_limpo).ok


@needs_pg
async def test_chave_emitida_autentica_numa_plataforma_nova(persistent: None, banco_limpo: str, tmp_path: Path) -> None:
    primeira = _platform(tmp_path, banco_limpo)
    async with serving(primeira):
        assert primeira.access is not None
        emitida = await primeira.access.issue_as_operator(subject="svc:robo", groups=["admin"])

    segunda = _platform(tmp_path, banco_limpo)
    async with serving(segunda) as client:
        chave = {"Authorization": f"Bearer {emitida.plaintext}"}
        assert (await client.get("/private/v1/models", headers=chave)).status_code == 200
        assert (await client.get("/private/v1/packs", headers=chave)).status_code == 200, "grupo de administração"
        assert (await client.get("/private/v1/models", headers=CHAVE)).status_code == 401, (
            "a chave semeada do perfil de teste não existe no armazenamento persistente"
        )


@needs_pg
async def test_conversa_aberta_numa_plataforma_continua_noutra(
    persistent: None, banco_limpo: str, tmp_path: Path
) -> None:
    primeira = _platform(tmp_path, banco_limpo)
    async with serving(primeira) as client:
        response = await client.post("/v1/chat/completions", headers=OIDC, json=body())
        assert response.status_code == 200, response.text
        conversa = response.headers["x-conversation-id"]

    segunda = _platform(tmp_path, banco_limpo)
    async with serving(segunda) as client:
        continuada = await client.post("/v1/chat/completions", headers=OIDC, json=body(conversation_id=conversa))
        assert continuada.status_code == 200, continuada.text
        lida = await client.get(f"/v1/conversations/{conversa}", headers=OIDC)
        assert lida.status_code == 200
        assert [m["role"] for m in lida.json()["messages"]] == ["user", "assistant", "user", "assistant"]


@needs_pg
async def test_assistant_de_usuario_sobrevive(persistent: None, banco_limpo: str, tmp_path: Path) -> None:
    rascunho = {"name": "meu", "packs": ["generic"], "models": {"generation": "ollama/qwen3:1.7b"}}
    primeira = _platform(tmp_path, banco_limpo)
    async with serving(primeira) as client:
        criado = await client.post("/v1/assistants", headers=OIDC, json=rascunho)
        assert criado.status_code == 201, criado.text

    segunda = _platform(tmp_path, banco_limpo)
    async with serving(segunda) as client:
        lido = await client.get("/v1/assistants/~meu", headers=OIDC)
        assert lido.status_code == 200, lido.text
        assert lido.json()["owner"] == TEST_SUBJECT


async def test_banco_inacessivel_para_o_boot_sem_expor_a_url(persistent: None, tmp_path: Path) -> None:
    """US2 cen. 2: a etapa crítica `adapters` falha nomeando a porta e o adapter — nunca a URL nem a senha."""
    plataforma = _platform(tmp_path, UNREACHABLE)

    assert not plataforma.ok
    falha = plataforma.report.failure()
    assert falha is not None and falha.name == "adapters"
    assert falha.detail is not None
    assert "database" in falha.detail and "Postgres" in falha.detail
    texto = plataforma.report.render()
    for segredo in (UNREACHABLE, "segredo-do-banco"):
        assert segredo not in texto
    assert plataforma.app is None, "a API não chega a existir"


@needs_pg
async def test_saude_com_o_banco_e_com_o_banco_fora_depois_do_boot(
    persistent: None, banco_limpo: str, tmp_path: Path
) -> None:
    """US5 cen. 3: o banco é item crítico — fora do ar depois do boot, a saúde é `down` e o nomeia.

    Por HTTP, a chave do monitor mora no mesmo banco: a autenticação falha antes da saúde e responde 503
    `storage_unavailable` (008 FR-021). O provedor de saúde, com o pool real fechado, diz qual item caiu.
    """
    plataforma = _platform(tmp_path, banco_limpo)
    async with serving(plataforma) as client:
        assert plataforma.access is not None
        chave = await plataforma.access.issue_as_operator(subject="svc:monitor")
        saudavel = await client.get("/private/v1/health", headers={"Authorization": f"Bearer {chave.plaintext}"})
        assert saudavel.status_code == 200, saudavel.text
        assert saudavel.json()["status"] == "ok"
        assert {"name": "database", "ok": True, "critical": True, "detail": None} in saudavel.json()["items"]

        health = plataforma.parts["health"]
        health._cached = None  # a janela de cache esconderia a queda por 15 s
        await plataforma.parts["database"].close()
        por_http = await client.get("/private/v1/health", headers={"Authorization": f"Bearer {chave.plaintext}"})
        assert por_http.status_code == 503
        assert por_http.json()["error"]["code"] == "storage_unavailable"
        fora = await health.health()

    assert fora.status == "down"
    database = next(item for item in fora.items if item.name == "database")
    assert not database.ok and database.detail is not None and "Postgres" in database.detail
    assert banco_limpo not in database.detail


# --- Fase 3 (T042; research R22, R25, R26): registry MCP e auditoria no Postgres -----------------------------------

ASSISTANT_COM_MCP_DA_API = AGENTIC_ASSISTANTS_YAML.replace("mcp: [demo]", "mcp: [arquivado]")
"""`pesquisador` passa a referenciar um alias que só existe depois de criado pela API (armazenado no schema `mcp`)."""


@needs_pg
@pytest.mark.us2
async def test_o_boot_migra_mcp_e_capabilities_e_oferece_agentic(
    persistent: None, banco_limpo: str, tmp_path: Path
) -> None:
    import psycopg

    plataforma = _platform(tmp_path, banco_limpo)
    assert plataforma.ok, plataforma.report.render()
    assert plataforma.engine is not None and plataforma.engine.flows() == frozenset({"chat", "agentic"})
    async with await psycopg.AsyncConnection.connect(banco_limpo) as connection:
        for schema in ("mcp", "capabilities"):
            cursor = await connection.execute(f"SELECT count(*) FROM {schema}.schema_version")
            row = await cursor.fetchone()
            assert row is not None and row[0] >= 1, f"schema {schema} sem migração"


@needs_pg
@pytest.mark.us2
async def test_servidor_criado_pelo_registry_sobrevive_e_valida_o_assistant(
    persistent: None, banco_limpo: str, tmp_path: Path
) -> None:
    primeira = _platform(tmp_path, banco_limpo, assistants=ASSISTANT_COM_MCP_DA_API)
    (etapa,) = [o for o in primeira.report.stages if o.name == "assistants"]
    assert "pesquisador" in (etapa.detail or ""), "antes de criado, o alias não existe"
    async with serving(primeira):
        assert primeira.mcp is not None
        await primeira.mcp.create_global(
            McpServerDraft(
                alias="arquivado",
                transport="http",
                endpoint="https://arquivado.test/mcp",
                policy=SecurityPolicy(allowed_tools=("eco",)),
            )
        )

    segunda = _platform(tmp_path, banco_limpo, assistants=ASSISTANT_COM_MCP_DA_API)
    assert segunda.ok, segunda.report.render()
    async with storage(segunda.parts) as session:
        aliases = {server.alias for server in await mcp_service(segunda.parts, store=session["mcp_store"]).globals()}
    assert "arquivado" in aliases
    (etapa,) = [o for o in segunda.report.stages if o.name == "assistants"]
    assert "pesquisador" not in (etapa.detail or "")


@needs_pg
@pytest.mark.us4
async def test_audit_lista_o_registro_gravado_pela_auditoria_da_004(
    persistent: None,
    banco_limpo: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from datetime import UTC, datetime

    from psycopg_pool import AsyncConnectionPool

    from ai_core.bootstrap import cli
    from ai_core.capabilities.adapters.audit_postgres import PostgresAuditLog
    from ai_core.capabilities.api import AuditEntry

    assert _platform(tmp_path, banco_limpo).ok  # migra o schema `capabilities`
    async with AsyncConnectionPool(banco_limpo, open=False) as pool:
        log = PostgresAuditLog(pool)
        record_id = await log.begin(
            AuditEntry(
                request_id="req-a1",
                principal=TEST_SUBJECT,
                assistant="geral",
                tool="crm.apagar",
                kind="mcp",
                arguments={"id": 7},
                started_at=datetime(2026, 10, 2, 9, tzinfo=UTC),
            )
        )
        await log.finish(
            record_id,
            status="ok",
            result="<tool_result>apagado</tool_result>",
            at=datetime(2026, 10, 2, 9, 0, 1, tzinfo=UTC),
        )

    write_config(tmp_path)
    monkeypatch.setenv("AI_CORE_PROFILE", "persistent")
    monkeypatch.setenv("AI_CORE_DATABASE_URL", banco_limpo)
    monkeypatch.setenv("AI_CORE_PACKS_FILE", str(tmp_path / "packs.yaml"))
    monkeypatch.setenv("AI_CORE_ASSISTANTS_FILE", str(tmp_path / "assistants.yaml"))

    assert await asyncio.to_thread(cli.main, ["audit"]) == 0
    saida = capsys.readouterr().out
    assert "crm.apagar" in saida and '{"id": 7}' in saida and "apagado" not in saida

    assert await asyncio.to_thread(cli.main, ["audit", "--results"]) == 0
    assert "apagado" in capsys.readouterr().out
