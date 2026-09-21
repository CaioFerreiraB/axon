"""T010 — conformidade das portas da 008 (contracts/ports.md)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from graph_testkit import RecordingTraceSink
from http_testkit import CREATED, RejectingAuthenticator, StaticGrants, app, body

from ai_core.http.adapters.development import (
    ANONYMOUS_ID,
    AnonymousAuthenticator,
    DevelopmentPrincipal,
    FixedClock,
    SequentialRequestIds,
    Uuid4RequestIds,
)
from ai_core.http.ports import PRIVATE_SURFACE, PUBLIC_SURFACE
from ai_core.observability.api import ExecutionStarted, ModelCall


async def test_autenticador_anonimo_devolve_o_mesmo_principal_nas_duas_superficies() -> None:
    authenticator = AnonymousAuthenticator()
    publico = await authenticator.authenticate(surface=PUBLIC_SURFACE, credential=None)
    privado = await authenticator.authenticate(surface=PRIVATE_SURFACE, credential="chave")
    assert publico.id == privado.id == ANONYMOUS_ID


async def test_autenticador_anonimo_nunca_levanta_por_credencial_ausente() -> None:
    assert await AnonymousAuthenticator().authenticate(surface=PUBLIC_SURFACE, credential=None) is not None


async def test_principal_customizado_e_respeitado() -> None:
    authenticator = AnonymousAuthenticator(DevelopmentPrincipal(id="operador"))
    principal = await authenticator.authenticate(surface=PRIVATE_SURFACE, credential=None)
    assert principal.id == "operador"


def test_autenticador_que_recusa_faz_a_rota_responder_401() -> None:
    client = TestClient(app(authenticator=RejectingAuthenticator()))
    assert client.post("/v1/chat/completions", json=body()).status_code == 401


def test_assistant_nao_encontrado_faz_a_rota_responder_404() -> None:
    client = TestClient(app(grants=StaticGrants(known=())))
    response = client.post("/v1/chat/completions", json=body())
    assert response.status_code == 404


def test_o_resolvedor_recebe_o_modelo_pedido_e_o_principal() -> None:
    grants = StaticGrants()
    client = TestClient(app(grants=grants))
    client.post("/v1/chat/completions", json=body())
    assert grants.calls == [("geral/qwen3:1.7b", ANONYMOUS_ID)]


def test_identificadores_sequenciais_sao_distintos_e_crescentes() -> None:
    ids = SequentialRequestIds()
    assert [ids.next() for _ in range(3)] == ["req-1", "req-2", "req-3"]


def test_identificadores_aleatorios_sao_distintos() -> None:
    ids = Uuid4RequestIds()
    assert len({ids.next() for _ in range(5)}) == 5


def test_o_identificador_liga_resposta_e_trace() -> None:
    """É o elo que a FR-010 existe para criar: do cabeçalho da resposta ao trace da requisição."""
    trace = RecordingTraceSink()
    client = TestClient(app(trace=trace))
    response = client.post("/v1/chat/completions", json=body())

    request_id = response.headers["x-request-id"]
    assert response.json()["x_ai_core"]["request_id"] == request_id
    assert trace.of_type(ExecutionStarted)[0].request_id == request_id
    assert trace.of_type(ModelCall)[0].request_id == request_id


def test_duas_requisicoes_recebem_identificadores_diferentes() -> None:
    client = TestClient(app())
    primeiro = client.post("/v1/chat/completions", json=body()).headers["x-request-id"]
    segundo = client.post("/v1/chat/completions", json=body()).headers["x-request-id"]
    assert primeiro != segundo


def test_relogio_fixo_torna_o_campo_created_verificavel() -> None:
    client = TestClient(app())
    assert client.post("/v1/chat/completions", json=body()).json()["created"] == int(CREATED.timestamp())


def test_relogio_fixo_exige_timezone() -> None:
    with pytest.raises(ValueError):
        FixedClock(datetime(2026, 9, 21))


def test_relogio_do_sistema_devolve_instante_com_timezone() -> None:
    from ai_core.http.adapters.development import SystemClock

    agora = SystemClock().now()
    assert agora.tzinfo is not None
    assert agora.utcoffset() is not None
    assert agora <= datetime.now(UTC)
