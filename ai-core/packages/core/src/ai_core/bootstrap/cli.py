"""Ponto de entrada do processo: o comando `ai-core` (contracts/cli.md e contracts/boot-sequence.md).

A raiz é a da biblioteca padrão (research R5, R17). Cada subcomando chama a função que o módulo dono oferece no próprio
`adapters/cli.py` — `packs` da 002, `assistants` e `keys` da 003, `health` desta spec —; aqui só se montam o parser, a
configuração e os adapters, com a mesma configuração e os mesmos adapters do servidor (FR-010). Nenhum subcomando além
de `serve` abre a API (FR-011). Acrescentar os comandos de um módulo é acrescentar entradas a `COMMANDS`.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, TextIO

from ai_core.assistants.adapters import cli as assistants_cli
from ai_core.assistants.api import AssistantsConfigError
from ai_core.assistants.service import AccessService
from ai_core.bootstrap.health import boot_items, health_command
from ai_core.bootstrap.profiles import NO_CREDENTIALS_WARNING, lacks_credentials
from ai_core.bootstrap.settings import ConfigurationError, EnvConfigSource, Settings
from ai_core.bootstrap.wiring import (
    STAGE_ADAPTERS,
    STAGE_CONFIGURATION,
    STAGE_ENGINE,
    Platform,
    access_service,
    assistants_source,
    capabilities_service,
    mcp_service,
    pack_runtime,
    platform,
    platform_health,
    session_assistants,
    storage,
)
from ai_core.capabilities.adapters.cli import audit_command
from ai_core.http.ports import HealthReport
from ai_core.packs.adapters import cli as packs_cli
from ai_core.packs.api import PackConfigError, PackRegistry

Server = Callable[[Any, str, int, float], None]
"""Como servir a aplicação: app, host, porta e prazo de encerramento."""

EXIT_OK: Final = 0
EXIT_FAILURE: Final = 1
EXIT_DOWN: Final = 2


def _uvicorn_server(app: Any, host: str, port: int, grace: float) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, timeout_graceful_shutdown=int(grace))


@dataclass(frozen=True, slots=True, kw_only=True)
class Io:
    """Saídas e servidor de uma execução do comando — parâmetros, para que a suíte exercite tudo sem abrir porta."""

    out: TextIO
    err: TextIO
    server: Server


Handler = Callable[[argparse.Namespace, Io], int]


def _no_arguments(_parser: argparse.ArgumentParser) -> None:
    return None


@dataclass(frozen=True, slots=True, kw_only=True)
class Command:
    """Um subcomando registrado: o caminho (`("keys", "create")`), a ajuda, os argumentos próprios e a ação."""

    path: tuple[str, ...]
    help: str
    run: Handler
    arguments: Callable[[argparse.ArgumentParser], None] = _no_arguments


def main(
    argv: Sequence[str] | None = None,
    *,
    server: Server = _uvicorn_server,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Raiz do comando. `server`, `out` e `err` são parâmetros para que a suíte o exercite sem abrir porta."""
    args = _parser().parse_args(argv)
    command: Command = args.command_entry
    return command.run(args, Io(out=out or sys.stdout, err=err or sys.stderr, server=server))


def _parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--profile", default=None, help="perfil de adapters (sobrepõe AI_CORE_PROFILE)")

    parser = argparse.ArgumentParser(prog="ai-core", description="Plataforma Agentic AI — núcleo")
    root = parser.add_subparsers(dest="command", required=True)
    groups: dict[str, Any] = {}
    for command in COMMANDS:
        head, *rest = command.path
        if not rest:
            leaf = root.add_parser(head, help=command.help, parents=[common])
        else:
            if head not in groups:
                group = root.add_parser(head, help=GROUPS.get(head))
                groups[head] = group.add_subparsers(dest=f"{head}_command", required=True)
            leaf = groups[head].add_parser(rest[0], help=command.help, parents=[common])
        command.arguments(leaf)
        leaf.set_defaults(command_entry=command)
    return parser


# --- montagem compartilhada -------------------------------------------------------------------------------------------


def _boot(args: argparse.Namespace, io: Io, *, until: str | None = None) -> Platform | None:
    """A plataforma, ou `None` com o motivo no erro — nomeando a variável, a etapa e, para o banco, porta e adapter."""
    built = platform(profile=args.profile, until=until)
    if built.report.ok:
        return built
    failure = built.report.failure()
    detail = f"{failure.name}: {failure.detail}" if failure else "etapa desconhecida"
    print(f"boot interrompido em {detail}", file=io.err, flush=True)
    built.aclose()
    return None


def _failed_at_configuration(built: Platform) -> bool:
    failure = built.report.failure()
    return failure is not None and failure.name == STAGE_CONFIGURATION


