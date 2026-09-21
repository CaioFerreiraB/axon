"""Sequência de boot e encerramento (specs/011-core-bootstrap/contracts/boot-sequence.md).

As etapas são **dado**: nome, ação e política de falha. Este executor não menciona módulo nenhum, e é por isso que
acrescentar uma etapa numa fase futura não o toca (research R1).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

Closer = Callable[[], None]


class StageStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass(slots=True)
class BootContext:
    """O que as etapas constroem e onde registram o que precisa ser liberado."""

    parts: dict[str, Any] = field(default_factory=dict)
    closers: list[Closer] = field(default_factory=list)

    def on_close(self, closer: Closer) -> None:
        """Registra um recurso a liberar. O encerramento roda na ordem inversa do registro (FR-013)."""
        self.closers.append(closer)


@dataclass(frozen=True, slots=True, kw_only=True)
class Stage:
    """Uma etapa do boot.

    `critical` é a política de falha: interromper o boot ou degradar e seguir. É o princípio VII escrito como dado —
    configuração e adapters são críticos; pack em erro degrada e o resto atende.
    """

    name: str
    run: Callable[[BootContext], None]
    critical: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class StageOutcome:
    name: str
    status: StageStatus
    detail: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class BootReport:
    """O que o operador lê para saber o que falhou e por quê, sem abrir log (SC-005)."""

    stages: tuple[StageOutcome, ...] = ()

    @property
    def ok(self) -> bool:
        """Verdadeiro quando nenhuma etapa crítica falhou."""
        return all(outcome.status is not StageStatus.FAILED for outcome in self.stages)

    @property
    def degraded(self) -> tuple[str, ...]:
        return tuple(o.name for o in self.stages if o.status is StageStatus.DEGRADED)

    def failure(self) -> StageOutcome | None:
        return next((o for o in self.stages if o.status is StageStatus.FAILED), None)

    def render(self) -> str:
        """Uma linha por etapa, alinhada — é o que o `serve` imprime."""
        width = max((len(o.name) for o in self.stages), default=0)
        lines = []
        for outcome in self.stages:
            line = f"{outcome.name.ljust(width)}  {outcome.status}"
            if outcome.detail:
                line += f"  — {outcome.detail}"
            lines.append(line)
        return "\n".join(lines)


def run_stages(stages: Sequence[Stage], context: BootContext | None = None) -> tuple[BootReport, BootContext]:
    """Executa as etapas na ordem declarada, respeitando a política de cada uma.

    Falha em etapa crítica interrompe o boot e desfaz o que já foi construído, na ordem inversa; falha em etapa
    degradável registra o motivo e o boot segue.
    """
    ctx = context or BootContext()
    outcomes: list[StageOutcome] = []
    for stage in stages:
        try:
            stage.run(ctx)
        except Exception as error:
            detail = f"{type(error).__name__}: {error}"
            if stage.critical:
                outcomes.append(StageOutcome(name=stage.name, status=StageStatus.FAILED, detail=detail))
                shutdown(ctx)
                return BootReport(stages=tuple(outcomes)), ctx
            outcomes.append(StageOutcome(name=stage.name, status=StageStatus.DEGRADED, detail=detail))
            continue
        outcomes.append(_outcome_of(stage, ctx))
    return BootReport(stages=tuple(outcomes)), ctx


def _outcome_of(stage: Stage, ctx: BootContext) -> StageOutcome:
    """Uma etapa que concluiu pode ainda estar degradada — é o caso de um pack em erro (002)."""
    detail = ctx.parts.pop(f"{stage.name}:degraded", None)
    if detail:
        return StageOutcome(name=stage.name, status=StageStatus.DEGRADED, detail=str(detail))
    return StageOutcome(name=stage.name, status=StageStatus.OK)


def shutdown(ctx: BootContext) -> None:
    """Libera os recursos na ordem inversa do boot. Falha ao liberar não impede os demais."""
    for closer in reversed(ctx.closers):
        try:
            closer()
        except Exception:
            # Encerrar precisa terminar: um recurso que falha ao fechar não pode reter os outros.
            continue
    ctx.closers.clear()
