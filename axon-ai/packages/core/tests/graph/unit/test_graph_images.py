"""Políticas puras das imagens (ADR-044; research R51): o plano, o conteúdo ao modelo, a escolha e o custo no teto."""

from __future__ import annotations

import pytest

from axon_ai.graph.domain.actions import UNKNOWN_IMAGE, InvalidAction, ViewImageAction, action_schema, parse_action
from axon_ai.graph.domain.budget import estimate_tokens
from axon_ai.graph.domain.images import (
    IMAGE_TOKENS,
    candidates,
    chosen,
    gate_format,
    image_plan,
    parse_gate,
    unique,
    user_content,
    user_images,
)
from axon_ai.llm.api import image_part
from axon_ai_contracts import Attachment, Message

A = Attachment(mime="image/png", data=b"a" * 10)
B = Attachment(mime="image/gif", data=b"b" * 10)
F = Attachment(mime="image/jpeg", data=b"f" * 10)

CONVERSA: tuple[Message, ...] = (
    {"role": "assistant", "content": "antiga", "attachments": (F,)},
    {"role": "user", "content": "1"},
    {"role": "assistant", "content": "nova", "attachments": (A, B, A)},
    {"role": "user", "content": "e isto?", "attachments": (F,)},
)


def test_candidatas_so_da_ultima_mensagem_do_assistente_e_sem_repeticao() -> None:
    assert candidates(CONVERSA) == (A, B)
    assert user_images(CONVERSA) == (F,)
    assert candidates(({"role": "user", "content": "oi"},)) == ()
    assert unique((A, B, A, F, B)) == (A, B, F)


@pytest.mark.parametrize(
    ("loop", "controller", "vision", "esperado"),
    [
        (True, True, True, {"candidates": (A, B), "viewed": (), "gate": False}),
        (False, True, True, {"candidates": (A, B), "viewed": (), "gate": True}),
        (False, False, True, {"candidates": (A, B), "viewed": (A.id, B.id), "gate": False}),
        (False, True, False, {"candidates": (), "viewed": (), "gate": False}),
        (True, True, False, {"candidates": (), "viewed": (), "gate": False}),
    ],
)
def test_a_tabela_do_item_8(loop: bool, controller: bool, vision: bool, esperado: dict[str, object]) -> None:
    plan = image_plan(
        CONVERSA, loop_flow=loop, controller=controller, generation_vision=vision, controller_vision=False
    )
    assert {"candidates": plan.candidates, "viewed": plan.viewed, "gate": plan.gate} == esperado
    assert plan.user_images == (F,) and plan.to_generation is vision and plan.to_controller is False


def test_conteudo_da_ultima_mensagem() -> None:
    assert user_content("oi", ()) == "oi"
    assert user_content("oi", (F,), send_own=False) == f"oi\n[imagem {F.id} enviada pelo usuário]"
    assert user_content("", (F,), send_own=False) == f"[imagem {F.id} enviada pelo usuário]"
    assert user_content("oi", (F,), send_own=True) == [
        {"type": "text", "text": "oi"},
        image_part(F.mime, F.data),
    ]
    assert user_content("oi", (F,), send_own=False, shown=(A,)) == [
        {"type": "text", "text": f"oi\n[imagem {F.id} enviada pelo usuário]"},
        {"type": "text", "text": f"[imagem {A.id} mostrada ao usuário]"},
        image_part(A.mime, A.data),
    ]
    assert chosen((A, B), (B.id,)) == (B,)


def test_escolha_da_image_gate() -> None:
    ids = (A.id, B.id)
    schema = gate_format(ids)["json_schema"]["schema"]
    assert schema["properties"]["view"]["items"]["enum"] == list(ids)
    assert parse_gate(f'{{"view": ["{B.id}", "{A.id}"]}}', ids) == (A.id, B.id)
    assert parse_gate('{"view": []}', ids) == ()
    for ruim in (None, "", "[]", '{"view": "x"}', '{"view": ["img-falsa"]}', '{"view": [1]}'):
        assert parse_gate(ruim, ids) is None


def test_view_image_no_formato_e_na_leitura_da_acao() -> None:
    assert len(action_schema([], ())["anyOf"]) == 1
    branch = action_schema([], (A.id,))["anyOf"][1]
    assert branch["required"] == ["action", "id"] and branch["properties"]["id"]["enum"] == [A.id]
    assert parse_action(f'{{"action": "view_image", "id": "{A.id}"}}', (A.id,)) == ViewImageAction(id=A.id)
    assert parse_action(f'{{"action": "view_image", "id": "{A.id}"}}', ()) == InvalidAction(reason=UNKNOWN_IMAGE)
    assert parse_action('{"action": "view_image"}', (A.id,)) == InvalidAction(reason=UNKNOWN_IMAGE)


def test_cada_imagem_custa_um_valor_fixo_no_teto() -> None:
    texto = estimate_tokens([{"role": "user", "content": "oi"}])
    com_imagem = estimate_tokens(
        [{"role": "user", "content": [{"type": "text", "text": "oi"}, image_part("image/png", b"x" * 9000)]}]
    )
    assert com_imagem == texto + IMAGE_TOKENS
