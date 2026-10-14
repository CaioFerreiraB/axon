"""Fábricas dos testes da 011: etapas de teste, configuração em memória e arquivos de exemplo."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import parse_qs, urlsplit

import httpx

from ai_core.bootstrap.identity import (
    TEST_ADMIN_PASSWORD,
    TEST_ADMIN_USERNAME,
    TEST_CHAT_CALLBACK,
    TEST_CHAT_CLIENT,
    TEST_CHAT_SECRET,
    TEST_CONSOLE_CALLBACK,
    TEST_CONSOLE_CLIENT,
)
from ai_core.bootstrap.lifecycle import BootContext, Stage
from ai_core.bootstrap.profiles import TEST_ADMIN_GROUP, TEST_API_KEY, TEST_OIDC_TOKEN
from ai_core.bootstrap.settings import TEST_PROFILE, Settings

if TYPE_CHECKING:
    from ai_core.bootstrap.wiring import Platform

ASSISTANT: Final = "geral"
MODEL: Final = "qwen3:1.7b"
MODEL_ID: Final = f"{ASSISTANT}/{MODEL}"

PACKS_YAML: Final = """
packs:
  generic:
    enabled: true
"""

PACKS_YAML_COM_QUEBRADO: Final = """
packs:
  generic:
    enabled: true
  inexistente:
    enabled: true
"""

PUBLICO: Final = """
    visibility: public
    auth:
      schemes: [oidc, api_key]
      allow: ["*"]"""
"""ACL de um Assistant público: `*` deixa entrar o `user:test` das credenciais exportadas pelo perfil de teste."""

USER_ASSISTANTS_E_ADMIN: Final = f"""
user_assistants:
  policies:
    - match: "*"
      packs: [generic]
      flows: [chat]
      models:
        allow: ["ollama/*"]
      limits: {{ rpm: 30 }}
api_keys:
  admin_group: {TEST_ADMIN_GROUP}
"""
"""Qualquer Principal cria Assistants de usuário, e a chave de teste administra (grupo `admin`)."""

ASSISTANTS_YAML: Final = f"""
assistants:
  {ASSISTANT}:{PUBLICO}
    flow: chat
    packs: [generic]
    models:
      generation: ollama/{MODEL}
      allow: ["ollama/*"]
{USER_ASSISTANTS_E_ADMIN}"""

ASSISTANTS_YAML_SEM_PACK: Final = f"""
assistants:
  {ASSISTANT}:{PUBLICO}
    packs: [generic]
    models:
      generation: ollama/{MODEL}
      allow: ["ollama/*"]
  orfao:{PUBLICO}
    packs: [inexistente]
    models:
      generation: ollama/{MODEL}
      allow: ["ollama/*"]
"""

ASSISTANTS_YAML_QUEBRADO: Final = "assistentes: {}\n"
"""Erro de **arquivo** (chave de topo desconhecida): o boot para. Erro de um Assistant só o deixa indisponível."""


class Recorder:
    """Guarda a ordem em que as etapas rodaram e em que os recursos foram liberados."""

    def __init__(self) -> None:
        self.ran: list[str] = []
        self.closed: list[str] = []

    def stage(self, name: str, *, critical: bool = True, fails: Exception | None = None) -> Stage:
        def run(ctx: BootContext) -> None:
            self.ran.append(name)
            ctx.on_close(lambda: self.closed.append(name))
            if fails is not None:
                raise fails

        return Stage(name=name, run=run, critical=critical)

    def degrading_stage(self, name: str, detail: str) -> Stage:
        """Etapa que conclui, mas relata degradação — é o caso de um pack em erro."""

        def run(ctx: BootContext) -> None:
            self.ran.append(name)
            ctx.parts[f"{name}:degraded"] = detail

        return Stage(name=name, run=run, critical=False)


class MemoryConfig:
    """Adapter em memória da porta `ConfigSource`."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings(profile=TEST_PROFILE)

    def load(self) -> Settings:
        return self._settings


def write_config(
    tmp_path: Path, *, packs: str = PACKS_YAML, assistants: str = ASSISTANTS_YAML, mcp: str | None = None, **extra: Any
) -> Settings:
    """Escreve os arquivos e devolve a configuração que os aponta. `mcp`: o `mcp.yaml` da 007, quando dado."""
    packs_file = tmp_path / "packs.yaml"
    assistants_file = tmp_path / "assistants.yaml"
    packs_file.write_text(packs, encoding="utf-8")
    assistants_file.write_text(assistants, encoding="utf-8")
    mcp_file = None
    if mcp is not None:
        mcp_file = tmp_path / "mcp.yaml"
        mcp_file.write_text(mcp, encoding="utf-8")
    fields: dict[str, Any] = {"profile": TEST_PROFILE, "packs_file": packs_file, "assistants_file": assistants_file}
    return Settings(**(fields | {"mcp_file": mcp_file} | extra))


# --- Fase 3: registry MCP e agentic ----------------------------------------------------------------------------------

DEMO_ENDPOINT: Final = "https://demo.test/mcp"

MCP_YAML: Final = f"""
servers:
  demo:
    transport: http
    endpoint: {DEMO_ENDPOINT}
    policy:
      allowed_tools: [eco]
"""
"""Um servidor global do operador. No perfil `test`, o transporte é programado: nada sai para a rede."""

