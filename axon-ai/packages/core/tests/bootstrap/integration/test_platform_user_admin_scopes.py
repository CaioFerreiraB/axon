"""T100 — o apagamento de uma conta em cascata, ponta a ponta e sem rede (011 US9, SC-009; 003 SC-012; research R62).

A plataforma de verdade com a identidade ligada; o controller e o servidor MCP são trocas de porta. Uma chave `users`
cria `ana`; o admin semeado a põe no grupo de administração; `ana` gera dados em 003, 004, 007, 008, 009 e 012; o admin
a apaga. No `persistent`, nenhuma linha de nenhum schema cita `ana`, e a linha de comando apaga uma segunda conta pela
sessão de armazenamento dela.
"""

from __future__ import annotations

import asyncio
import base64
import dataclasses
import io
import os
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from bootstrap_testkit import (
    CHALLENGE,
    DEMO_ENDPOINT,
    PACKS_YAML,
    PUBLIC_URL,
    PUBLICO,
    USER_ASSISTANTS_E_ADMIN,
    VERIFIER,
    FakeServer,
    MemoryConfig,
    bearer,
    console_token,
    hidden_fields,
    write_config,
)
from graph_testkit import ANSWER, ScriptedController, tool_action

from axon_ai.bootstrap import cli, profiles
from axon_ai.bootstrap.identity import (
    TEST_CHAT_CALLBACK,
    TEST_CHAT_CLIENT,
    TEST_CHAT_SECRET,
    TEST_CONSOLE_CALLBACK,
    TEST_CONSOLE_CLIENT,
)
from axon_ai.bootstrap.profiles import TEST_ADMIN_GROUP, TEST_USERS_API_KEY, Profile
from axon_ai.bootstrap.wiring import Platform, platform
from axon_ai.llm.adapters.fake import ScriptedProvider
from axon_ai.mcp.adapters.memory import ScriptedMcpTransport, ScriptedServer
from axon_ai.mcp.ports import RemotePart, RemoteResult, RemoteTool

pytestmark = pytest.mark.us9

PG_DSN = os.environ.get("AXON_TEST_POSTGRES_DSN")
SCHEMAS: Final = ("assistants", "mcp", "http", "capabilities", "observability", "identity")
PNG: Final = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

GRAVAR = RemoteTool(
    name="gravar",
    description="Grava uma nota.",
    input_schema={"type": "object", "properties": {"texto": {"type": "string"}}, "required": ["texto"]},
)

ASSISTANTS: Final = f"""
assistants:
  geral:{PUBLICO}
    flow: chat
    packs: [generic]
    models:
      generation: ollama/qwen3:1.7b
      allow: ["ollama/*"]
  escritor:
    visibility: private
    auth:
      schemes: [oidc]
      allow: ["user:ana"]
    overrides: [auth]
    flow: agentic
    packs: [generic]
    mcp: [demo]
    allowed_tools: [demo.gravar]
    write_tools: [demo.gravar]
    models:
      generation: ollama/qwen3:1.7b
      controller: ctrl/controlador
      allow: ["ollama/*", "ctrl/*"]
{USER_ASSISTANTS_E_ADMIN}"""
"""`escritor` é privado, cita `user:ana` no YAML (vira aviso da 003) e tem a tool de escrita `demo.gravar`."""

MCP: Final = f"""
servers:
  demo:
    transport: http
    endpoint: {DEMO_ENDPOINT}
    policy:
      allowed_tools: [gravar]
      write_tools: [gravar]
"""


def _overrides() -> dict[str, Any]:
    image = RemotePart(kind="image", mime="image/png", data=PNG)
    result = RemoteResult(parts=(RemotePart(kind="text", text="gravado"), image))
    transport = ScriptedMcpTransport({DEMO_ENDPOINT: ScriptedServer(tools=(GRAVAR,), results={"gravar": result})})
    controller = ScriptedController([tool_action("demo.gravar", texto="nota"), ANSWER] * 4)
    return {
        "providers": {"ollama": ScriptedProvider(name="ollama", deltas=("Feito.",)), "ctrl": controller},
        "mcp_transports": {"http": transport, "sse": transport, "stdio": transport},
    }


