"""T025 — o perfil persistente contra um Postgres real (US2; research R13, R20).

Pulado sem `AI_CORE_TEST_POSTGRES_DSN`, exceto o banco inacessível, que não precisa de banco. A app roda com o ciclo de
vida no laço do próprio teste — é ali que o pool de serviço abre, como no servidor (R13).

O relógio, o provider e o verificador OIDC são trocados pelos do perfil de teste: o que está sob prova é o
armazenamento, e uma conversa precisa de modelo e a superfície pública, de emissor (o token de teste vale no instante do
relógio fixo). Trocar fábricas de um perfil não toca módulo nenhum.
"""

from __future__ import annotations

import dataclasses
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

import httpx
import pytest
from bootstrap_testkit import CHAVE, OIDC, MemoryConfig, body, write_config

from ai_core.bootstrap import profiles
from ai_core.bootstrap.profiles import TEST_SUBJECT, Profile
from ai_core.bootstrap.wiring import Platform, platform

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
        for schema in ("assistants", "http"):
            await connection.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    yield PG_DSN


def _platform(tmp_path: Path, dsn: str) -> Platform:
    settings = dataclasses.replace(write_config(tmp_path), profile="persistent", database_url=dsn)
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