MCP_YAML_COM_PROBLEMA: Final = (
    MCP_YAML
    + """
  sem_politica:
    transport: http
    endpoint: https://outro.test/mcp
"""
)
"""`sem_politica` não declara `policy.allowed_tools`: fica indisponível, e o resto sobe (007, 011 FR-003)."""

MCP_YAML_COM_CREDENCIAL: Final = (
    MCP_YAML
    + """
  cofre:
    transport: http
    endpoint: https://cofre.test/mcp
    auth: { type: bearer, credential: falta }
    policy:
      allowed_tools: [abrir]
"""
)
"""`cofre` referencia `AI_CORE_MCP_SECRET_FALTA`, que não existe: a etapa `mcp_registry` acusa (R23)."""

AGENTIC_ASSISTANTS_YAML: Final = f"""
assistants:
  {ASSISTANT}:{PUBLICO}
    flow: chat
    packs: [generic]
    models:
      generation: ollama/{MODEL}
      allow: ["ollama/*"]
  pesquisador:{PUBLICO}
    flow: agentic
    packs: [generic]
    mcp: [demo]
    models:
      generation: ollama/{MODEL}
      controller: ollama/{MODEL}
      allow: ["ollama/*"]
  perdido:{PUBLICO}
    flow: agentic
    packs: [generic]
    mcp: [nao_existe]
    models:
      generation: ollama/{MODEL}
      controller: ollama/{MODEL}
      allow: ["ollama/*"]
{USER_ASSISTANTS_E_ADMIN}"""
"""`pesquisador` usa o MCP do arquivo; `perdido` referencia um alias que não existe e fica indisponível."""


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


OIDC: Final = bearer(TEST_OIDC_TOKEN)
"""Cabeçalho da superfície pública (`/v1`) no perfil de teste."""

CHAVE: Final = bearer(TEST_API_KEY)
"""Cabeçalho da superfície privada (`/private/v1`) no perfil de teste."""


def body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "qual é a capital?"}],
    }
    return base | overrides


class FakeServer:
    """Servidor injetado no comando: registra a chamada em vez de abrir porta."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, str, int, float]] = []

    def __call__(self, app: Any, host: str, port: int, grace: float) -> None:
        self.calls.append((app, host, port, grace))


def names(stages: Sequence[Any]) -> list[str]:
    return [stage.name for stage in stages]


Factory = Callable[[Settings], Any]


# --- Fase 9: identidade da plataforma no perfil de teste (R39, R43) ---------------------------------------------------

PUBLIC_URL: Final = "http://localhost:8000"
VERIFIER: Final = "v" * 64
CHALLENGE: Final = "w1TpKUdYE9hUAcNSeeSRFioHDxfUxuHho_JHAfZ_vDM"
"""S256 de `VERIFIER`: o PKCE do cliente público da console."""


@asynccontextmanager
async def serving(plataforma: Platform) -> AsyncIterator[httpx.AsyncClient]:
    app = plataforma.app
    assert app is not None, plataforma.report.render()
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=PUBLIC_URL) as client:
            yield client


def hidden_fields(html: str) -> dict[str, str]:
    return dict(re.findall(r'<input type="hidden" name="([a-z_]+)" value="([^"]*)"', html))


async def login_code(
    client: httpx.AsyncClient, *, client_id: str, callback: str, username: str, password: str, pkce: bool = False
) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": callback,
        "response_type": "code",
        "scope": "openid profile email groups",
        "state": "s",
        "nonce": "n",
    }
    if pkce:
        params.update(code_challenge=CHALLENGE, code_challenge_method="S256")
    page = await client.get("/oauth2/authorize", params=params)
    if page.status_code == 302:  # sessão já aberta
        return parse_qs(urlsplit(page.headers["location"]).query)["code"][0]
    assert page.status_code == 200, page.text
    response = await client.post(
        "/oauth2/login", data={**hidden_fields(page.text), "identifier": username, "password": password}
    )
    assert response.status_code == 303, response.text
    return parse_qs(urlsplit(response.headers["location"]).query)["code"][0]


async def chat_token(
    client: httpx.AsyncClient, username: str = TEST_ADMIN_USERNAME, password: str = TEST_ADMIN_PASSWORD
) -> str:
    code = await login_code(
        client, client_id=TEST_CHAT_CLIENT, callback=TEST_CHAT_CALLBACK, username=username, password=password
    )
    response = await client.post(
        "/oauth2/token",
        data={"grant_type": "authorization_code", "code": code, "redirect_uri": TEST_CHAT_CALLBACK},
        auth=(TEST_CHAT_CLIENT, TEST_CHAT_SECRET),
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


async def console_token(client: httpx.AsyncClient) -> str:
    code = await login_code(
        client,
        client_id=TEST_CONSOLE_CLIENT,
        callback=TEST_CONSOLE_CALLBACK,
        username=TEST_ADMIN_USERNAME,
        password=TEST_ADMIN_PASSWORD,
        pkce=True,
    )
    response = await client.post(
        "/oauth2/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": TEST_CONSOLE_CALLBACK,
            "client_id": TEST_CONSOLE_CLIENT,
            "code_verifier": VERIFIER,
        },
    )
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