@asynccontextmanager
async def _clients(plataforma: Platform) -> AsyncIterator[Callable[[], httpx.AsyncClient]]:
    """Um cliente por pessoa (cookies de sessão separados), todos no ciclo de vida da mesma app."""
    app = plataforma.app
    assert app is not None, plataforma.report.render()
    opened: list[httpx.AsyncClient] = []

    def new() -> httpx.AsyncClient:
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=PUBLIC_URL)
        opened.append(client)
        return client

    async with app.router.lifespan_context(app):
        try:
            yield new
        finally:
            for client in opened:
                await client.aclose()


async def _code(client: httpx.AsyncClient, *, username: str, password: str, console: bool, new_password: str) -> str:
    params = {
        "client_id": TEST_CONSOLE_CLIENT if console else TEST_CHAT_CLIENT,
        "redirect_uri": TEST_CONSOLE_CALLBACK if console else TEST_CHAT_CALLBACK,
        "response_type": "code",
        "scope": "openid profile email groups",
        "state": "s",
        "nonce": "n",
    }
    if console:
        params.update(code_challenge=CHALLENGE, code_challenge_method="S256")
    page = await client.get("/oauth2/authorize", params=params)
    if page.status_code == 302:
        return parse_qs(urlsplit(page.headers["location"]).query)["code"][0]
    response = await client.post(
        "/oauth2/login", data={**hidden_fields(page.text), "identifier": username, "password": password}
    )
    if response.status_code == 200:  # senha temporária: a troca obrigatória
        response = await client.post(
            "/oauth2/password",
            data={**hidden_fields(response.text), "new_password": new_password, "confirm": new_password},
        )
    assert response.status_code == 303, response.text
    return parse_qs(urlsplit(response.headers["location"]).query)["code"][0]


async def _tokens(client: httpx.AsyncClient, username: str, temporary: str) -> tuple[str, str]:
    """O token do chat e o da console de uma conta nova, trocando a senha temporária no primeiro login."""
    nova = f"senha-definitiva-de-{username}"
    code = await _code(client, username=username, password=temporary, console=False, new_password=nova)
    chat = await client.post(
        "/oauth2/token",
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": TEST_CHAT_CALLBACK},
        auth=(TEST_CHAT_CLIENT, TEST_CHAT_SECRET),
    )
    code = await _code(client, username=username, password=nova, console=True, new_password=nova)
    console = await client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TEST_CONSOLE_CALLBACK,
            "client_id": TEST_CONSOLE_CLIENT,
            "code_verifier": VERIFIER,
        },
    )
    assert chat.status_code == 200 and console.status_code == 200, (chat.text, console.text)
    return str(chat.json()["access_token"]), str(console.json()["access_token"])


async def _create(client: httpx.AsyncClient, users_key: str, username: str, groups: list[str]) -> str:
    created = await client.post(
        "/admin/v1/users",
        headers=bearer(users_key),
        json={"username": username, "email": f"{username}@exemplo.org", "name": username.title(), "groups": groups},
    )
    assert created.status_code == 201, created.text
    return str(created.json()["temporary_password"])


