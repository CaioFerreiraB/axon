"""Comandos de linha de comando da 012 (research R14): `users …` e `identity keys rotate`.

Funções que recebem o serviço já montado, as entradas e as saídas, e devolvem o código de saída. Quem as registra na
raiz `ai-core` é a composition root (011), como os da 003: não há parser aqui. A senha da linha de comando é a
definitiva da pessoa e chega pela entrada padrão (`--password-stdin`) ou por um prompt sem eco; a senha temporária
gerada sai uma vez, sozinha na última linha, para que um script a capture.
"""

from __future__ import annotations

import getpass
from collections.abc import Callable, Sequence
from typing import Final, TextIO

from ai_core.identity.api import Account, AccountDraft, AccountPatch, IdentityError, InvalidField
from ai_core.identity.service import IdentityService

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
EXIT_INVALID: Final = 2
ACTOR: Final = "cli"

NOT_PERSISTENT_WARNING: Final = (
    "ATENÇÃO: este perfil não tem armazenamento persistente — a conta vale só neste processo, não para o servidor. "
    "Use o perfil persistente."
)

type Prompt = Callable[[str], str]


def _warn(persistent: bool, err: TextIO) -> None:
    if not persistent:
        print(NOT_PERSISTENT_WARNING, file=err)


def _line(account: Account) -> str:
    state = "ativa" if account.active else "desativada"
    groups = ", ".join(sorted(account.groups)) or "-"
    flags = []
    if account.temporary_password:
        flags.append("senha temporária")
    if not account.has_password:
        flags.append("só Google")
    if account.google_linked:
        flags.append("Google vinculado")
    extra = f"  ({'; '.join(flags)})" if flags else ""
    return f"{account.username}  {account.email}  {groups}  {state}{extra}"


def _read_password(*, stdin_flag: bool, stdin: TextIO, prompt: Prompt, err: TextIO) -> str | None:
    if stdin_flag:
        return stdin.readline().rstrip("\r\n")
    first = prompt("Senha: ")
    if first != prompt("Confirme a senha: "):
        print("erro: as senhas não conferem", file=err)
        return None
    return first


async def users_create_command(
    service: IdentityService,
    *,
    username: str,
    email: str,
    name: str | None,
    groups: Sequence[str],
    password_stdin: bool,
    persistent: bool,
    stdin: TextIO,
    out: TextIO,
    err: TextIO,
    prompt: Prompt = getpass.getpass,
) -> int:
    """`ai-core users create <usuário> --email … [--name …] [--group …]… [--password-stdin]` (FR-018)."""
    _warn(persistent, err)
    try:
        draft = AccountDraft(
            username=username.strip().lower(),
            email=email.strip().lower(),
            name=(name or username).strip(),
            groups=frozenset(groups),
        )
    except ValueError as error:
        print(f"erro: {error}", file=err)
        return EXIT_INVALID
    password = _read_password(stdin_flag=password_stdin, stdin=stdin, prompt=prompt, err=err)
    if password is None:
        return EXIT_INVALID
    try:
        account = await service.create_with_password(draft, password, actor=ACTOR)
    except InvalidField as error:
        print(f"erro: {error.field}: {error}", file=err)
        return EXIT_INVALID
    except IdentityError as error:
        print(f"erro: {error}", file=err)
        return EXIT_FAILED
    print(f"criada: {_line(account)}", file=out)
    return EXIT_OK


async def users_list_command(
    service: IdentityService, *, query: str | None, include_disabled: bool, persistent: bool, out: TextIO, err: TextIO
) -> int:
    """`ai-core users list [--all] [--query …]`: nunca mostra hash nem segredo."""
    _warn(persistent, err)
    cursor: str | None = None
    while True:
        page = await service.accounts(query=query, active=None if include_disabled else True, limit=200, cursor=cursor)
        for account in page.items:
            print(_line(account), file=out)
        if page.next_cursor is None:
            return EXIT_OK
        cursor = page.next_cursor


async def users_disable_command(
    service: IdentityService, *, username: str, persistent: bool, out: TextIO, err: TextIO
) -> int:
    """`ai-core users disable <usuário>`: encerra as sessões; o token de acesso já emitido vence em até 10 min."""
    _warn(persistent, err)
    try:
        account = await service.disable(username, actor=ACTOR)
    except IdentityError as error:
        print(f"erro: {error}", file=err)
        return EXIT_FAILED
    print(f"desativada: {_line(account)}", file=out)
    return EXIT_OK


async def users_enable_command(
    service: IdentityService, *, username: str, persistent: bool, out: TextIO, err: TextIO
) -> int:
    _warn(persistent, err)
    try:
        account = await service.enable(username, actor=ACTOR)
    except IdentityError as error:
        print(f"erro: {error}", file=err)
        return EXIT_FAILED
    print(f"reativada: {_line(account)}", file=out)
    return EXIT_OK


async def users_password_command(
    service: IdentityService, *, username: str, persistent: bool, out: TextIO, err: TextIO
) -> int:
    """`ai-core users password <usuário>`: gera uma senha temporária e a mostra uma vez, na última linha."""
    _warn(persistent, err)
    try:
        issued = await service.reset_password(username, actor=ACTOR)
    except IdentityError as error:
        print(f"erro: {error}", file=err)
        return EXIT_FAILED
    print(f"senha temporária de {issued.account.username} (troca obrigatória no próximo login):", file=out)
    print(issued.temporary_password, file=out)
    return EXIT_OK


async def users_groups_command(
    service: IdentityService, *, username: str, groups: Sequence[str], persistent: bool, out: TextIO, err: TextIO
) -> int:
    """`ai-core users groups <usuário> --set a --set b`: os grupos passam a ser exatamente estes."""
    _warn(persistent, err)
    try:
        current = await service.account(username)
        account = await service.update(
            username, AccountPatch(groups=frozenset(groups)), actor=ACTOR, version=current.version
        )
    except ValueError as error:
        print(f"erro: {error}", file=err)
        return EXIT_INVALID
    except IdentityError as error:
        print(f"erro: {error}", file=err)
        return EXIT_FAILED
    print(f"grupos: {_line(account)}", file=out)
    return EXIT_OK


async def identity_keys_rotate_command(
    service: IdentityService, *, force: bool, persistent: bool, out: TextIO, err: TextIO
) -> int:
    """`ai-core identity keys rotate [--force]` (FR-016). Forçada: todas as sessões caem."""
    _warn(persistent, err)
    kid = await service.rotate_keys(force=force)
    if force:
        print(f"chave nova: {kid}; as anteriores saíram e todas as sessões foram encerradas", file=out)
    else:
        print(f"chave nova: {kid}; a anterior segue publicada até os tokens dela vencerem", file=out)
    return EXIT_OK
