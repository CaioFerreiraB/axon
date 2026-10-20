"""Comandos de linha de comando da 003 (contracts/cli.md).

Funções que recebem o serviço já montado e a saída, e devolvem o código de saída. Quem as registra na raiz `axon` é
a composition root (011 US4): o framework de linha de comando é decisão dela (research R14), por isso não há parser
aqui.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from typing import Protocol, TextIO

from axon_ai.assistants.api import (
    ApiKeyInfo,
    AssistantsConfigError,
    AssistantStatus,
    IssuedApiKey,
    NotFound,
    OverrideView,
    RequestRejected,
    ValidationReport,
)

EXIT_OK = 0
EXIT_UNAVAILABLE = 1
EXIT_CONFIG_ERROR = 2


class _Validator(Protocol):
    async def validate(self) -> ValidationReport: ...

    async def overrides_as_operator(self) -> Sequence[tuple[str, OverrideView]]: ...


async def validate_command(service: _Validator, out: TextIO) -> int:
    """`axon assistants validate`: uma linha por Assistant e um resumo. 0 se todos disponíveis, 1 se algum não."""
    report = await service.validate()
    width = max((len(status.name) for status in report.statuses), default=0)
    for status in report.statuses:
        print(_line(status, width), file=out)
    # Sobreposições que o deploy desligou: guardadas, sem efeito — o operador fica sabendo (ADR-032, T082).
    for name, override in await service.overrides_as_operator():
        if override.state == "inactive":
            print(f"sobreposição inativa: {name}.{override.section} — {override.reason}", file=out)

    total = len(report.statuses)
    unavailable = sum(1 for status in report.statuses if not status.available)
    if unavailable:
        noun = "indisponível" if unavailable == 1 else "indisponíveis"
        print(f"{unavailable} de {total} Assistants {noun}", file=out)
        return EXIT_UNAVAILABLE
    print(f"{total} Assistants disponíveis", file=out)
    return EXIT_OK


def validate_config_error(error: AssistantsConfigError, err: TextIO) -> int:
    """Erro de arquivo no `assistants.yaml`: a mensagem já nomeia o campo."""
    print(f"assistants.yaml inválido: {error}", file=err)
    return EXIT_CONFIG_ERROR


def _line(status: AssistantStatus, width: int) -> str:
    state = "ok" if status.available else "indisponível"
    parts = [f"{status.name:<{width}}", f"{status.origin:<6}", f"{state:<12}"]
    if status.reasons:
        parts.append("; ".join(status.reasons))
    if status.owner is not None:
        parts.append(f"(dono {status.owner})")
    return "  ".join(parts).rstrip()


# --- keys (FR-015) ----------------------------------------------------------------------------------------------------

NOT_PERSISTENT_WARNING = (
    "ATENÇÃO: este perfil não tem armazenamento persistente — a chave vale só neste processo, "
    "não para o servidor. Emita chaves no perfil persistente."
)


class _KeysOperator(Protocol):
    async def issue_as_operator(
        self, *, subject: str, groups: Collection[str] = (), label: str | None = None
    ) -> IssuedApiKey: ...

    async def keys_as_operator(self) -> Sequence[ApiKeyInfo]: ...

    async def revoke_as_operator(self, *, key_id: str) -> ApiKeyInfo: ...


async def keys_create_command(
    service: _KeysOperator,
    *,
    subject: str,
    groups: Sequence[str],
    label: str | None,
    persistent: bool,
    out: TextIO,
    err: TextIO,
) -> int:
    """`axon keys create`: a chave em claro sai **uma vez**, sozinha na última linha — para que um script a capture —
    e em nenhum outro lugar."""
    _warn_if_not_persistent(persistent, err)
    try:
        issued = await service.issue_as_operator(subject=subject, groups=groups, label=label)
    except RequestRejected as error:
        print(f"erro: {error}", file=err)
        return EXIT_UNAVAILABLE
    info = issued.info
    print(f"key_id: {info.key_id}", file=out)
    print(f"subject: {info.subject}  groups: {_groups(info.groups)}", file=out)
    if info.label:
        print(f"label: {info.label}", file=out)
    print(issued.plaintext, file=out)
    return EXIT_OK


async def keys_list_command(service: _KeysOperator, *, persistent: bool, out: TextIO, err: TextIO) -> int:
    """`axon keys list`: nunca mostra hash nem chave."""
    _warn_if_not_persistent(persistent, err)
    for info in await service.keys_as_operator():
        state = f"revogada em {info.revoked_at.isoformat()}" if info.revoked_at else "ativa"
        label = info.label or "-"
        created = info.created_at.isoformat()
        print(f"{info.key_id}  {info.subject}  {_groups(info.groups)}  {label}  {created}  {state}", file=out)
    return EXIT_OK


async def keys_revoke_command(
    service: _KeysOperator, *, key_id: str, persistent: bool, out: TextIO, err: TextIO
) -> int:
    """`axon keys revoke <key_id>`: a próxima requisição com a chave é recusada."""
    _warn_if_not_persistent(persistent, err)
    try:
        info = await service.revoke_as_operator(key_id=key_id)
    except NotFound as error:
        print(f"erro: {error}", file=err)
        return EXIT_UNAVAILABLE
    revoked = info.revoked_at.isoformat() if info.revoked_at else "?"
    print(f"revogada: {info.key_id} ({info.subject}) em {revoked}", file=out)
    return EXIT_OK


def _groups(groups: Collection[str]) -> str:
    return ", ".join(sorted(groups)) or "-"


def _warn_if_not_persistent(persistent: bool, err: TextIO) -> None:
    if not persistent:
        print(NOT_PERSISTENT_WARNING, file=err)
