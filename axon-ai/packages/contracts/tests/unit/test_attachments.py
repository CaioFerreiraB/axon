"""`Attachment` e os anexos no `ToolResult` e na `Message` (FR-028, FR-029, ADR-044, research R34)."""

from __future__ import annotations

import hashlib

import pytest

from axon_ai_contracts import ATTACHMENT_MIME_TYPES, Attachment, Message, ToolResult

PNG = b"\x89PNG\r\n\x1a\nconteudo"


def test_id_comes_from_the_bytes() -> None:
    attachment = Attachment(mime="image/png", data=PNG)
    assert attachment.id == "img-" + hashlib.sha256(PNG).hexdigest()[:12]
    assert Attachment(mime="image/png", data=PNG, alt="outro").id == attachment.id
    assert Attachment(mime="image/png", data=PNG + b"x").id != attachment.id


def test_id_is_not_an_argument() -> None:
    with pytest.raises(TypeError):
        Attachment(mime="image/png", data=PNG, id="img-000000000000")  # type: ignore[call-arg]


def test_closed_mime_list() -> None:
    assert frozenset({"image/png", "image/jpeg", "image/webp", "image/gif"}) == ATTACHMENT_MIME_TYPES
    assert Attachment(mime="IMAGE/JPEG", data=PNG).mime == "image/jpeg"
    for mime in ("image/svg+xml", "text/html", "image/jpg", ""):
        with pytest.raises(ValueError):
            Attachment(mime=mime, data=PNG)


def test_data_must_be_non_empty_bytes() -> None:
    with pytest.raises(ValueError):
        Attachment(mime="image/png", data=b"")
    with pytest.raises(TypeError):
        Attachment(mime="image/png", data="iVBOR")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Attachment(mime="image/png", data=bytearray(PNG))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("alt", "expected"),
    [
        (None, None),
        ("Gastos por categoria", "Gastos por categoria"),
        ("linha 1\nlinha 2\r\n", "linha 1 linha 2"),
        ("![x](javascript:alert(1))", "!xjavascript:alert1"),
        ("   ", None),
        ("[]()", None),
        ("a" * 200, "a" * 120),
    ],
)
def test_alt_is_cleaned(alt: str | None, expected: str | None) -> None:
    assert Attachment(mime="image/png", data=PNG, alt=alt).alt == expected


def test_repr_has_no_bytes_and_value_is_frozen() -> None:
    attachment = Attachment(mime="image/png", data=PNG, alt="gráfico")
    assert "PNG" not in repr(attachment)
    with pytest.raises(AttributeError):
        attachment.alt = "outro"  # type: ignore[misc]


def test_tool_result_attachments() -> None:
    assert ToolResult(content="ok").attachments == ()
    image = Attachment(mime="image/png", data=PNG)
    result = ToolResult(content="tabela", attachments=[image])  # type: ignore[arg-type]
    assert result.attachments == (image,)
    with pytest.raises(TypeError):
        ToolResult(content="x", attachments=("não é anexo",))  # type: ignore[arg-type]


def test_message_with_attachments() -> None:
    image = Attachment(mime="image/webp", data=PNG)
    message: Message = {"role": "user", "content": "o que é isto?", "attachments": (image,)}
    plain: Message = {"role": "user", "content": "oi"}
    assert message["attachments"][0].id == image.id
    assert "attachments" not in plain