async def _populate(new: Callable[[], httpx.AsyncClient], root: str, users_key: str, username: str) -> None:
    """A conta gera dados em todos os módulos (US9 cen. 2)."""
    admin = new()
    temporary = await _create(admin, users_key, username, ["equipe"])
    posta = await admin.put(f"/admin/v1/users/{username}/groups/{TEST_ADMIN_GROUP}", headers=bearer(root))
    assert posta.status_code == 200, posta.text

    pessoa = new()
    chat, console = await _tokens(pessoa, username, temporary)
    subject = f"user:{username}"
    # 003: Assistant de usuário, chave e o `allow` de uma sobreposição de `auth` de autoria da conta
    assistant = {"name": "x", "flow": "chat", "packs": ["generic"], "models": {"generation": "ollama/qwen3:1.7b"}}
    assert (await pessoa.post("/v1/assistants", headers=bearer(chat), json=assistant)).status_code == 201
    chave = await admin.post("/admin/v1/keys", headers=bearer(root), json={"subject": subject})
    assert chave.status_code == 201, chave.text
    auth = {"schemes": ["oidc"], "allow": [subject, "user:root"], "version": None}
    sobreposta = await pessoa.put("/admin/v1/assistants/escritor/auth", headers=bearer(console), json=auth)
    assert sobreposta.status_code == 200, sobreposta.text
    # 007: servidor MCP de usuário
    mcp = {"alias": "~drive", "transport": "http", "endpoint": "https://drive.example/mcp"}
    mcp["policy"] = {"allowed_tools": ["ler"]}  # type: ignore[assignment]
    assert (await pessoa.post("/v1/mcp", headers=bearer(chat), json=mcp)).status_code == 201
    # 008 e 004: uma conversa com a tool de escrita, que devolve uma imagem
    conversa = await pessoa.post(
        "/v1/chat/completions",
        headers=bearer(chat),
        json={"model": "escritor", "messages": [{"role": "user", "content": "grave uma nota"}]},
    )
    assert conversa.status_code == 200, conversa.text
    # 009: um preço e a captura, de autoria da conta
    preco = {
        "provider": "ollama",
        "model": "modelo-de-teste",
        "input": "0",
        "output": "0",
        "effective_from": "2026-01-01",
    }
    assert (await pessoa.post("/admin/v1/prices", headers=bearer(console), json=preco)).status_code == 201
    versao = (await pessoa.get("/admin/v1/observability", headers=bearer(console))).json()["version"]
    captura = {"enabled": False, "version": versao}
    assert (
        await pessoa.put("/admin/v1/observability/capture", headers=bearer(console), json=captura)
    ).status_code == 200
    # 012: a conta altera outra conta (o `updated_by` dela)
    alvo = (await admin.get("/admin/v1/users/bia", headers=bearer(root))).json()
    patch = {"name": "Bia Alterada", "version": alvo["version"]}
    assert (await pessoa.patch("/admin/v1/users/bia", headers=bearer(console), json=patch)).status_code == 200


def _modules(report: dict[str, Any]) -> dict[str, dict[str, int]]:
    return {m["name"]: m["counts"] for m in report["modules"]}


async def _scenario(plataforma: Platform, *, users_key: str | None) -> None:
    async with _clients(plataforma) as new:
        root = await console_token(new())
        admin = new()
        if users_key is None:  # no `persistent` não há chave semeada: o admin emite a de provisionamento
            emitida = await admin.post(
                "/admin/v1/keys", headers=bearer(root), json={"subject": "svc:provisionamento", "scopes": ["users"]}
            )
            assert emitida.status_code == 201, emitida.text
            users_key = str(emitida.json()["key"])
        assert (
            await admin.post("/admin/v1/groups", headers=bearer(users_key), json={"name": "equipe"})
        ).status_code == 201
        await _create(admin, users_key, "bia", [])
        await _populate(new, root, users_key, "ana")
        await _assert_found(plataforma)

        apagada = await admin.delete("/admin/v1/users/ana", headers=bearer(root))

        assert apagada.status_code == 200, apagada.text
        report = apagada.json()
        assert report["complete"] is True and "deleted:" not in apagada.text
        assert [m["name"] for m in report["modules"]] == [
            "assistants",
            "mcp",
            "conversations",
            "audit",
            "observability",
        ]
        modulos = _modules(report)
        assert modulos["assistants"]["user_assistants"] == 1 and modulos["assistants"]["api_keys"] == 1
        assert modulos["assistants"]["override_entries"] == 1 and modulos["assistants"]["authored"] >= 1
        assert modulos["mcp"] == {"servers": 1}
        assert modulos["conversations"] == {"conversations": 1, "attachments": 1}
        assert modulos["audit"] == {"audit_records": 1}
        assert modulos["observability"] == {"prices": 1, "destination_settings": 1}
        (assistants,) = [m for m in report["modules"] if m["name"] == "assistants"]
        assert assistants["warnings"] == ["referências na configuração (assistants.yaml): escritor"]
        assert report["identity"]["account"] == 1 and report["identity"]["authored"] >= 1

        await _assert_nothing_left(plataforma)

        # um usuário novo com o mesmo nome não herda nada
        temporary = await _create(admin, users_key, "ana", [])
        nova = new()
        chat, _ = await _tokens(nova, "ana", temporary)
        assert (await nova.get("/v1/assistants", headers=bearer(chat))).json()["data"] == []
        assert (await nova.get("/v1/mcp", headers=bearer(chat))).json()["data"] == []
        assert (await nova.get("/v1/conversations", headers=bearer(chat))).json()["data"] == []
        chaves = (await admin.get("/admin/v1/keys", headers=bearer(root))).json()["data"]
        assert [k for k in chaves if k["subject"] == "user:ana"] == []


