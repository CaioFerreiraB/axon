"""Imagens na API (ADR-044, itens 5, 6, 7 e 9; FR-033 a FR-038; research R60).

O motor é programado: emite as imagens de uma tool e guarda as mensagens que recebeu — o que a API leva ao motor e o
que ela devolve ao cliente é o que se prova aqui.
"""

from __future__ import annotations

import base64
from collections.abc import AsyncIterator, Mapping
from typing import Any

from fastapi.testclient import TestClient
from graph_testkit import Grant, models
from http_testkit import ANONYMOUS, SurfaceRecordingAuthenticator, app_with, body, chunks_of

from axon_ai.assistants.api import Principal
from axon_ai.graph.api import AttachmentEvent, ExecutionEvent, FinalEvent, TokenEvent
from axon_ai.http.adapters.conversations_memory import InMemoryConversationStore
from axon_ai.http.domain.images import ImageLimits
from axon_ai_contracts import Attachment

GRAFICO = Attachment(mime="image/png", data=b"\x89PNG\r\n\x1a\n" + b"g" * 60, alt="Gastos [por] categoria")
FOTO = Attachment(mime="image/jpeg", data=b"\xff\xd8\xff" + b"f" * 30)


def uri(image: Attachment) -> str:
    return f"data:{image.mime};base64,{base64.b64encode(image.data).decode()}"


class Grants:
    """Grant de `geral` com ou sem `vision` na geração."""

    def __init__(self, *, vision: bool) -> None:
        self._vision = frozenset({"generation"}) if vision else frozenset()

    async def resolve(self, *, model: str, principal: Principal) -> Any:
        return Grant(assistant=model.split("/", 1)[0], models=models(controller=False, vision=self._vision))


class ImageEngine:
    """Responde "Pronto." e, se programado, devolve as imagens de uma tool; guarda as mensagens recebidas."""

    def __init__(self, images: tuple[Attachment, ...] = ()) -> None:
        self.images = images
        self.received: list[Any] = []

    def flows(self) -> tuple[str, ...]:
        return ("chat",)

    def flow_roles(self) -> Mapping[str, tuple[str, ...]]:
        return {"chat": ("generation",)}

    def run(self, grant: Any, request: Any) -> AsyncIterator[ExecutionEvent]:
        self.received.append(request.messages)
        return self._events()

    async def _events(self) -> AsyncIterator[ExecutionEvent]:
        for image in self.images:
            yield AttachmentEvent(attachment=image, tool="mango.grafico")
        yield TokenEvent(text="Pronto.")
        yield FinalEvent(answer="Pronto.", attachments=self.images)


def cliente(
    engine: ImageEngine, *, vision: bool = True, limits: ImageLimits | None = None, store: Any = None
) -> TestClient:
    overrides: dict[str, Any] = {} if limits is None else {"image_limits": limits}
    if store is not None:
        overrides["conversations"] = store
    app = app_with(engine, authenticator=SurfaceRecordingAuthenticator(), grants=Grants(vision=vision), **overrides)
    return TestClient(app)


EFEMERO = {"x-axon-store": "false"}


def pergunta_com_foto(texto: str = "o que é isto?") -> list[dict[str, Any]]:
    return [
        {
            "role": "user",
            "content": [{"type": "text", "text": texto}, {"type": "image_url", "image_url": {"url": uri(FOTO)}}],
        }
    ]


# --- entrega ao cliente (item 9) -----------------------------------------------------------------------------------


def test_streaming_entrega_a_imagem_depois_do_ultimo_token_e_o_resumo_no_fim() -> None:
    client = cliente(ImageEngine((GRAFICO,)))
    response = client.post("/v1/chat/completions", json=body(stream=True), headers=EFEMERO)
    chunks = chunks_of(response.text)
    textos = [c["choices"][0]["delta"].get("content") for c in chunks if c["choices"][0]["delta"].get("content")]
    assert textos == ["Pronto.", f"\n\n![Gastos por categoria]({uri(GRAFICO)})"]
    final = chunks[-1]
    assert final["x_axon"]["attachments"] == [{"id": GRAFICO.id, "mime": "image/png", "size_bytes": len(GRAFICO.data)}]


def test_sem_streaming_a_imagem_vem_no_conteudo_em_paragrafo_proprio() -> None:
    client = cliente(ImageEngine((GRAFICO,)))
    response = client.post("/v1/chat/completions", json=body(), headers=EFEMERO)
    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert content == f"Pronto.\n\n![Gastos por categoria]({uri(GRAFICO)})"
    assert response.json()["x_axon"]["attachments"][0]["id"] == GRAFICO.id


def test_sem_imagem_a_resposta_nao_muda() -> None:
    response = cliente(ImageEngine()).post("/v1/chat/completions", json=body(), headers=EFEMERO)
    assert response.json()["choices"][0]["message"]["content"] == "Pronto."
    assert response.json()["x_axon"]["attachments"] == []


# --- conversa no Axon (item 9) -------------------------------------------------------------------------------------


