"""A plataforma do e2e da console (013 T015, R11): `platform(profile="test")` com a identidade ligada, em memória, sem
rede, servida pelo uvicorn em 127.0.0.1:8765. O `vite preview` (4173) repassa a ela os prefixos do core, como o nginx
da instalação, e a origem da console é o emissor (`AI_CORE_PUBLIC_URL`).

Semeia o que as telas precisam: o admin `ana` (senha e Google), `bia` fora do grupo de administração, Assistants com
e sem `overrides`, uma sobreposição ativa e outra que o YAML deixou inativa, servidores MCP (dois pela API, um do
arquivo do operador sem credencial), 90 dias de uso e preços com vigência. O "Google" é uma rota local que aprova o
pedido como `ana` e devolve ao retorno da 012.

Rode a partir de `ai-core/`: `uv run python console/e2e/serve_platform.py`.
"""

from __future__ import annotations

import asyncio
import os
import random
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Final

import uvicorn
from fastapi.responses import RedirectResponse

from ai_core.assistants.api import ModelsOverride, Principal
from ai_core.assistants.domain.overrides import StoredOverride
from ai_core.bootstrap.settings import InMemoryConfigSource, Settings
from ai_core.bootstrap.wiring import Platform, platform
from ai_core.graph.adapters.clock import SystemClock
from ai_core.identity.adapters.memory import SimulatedUpstreamOidc
from ai_core.identity.api import AccountDraft
from ai_core.llm.api import ModelRef
from ai_core.mcp.adapters.memory import ScriptedMcpTransport, ScriptedServer
from ai_core.mcp.api import McpServerDraft, SecurityPolicy
from ai_core.mcp.domain.records import RemoteTool
from ai_core.observability.ports import ModelCallRow

CONSOLE: Final = os.environ.get("CONSOLE_ORIGIN", "http://127.0.0.1:4173")
HOST: Final = "127.0.0.1"
PORT: Final = int(os.environ.get("CONSOLE_E2E_PORT", "8765"))

ADMIN: Final = ("ana", "ana@exemplo.org", "Ana Souza", "senha-da-ana-no-e2e")
OUTSIDER: Final = ("bia", "bia@exemplo.org", "Bia Lima", "senha-da-bia-no-e2e")

IDENTITY_YAML: Final = f"""
version: 1
clients:
  console:
    type: public
    audience: ai-core-admin
    redirect_uris: [{CONSOLE}/callback]
    post_logout_redirect_uris: [{CONSOLE}/]
  open-webui:
    type: confidential
    secret: open_webui
    audience: ai-core
    redirect_uris: [http://localhost:3000/oauth/oidc/callback]
"""

PACKS_YAML: Final = """
packs:
  generic:
    enabled: true
"""

ASSISTANTS_YAML: Final = """
assistants:
  geral:
    description: Uso geral, com ferramentas
    visibility: public
    flow: agentic
    packs: [generic]
    overrides: [models, mcp]
    models:
      generation: ollama/qwen3:1.7b
      controller: ollama/qwen3:1.7b
      allow: ["ollama/*", "openrouter/*"]
    auth:
      schemes: [oidc, api_key]
      allow: ["*"]
  documentos:
    description: Perguntas sobre documentos
    visibility: private
    flow: chat
    packs: [generic]
    overrides: [models]
    models:
      generation: ollama/qwen3:1.7b
      allow: ["ollama/*"]
    auth:
      schemes: [oidc, api_key]
      allow: ["group:admin"]
  rascunho:
    description: Conversa simples, local
    visibility: public
    flow: chat
    packs: [generic]
    models:
      generation: ollama/qwen3:1.7b
      allow: ["ollama/*"]
    auth:
      schemes: [oidc, api_key]
      allow: ["*"]
api_keys:
  admin_group: admin
"""

MCP_YAML: Final = """
servers:
  planilhas:
    transport: http
    endpoint: https://planilhas.interno.exemplo.org/mcp
    description: Planilhas
    auth:
      type: bearer
      credential: planilhas
    policy:
      allowed_tools: [ler, escrever]
      write_tools: [escrever]
"""

MODELS: Final = (
    ("openrouter", "openai/gpt-4.1-mini", "geral", 120),
    ("openai", "gpt-4.1-nano", "documentos", 70),
    ("ollama", "qwen3:1.7b", "rascunho", 30),
)


def _write(directory: Path) -> Settings:
    files = {
        "identity.yaml": IDENTITY_YAML,
        "packs.yaml": PACKS_YAML,
        "assistants.yaml": ASSISTANTS_YAML,
        "mcp.yaml": MCP_YAML,
    }
    for name, content in files.items():
        (directory / name).write_text(content, encoding="utf-8")
    return Settings(
        profile="test",
        packs_file=directory / "packs.yaml",
        assistants_file=directory / "assistants.yaml",
        mcp_file=directory / "mcp.yaml",
        identity_enabled=True,
        public_url=CONSOLE,
        identity_clients_file=directory / "identity.yaml",
        usage_timezone="America/Sao_Paulo",
    )


