"""T085 — a superfície de administração `/admin/v1` (US9; contracts/admin-api.md; ADR-031; research R43 a R49).

A app com os serviços reais em memória: 003 (acesso e sobreposições), 006 (Model Router com providers programados),
007 (MCP), 009 (uso, preços e destinos) e 012 (contas e login). Para cada rota: admin pelo token da console e pela
chave; quem não administra recebe o 404 de rota inexistente; o token do chat é 401; erros com `param`; `no-store` e
identificador em toda resposta; nenhum segredo em resposta nenhuma (SC-009).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from typing import Any, Final

import httpx
import pytest
from assistants_testkit import assistant, claims, config
from fastapi.testclient import TestClient
from graph_testkit import RecordingTraceSink
from http_testkit import ADMIN_KEY, CREATED, SVC_KEY, Platform, bearer
from identity_testkit import GOOGLE, MASTER_KEY, OPEN_WEBUI_SECRET, harness
from mcp_testkit import build, scripted

from axon_ai.assistants.adapters.memory import InMemorySystemOverrideStore
from axon_ai.graph.adapters.clock import FixedClock as GraphFixedClock
from axon_ai.http.adapters.development import FixedClock
from axon_ai.http.ports import AdminSeams, InstanceBranding
from axon_ai.llm.adapters.fake import ScriptedProvider
from axon_ai.llm.service import ModelRoutingService
from axon_ai.mcp.ports import RemoteTool
from axon_ai.observability.adapters.cipher import AesGcmCipher
from axon_ai.observability.adapters.langfuse import LangfuseDestination
from axon_ai.observability.adapters.memory import (
    InMemoryDestinationSettingsStore,
    InMemoryPriceStore,
    InMemoryUsageStore,
    RecordingLangfuseTransport,
)
from axon_ai.observability.domain.settings import InstallationDestinations, LangfuseCredentials
from axon_ai.observability.ports import ModelCallRow
from axon_ai.observability.service import DestinationService, UsageService

pytestmark = pytest.mark.us9

CONSOLE_ROOT: Final = "tok-console-root"
"""Token da console (audiência `ai-core-admin`) de `user:root`, do grupo de administração `operadores`."""
CONSOLE_ANA: Final = "tok-console-ana"
"""Token da console de `user:ana`, fora do grupo de administração."""
CHAT_ROOT: Final = "tok-chat-root"
"""Token do Open WebUI (audiência `ai-core`) do mesmo admin: não alcança a administração (ADR-031)."""

AGENDA_URL: Final = "https://agenda.example/mcp"
LANGFUSE_SECRET: Final = "sk-lf-segredo-de-teste"
MINI: Final = "openrouter/openai/gpt-4.1-mini"
GLOBAL_MCP: Final = {
    "alias": "agenda",
    "transport": "http",
    "endpoint": AGENDA_URL,
    "user_access": True,
    "policy": {"allowed_tools": ["listar", "marcar"]},
}
SECRETS: Final = (LANGFUSE_SECRET, OPEN_WEBUI_SECRET, GOOGLE.client_secret, "fast-v1$", MASTER_KEY.hex())


@dataclass
class Kit:
    client: TestClient
    platform: Platform
    identity: Any
    transport: RecordingLangfuseTransport
    responses: list[tuple[str, str, httpx.Response]] = field(default_factory=list)

    def call(self, method: str, path: str, token: str | None = CONSOLE_ROOT, body: Any = None) -> httpx.Response:
        headers = bearer(token) if token is not None else {}
        response = self.client.request(method, f"/admin/v1{path}", headers=headers, json=body)
        self.responses.append((method, path, response))
        return response


def _kit(
    *,
    installation: InstallationDestinations | None = None,
    cipher: bool = True,
    google: bool = False,
    seams: bool = True,
) -> Kit:
    identity = harness(google=google)
    asyncio.run(identity.service.start())
    asyncio.run(identity.add_account("root", name="Root da Silva", groups={"admin"}))
    usage_store = InMemoryUsageStore()
    asyncio.run(
        usage_store.append(
            [
                ModelCallRow(
                    request_id="req-1",
                    at=CREATED - timedelta(days=1),
                    origin="production",
                    assistant="geral",
                    provider="openrouter",
                    model="openai/gpt-4.1-mini",
                    role="generation",
                    input_tokens=1_000,
                    output_tokens=200,
                    duration_ms=800.0,
                )
            ],
            [],
        )
    )
    usage = UsageService(store=usage_store, prices=InMemoryPriceStore(), clock=FixedClock(CREATED))
    transport = RecordingLangfuseTransport()
    destinations = DestinationService(
        store=InMemoryDestinationSettingsStore(),
        cipher=AesGcmCipher(MASTER_KEY) if cipher else None,
        installation=installation or InstallationDestinations(),
        transport=transport,
        langfuse=LangfuseDestination(transport, clock=lambda: CREATED),
        usage=None,
        clock=FixedClock(CREATED),
    )
    routing = ModelRoutingService(
        providers={
            "openrouter": ScriptedProvider(name="openrouter", known_models=["openai/gpt-4.1-mini", "nvidia/nemotron"]),
            "ollama": ScriptedProvider(name="ollama", unready="provider inalcançável em http://ollama.test/v1"),
            "informa": ScriptedProvider(name="informa", reports_cost=True),
        },
        trace=RecordingTraceSink(),
        clock=GraphFixedClock(CREATED),
    )

    def admin_seams(platform: Platform) -> AdminSeams:
        return AdminSeams(
            assistants=platform.assistants,
            models=routing,
            usage=usage,
            prices=usage,
            destinations=destinations,
            accounts=identity.service,
            login=identity.service,
        )

    platform = Platform(
        config(
            {
                "geral": assistant(
                    flow="chat",
                    overrides=["models", "mcp"],
                    models={"generation": "openrouter/nvidia/nemotron", "allow": ["openrouter/*"]},
                ),
                "fixo": assistant(flow="chat"),
            }
        ),
        mcp=build(servers={AGENDA_URL: scripted(RemoteTool(name="listar"), RemoteTool(name="marcar"))}).service,
        oidc_tokens={
            CONSOLE_ROOT: claims("root", groups=["operadores"], aud="ai-core-admin", ttl=3600),
            CONSOLE_ANA: claims("ana", aud="ai-core-admin", ttl=3600),
            CHAT_ROOT: claims("root", groups=["operadores"], ttl=3600),
        },
        system_overrides=InMemorySystemOverrideStore(),
        flow_roles={"chat": ("generation",), "agentic": ("generation", "controller")},
        admin_seams=admin_seams if seams else None,
        instance=InstanceBranding(name="Agentic", logo_url="/oauth2/assets/logo"),
    )
    return Kit(client=TestClient(platform.app), platform=platform, identity=identity, transport=transport)


@pytest.fixture
def kit() -> Kit:
    return _kit()


def _error(response: httpx.Response) -> dict[str, Any]:
    return response.json()["error"]  # type: ignore[no-any-return]


def _stable(response: httpx.Response) -> dict[str, str]:
    """Os cabeçalhos que não mudam de uma requisição para outra (o identificador muda)."""
    return {name: value for name, value in response.headers.items() if name != "x-request-id"}


# --- toda rota do contrato -------------------------------------------------------------------------------------------

ROUTES: Final[list[tuple[str, str, Any]]] = [
    ("GET", "/me", None),
    ("GET", "/assistants", None),
    ("GET", "/assistants/geral", None),
    ("PUT", "/assistants/geral/models", {"roles": {"generation": MINI}, "version": None}),
    ("PUT", "/assistants/geral/mcp", {"aliases": [], "version": None}),
    ("DELETE", "/assistants/geral/overrides/models?version=1", None),
    ("GET", "/assistants/geral/history", None),
    ("POST", "/assistants/geral/models/check", {"role": "generation", "model": MINI}),
    ("GET", "/providers", None),
    ("GET", "/mcp", None),
    ("POST", "/mcp", GLOBAL_MCP),
    ("GET", "/mcp/agenda", None),
    ("PUT", "/mcp/agenda", GLOBAL_MCP),
    ("DELETE", "/mcp/agenda", None),
    ("GET", "/mcp/agenda/health", None),
    ("GET", "/usage", None),
    ("GET", "/prices", None),
    (
        "POST",
        "/prices",
        {"provider": "ollama", "model": "qwen3", "input": "0", "output": "0", "effective_from": "2026-09-01"},
    ),
    ("GET", "/prices/unpriced", None),
    ("GET", "/observability", None),
    ("PUT", "/observability/langfuse", {"enabled": False, "version": 0}),
    ("PUT", "/observability/capture", {"enabled": False, "version": 0}),
    ("POST", "/observability/langfuse/test", {}),
    ("GET", "/users", None),
    ("POST", "/users", {"username": "bia", "email": "bia@exemplo.org", "name": "Bia"}),
    ("GET", "/users/root", None),
    ("PATCH", "/users/root", {"name": "Root", "version": 1}),
    ("POST", "/users/root/password", None),
    ("POST", "/users/root/disable", None),
    ("POST", "/users/root/enable", None),
    ("DELETE", "/users/root/google", None),
    ("GET", "/groups", None),
    ("POST", "/groups", {"name": "equipe"}),
    ("DELETE", "/groups/equipe", None),
    ("PUT", "/groups/equipe/members", {"usernames": []}),
    ("GET", "/login-settings", None),
    ("PUT", "/login-settings", {"google_enabled": False, "version": 0}),
    ("GET", "/keys", None),
    ("POST", "/keys", {"subject": "svc:etl", "groups": [], "label": "etl"}),
    ("DELETE", "/keys/00000000000000b2", None),
    ("GET", "/health", None),
]


def test_quem_nao_administra_recebe_o_404_de_rota_inexistente(kit: Kit) -> None:
    """FR-024: corpo e cabeçalhos iguais aos de um caminho que não existe, pelo token da console e pela chave."""
    for token in (CONSOLE_ANA, SVC_KEY):
        reference = kit.call("GET", "/nao-existe", token)
        assert reference.status_code == 404
        for method, path, body in ROUTES:
            response = kit.call(method, path, token, body)
            assert response.status_code == 404, (token, method, path, response.text)
            assert response.json() == reference.json(), (method, path)
            assert _stable(response) == _stable(reference), (method, path)
        # método que a rota não tem também é o mesmo 404, e não 405
        assert kit.call("PATCH", "/assistants", token).json() == reference.json()
    # e nada mudou: as escritas de quem não administra não chegaram aos módulos
    assert kit.call("GET", "/assistants/geral").json()["overrides"] == []
    assert [group["name"] for group in kit.call("GET", "/groups").json()["data"]] == ["admin"]


@pytest.mark.parametrize("token", [CHAT_ROOT, "tok-desconhecido", None])
def test_credencial_recusada_e_401_em_toda_rota(kit: Kit, token: str | None) -> None:
    """O token do chat (audiência `ai-core`) não alcança a administração, mesmo de um admin (ADR-031)."""
    for method, path, body in [*ROUTES, ("GET", "/nao-existe", None)]:
        response = kit.call(method, path, token, body)
        assert response.status_code == 401, (method, path)
        assert _error(response)["code"] == "invalid_credential"


@pytest.mark.parametrize("token", [CONSOLE_ROOT, ADMIN_KEY], ids=["console", "chave"])
@pytest.mark.parametrize(
    "path",
    [
        "/assistants",
        "/assistants/geral",
        "/assistants/geral/history",
        "/mcp",
        "/usage",
        "/prices",
        "/prices/unpriced",
        "/observability",
        "/users",
        "/users/root",
        "/groups",
        "/login-settings",
        "/keys",
        "/health",
    ],
)
def test_leituras_pelo_token_da_console_e_pela_chave(kit: Kit, token: str, path: str) -> None:
    response = kit.call("GET", path, token)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store" and response.headers["x-request-id"]


def test_me_traz_a_sessao_e_a_marca_da_instalacao(kit: Kit) -> None:
    console = kit.call("GET", "/me").json()
    assert console == {
        "subject": "user:root",
        "username": "root",
        "name": "Root da Silva",
        "groups": ["operadores"],
        "scheme": "oidc",
        "instance": {"name": "Agentic", "logo_url": "/oauth2/assets/logo"},
    }
    key = kit.call("GET", "/me", ADMIN_KEY).json()
    assert (key["subject"], key["scheme"], key["name"]) == ("user:caio", "api_key", "caio")


def test_sem_os_seams_a_superficie_nao_existe() -> None:
    kit = _kit(seams=False)
    assert kit.call("GET", "/me").status_code == 404
    assert kit.call("GET", "/assistants", ADMIN_KEY).status_code == 404


# --- Assistants de sistema (003 US10) --------------------------------------------------------------------------------


def test_sobreposicao_de_modelos_ciclo_completo(kit: Kit) -> None:
    listed = {view["name"]: view for view in kit.call("GET", "/assistants").json()["data"]}
    assert listed["geral"]["overridable"] == ["mcp", "models"] and listed["fixo"]["overridable"] == []

    saved = kit.call("PUT", "/assistants/geral/models", body={"roles": {"generation": MINI}, "version": None})
    assert saved.status_code == 200, saved.text
    view = saved.json()
    assert view["effective"]["models"]["generation"] == MINI
    assert view["yaml"]["models"]["generation"] == "openrouter/nvidia/nemotron"
    (override,) = view["overrides"]
    assert (override["state"], override["version"], override["updated_by"]) == ("active", 1, "user:root")

    stale = kit.call("PUT", "/assistants/geral/models", ADMIN_KEY, {"roles": {"generation": MINI}, "version": None})
    assert stale.status_code == 409
    assert _error(stale)["code"] == "version_conflict" and _error(stale)["current_version"] == 1
    assert _error(stale)["param"] == "version"

    history = kit.call("GET", "/assistants/geral/history").json()["data"]
    assert [(entry["section"], entry["action"], entry["version"]) for entry in history] == [("models", "saved", 1)]

    discarded = kit.call("DELETE", "/assistants/geral/overrides/models?version=1")
    assert discarded.status_code == 200 and discarded.json()["overrides"] == []
    assert discarded.json()["effective"]["models"]["generation"] == "openrouter/nvidia/nemotron"


def test_sobreposicao_recusada_nomeia_o_campo(kit: Kit) -> None:
    outside = kit.call(
        "PUT", "/assistants/geral/models", body={"roles": {"generation": "ollama/qwen3"}, "version": None}
    )
    assert outside.status_code == 422 and _error(outside)["code"] == "invalid_field" and _error(outside)["param"]
    locked = kit.call("PUT", "/assistants/fixo/models", body={"roles": {"generation": MINI}, "version": None})
    assert locked.status_code == 422 and "deploy" in _error(locked)["message"]
    unknown = kit.call("PUT", "/assistants/geral/models", body={"roles": {"generation": MINI}, "versao": 1})
    assert _error(unknown)["param"] == "versao"
    assert kit.call("GET", "/assistants/nao-existe").status_code == 404
    assert kit.call("DELETE", "/assistants/geral/overrides/models").json()["error"]["param"] == "version"
    assert kit.call("DELETE", "/assistants/geral/overrides/packs?version=1").status_code == 404


def test_mcp_global_pela_administracao_e_sobreposicao_de_mcp(kit: Kit) -> None:
    created = kit.call("POST", "/mcp", body=GLOBAL_MCP)
    assert created.status_code == 201, created.text
    tools = kit.call("GET", "/mcp/agenda/health").json()
    assert set(tools["tools"]) == {"listar", "marcar"}
    saved = kit.call(
        "PUT", "/assistants/geral/mcp", body={"aliases": ["agenda"], "allowed": ["agenda.listar"], "version": None}
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["effective"]["mcp"] == {"aliases": ["agenda"], "allowed": ["agenda.listar"], "write": []}


def test_testar_modelo_pelo_model_router(kit: Kit) -> None:
    ok = kit.call("POST", "/assistants/geral/models/check", body={"role": "generation", "model": MINI})
    assert ok.status_code == 200 and ok.json() == {"available": True, "detail": None, "latency_ms": 0}
    missing = kit.call(
        "POST", "/assistants/geral/models/check", body={"role": "generation", "model": "openrouter/x/inexistente"}
    ).json()
    assert missing["available"] is False and "não encontrado" in missing["detail"]
    outside = kit.call("POST", "/assistants/geral/models/check", body={"role": "generation", "model": "ollama/qwen3"})
    assert outside.status_code == 422 and _error(outside)["param"] == "model"


def test_providers_com_a_prontidao_de_cada_um(kit: Kit) -> None:
    """ADR-035: a lista por nome, com o motivo de quem não está pronto."""
    response = kit.call("GET", "/providers")
    assert response.status_code == 200
    assert response.json() == {
        "data": [
            {"name": "informa", "ready": True, "detail": None, "reports_cost": True},
            {
                "name": "ollama",
                "ready": False,
                "detail": "provider inalcançável em http://ollama.test/v1",
                "reports_cost": False,
            },
            {"name": "openrouter", "ready": True, "detail": None, "reports_cost": False},
        ]
    }


def test_preco_recusado_para_provider_que_informa_o_custo(kit: Kit) -> None:
    """ADR-036: o custo vem de cada chamada; preço de tabela não se aplica."""
    price = {"provider": "informa", "model": "x/y", "input": "1", "output": "2", "effective_from": "2026-09-01"}
    refused = kit.call("POST", "/prices", body=price)
    assert refused.status_code == 422 and _error(refused)["param"] == "provider"
    assert kit.call("GET", "/prices").json()["data"] == []


# --- uso e preços (009 US5) ------------------------------------------------------------------------------------------


def test_uso_preco_e_custo_calculado_na_consulta(kit: Kit) -> None:
    before = kit.call("GET", "/usage").json()
    (row,) = before["totals"]
    assert (row["key"], row["calls"], row["input_tokens"], row["priced"]) == (MINI, 1, 1_000, False)
    assert before["incomplete"] is True and before["currency"] == "USD"
    assert [(d["requests"], len(d["rows"])) for d in before["days"]] == [(1, 1)]
    assert kit.call("GET", "/prices/unpriced").json()["data"] == [MINI]

    price = {"provider": "openrouter", "model": "openai/gpt-4.1-mini", "input": "0.40", "output": "1.60"}
    created = kit.call("POST", "/prices", body=price | {"effective_from": "2026-09-01"})
    assert (
        created.status_code == 201 and created.json()["input"] == "0.40" and created.json()["created_by"] == "user:root"
    )

    after = kit.call("GET", "/usage").json()
    assert Decimal(after["totals"][0]["cost"]) == Decimal("0.00072") and after["incomplete"] is False
    assert kit.call("GET", "/prices/unpriced").json()["data"] == []

    assert _error(kit.call("GET", "/usage?tz=Lua/Base"))["param"] == "tz"
    assert (
        _error(kit.call("POST", "/prices", body=price | {"input": 0.4, "effective_from": "2026-09-01"}))["param"]
        == "input"
    )


# --- observabilidade (009 US6, US7) ----------------------------------------------------------------------------------


def test_langfuse_e_captura_com_versao(kit: Kit) -> None:
    assert kit.call("GET", "/observability").json()["version"] == 0
    saved = kit.call(
        "PUT",
        "/observability/langfuse",
        body={
            "enabled": True,
            "host": "https://lf.exemplo.org",
            "public_key": "pk-1",
            "secret_key": LANGFUSE_SECRET,
            "version": 0,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["langfuse"]["secret_set"] is True and saved.json()["version"] == 1
    assert kit.transport.credentials is not None and kit.transport.credentials.secret_key == LANGFUSE_SECRET

    stale = kit.call("PUT", "/observability/capture", body={"enabled": False, "version": 0})
    assert stale.status_code == 409 and _error(stale)["current_version"] == 1

    unacknowledged = kit.call("PUT", "/observability/capture", body={"enabled": True, "version": 1})
    assert unacknowledged.status_code == 422 and _error(unacknowledged)["param"] == "acknowledged"
    on = kit.call("PUT", "/observability/capture", body={"enabled": True, "acknowledged": True, "version": 1})
    assert on.status_code == 200 and on.json()["capture_content"] is True

    tested = kit.call("POST", "/observability/langfuse/test", body={})
    assert tested.json() == {"ok": True, "detail": "projeto de teste"}


def test_langfuse_da_instalacao_e_somente_leitura() -> None:
    credentials = LangfuseCredentials(host="https://lf.exemplo.org", public_key="pk-inst", secret_key=LANGFUSE_SECRET)
    kit = _kit(installation=InstallationDestinations(langfuse=credentials))
    view = kit.call("GET", "/observability").json()
    assert view["langfuse"]["sources"]["host"] == "installation" and view["langfuse"]["secret_set"] is True
    refused = kit.call("PUT", "/observability/langfuse", body={"host": "https://outro.org", "version": 0})
    assert refused.status_code == 409
    assert (_error(refused)["code"], _error(refused)["param"]) == ("installation_defined", "langfuse_host")


def test_segredo_sem_chave_mestra() -> None:
    kit = _kit(cipher=False)
    refused = kit.call("PUT", "/observability/langfuse", body={"secret_key": LANGFUSE_SECRET, "version": 0})
    assert refused.status_code == 409 and _error(refused)["code"] == "master_key_missing"


# --- contas, grupos e login (012) ------------------------------------------------------------------------------------


def test_contas_senha_temporaria_so_na_resposta_que_a_define(kit: Kit) -> None:
    created = kit.call(
        "POST", "/users", body={"username": "ana", "email": "ana@exemplo.org", "name": "Ana Souza", "groups": []}
    )
    assert created.status_code == 201, created.text
    first = created.json()["temporary_password"]
    assert first and created.json()["account"]["temporary_password"] is True

    reset = kit.call("POST", "/users/ana/password").json()["temporary_password"]
    assert reset and reset != first

    account = kit.call("GET", "/users/ana").json()
    patched = kit.call("PATCH", "/users/ana", body={"name": "Ana S.", "version": account["version"]})
    assert patched.status_code == 200 and patched.json()["name"] == "Ana S."
    stale = kit.call("PATCH", "/users/ana", body={"name": "Ana", "version": account["version"]})
    assert stale.status_code == 409 and _error(stale)["code"] == "version_conflict"
    assert _error(stale)["current_version"] == patched.json()["version"]

    assert kit.call("POST", "/users/ana/disable").json()["active"] is False
    assert kit.call("POST", "/users/ana/enable").json()["active"] is True
    assert kit.call("GET", "/users/nao-existe").status_code == 404
    invalid = kit.call("POST", "/users", body={"username": "ana", "email": "sem-arroba", "name": "Ana"})
    assert invalid.status_code == 422 and _error(invalid)["param"] == "email"

    for method, path, response in kit.responses:
        if (method, path) not in {("POST", "/users"), ("POST", "/users/ana/password")}:
            assert first not in response.text and reset not in response.text, (method, path)


def test_grupos_com_o_de_administracao_protegido(kit: Kit) -> None:
    assert kit.call("POST", "/groups", body={"name": "equipe"}).status_code == 201
    members = kit.call("PUT", "/groups/equipe/members", body={"usernames": ["root"]})
    assert members.status_code == 200 and members.json()["members"] == 1
    protected = kit.call("DELETE", "/groups/admin")
    assert protected.status_code == 409 and _error(protected)["code"] == "protected_group"
    assert kit.call("DELETE", "/groups/equipe").status_code == 204
    assert kit.call("DELETE", "/groups/equipe").status_code == 404


def test_login_google_exige_cliente_na_instalacao(kit: Kit) -> None:
    view = kit.call("GET", "/login-settings").json()
    assert view["google_configured"] is False
    refused = kit.call("PUT", "/login-settings", body={"google_enabled": True, "version": view["version"]})
    assert refused.status_code == 409 and _error(refused)["code"] == "google_not_configured"

    with_google = _kit(google=True)
    current = with_google.call("GET", "/login-settings").json()
    turned = with_google.call("PUT", "/login-settings", body={"google_enabled": True, "version": current["version"]})
    assert turned.status_code == 200 and turned.json()["google_enabled"] is True
    assert GOOGLE.client_secret not in turned.text


# --- chaves e saúde --------------------------------------------------------------------------------------------------


def test_chaves_pela_administracao(kit: Kit) -> None:
    issued = kit.call("POST", "/keys", body={"subject": "svc:etl", "groups": ["leitores"], "label": "etl"})
    assert issued.status_code == 201 and issued.json()["key"].startswith("aic_")
    plaintext, key_id = issued.json()["key"], issued.json()["key_id"]
    listed = kit.call("GET", "/keys").json()["data"]
    assert key_id in [key["key_id"] for key in listed] and plaintext not in str(listed)
    assert kit.call("DELETE", f"/keys/{key_id}").json()["revoked_at"] is not None


# --- varredura (SC-009) e cabeçalhos ---------------------------------------------------------------------------------


Scenario = Callable[[Kit], None]


@pytest.mark.parametrize(
    "scenario",
    [
        test_sobreposicao_de_modelos_ciclo_completo,
        test_mcp_global_pela_administracao_e_sobreposicao_de_mcp,
        test_uso_preco_e_custo_calculado_na_consulta,
        test_langfuse_e_captura_com_versao,
        test_contas_senha_temporaria_so_na_resposta_que_a_define,
        test_grupos_com_o_de_administracao_protegido,
        test_quem_nao_administra_recebe_o_404_de_rota_inexistente,
    ],
    ids=lambda scenario: scenario.__name__.removeprefix("test_"),
)
def test_nenhuma_resposta_traz_segredo_e_toda_sai_sem_cache(scenario: Scenario) -> None:
    kit = _kit()
    scenario(kit)
    for method, path in (("GET", "/observability"), ("GET", "/users"), ("GET", "/login-settings"), ("GET", "/me")):
        kit.call(method, path)
    assert kit.responses
    for method, path, response in kit.responses:
        assert response.headers["cache-control"] == "no-store", (method, path)
        assert response.headers.get("x-request-id"), (method, path)
        for secret in SECRETS:
            assert secret not in response.text, (method, path, secret)
