"""T048 e T051 — rotas de MCP (contracts/mcp-routes.md; US4, US5; research R26 a R29).

O registry é o `McpService` da 007 com adapters em memória e um transporte programado; Assistants e acesso são os
serviços reais da 003. Nada fala com rede.
"""

from __future__ import annotations

from typing import Any, Final

import pytest
from fastapi.testclient import TestClient
from http_testkit import ADMIN_KEY, ANA_TOKEN, BIA_TOKEN, SVC_KEY, Platform, bearer
from mcp_testkit import build, scripted

from ai_core.mcp.ports import McpConfig, RemoteTool

AGENDA_URL: Final = "https://agenda.example/mcp"
AGENDA = scripted(RemoteTool(name="listar"), RemoteTool(name="marcar"))


def mcp_proprio(alias: str = "~agenda", **overrides: Any) -> dict[str, Any]:
    return {
        "alias": alias,
        "transport": "http",
        "endpoint": AGENDA_URL,
        "description": "minha agenda",
        "policy": {"allowed_tools": ["listar", "marcar"], "write_tools": ["marcar"]},
    } | overrides


def plataforma(config: McpConfig | None = None) -> Platform:
    kit = build(servers={AGENDA_URL: AGENDA}, config=config)
    return Platform(mcp=kit.service)


@pytest.fixture
def client() -> TestClient:
    return TestClient(plataforma().app)


# --- usuário (US4) --------------------------------------------------------------------------------------------------


@pytest.mark.us4
def test_ciclo_completo_do_mcp_do_usuario(client: TestClient) -> None:
    ana = bearer(ANA_TOKEN)
    criado = client.post("/v1/mcp", headers=ana, json=mcp_proprio())
    assert criado.status_code == 201, criado.text
    assert criado.json()["alias"] == "~agenda" and criado.json()["owner"] == "user:ana"
    assert criado.json()["scope"] == "user" and criado.json()["origin"] == "registry"

    assert client.get("/v1/mcp/agenda", headers=ana).json()["description"] == "minha agenda"
    atualizado = client.put("/v1/mcp/~agenda", headers=ana, json=mcp_proprio(description="v2"))
    assert atualizado.status_code == 200 and atualizado.json()["description"] == "v2"
    assert [s["alias"] for s in client.get("/v1/mcp", headers=ana).json()["data"]] == ["~agenda"]

    saude = client.get("/v1/mcp/~agenda/health", headers=ana)
    assert saude.status_code == 200
    assert saude.json()["ok"] is True and sorted(saude.json()["tools"]) == ["listar", "marcar"]

    assert client.delete("/v1/mcp/agenda", headers=ana).status_code == 204
    assert client.get("/v1/mcp/~agenda", headers=ana).status_code == 404
    assert client.get("/v1/mcp", headers=ana).json()["data"] == []


@pytest.mark.us4
def test_mcp_de_outro_usuario_e_inexistente(client: TestClient) -> None:
    client.post("/v1/mcp", headers=bearer(ANA_TOKEN), json=mcp_proprio())
    bia = bearer(BIA_TOKEN)
    respostas = [
        client.get("/v1/mcp/~agenda", headers=bia),
        client.put("/v1/mcp/~agenda", headers=bia, json=mcp_proprio()),
        client.delete("/v1/mcp/~agenda", headers=bia),
        client.get("/v1/mcp/~agenda/health", headers=bia),
        client.get("/v1/mcp/~nunca-existiu", headers=bia),
    ]
    assert {r.status_code for r in respostas} == {404}
    assert len({r.json()["error"]["message"] for r in respostas}) == 1
    assert client.get("/v1/mcp", headers=bia).json()["data"] == []


@pytest.mark.us4
def test_available_mostra_proprios_e_globais_liberados_sem_detalhes(client: TestClient) -> None:
    admin = bearer(ADMIN_KEY)
    liberado = {
        "alias": "agenda-da-casa",
        "transport": "http",
        "endpoint": AGENDA_URL,
        "user_access": True,
        "policy": {"allowed_tools": ["listar"]},
    }
    fechado = liberado | {"alias": "interno", "user_access": False}
    assert client.post("/private/v1/mcp", headers=admin, json=liberado).status_code == 201
    assert client.post("/private/v1/mcp", headers=admin, json=fechado).status_code == 201
    client.post("/v1/mcp", headers=bearer(ANA_TOKEN), json=mcp_proprio())

    disponiveis = client.get("/v1/mcp/available", headers=bearer(ANA_TOKEN)).json()["data"]
    assert {d["alias"] for d in disponiveis} == {"~agenda", "agenda-da-casa"}
    assert all(set(d) == {"alias", "scope", "description"} for d in disponiveis)


@pytest.mark.us4
@pytest.mark.parametrize(
    ("corpo", "campo"),
    [
        (mcp_proprio(endpoint="http://agenda.example/mcp"), "endpoint"),
        (mcp_proprio(transport="stdio"), "transport"),
        (mcp_proprio(policy={"allowed_tools": []}), "policy.allowed_tools"),
        (mcp_proprio(segredo="x"), "segredo"),
    ],
)
def test_recusas_nomeiam_o_campo(client: TestClient, corpo: dict[str, Any], campo: str) -> None:
    resposta = client.post("/v1/mcp", headers=bearer(ANA_TOKEN), json=corpo)
    assert resposta.status_code == 400, resposta.text
    assert resposta.json()["error"]["param"] == campo


