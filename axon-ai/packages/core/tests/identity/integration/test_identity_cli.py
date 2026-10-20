"""T034/T061 — linha de comando da 012 (R14): `users …` e `identity keys rotate`."""

from __future__ import annotations

import io

from identity_testkit import ADMIN_GROUP, Harness

from axon_ai.identity.adapters import cli
from axon_ai.identity.domain.accounts import TEMPORARY_PASSWORD_PATTERN


def _io() -> tuple[io.StringIO, io.StringIO]:
    return io.StringIO(), io.StringIO()


async def test_create_pela_entrada_padrao_e_pelo_prompt(started: Harness) -> None:
    out, err = _io()
    code = await cli.users_create_command(
        started.service,
        username="Admin",
        email="Admin@Exemplo.org",
        name=None,
        groups=[ADMIN_GROUP],
        password_stdin=True,
        persistent=True,
        stdin=io.StringIO("senha-do-admin-inicial\n"),
        out=out,
        err=err,
    )
    assert code == 0 and err.getvalue() == ""
    assert "admin  admin@exemplo.org  admin  ativa" in out.getvalue()
    assert "senha-do-admin-inicial" not in out.getvalue()
    record = await started.accounts.by_username("admin")
    assert await started.hasher.verify(record.password_hash, "senha-do-admin-inicial")
    assert not record.account.temporary_password

    answers = iter(["outra-senha-boa-1", "outra-senha-boa-1"])
    out, err = _io()
    code = await cli.users_create_command(
        started.service,
        username="bia",
        email="bia@exemplo.org",
        name="Bia",
        groups=[],
        password_stdin=False,
        persistent=False,
        stdin=io.StringIO(),
        out=out,
        err=err,
        prompt=lambda _: next(answers),
    )
    assert code == 0 and "ATENÇÃO" in err.getvalue()


async def test_create_recusa_senha_curta_confirmacao_diferente_e_nome_repetido(started: Harness) -> None:
    out, err = _io()
    code = await cli.users_create_command(
        started.service,
        username="ana",
        email="ana@exemplo.org",
        name=None,
        groups=[],
        password_stdin=True,
        persistent=True,
        stdin=io.StringIO("curta\n"),
        out=out,
        err=err,
    )
    assert code == 2 and "password" in err.getvalue() and "curta" not in err.getvalue()
    answers = iter(["senha-forte-numero-1", "senha-forte-numero-2"])
    code = await cli.users_create_command(
        started.service,
        username="ana",
        email="ana@exemplo.org",
        name=None,
        groups=[],
        password_stdin=False,
        persistent=True,
        stdin=io.StringIO(),
        out=out,
        err=err,
        prompt=lambda _: next(answers),
    )
    assert code == 2 and "não conferem" in err.getvalue()
    await started.add_account("ana")
    err = io.StringIO()
    code = await cli.users_create_command(
        started.service,
        username="ana",
        email="outra@exemplo.org",
        name=None,
        groups=[],
        password_stdin=True,
        persistent=True,
        stdin=io.StringIO("senha-forte-numero-1\n"),
        out=out,
        err=err,
    )
    assert code == 1 and "já existe" in err.getvalue()


async def test_list_disable_enable_password_e_groups(started: Harness) -> None:
    await started.add_account("ana")
    await started.add_account("bia", groups={"equipe"})
    out, err = _io()
    assert await cli.users_disable_command(started.service, username="bia", persistent=True, out=out, err=err) == 0
    out = io.StringIO()
    await cli.users_list_command(started.service, query=None, include_disabled=False, persistent=True, out=out, err=err)
    assert out.getvalue().splitlines() == ["ana  ana@exemplo.org  -  ativa"]
    out = io.StringIO()
    await cli.users_list_command(started.service, query=None, include_disabled=True, persistent=True, out=out, err=err)
    assert "bia  bia@exemplo.org  equipe  desativada" in out.getvalue()
    assert await cli.users_enable_command(started.service, username="bia", persistent=True, out=out, err=err) == 0

    out = io.StringIO()
    assert await cli.users_password_command(started.service, username="ana", persistent=True, out=out, err=err) == 0
    temporary = out.getvalue().splitlines()[-1]
    assert TEMPORARY_PASSWORD_PATTERN.fullmatch(temporary)

    out = io.StringIO()
    code = await cli.users_groups_command(
        started.service, username="ana", groups=["equipe"], persistent=True, out=out, err=err
    )
    assert code == 0 and (await started.service.account("ana")).groups == frozenset({"equipe"})
    err = io.StringIO()
    code = await cli.users_groups_command(
        started.service, username="ana", groups=["fantasma"], persistent=True, out=out, err=err
    )
    assert code == 1 and "fantasma" in err.getvalue()
    err = io.StringIO()
    assert await cli.users_disable_command(started.service, username="zeca", persistent=True, out=out, err=err) == 1


async def test_grupos_pela_linha_de_comando(started: Harness) -> None:
    out, err = _io()
    assert await cli.groups_create_command(started.service, name="Equipe", persistent=True, out=out, err=err) == 0
    assert await cli.groups_create_command(started.service, name="equipe", persistent=True, out=out, err=err) == 1
    out = io.StringIO()
    assert await cli.groups_list_command(started.service, persistent=True, out=out, err=err) == 0
    assert out.getvalue().splitlines() == ["admin  0  (administração)", "equipe  0"]


async def test_rotacao_de_chaves(started: Harness) -> None:
    before = started.service.jwks()["keys"][0]["kid"]
    out, err = _io()
    assert await cli.identity_keys_rotate_command(started.service, force=False, persistent=True, out=out, err=err) == 0
    kids = [key["kid"] for key in started.service.jwks()["keys"]]
    assert before in kids and len(kids) == 2 and "segue publicada" in out.getvalue()