def _settings(args: argparse.Namespace) -> Settings:
    settings = EnvConfigSource().load()
    return dataclasses.replace(settings, profile=args.profile) if args.profile else settings


# --- serve ------------------------------------------------------------------------------------------------------------


def _serve(args: argparse.Namespace, io: Io) -> int:
    try:
        built = platform(profile=args.profile)
    except Exception as error:
        print(f"falha ao carregar a configuração: {type(error).__name__}: {error}", file=io.err, flush=True)
        return EXIT_FAILURE

    # `flush` em toda saída do boot: o relatório precisa aparecer na hora, não quando o buffer encher — é o que o
    # operador lê para achar a falha em menos de um minuto (SC-005), inclusive quando o processo é morto em seguida.
    print(built.report.render(), file=io.out, flush=True)
    if not built.report.ok:
        failure = built.report.failure()
        detail = f"{failure.name}: {failure.detail}" if failure else "etapa desconhecida"
        print(f"boot interrompido em {detail}", file=io.err, flush=True)
        return EXIT_FAILURE

    if lacks_credentials(built.settings):
        # Falha fechada por falta de configuração não é defeito — mas só parece isso se o boot disser alto.
        print(NO_CREDENTIALS_WARNING, file=io.err, flush=True)
    settings = built.settings
    print(f"servindo em http://{settings.host}:{settings.port}", file=io.out, flush=True)
    try:
        io.server(built.app, settings.host, settings.port, settings.shutdown_grace_seconds)
    finally:
        built.aclose()
    return EXIT_OK


# --- packs (002) ------------------------------------------------------------------------------------------------------


def _packs(action: Callable[[PackRegistry, TextIO], int]) -> Handler:
    """Só configuração, adapters e a carga dos packs: é o que distingue `packs.yaml` malformado (2) de pack em erro."""

    def run(args: argparse.Namespace, io: Io) -> int:
        built = _boot(args, io, until=STAGE_ADAPTERS)
        if built is None:
            return EXIT_FAILURE
        try:
            registry = pack_runtime(built.parts)
            try:
                registry.load()
            except PackConfigError as error:
                return packs_cli.config_error_command(error, io.err)
            return action(registry, io.out)
        finally:
            built.aclose()

    return run


# --- assistants validate (003) ----------------------------------------------------------------------------------------


def _assistants_validate(args: argparse.Namespace, io: Io) -> int:
    try:
        assistants_source(_settings(args)).load()
    except ConfigurationError as error:
        print(f"boot interrompido em {STAGE_CONFIGURATION}: {error}", file=io.err, flush=True)
        return EXIT_FAILURE
    except AssistantsConfigError as error:
        # O boot pararia pelo mesmo motivo; o código 2 distingue arquivo malformado de Assistant indisponível.
        return assistants_cli.validate_config_error(error, io.err)
    built = _boot(args, io)
    if built is None:
        return EXIT_FAILURE
    try:
        return asyncio.run(_validate(built.parts, io.out))
    finally:
        built.aclose()


async def _validate(parts: Mapping[str, Any], out: TextIO) -> int:
    async with storage(parts) as session:
        return await assistants_cli.validate_command(session_assistants(parts, session), out)


# --- keys (003) -------------------------------------------------------------------------------------------------------


def _keys_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--subject", required=True, help="dono da chave: user:<id> ou svc:<id>")
    parser.add_argument("--group", action="append", default=[], help="grupo da chave (repetível)")
    parser.add_argument("--label", default=None, help="rótulo para reconhecer a chave na listagem")


def _keys_revoke_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("key_id", help="a parte pública da chave (16 hex)")


KeysAction = Callable[[AccessService, argparse.Namespace, bool, Io], Awaitable[int]]
"""Serviço de acesso sobre o armazenamento da sessão, argumentos, se o armazenamento persiste, e saídas."""


def _keys(action: KeysAction) -> Handler:
    """Configuração e adapters; o armazenamento de chaves abre e fecha no laço do próprio comando (R13)."""

    def run(args: argparse.Namespace, io: Io) -> int:
        built = _boot(args, io, until=STAGE_ADAPTERS)
        if built is None:
            return EXIT_FAILURE
        try:
            return asyncio.run(_with_keys(built.parts, args, io, action))
        except Exception as error:
            print(f"erro: {error}", file=io.err, flush=True)
            return EXIT_FAILURE
        finally:
            built.aclose()

    return run


async def _with_keys(parts: Mapping[str, Any], args: argparse.Namespace, io: Io, action: KeysAction) -> int:
    persistent = parts["database"] is not None
    async with storage(parts) as session:
        return await action(access_service(parts, keys=session["api_keys"]), args, persistent, io)