async def _seed(plataforma: Platform) -> None:
    identity = plataforma.identity
    assistants = plataforma.assistants
    mcp = plataforma.mcp
    usage = plataforma.usage
    assert identity and assistants and mcp and usage
    now = datetime.now(UTC)

    await identity.create_group("equipe", actor="cli")
    for (username, email, name, password), groups in ((ADMIN, {"admin", "equipe"}), (OUTSIDER, {"equipe"})):
        draft = AccountDraft(username=username, email=email, name=name, groups=frozenset(groups))
        await identity.create_with_password(draft, password, actor="cli")
    login = await identity.view()
    await identity.set_google(True, actor="cli", version=login.version)

    for alias, description, tools, write in (
        ("arquivos", "Arquivos da equipe", ("listar", "ler", "mover", "apagar"), ("mover", "apagar")),
        ("agenda", "Agenda compartilhada", ("listar_eventos", "criar_evento"), ("criar_evento",)),
    ):
        await mcp.create_global(
            McpServerDraft(
                alias=alias,
                transport="http",
                endpoint=f"https://mcp.exemplo.org/{alias}",
                description=description,
                policy=SecurityPolicy(allowed_tools=tools, write_tools=write),
            )
        )

    ana = Principal(subject="user:ana", scheme="oidc", groups=frozenset({"admin"}))
    await assistants.override_models(
        "geral",
        ModelsOverride(
            roles={
                "generation": ModelRef.parse("openrouter/openai/gpt-4.1-mini"),
                "controller": ModelRef.parse("ollama/qwen3:1.7b"),
            }
        ),
        actor=ana,
        version=None,
    )
    # Uma sobreposição gravada sobre outro YAML: a impressão digital não casa, e a 003 a mostra inativa.
    await plataforma.parts["system_overrides"].put(
        StoredOverride(
            assistant="documentos",
            section="models",
            payload={"roles": {"generation": "ollama/gemma3:1b"}},
            fingerprint="yaml-do-deploy-anterior",
            version=2,
            updated_by="user:ana",
            updated_at=now - timedelta(days=7),
        ),
        expected_version=None,
    )

    today = now.date()
    await usage.add_price(
        provider="openrouter",
        model="openai/gpt-4.1-mini",
        usd_per_mtok_in=Decimal("0.30"),
        usd_per_mtok_out=Decimal("1.20"),
        effective_from=today - timedelta(days=80),
        actor="user:ana",
    )
    await usage.add_price(
        provider="openrouter",
        model="openai/gpt-4.1-mini",
        usd_per_mtok_in=Decimal("0.40"),
        usd_per_mtok_out=Decimal("1.60"),
        effective_from=today - timedelta(days=12),
        actor="user:ana",
    )
    await usage.add_price(
        provider="openai",
        model="gpt-4.1-nano",
        usd_per_mtok_in=Decimal("0.10"),
        usd_per_mtok_out=Decimal("0.40"),
        effective_from=today - timedelta(days=95),
        actor="user:ana",
    )
    rng = random.Random(13)
    rows: list[ModelCallRow] = []
    for back in range(90, 0, -1):
        day = now - timedelta(days=back)
        for provider, model, assistant, volume in MODELS:
            for index in range(rng.randint(volume // 3, volume)):
                rows.append(
                    ModelCallRow(
                        request_id=f"{assistant}-{back}-{index // 2}",
                        at=day.replace(hour=12) + timedelta(minutes=index),
                        origin="production",
                        assistant=assistant,
                        provider=provider,
                        model=model,
                        role="generation",
                        input_tokens=rng.randint(1_500, 6_000),
                        output_tokens=rng.randint(200, 900),
                        duration_ms=float(rng.randint(300, 2_400)),
                    )
                )
    await plataforma.parts["usage_store"].append(rows, [])


def main() -> None:
    directory = Path(tempfile.mkdtemp(prefix="console-e2e-"))
    settings = _write(directory)
    transport = ScriptedMcpTransport(
        {
            "https://mcp.exemplo.org/arquivos": ScriptedServer(
                tools=tuple(RemoteTool(name=name) for name in ("listar", "ler", "mover", "apagar"))
            ),
            "https://mcp.exemplo.org/agenda": ScriptedServer(
                tools=tuple(RemoteTool(name=name) for name in ("listar_eventos", "criar_evento"))
            ),
        }
    )
    google = SimulatedUpstreamOidc(authorize_url=f"http://{HOST}:{PORT}/__google/autorizar")
    plataforma = platform(
        config=InMemoryConfigSource(settings),
        overrides={
            "clock": SystemClock(),
            "mcp_transports": {"http": transport, "sse": transport, "stdio": transport},
            "identity_upstream": google,
        },
    )
    if not plataforma.ok or plataforma.app is None:
        raise SystemExit(plataforma.report.render())
    asyncio.run(_seed(plataforma))

    @plataforma.app.get("/__google/autorizar", include_in_schema=False)
    async def google_consent(state: str) -> RedirectResponse:
        """O Google do e2e: aprova como a conta `ana` (e-mail verificado) e volta ao retorno da 012."""
        code = google.approve(state, sub="google-ana", email=ADMIN[1])
        return RedirectResponse(f"{CONSOLE}/oauth2/google/callback?state={state}&code={code}", status_code=302)

    uvicorn.run(plataforma.app, host=HOST, port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
