"""Comandos `packs list`, `packs check` e `packs prepare` (US4; specs/002-core-pack-runtime/contracts/cli.md).

Funções sobre o Pack Registry que a composition root já montou e carregou — com os mesmos adapters do servidor e sem
abrir a API. Como leem o mesmo registry, pela mesma rotina de carga do boot, `check` reprova exatamente o que o
servidor marcaria como erro (research R15, R16). `prepare` não carrega o registry: leva cada pack habilitado só até a
configuração validada e chama o hook `prepare` (ADR-041, research R63, R65). Quem as registra na raiz `axon` é a 011
(US4), por isso não há parser aqui.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TextIO

from axon_ai.packs.api import PackConfigError, PackDataPreparation, PackEntry, PackRegistry, PackStatus

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


def prepare_command(preparation: PackDataPreparation, out: TextIO, err: TextIO) -> int:
    """Uma linha por pack habilitado — nome, `ok`/`error`, diretório ou causa — e um resumo. 1 se algum falhar."""
    try:
        prepared = preparation.prepare_data()
    except PackConfigError as error:
        return config_error_command(error, err)
    rows = [
        (
            item.name,
            "ok" if item.ok else "error",
            item.error or (str(item.data_dir) if item.data_dir is not None else _MISSING),
        )
        for item in prepared
    ]
    _print_rows(rows, out)
    failed = sum(1 for item in prepared if not item.ok)
    if failed:
        print(f"{failed} de {len(prepared)} packs falharam no preparo", file=out)
        return EXIT_ERROR
    print(f"{len(prepared)} packs preparados", file=out)
    return EXIT_OK


def _print_rows(rows: Sequence[tuple[str, ...]], out: TextIO) -> None:
    """Colunas alinhadas, menos a última, que é texto livre (a causa)."""
    fixed = max((len(row) for row in rows), default=1) - 1
    widths = [max((len(row[column]) for row in rows), default=0) for column in range(fixed)]
    for row in rows:
        columns = [value.ljust(width) for value, width in zip(row[:fixed], widths, strict=True)]
        print("  ".join([*columns, row[fixed]]).rstrip(), file=out)


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
    _print_rows(rows, out)