@pytest.mark.us4
def test_us4_cen1_mcp_proprio_e_assistant_que_o_usa_aparecem_nos_modelos(client: TestClient) -> None:
    ana = bearer(ANA_TOKEN)
    assert client.post("/v1/mcp", headers=ana, json=mcp_proprio()).status_code == 201
    assistant = {
        "name": "com-agenda",
        "packs": ["generic"],
        "mcp": ["~agenda"],
        "models": {"generation": "ollama/qwen3:1.7b"},
    }
    criado = client.post("/v1/assistants", headers=ana, json=assistant)
    assert criado.status_code == 201, criado.text
    assert criado.json()["status"]["available"] is True
    assert "~com-agenda" in [m["id"] for m in client.get("/v1/models", headers=ana).json()["data"]]


@pytest.mark.us4
def test_nenhuma_resposta_traz_valor_de_credencial(monkeypatch: pytest.MonkeyPatch) -> None:
    kit = build(servers={AGENDA_URL: AGENDA}, secrets={"cofre_token": "segredo-do-cofre"})
    client = TestClient(Platform(mcp=kit.service).app)
    admin = bearer(ADMIN_KEY)
    corpo = {
        "alias": "cofre",
        "transport": "http",
        "endpoint": AGENDA_URL,
        "auth": {"type": "bearer", "credential": "cofre_token"},
        "policy": {"allowed_tools": ["listar"]},
    }
    respostas = [
        client.post("/private/v1/mcp", headers=admin, json=corpo),
        client.get("/private/v1/mcp", headers=admin),
        client.get("/private/v1/mcp/cofre", headers=admin),
        client.get("/private/v1/mcp/cofre/health", headers=admin),
    ]
    assert respostas[0].json()["auth"] == {"type": "bearer", "credential": "cofre_token"}
    assert all("segredo-do-cofre" not in r.text for r in respostas)


# --- globais (US5) --------------------------------------------------------------------------------------------------

GLOBAL: Final = {
    "alias": "financeiro",
    "transport": "http",
    "endpoint": AGENDA_URL,
    "auth": {"type": "bearer", "credential": "financeiro_token"},
    "user_access": True,
    "policy": {"allowed_tools": ["listar"]},
}


@pytest.mark.us5
def test_quem_nao_administra_recebe_404_em_todas_as_rotas_globais(client: TestClient) -> None:
    for cabecalho in (bearer(SVC_KEY),):
        respostas = [
            client.get("/private/v1/mcp", headers=cabecalho),
            client.post("/private/v1/mcp", headers=cabecalho, json=GLOBAL),
            client.get("/private/v1/mcp/financeiro", headers=cabecalho),
            client.put("/private/v1/mcp/financeiro", headers=cabecalho, json=GLOBAL),
            client.delete("/private/v1/mcp/financeiro", headers=cabecalho),
            client.get("/private/v1/mcp/financeiro/health", headers=cabecalho),
        ]
        assert {r.status_code for r in respostas} == {404}
    assert client.get("/private/v1/mcp", headers=bearer(ADMIN_KEY)).json()["data"] == []


@pytest.mark.us5
def test_administrador_gerencia_os_globais(client: TestClient) -> None:
    admin = bearer(ADMIN_KEY)
    criado = client.post("/private/v1/mcp", headers=admin, json=GLOBAL)
    assert criado.status_code == 201, criado.text
    assert criado.json()["scope"] == "global" and criado.json()["user_access"] is True
    assert client.get("/private/v1/mcp/financeiro", headers=admin).json()["alias"] == "financeiro"
    alterado = client.put("/private/v1/mcp/financeiro", headers=admin, json=GLOBAL | {"description": "v2"})
    assert alterado.status_code == 200 and alterado.json()["description"] == "v2"
    assert [s["alias"] for s in client.get("/private/v1/mcp", headers=admin).json()["data"]] == ["financeiro"]
    assert client.delete("/private/v1/mcp/financeiro", headers=admin).status_code == 204
    assert client.get("/private/v1/mcp/financeiro", headers=admin).status_code == 404


@pytest.mark.us5
def test_entrada_do_arquivo_aparece_e_e_somente_leitura() -> None:
    from mcp_testkit import global_draft

    from ai_core.mcp.ports import ConfigEntry

    config = McpConfig(entries=(ConfigEntry(alias="arquivado", draft=global_draft(alias="arquivado")),))
    client = TestClient(plataforma(config=config).app)
    admin = bearer(ADMIN_KEY)
    (entrada,) = [s for s in client.get("/private/v1/mcp", headers=admin).json()["data"] if s["alias"] == "arquivado"]
    assert entrada["origin"] == "file"
    for resposta in (
        client.put("/private/v1/mcp/arquivado", headers=admin, json=GLOBAL | {"alias": "arquivado"}),
        client.delete("/private/v1/mcp/arquivado", headers=admin),
    ):
        assert resposta.status_code == 409, resposta.text
        assert resposta.json()["error"]["param"] == "alias"


@pytest.mark.us5
def test_saude_de_um_global_no_ar_e_fora_do_ar() -> None:
    kit = build(servers={AGENDA_URL: AGENDA}, secrets={"financeiro_token": "t"})
    client = TestClient(Platform(mcp=kit.service).app)
    admin = bearer(ADMIN_KEY)
    client.post("/private/v1/mcp", headers=admin, json=GLOBAL)
    no_ar = client.get("/private/v1/mcp/financeiro/health", headers=admin).json()
    assert no_ar["ok"] is True and no_ar["tools"]

    kit.transport.servers[AGENDA_URL] = scripted(failure="conexão recusada")
    fora = client.get("/private/v1/mcp/financeiro/health", headers=admin).json()
    assert fora["ok"] is False and "conexão recusada" in (fora["detail"] or "")
