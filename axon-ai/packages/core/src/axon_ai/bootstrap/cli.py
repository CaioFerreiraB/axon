"""Ponto de entrada do processo: o comando `axon` (contracts/cli.md e contracts/boot-sequence.md).

A raiz é a da biblioteca padrão (research R5, R17). Cada subcomando chama a função que o módulo dono oferece no próprio
`adapters/cli.py` — `packs` da 002, `assistants` e `keys` da 003, `health` desta spec —; aqui só se montam o parser, a
configuração e os adapters, com a mesma configuração e os mesmos adapters do servidor (FR-010). Nenhum subcomando além
de `serve` abre a API (FR-011). Acrescentar os comandos de um módulo é acrescentar entradas a `COMMANDS`.
"""

from __future__ import annotations

import argparse
import asyncio
import dataclasses
import importlib.metadata
import sys
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TextIO

from axon_ai.assistants.adapters import cli as assistants_cli
from axon_ai.assistants.api import AssistantsConfigError, Principal
from axon_ai.assistants.service import AccessService
from axon_ai.bootstrap import identity as identity_parts
from axon_ai.bootstrap.health import boot_items, health_command
from axon_ai.bootstrap.observability import EVALUATION, PRODUCTION
from axon_ai.bootstrap.profiles import NO_CREDENTIALS_WARNING, lacks_credentials
from axon_ai.bootstrap.settings import ConfigurationError, EnvConfigSource, Settings
from axon_ai.bootstrap.wiring import (
    STAGE_ADAPTERS,
    STAGE_ASSISTANTS,
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
    session_identity,
    storage,
)
from axon_ai.capabilities.adapters.cli import audit_command
from axon_ai.eval.adapters import cli as eval_cli
from axon_ai.eval.adapters.files import JsonReportStore, YamlGoldenSetSource
from axon_ai.eval.adapters.judge import RoutedJudge
from axon_ai.eval.api import EvalInputError
from axon_ai.eval.service import EvalService
from axon_ai.http.ports import HealthReport
from axon_ai.identity.adapters import cli as identity_cli
from axon_ai.identity.service import IdentityService
from axon_ai.observability.ports import Origin
from axon_ai.packs.adapters import cli as packs_cli
from axon_ai.packs.api import PackConfigError, PackRegistry

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
    common.add_argument("--profile", default=None, help="perfil de adapters (sobrepõe AXON_PROFILE)")

    parser = argparse.ArgumentParser(prog="axon", description="Axon — linha de comando do operador")
    # Sai antes de qualquer subcomando: a versão não carrega configuração (US7, R49).
    parser.add_argument("--version", action="version", version=f"axon-ai {_core_version()}")
    root = parser.add_subparsers(dest="command", required=True)
    groups: dict[tuple[str, ...], Any] = {(): root}
    for command in COMMANDS:
        # Grupos aninhados pelo caminho: `identity keys rotate` cria `identity` e `identity keys` (Fase 9, R42).
        for depth in range(1, len(command.path)):
            prefix = command.path[:depth]
            if prefix not in groups:
                group = groups[prefix[:-1]].add_parser(prefix[-1], help=GROUPS.get(" ".join(prefix)))
                groups[prefix] = group.add_subparsers(dest="_".join(prefix) + "_command", required=True)
        leaf = groups[command.path[:-1]].add_parser(command.path[-1], help=command.help, parents=[common])
        command.arguments(leaf)
        leaf.set_defaults(command_entry=command)
    return parser


# --- montagem compartilhada -------------------------------------------------------------------------------------------


def _boot(
    args: argparse.Namespace, io: Io, *, until: str | None = None, origin: Origin = PRODUCTION
) -> Platform | None:
    """A plataforma, ou `None` com o motivo no erro — nomeando a variável, a etapa e, para o banco, porta e adapter."""
    built = platform(profile=args.profile, until=until, origin=origin)
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


def _key_id_arguments(parser: argparse.ArgumentParser) -> None:
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