async def _found(plataforma: Platform) -> list[tuple[str, str, str, int]]:
    """As colunas de texto, JSON ou lista dos seis schemas que citam `user:ana` ou têm `ana` como valor inteiro."""
    import psycopg

    assert plataforma.settings.database_url is not None
    achados = []
    async with await psycopg.AsyncConnection.connect(plataforma.settings.database_url) as connection:
        cursor = await connection.execute(
            "SELECT table_schema, table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = ANY(%s) AND data_type IN ('text', 'jsonb', 'ARRAY')",
            (list(SCHEMAS),),
        )
        for schema, table, column, data_type in await cursor.fetchall():
            exact = f" OR {column} = 'ana'" if data_type == "text" else ""
            cursor = await connection.execute(
                f"SELECT count(*) FROM {schema}.{table} WHERE {column}::text LIKE '%%user:ana%%'{exact}"
            )
            row = await cursor.fetchone()
            if row is not None and row[0]:
                achados.append((schema, table, column, int(row[0])))
    return achados


async def _assert_found(plataforma: Platform) -> None:
    """Antes do apagamento, a varredura acha `ana` em cada módulo — prova de que ela enxerga o que procura."""
    if plataforma.settings.database_url is None:
        return
    schemas = {schema for schema, *_ in await _found(plataforma)}
    assert schemas == set(SCHEMAS), schemas


async def _assert_nothing_left(plataforma: Platform) -> None:
    """No `persistent`, a varredura de todos os schemas (SC-009; 003 SC-012). Na memória, não há o que varrer."""
    if plataforma.settings.database_url is None:
        return
    assert await _found(plataforma) == []


def _settings(tmp_path: Path, **extra: Any) -> Any:
    return write_config(
        tmp_path,
        packs=PACKS_YAML,
        assistants=ASSISTANTS,
        mcp=MCP,
        identity_enabled=True,
        public_url=PUBLIC_URL,
        **extra,
    )


async def test_us9_apagar_em_cascata_no_perfil_test(tmp_path: Path) -> None:
    plataforma = platform(config=MemoryConfig(_settings(tmp_path)), overrides=_overrides())
    assert plataforma.ok, plataforma.report.render()
    await _scenario(plataforma, users_key=TEST_USERS_API_KEY)


# --- o mesmo roteiro no `persistent`, com a varredura de todos os schemas e a linha de comando -----------------------

MASTER_KEY: Final = bytes(range(32))

CLIENTS: Final = f"""version: 1
clients:
  {TEST_CHAT_CLIENT}:
    type: confidential
    secret: open_webui
    audience: axon
    redirect_uris: [{TEST_CHAT_CALLBACK}]
  {TEST_CONSOLE_CLIENT}:
    type: public
    audience: axon-admin
    redirect_uris: [{TEST_CONSOLE_CALLBACK}]
"""
"""Os mesmos clientes do `test`: no `persistent`, o arquivo de clientes é obrigatório."""