def _keys_create(service: AccessService, args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
    return assistants_cli.keys_create_command(
        service,
        subject=args.subject,
        groups=args.group,
        label=args.label,
        persistent=persistent,
        out=io.out,
        err=io.err,
    )


def _keys_list(service: AccessService, _args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
    return assistants_cli.keys_list_command(service, persistent=persistent, out=io.out, err=io.err)


def _keys_revoke(service: AccessService, args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
    return assistants_cli.keys_revoke_command(
        service, key_id=args.key_id, persistent=persistent, out=io.out, err=io.err
    )


# --- health (011) -----------------------------------------------------------------------------------------------------


def _health(args: argparse.Namespace, io: Io) -> int:
    """A plataforma inteira, sem servir. Boot que falha numa etapa crítica é `down`: os itens dizem qual e por quê."""
    built = platform(profile=args.profile)
    try:
        if _failed_at_configuration(built):
            failure = built.report.failure()
            print(f"boot interrompido em {STAGE_CONFIGURATION}: {failure.detail if failure else ''}", file=io.err)
            return EXIT_FAILURE
        if not built.report.ok:
            return health_command(HealthReport(items=boot_items(built.report)), io.out)
        return asyncio.run(_check(built, io.out))
    finally:
        built.aclose()


async def _check(built: Platform, out: TextIO) -> int:
    async with storage(built.parts) as session:
        health = platform_health(built.parts, session=session)
        health.report = built.report
        return health_command(await health.health(), out)


# --- audit (004) ------------------------------------------------------------------------------------------------------


def _audit_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--principal", default=None, help="só os registros deste Principal")
    parser.add_argument("--assistant", default=None, help="só os registros deste Assistant")
    parser.add_argument("--tool", default=None, help="só os registros desta tool (nome com namespace)")
    parser.add_argument("--since", default=None, help="a partir deste instante (ISO 8601, com fuso)")
    parser.add_argument("--until", default=None, help="até este instante (ISO 8601, com fuso)")
    parser.add_argument("--limit", type=int, default=100, help="quantos registros, de 1 a 1000")
    parser.add_argument("--results", action="store_true", help="imprime também o resultado que o modelo recebeu")


def _audit(args: argparse.Namespace, io: Io) -> int:
    """Sobe até o motor — sem rede: o gateway precisa do Trace Sink — e consulta a auditoria da 004 na sessão de
    armazenamento, pela mesma fábrica do servidor (R29)."""
    built = _boot(args, io, until=STAGE_ENGINE)
    if built is None:
        return EXIT_FAILURE
    try:
        return asyncio.run(_audit_query(built.parts, args, io))
    finally:
        built.aclose()


async def _audit_query(parts: Mapping[str, Any], args: argparse.Namespace, io: Io) -> int:
    async with storage(parts) as session:
        query = capabilities_service(parts, audit=session["audit"], mcp=mcp_service(parts, store=session["mcp_store"]))
        return await audit_command(
            query,
            principal=args.principal,
            assistant=args.assistant,
            tool=args.tool,
            since=args.since,
            until=args.until,
            limit=args.limit,
            results=args.results,
            out=io.out,
            err=io.err,
        )


# --- registro ---------------------------------------------------------------------------------------------------------

GROUPS: Final[Mapping[str, str]] = {
    "packs": "packs instalados e configurados (002)",
    "assistants": "Assistants de sistema e de usuário (003)",
    "keys": "chaves de API da superfície privada (003)",
}

COMMANDS: Final[tuple[Command, ...]] = (
    Command(path=("serve",), help="sobe a plataforma e serve a API", run=_serve),
    Command(path=("packs", "list"), help="lista os packs e o estado de cada um", run=_packs(packs_cli.list_command)),
    Command(path=("packs", "check"), help="reprova pack em erro (código 1)", run=_packs(packs_cli.check_command)),
    Command(path=("assistants", "validate"), help="valida as referências dos Assistants", run=_assistants_validate),
    Command(
        path=("keys", "create"),
        help="emite uma chave de API (aparece uma vez)",
        run=_keys(_keys_create),
        arguments=_keys_create_arguments,
    ),
    Command(path=("keys", "list"), help="lista as chaves, sem segredo", run=_keys(_keys_list)),
    Command(
        path=("keys", "revoke"), help="revoga uma chave", run=_keys(_keys_revoke), arguments=_keys_revoke_arguments
    ),
    Command(path=("health",), help="saúde agregada: 0 ok, 1 degradada, 2 fora do ar", run=_health),
    Command(
        path=("audit",),
        help="lista as chamadas de tool de escrita auditadas (004); 2 para filtro inválido",
        run=_audit,
        arguments=_audit_arguments,
    ),
)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
