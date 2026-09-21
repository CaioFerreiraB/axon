"""Ponto de entrada do processo: o comando `ai-core` (specs/011-core-bootstrap/contracts/boot-sequence.md).

Nesta fase há um subcomando só, `serve`. Os subcomandos contribuídos por cada módulo — `packs list`,
`assistants validate` — chegam na Fase 2, e é por isso que o parser é o da biblioteca padrão: não vale escolher agora
um framework de linha de comando que a US4 pode querer diferente (research R5).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import Any

from ai_core.bootstrap.profiles import ANONYMOUS_WARNING
from ai_core.bootstrap.wiring import Platform, platform

Server = Callable[[Any, str, int, float], None]
"""Como servir a aplicação: app, host, porta e prazo de encerramento."""


def _uvicorn_server(app: Any, host: str, port: int, grace: float) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, timeout_graceful_shutdown=int(grace))


def main(argv: Sequence[str] | None = None, *, server: Server = _uvicorn_server) -> int:
    """Raiz do comando. `server` é parâmetro para que a suíte exercite o comando sem abrir porta."""
    parser = argparse.ArgumentParser(prog="ai-core", description="Plataforma Agentic AI — núcleo")
    subcommands = parser.add_subparsers(dest="command", required=True)
    serve = subcommands.add_parser("serve", help="sobe a plataforma e serve a API")
    serve.add_argument("--profile", default=None, help="perfil de adapters (sobrepõe a configuração)")

    args = parser.parse_args(argv)
    if args.command == "serve":
        return _serve(profile=args.profile, server=server)
    return 2  # pragma: no cover — argparse já recusa comando desconhecido


def _serve(*, profile: str | None, server: Server) -> int:
    try:
        built = platform(profile=profile)
    except Exception as error:
        print(f"falha ao carregar a configuração: {type(error).__name__}: {error}", file=sys.stderr, flush=True)
        return 1

    # `flush` em toda saída do boot: o relatório precisa aparecer na hora, não quando o buffer encher — é o que o
    # operador lê para achar a falha em menos de um minuto (SC-005), inclusive quando o processo é morto em seguida.
    print(built.report.render(), flush=True)
    if not built.report.ok:
        failure = built.report.failure()
        detail = f"{failure.name}: {failure.detail}" if failure else "etapa desconhecida"
        print(f"boot interrompido em {detail}", file=sys.stderr, flush=True)
        return 1

    _warn_if_anonymous(built)
    settings = built.settings
    print(f"servindo em http://{settings.host}:{settings.port}", flush=True)
    try:
        server(built.app, settings.host, settings.port, settings.shutdown_grace_seconds)
    finally:
        built.aclose()
    return 0


def _warn_if_anonymous(built: Platform) -> None:
    """O perfil que mais parece produção é o que não tem autenticação: dizer isso alto é barato (princípio VII)."""
    if built.profile is not None and built.profile.anonymous_auth:
        print(ANONYMOUS_WARNING, file=sys.stderr, flush=True)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