def test_conversa_guardada_tem_marca_metadados_e_a_rota_dos_bytes_so_para_o_dono() -> None:
    store = InMemoryConversationStore()
    client = cliente(ImageEngine((GRAFICO,)), store=store)
    response = client.post("/v1/chat/completions", json=body(messages=pergunta_com_foto()))
    cid = response.headers["x-conversation-id"]
    assert uri(GRAFICO) in response.json()["choices"][0]["message"]["content"], "a resposta do turno leva o data URI"

    lida = client.get(f"/v1/conversations/{cid}").json()
    usuario, resposta = lida["messages"]
    assert usuario["content"] == f"o que é isto?\n\n[imagem {FOTO.id} enviada pelo usuário]"
    assert resposta["content"] == f"Pronto.\n\n[imagem {GRAFICO.id} mostrada ao usuário]"
    assert "base64" not in resposta["content"]
    assert resposta["attachments"] == [{"id": GRAFICO.id, "mime": "image/png", "size_bytes": len(GRAFICO.data)}]
    assert usuario["attachments"][0]["id"] == FOTO.id

    imagem = client.get(f"/v1/conversations/{cid}/attachments/{GRAFICO.id}")
    assert imagem.status_code == 200 and imagem.content == GRAFICO.data
    assert imagem.headers["content-type"] == "image/png" and imagem.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/v1/conversations/{cid}/attachments/img-000000000000").status_code == 404


def test_outro_usuario_recebe_404_na_imagem() -> None:
    store = InMemoryConversationStore()
    engine = ImageEngine((GRAFICO,))
    client = cliente(engine, store=store)
    cid = client.post("/v1/chat/completions", json=body()).headers["x-conversation-id"]

    class Outro(SurfaceRecordingAuthenticator):
        async def authenticate(self, *, surface: str, credential: str | None) -> Principal:
            return Principal(subject="user:bia", scheme="oidc")

    alheio = TestClient(app_with(engine, authenticator=Outro(), grants=Grants(vision=True), conversations=store))
    response = alheio.get(f"/v1/conversations/{cid}/attachments/{GRAFICO.id}")
    assert response.status_code == 404 and response.json()["error"]["code"] == "not_found"
    assert store is not None and ANONYMOUS


def test_turno_seguinte_le_do_banco_as_imagens_da_ultima_resposta() -> None:
    engine = ImageEngine((GRAFICO,))
    client = cliente(engine, store=InMemoryConversationStore())
    cid = client.post("/v1/chat/completions", json=body()).headers["x-conversation-id"]
    engine.images = ()
    client.post(
        "/v1/chat/completions", json=body(conversation_id=cid, messages=[{"role": "user", "content": "e o pico?"}])
    )
    anterior = engine.received[-1][-2]
    assert anterior["role"] == "assistant" and anterior["attachments"] == (GRAFICO,)
    assert "base64" not in anterior["content"]


# --- imagem do usuário (item 5) ------------------------------------------------------------------------------------


def test_imagem_do_usuario_chega_ao_motor() -> None:
    engine = ImageEngine()
    response = cliente(engine).post("/v1/chat/completions", json=body(messages=pergunta_com_foto()), headers=EFEMERO)
    assert response.status_code == 200
    ultima = engine.received[-1][-1]
    assert ultima["content"] == "o que é isto?" and ultima["attachments"] == (FOTO,)


def test_assistant_sem_visao_e_400_vision_unsupported_antes_de_executar() -> None:
    engine = ImageEngine()
    response = cliente(engine, vision=False).post(
        "/v1/chat/completions", json=body(messages=pergunta_com_foto()), headers=EFEMERO
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "vision_unsupported" and "'geral'" in error["message"]
    assert engine.received == []


def test_corpo_acima_do_teto_e_413_antes_de_decodificar() -> None:
    client = cliente(ImageEngine(), limits=ImageLimits(max_request_bytes=200))
    response = client.post(
        "/v1/chat/completions",
        content=b'{"model": "geral", "messages": [' + b" " * 400 + b"]}",
        headers={"content-type": "application/json", **EFEMERO},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


# --- histórico do cliente (item 7) ---------------------------------------------------------------------------------


def test_historico_do_open_webui_vira_marcas_e_so_a_ultima_resposta_guarda_bytes() -> None:
    antiga = Attachment(mime="image/png", data=b"\x89PNG" + b"a" * 20)
    engine = ImageEngine()
    mensagens = [
        {"role": "user", "content": pergunta_com_foto("primeira")[0]["content"]},
        {"role": "assistant", "content": f"Antes.\n\n![x]({uri(antiga)})"},
        {"role": "user", "content": "e agora?"},
        {"role": "assistant", "content": f"Aqui.\n\n![grafico]({uri(GRAFICO)})"},
        {"role": "user", "content": "o que é aquele pico?"},
    ]
    response = cliente(engine).post("/v1/chat/completions", json=body(messages=mensagens), headers=EFEMERO)
    assert response.status_code == 200
    recebidas = engine.received[-1]
    assert recebidas[0] == {"role": "user", "content": f"primeira\n[imagem {FOTO.id} enviada pelo usuário]"}
    assert recebidas[1] == {"role": "assistant", "content": f"Antes.\n\n[imagem {antiga.id} mostrada ao usuário]"}
    assert recebidas[3]["content"] == f"Aqui.\n\n[imagem {GRAFICO.id} mostrada ao usuário]"
    [candidata] = recebidas[3]["attachments"]
    assert (candidata.id, candidata.data, candidata.alt) == (GRAFICO.id, GRAFICO.data, None), "o alt veio de fora"
