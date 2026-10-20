"""A timeline de status do Open WebUI (FR-005a, research R42): pura, com o tempo dado por quem chama.

Cada etapa vira duas linhas: o início, com `done: false`, e o desfecho que o motor publica (005, ADR-028), com o tempo
que a API mede entre os dois. No fim, uma linha por registro do evento final e a linha de conclusão. Daqui só saem
nomes, argumentos, contagens, fontes e decisões — o desfecho do motor já não traz texto de trecho, conteúdo de resultado
nem texto de erro de tool, e um registro `error` aparece pelo tipo, não pela mensagem.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from ai_core.graph.api import (
    CatalogOutcome,
    ControllerOutcome,
    ExecutionIssue,
    FinalEvent,
    GateOutcome,
    GenerationOutcome,
    ProgressEvent,
    RerankOutcome,
    SourceRef,
    StepFinished,
    StepOutcome,
    ToolCallsOutcome,
    ToolCallSummary,
)
from ai_core.http.domain.progress_text import progress_line, queue_line
from axon_ai_contracts import JSONValue

ARGUMENTS_LIMIT: Final = 120
"""Argumentos maiores que isto saem cortados com "…": a linha é para acompanhar, não para auditar."""

LISTED: Final = 3
"""Quantos documentos ou fontes a linha nomeia antes de "e mais N"."""

RETRIEVAL_KIND: Final = "retrieval"

_DONE: Final[Mapping[str, str]] = {
    "prepare_context": "Contexto preparado",
    "validate_answer": "Resposta conferida",
}

_TOOL_STATUS: Final[Mapping[str, str]] = {
    "ok": "ok",
    "error": "erro",
    "timeout": "tempo esgotado",
    "unknown": "ferramenta inexistente",
    "invalid_arguments": "argumentos inválidos",
}

_ROUTE: Final[Mapping[str, str]] = {
    "controller": "busca com ferramentas",
    "fallback": "resposta sem trechos",
}

_DECISION: Final[Mapping[str, str]] = {
    "answer": "responder",
    "failed": "o controller falhou; segue para a resposta",
}


@dataclass(frozen=True, slots=True)
class Status:
    """Um item da timeline: o texto e se ele fecha uma etapa (`done`). Sem `done`, o Open WebUI o anima."""

    description: str
    done: bool


class Timeline:
    """A timeline de uma resposta. Guarda só o início de cada etapa em curso, para medir o desfecho."""

    def __init__(self, started_at: datetime) -> None:
        self._started_at = started_at
        self._begun: dict[str, datetime] = {}

    def queued(self, position: int) -> Status:
        return Status(queue_line(position), done=False)

    def started(self, event: ProgressEvent, at: datetime) -> Status:
        self._begun[event.stage] = at
        return Status(progress_line(event.stage, event.detail), done=False)

    def finished(self, event: StepFinished, at: datetime) -> tuple[Status, ...]:
        """Uma linha por desfecho (no `retrieve`, uma por chamada); o tempo da etapa vai na última. Fim sem início
        conhecido sai sem tempo."""
        lines = outcome_lines(event.stage, event.outcome)
        begun = self._begun.pop(event.stage, None)
        if begun is not None:
            lines[-1] += f" · {duration(at - begun)}"
        return tuple(Status(line, done=True) for line in lines)

    def final(self, event: FinalEvent, at: datetime) -> tuple[Status, ...]:
        """Os registros da execução e a linha de conclusão, com o tempo desde a abertura da resposta."""
        total = duration(at - self._started_at)
        if any(issue.severity == "error" for issue in event.errors):
            closing = f"Terminou com erro em {total}"
        else:
            closing = f"Concluído em {total}"
            if event.citations:
                closing += f" · {plural(len(event.citations), 'citação', 'citações')}"
        return (*(Status(issue_line(issue), done=True) for issue in event.errors), Status(closing, done=True))


def outcome_lines(stage: str, outcome: StepOutcome | None) -> list[str]:
    match outcome:
        case None:
            return [_DONE.get(stage, f"Etapa {stage} concluída")]
        case ToolCallsOutcome(calls=calls):
            return [call_line(call) for call in calls] or ["Nenhuma ferramenta chamada"]
        case CatalogOutcome():
            return [catalog_line(outcome)]
        case ControllerOutcome():
            return [controller_line(outcome)]
        case RerankOutcome():
            return [rerank_line(outcome)]
        case GateOutcome():
            return [gate_line(outcome)]
        case GenerationOutcome():
            return [generation_line(outcome)]


def call_line(call: ToolCallSummary) -> str:
    result = _TOOL_STATUS.get(call.status, call.status)
    if call.truncated:
        result += ", cortado"
    if call.sources or (call.kind == RETRIEVAL_KIND and call.status == "ok"):
        result += f": {sources_text(call.sources)}"
    return f"{call.tool}({arguments_text(call.arguments)}) → {result}"


def catalog_line(outcome: CatalogOutcome) -> str:
    if outcome.tools == 0:
        line = "Nenhuma ferramenta disponível"
    else:
        line = plural(outcome.tools, "ferramenta disponível", "ferramentas disponíveis")
    if outcome.unavailable:
        line += f"; indisponível: {', '.join(outcome.unavailable)}"
    return line


def controller_line(outcome: ControllerOutcome) -> str:
    if outcome.action == "tool":
        what = f"chamar {outcome.tool}({arguments_text(outcome.arguments or {})})"
    elif outcome.action == "invalid":
        what = "ação inválida" + (f" ({outcome.reason})" if outcome.reason else "")
    else:
        what = _DECISION[outcome.action]
    return f"Decisão (iteração {outcome.iteration}, {outcome.model}): {what}"


def rerank_line(outcome: RerankOutcome) -> str:
    if outcome.candidates == 0:
        line = "Nenhum trecho para ordenar"
    else:
        kept = listing([reference(source) for source in outcome.kept], separator="; ")
        line = f"{len(outcome.kept)} de {plural(outcome.candidates, 'trecho', 'trechos')}"
        if kept:
            line += f": {kept}"
    if outcome.degraded:
        line += f" (reranker de {', '.join(outcome.degraded)} falhou; valeu a ordem da busca)"
    return line


def gate_line(outcome: GateOutcome) -> str:
    best = None if outcome.best_score is None else score(outcome.best_score)
    if outcome.covered:
        head = "Coberto" if best is None else f"Coberto: melhor score {best}"
        head += ", sem limiar" if outcome.threshold is None else f", limiar {score(outcome.threshold)}"
    elif best is None:
        head = "Não coberto: nenhum trecho"
    elif outcome.threshold is None:
        head = f"Não coberto: melhor score {best}"
    else:
        head = f"Não coberto: melhor score {best} abaixo do limiar {score(outcome.threshold)}"
    if outcome.route == "generate":
        route = f"resposta com {plural(outcome.delivered, 'trecho', 'trechos')}"
    else:
        route = _ROUTE[outcome.route]
    return f"{head} → {route}"


def generation_line(outcome: GenerationOutcome) -> str:
    tokens = []
    if outcome.input_tokens is not None:
        tokens.append(f"{thousands(outcome.input_tokens)} tokens de entrada")
    if outcome.output_tokens is not None:
        tokens.append(f"{thousands(outcome.output_tokens)} de saída")
    line = f"Resposta de {outcome.model}"
    return f"{line} · {', '.join(tokens)}" if tokens else line


def issue_line(issue: ExecutionIssue) -> str:
    """Aviso com a mensagem (escrita pelo motor ou pelo validator); erro só com o tipo e a etapa — a mensagem de um
    erro pode trazer o texto de erro de uma tool ou de um servidor."""
    if issue.severity == "notice":
        return f"Aviso: {issue.message}"
    return f"Erro em {issue.stage}: {issue.kind}"


# --- formatação pt-BR -------------------------------------------------------------------------------------------


def arguments_text(arguments: Mapping[str, JSONValue]) -> str:
    text = ", ".join(f"{name}={json.dumps(value, ensure_ascii=False)}" for name, value in arguments.items())
    if len(text) <= ARGUMENTS_LIMIT:
        return text
    return text[: ARGUMENTS_LIMIT - 1].rstrip() + "…"


def sources_text(sources: Sequence[SourceRef]) -> str:
    if not sources:
        return "nenhum trecho"
    documents = list(dict.fromkeys(source.document for source in sources))
    found = plural(len(sources), "trecho", "trechos")
    return f"{found} de {plural(len(documents), 'documento', 'documentos')}: {listing(documents)}"


def reference(source: SourceRef) -> str:
    text = source.document
    if source.section:
        text += f" — {source.section}"
    if source.page is not None:
        text += f", p. {source.page}"
    return text


def listing(items: Iterable[str], *, separator: str = ", ") -> str:
    values = list(items)
    shown = separator.join(values[:LISTED])
    if len(values) > LISTED:
        shown += f" e mais {len(values) - LISTED}"
    return shown


def plural(count: int, singular: str, plural_form: str) -> str:
    return f"{thousands(count)} {singular if count == 1 else plural_form}"


def thousands(value: int) -> str:
    return f"{value:,}".replace(",", ".")


def score(value: float) -> str:
    return f"{value:.2f}".replace(".", ",")


def duration(delta: timedelta) -> str:
    """`12 ms`, `1,2 s`, `18 s`, `1 min 3 s`."""
    seconds = max(delta.total_seconds(), 0.0)
    if seconds < 1:
        return f"{round(seconds * 1000)} ms"
    if seconds < 10:
        return f"{seconds:.1f} s".replace(".", ",")
    whole = round(seconds)
    if whole < 60:
        return f"{whole} s"
    minutes, rest = divmod(whole, 60)
    return f"{minutes} min {rest} s" if rest else f"{minutes} min"