def _api_keys_rotate(service: AccessService, args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
    return assistants_cli.keys_rotate_command(
        service, key_id=args.key_id, persistent=persistent, out=io.out, err=io.err
    )


# --- users e identity (012) -------------------------------------------------------------------------------------------

IDENTITY_DISABLED: Final = "identidade desligada: defina AXON_IDENTITY_ENABLED=true (e a configuração da 012)"


def _username_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("username", help="nome de usuário")


def _users_create_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("username", help="nome de usuário (minúsculas, sem @)")
    parser.add_argument("--email", required=True, help="e-mail da pessoa")
    parser.add_argument("--name", default=None, help="nome de exibição (padrão: o usuário)")
    parser.add_argument("--group", action="append", default=[], help="grupo (repetível)")
    parser.add_argument(
        "--password-stdin", action="store_true", help="lê a senha da entrada padrão (senão, pergunta sem eco)"
    )


def _users_list_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--all", action="store_true", help="inclui as contas desativadas")
    parser.add_argument("--query", default=None, help="busca em usuário, e-mail e nome")


def _users_groups_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("username", help="nome de usuário")
    parser.add_argument("--set", action="append", default=[], dest="groups", help="grupo (repetível; vazio = nenhum)")


def _group_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("name", help="nome do grupo (minúsculas, sem @)")


def _groups_create(service: IdentityService, args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
    return identity_cli.groups_create_command(service, name=args.name, persistent=persistent, out=io.out, err=io.err)


def _groups_list(service: IdentityService, _args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
    return identity_cli.groups_list_command(service, persistent=persistent, out=io.out, err=io.err)


def _keys_rotate_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--force", action="store_true", help="retira todas as chaves e encerra todas as sessões")


IdentityAction = Callable[[IdentityService, argparse.Namespace, bool, Io], Awaitable[int]]


def _identity_command(action: IdentityAction) -> Handler:
    """Configuração e adapters; o armazenamento da 012 abre e fecha no laço do próprio comando (R13, R42)."""

    def run(args: argparse.Namespace, io: Io) -> int:
        built = _boot(args, io, until=STAGE_ADAPTERS)
        if built is None:
            return EXIT_FAILURE
        try:
            if not built.settings.identity_enabled:
                print(f"erro: {IDENTITY_DISABLED}", file=io.err, flush=True)
                return EXIT_FAILURE
            return asyncio.run(_with_identity(built.context.parts, args, io, action))
        except Exception as error:
            print(f"erro: {error}", file=io.err, flush=True)
            return EXIT_FAILURE
        finally:
            built.aclose()

    return run


async def _with_identity(parts: dict[str, Any], args: argparse.Namespace, io: Io, action: IdentityAction) -> int:
    identity_parts.prepare(parts)
    persistent = parts["database"] is not None
    async with storage(parts) as session:
        service = identity_parts.identity_service(parts, session=session)
        service.load_configuration()
        await service.ensure_admin_group()
        return await action(service, args, persistent, io)


def _users_create(service: IdentityService, args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
    return identity_cli.users_create_command(
        service,
        username=args.username,
        email=args.email,
        name=args.name,
        groups=args.group,
        password_stdin=args.password_stdin,
        persistent=persistent,
        stdin=sys.stdin,
        out=io.out,
        err=io.err,
    )


def _users_list(service: IdentityService, args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
    return identity_cli.users_list_command(
        service, query=args.query, include_disabled=args.all, persistent=persistent, out=io.out, err=io.err
    )


def _users_simple(command: Callable[..., Awaitable[int]]) -> IdentityAction:
    def action(service: IdentityService, args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
        return command(service, username=args.username, persistent=persistent, out=io.out, err=io.err)

    return action


def _users_groups(service: IdentityService, args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
    return identity_cli.users_groups_command(
        service, username=args.username, groups=args.groups, persistent=persistent, out=io.out, err=io.err
    )


def _keys_rotate(service: IdentityService, args: argparse.Namespace, persistent: bool, io: Io) -> Awaitable[int]:
    return identity_cli.identity_keys_rotate_command(
        service, force=args.force, persistent=persistent, out=io.out, err=io.err
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
        health = platform_health(built.parts, session=session, identity=await session_identity(built.parts, session))
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


# --- eval (009) -------------------------------------------------------------------------------------------------------


def _eval_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--golden", required=True, help="conjunto dourado (YAML, contracts/eval-harness.md)")
    parser.add_argument("--assistant", default=None, help="Assistant avaliado (sobrepõe o do conjunto)")
    parser.add_argument(
        "--judge", default=None, help="modelo juiz offline, provider/modelo (sem ele: fidelidade ausente)"
    )
    parser.add_argument("--baseline", default=None, help="linha de base (relatório JSON) para comparar")
    parser.add_argument("--update-baseline", action="store_true", help="grava esta rodada como linha de base")
    parser.add_argument("--force", action="store_true", help="com --update-baseline, grava mesmo com regressão")
    parser.add_argument("--report", default=None, help="grava o relatório desta rodada (JSON)")
    parser.add_argument("--principal", default="svc:eval", help="quem roda: user:<id> ou svc:<id> (default svc:eval)")
    parser.add_argument("--group", action="append", default=[], help="grupo do principal (repetível)")
    parser.add_argument("--annotate", action="append", default=[], help="anotação livre no relatório (ex.: RAM)")


def _eval_run(args: argparse.Namespace, io: Io) -> int:
    """Sobe a plataforma até os Assistants — sem a API — e roda o conjunto dourado pelo motor (009 research R25)."""
    try:
        principal = Principal(subject=args.principal, scheme="api_key", groups=frozenset(args.group))
    except ValueError as error:
        print(f"--principal inválido: {error}", file=io.err, flush=True)
        return eval_cli.EXIT_INVALID
    # As chamadas da rodada contam como `evaluation` no relatório de uso, não como produção (009; R40).
    built = _boot(args, io, until=STAGE_ASSISTANTS, origin=EVALUATION)
    if built is None:
        return EXIT_FAILURE
    try:
        return asyncio.run(_eval_session(built.parts, args, principal, io))
    finally:
        built.aclose()


async def _eval_session(parts: Mapping[str, Any], args: argparse.Namespace, principal: Principal, io: Io) -> int:
    try:
        judge = RoutedJudge(parts["routing"], args.judge) if args.judge else None
    except EvalInputError as error:
        print(str(error), file=io.err, flush=True)
        return eval_cli.EXIT_INVALID
    async with storage(parts) as session:
        harness = EvalService(
            engine=parts["engine"],
            trace=parts["trace"],
            grants=session_assistants(parts, session),
            pack_metrics=parts["packs"],
            clock=parts["clock"],
            core_version=_core_version(),
            judge=judge,
        )
        try:
            return await eval_cli.run_command(
                harness,
                YamlGoldenSetSource(),
                JsonReportStore(),
                golden=Path(args.golden),
                assistant=args.assistant,
                principal=principal,
                out=io.out,
                err=io.err,
                report=Path(args.report) if args.report else None,
                baseline=Path(args.baseline) if args.baseline else None,
                update_baseline=args.update_baseline,
                force=args.force,
                annotations=args.annotate,
            )
        finally:
            # O uso da rodada vai para o armazenamento desta sessão: o pool de serviço não abre na linha de comando.
            await parts["usage_destination"].flush(session["usage_store"])


def _eval_compare_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("reports", nargs="+", help="relatórios JSON a pôr lado a lado")


def _eval_compare(args: argparse.Namespace, io: Io) -> int:
    """Sem plataforma: só lê relatórios (US4)."""
    return eval_cli.compare_command(JsonReportStore(), [Path(p) for p in args.reports], out=io.out, err=io.err)


def _core_version() -> str:
    try:
        return importlib.metadata.version("axon-ai")
    except importlib.metadata.PackageNotFoundError:
        return "desconhecida"


# --- registro ---------------------------------------------------------------------------------------------------------

GROUPS: Final[Mapping[str, str]] = {
    "packs": "packs instalados e configurados (002)",
    "assistants": "Assistants de sistema e de usuário (003)",
    "keys": "chaves de API da superfície privada (003)",
    "eval": "harness de avaliação: conjunto dourado, linha de base e comparação (009)",
    "users": "contas do provedor de identidade da plataforma (012)",
    "groups": "grupos do provedor de identidade da plataforma (012)",
    "identity": "provedor de identidade da plataforma (012)",
    "identity keys": "chaves de assinatura dos tokens (012)",
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
    Command(path=("keys", "revoke"), help="revoga uma chave", run=_keys(_keys_revoke), arguments=_key_id_arguments),
    Command(
        path=("keys", "rotate"),
        help="gera um segredo novo para a chave (aparece uma vez; o anterior deixa de valer)",
        run=_keys(_api_keys_rotate),
        arguments=_key_id_arguments,
    ),
    Command(path=("health",), help="saúde agregada: 0 ok, 1 degradada, 2 fora do ar", run=_health),
    Command(
        path=("audit",),
        help="lista as chamadas de tool de escrita auditadas (004); 2 para filtro inválido",
        run=_audit,
        arguments=_audit_arguments,
    ),
    Command(
        path=("eval", "run"),
        help="roda um conjunto dourado contra um Assistant: 0 ok, 1 regressão, 2 entrada inválida",
        run=_eval_run,
        arguments=_eval_run_arguments,
    ),
    Command(
        path=("eval", "compare"),
        help="relatórios lado a lado (benchmark de modelos)",
        run=_eval_compare,
        arguments=_eval_compare_arguments,
    ),
    Command(
        path=("users", "create"),
        help="cria uma conta com a senha definitiva (lida sem eco)",
        run=_identity_command(_users_create),
        arguments=_users_create_arguments,
    ),
    Command(
        path=("users", "list"),
        help="lista as contas, sem segredo",
        run=_identity_command(_users_list),
        arguments=_users_list_arguments,
    ),
    Command(
        path=("users", "disable"),
        help="desativa uma conta e encerra as sessões dela",
        run=_identity_command(_users_simple(identity_cli.users_disable_command)),
        arguments=_username_argument,
    ),
    Command(
        path=("users", "enable"),
        help="reativa uma conta",
        run=_identity_command(_users_simple(identity_cli.users_enable_command)),
        arguments=_username_argument,
    ),
    Command(
        path=("users", "password"),
        help="gera uma senha temporária (aparece uma vez)",
        run=_identity_command(_users_simple(identity_cli.users_password_command)),
        arguments=_username_argument,
    ),
    Command(
        path=("users", "groups"),
        help="define os grupos de uma conta",
        run=_identity_command(_users_groups),
        arguments=_users_groups_arguments,
    ),
    Command(
        path=("groups", "create"),
        help="cria um grupo",
        run=_identity_command(_groups_create),
        arguments=_group_argument,
    ),
    Command(path=("groups", "list"), help="lista os grupos e os membros ativos", run=_identity_command(_groups_list)),
    Command(
        path=("identity", "keys", "rotate"),
        help="nova chave de assinatura; --force encerra todas as sessões",
        run=_identity_command(_keys_rotate),
        arguments=_keys_rotate_arguments,
    ),
)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
