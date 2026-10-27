"""ADR-044, itens 5 e 7 (R60): a leitura das mensagens — a pergunta validada, o histórico com marcas."""

from __future__ import annotations

import base64
from typing import Any

import pytest

from axon_ai.http.domain.chat_request import ChatRequestInvalid, parse_messages
from axon_ai.http.domain.images import ImageLimits, images_markdown, summary, with_markers
from axon_ai_contracts import Attachment

PNG = Attachment(mime="image/png", data=b"\x89PNG" + b"p" * 30)
LIMITES = ImageLimits(max_input_image_bytes=100, max_input_images=2)


def uri(data: bytes, mime: str = "image/png") -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def com_imagens(*urls: Any, texto: str = "veja") -> list[dict[str, Any]]:
    partes: list[dict[str, Any]] = [{"type": "text", "text": texto}] if texto else []
    partes += [{"type": "image_url", "image_url": {"url": url}} for url in urls]
    return [{"role": "user", "content": partes}]


def test_pergunta_com_imagem() -> None:
    (mensagem,) = parse_messages(com_imagens(uri(PNG.data)), LIMITES)
    assert mensagem == {"role": "user", "content": "veja", "attachments": (PNG,)}


def test_so_imagem_vale_como_pergunta() -> None:
    (mensagem,) = parse_messages(com_imagens(uri(PNG.data), texto=""), LIMITES)
    assert mensagem["content"] == "" and mensagem["attachments"] == (PNG,)


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("https://exemplo.com/a.png", "image_url_not_allowed"),
        ("http://169.254.169.254/x", "image_url_not_allowed"),
        (uri(b"<svg/>", "image/svg+xml"), "unsupported_image_type"),
        ("data:image/png;base64,@@@", "invalid_image"),
        (uri(b"p" * 101), "image_too_large"),
        (None, "image_url_not_allowed"),
    ],
)
def test_a_pergunta_e_validada_antes_de_qualquer_custo(url: Any, code: str) -> None:
    with pytest.raises(ChatRequestInvalid) as caught:
        parse_messages(com_imagens(url), LIMITES)
    assert caught.value.code == code
    assert caught.value.field == "messages[0].content[1].image_url.url"


def test_quantidade_maxima_de_imagens() -> None:
    with pytest.raises(ChatRequestInvalid) as caught:
        parse_messages(com_imagens(uri(b"a"), uri(b"b"), uri(b"c")), LIMITES)
    assert caught.value.code == "too_many_images"


def test_parte_desconhecida_na_pergunta_e_recusada_e_no_historico_ignorada() -> None:
    estranha = [{"type": "input_audio", "input_audio": {}}, {"type": "text", "text": "oi"}]
    with pytest.raises(ChatRequestInvalid):
        parse_messages([{"role": "user", "content": estranha}], LIMITES)
    mensagens = parse_messages([{"role": "user", "content": estranha}, {"role": "user", "content": "e?"}], LIMITES)
    assert mensagens[0] == {"role": "user", "content": "oi"}


def test_historico_nunca_trava_e_perde_os_bytes() -> None:
    enorme = uri(b"p" * 500)
    mensagens = parse_messages(
        [
            *com_imagens(enorme, "https://x/y.png"),
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "ok"}, {"type": "image_url", "image_url": {"url": uri(PNG.data)}}],
            },
            {"role": "user", "content": "e então?"},
        ],
        LIMITES,
    )
    grande = Attachment(mime="image/png", data=b"p" * 500)
    assert mensagens[0] == {
        "role": "user",
        "content": f"veja\n[imagem {grande.id} enviada pelo usuário]\n[imagem enviada pelo usuário]",
    }
    assert mensagens[1]["content"] == f"ok\n[imagem {PNG.id} mostrada ao usuário]"
    assert mensagens[1]["attachments"] == (PNG,)


def test_imagem_de_tipo_fora_da_lista_na_resposta_perde_os_bytes() -> None:
    svg = uri(b"<svg/>", "image/svg+xml")
    mensagens = parse_messages(
        [{"role": "assistant", "content": f"a\n\n![x]({svg})"}, {"role": "user", "content": "?"}], LIMITES
    )
    assert mensagens[0] == {"role": "assistant", "content": "a\n\n[imagem mostrada ao usuário]"}


def test_marcas_markdown_e_resumo() -> None:
    assert with_markers("oi", (PNG,), "[imagem {id} x]") == f"oi\n\n[imagem {PNG.id} x]"
    assert with_markers("", (PNG,), "[imagem {id} x]") == f"[imagem {PNG.id} x]"
    assert with_markers("oi", (), "[{id}]") == "oi"
    assert images_markdown((PNG,)) == f"\n\n![imagem]({uri(PNG.data)})"
    assert summary((PNG,)) == [{"id": PNG.id, "mime": "image/png", "size_bytes": len(PNG.data)}]
