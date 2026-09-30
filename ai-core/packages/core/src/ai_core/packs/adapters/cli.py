"""Comandos `packs list` e `packs check` (US4; specs/002-core-pack-runtime/contracts/cli.md).

Funções sobre o Pack Registry que a composition root já montou e carregou — com os mesmos adapters do servidor e sem
abrir a API. Como leem o mesmo registry, pela mesma rotina de carga do boot, `check` reprova exatamente o que o
servidor marcaria como erro (research R15, R16). Quem as registra na raiz `ai-core` é a 011 (US4), por isso não há
parser aqui.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TextIO

from ai_core.packs.api import PackConfigError, PackEntry, PackRegistry, PackStatus

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_CONFIG_ERROR = 2
"""Os códigos do `assistants validate` (003): um script de build trata os dois comandos do mesmo jeito."""

_MISSING = "-"


def list_command(registry: PackRegistry, out: TextIO) -> int:
    """Uma linha por pack: nome, versão, versão de contrato, status e, se em erro, a causa. Listar não é validar: 0."""
    _print_entries(registry.entries(), out)
    return EXIT_OK


def check_command(registry: PackRegistry, out: TextIO) -> int:
    """Só as entradas em erro e um resumo. 1 se houver alguma — inclusive pack instalado e desabilitado (R16)."""
    entries = registry.entries()
    broken = [entry for entry in entries if entry.status is PackStatus.ERROR]
    _print_entries(broken, out)
    if broken:
        print(f"{len(broken)} de {len(entries)} packs em erro", file=out)
        return EXIT_ERROR
    print(f"{len(entries)} packs ok", file=out)
    return EXIT_OK


def config_error_command(error: PackConfigError, err: TextIO) -> int:
    """`packs.yaml` malformado: o boot pararia pelo mesmo motivo. A mensagem já nomeia o campo."""
    print(f"packs.yaml inválido: {error}", file=err)
    return EXIT_CONFIG_ERROR


def _print_entries(entries: Sequence[PackEntry], out: TextIO) -> None:
    rows = [
        (
            entry.name,
            entry.version or _MISSING,
            entry.contract_version or _MISSING,
            str(entry.status),
            entry.error or "",
        )
        for entry in entries
    ]
    widths = [max((len(row[column]) for row in rows), default=0) for column in range(4)]
    for row in rows:
        columns = [value.ljust(width) for value, width in zip(row[:4], widths, strict=True)]
        print("  ".join([*columns, row[4]]).rstrip(), file=out)