def _persistent_settings(tmp_path: Path, dsn: str) -> Any:
    clients = tmp_path / "identity.yaml"
    clients.write_text(CLIENTS, encoding="utf-8")
    settings = _settings(tmp_path, master_key=MASTER_KEY, identity_clients_file=clients)
    return dataclasses.replace(settings, profile="persistent", database_url=dsn)


def _persistent_for_tests() -> Profile:
    """O `persistent` com o relógio, o provider, o verificador e os segredos da identidade (admin semeado) do `test`."""
    real = profiles._persistent_profile()
    test = profiles._test_profile()
    factories = dict(real.factories)
    for port in ("clock", "providers", "oidc", "identity_secrets"):
        factories[port] = test.factories[port]
    return dataclasses.replace(real, factories=factories)


@pytest.fixture
async def banco(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[str]:
    if PG_DSN is None:
        pytest.skip("defina AXON_TEST_POSTGRES_DSN")
    import psycopg

    monkeypatch.setitem(profiles.PROFILES, "persistent", _persistent_for_tests)  # type: ignore[index]
    async with await psycopg.AsyncConnection.connect(PG_DSN, autocommit=True) as connection:
        for schema in SCHEMAS:
            await connection.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
    yield PG_DSN


async def test_us9_apagar_em_cascata_no_persistent(banco: str, tmp_path: Path) -> None:
    settings = _persistent_settings(tmp_path, banco)
    plataforma = platform(config=MemoryConfig(settings), overrides=_overrides())
    assert plataforma.ok, plataforma.report.render()
    await _scenario(plataforma, users_key=None)


async def test_us9_a_linha_de_comando_apaga_pela_sessao(
    banco: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Achado C1: no `persistent`, `axon users delete` monta os apagadores sobre a sessão de armazenamento do comando —
    o Assistant, o servidor e a conversa da conta somem também."""
    settings = _persistent_settings(tmp_path, banco)
    plataforma = platform(config=MemoryConfig(settings), overrides=_overrides())
    assert plataforma.ok, plataforma.report.render()
    async with _clients(plataforma) as new:
        root = await console_token(new())
        admin = new()
        emitida = await admin.post(
            "/admin/v1/keys", headers=bearer(root), json={"subject": "svc:provisionamento", "scopes": ["users"]}
        )
        users_key = str(emitida.json()["key"])
        assert (
            await admin.post("/admin/v1/groups", headers=bearer(users_key), json={"name": "equipe"})
        ).status_code == 201
        await _create(admin, users_key, "bia", [])
        await _populate(new, root, users_key, "ana")

    for name, value in {
        "AXON_PROFILE": "persistent",
        "AXON_DATABASE_URL": banco,
        "AXON_PACKS_FILE": str(settings.packs_file),
        "AXON_ASSISTANTS_FILE": str(settings.assistants_file),
        "AXON_MCP_FILE": str(settings.mcp_file),
        "AXON_IDENTITY_ENABLED": "true",
        "AXON_PUBLIC_URL": PUBLIC_URL,
        "AXON_MASTER_KEY": base64.b64encode(MASTER_KEY).decode(),
        "AXON_IDENTITY_CLIENTS_FILE": str(settings.identity_clients_file),
    }.items():
        monkeypatch.setenv(name, value)
    out, err = io.StringIO(), io.StringIO()
    code = await asyncio.to_thread(cli.main, ["users", "delete", "ana", "--yes"], server=FakeServer(), out=out, err=err)

    assert code == 0, err.getvalue()
    texto = out.getvalue()
    assert re.search(r"^assistants: .*user_assistants=1", texto, re.M), texto
    assert re.search(r"^mcp: servers=1$", texto, re.M), texto
    assert re.search(r"^conversations: attachments=1 conversations=1$", texto, re.M), texto
    await _assert_nothing_left(plataforma)
