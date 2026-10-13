"""Os comandos do harness (research R20, R23 a R25), registrados pela 011 como `ai-core eval run|compare`.

Saída: 0 sem regressão; 1 com regressão de métrica determinística além da tolerância; 2 para entrada inválida
(conjunto ilegível, Assistant inexistente, trace sem leitura, relatório ilegível).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Final, TextIO

from ai_core.assistants.api import Principal
from ai_core.eval.api import Comparison, EvalHarness, EvalInputError, EvalReport, GoldenSetError, MetricValue
from ai_core.eval.domain.compare import compare
from ai_core.eval.ports import BaselineStore, GoldenSetSource

EXIT_OK: Final = 0
EXIT_REGRESSION: Final = 1
EXIT_INVALID: Final = 2


async def run_command(
    harness: EvalHarness,
    source: GoldenSetSource,
    store: BaselineStore,
    *,
    golden: Path,
    assistant: str | None,
    principal: Principal,
    out: TextIO,
    err: TextIO,
    report: Path | None = None,
    baseline: Path | None = None,
    update_baseline: bool = False,
    force: bool = False,
    annotations: Sequence[str] = (),
) -> int:
    try:
        golden_set = source.load(golden)
    except GoldenSetError as error:
        err.write(f"conjunto dourado inválido: {error}\n")
        return EXIT_INVALID
    target = assistant or golden_set.assistant
    if not target:
        err.write("nenhum Assistant: use --assistant ou declare `assistant` no conjunto dourado\n")
        return EXIT_INVALID
    try:
        base = store.load(baseline) if baseline is not None else None
        result = await harness.run(golden_set, assistant=target, principal=principal, annotations=annotations)
    except EvalInputError as error:
        err.write(f"{error}\n")
        return EXIT_INVALID

    _print_report(result, out)
    if report is not None:
        store.save(report, result)
        out.write(f"\nrelatório: {report}\n")
    if baseline is None:
        return EXIT_OK
    if base is None:
        out.write(f"\nsem linha de base em {baseline}")
        if update_baseline:
            store.save(baseline, result)
            out.write(" — gravada a desta rodada")
        out.write("\n")
        return EXIT_OK
    comparison = compare(result, base, golden_set.tolerances)
    _print_comparison(comparison, out)
    if update_baseline and (not comparison.regressed or force):
        store.save(baseline, result)
        out.write(f"linha de base atualizada: {baseline}\n")
    elif update_baseline:
        out.write("linha de base mantida: houve regressão (use --force para gravar mesmo assim)\n")
    return EXIT_REGRESSION if comparison.regressed else EXIT_OK


def compare_command(store: BaselineStore, paths: Sequence[Path], *, out: TextIO, err: TextIO) -> int:
    """O benchmark (US4): as métricas de vários relatórios lado a lado, com as anotações de cada um."""
    reports: list[EvalReport] = []
    for path in paths:
        try:
            loaded = store.load(path)
        except EvalInputError as error:
            err.write(f"{error}\n")
            return EXIT_INVALID
        if loaded is None:
            err.write(f"relatório não encontrado: {path}\n")
            return EXIT_INVALID
        reports.append(loaded)
    headers = [f"{r.assistant}" + (f" (juiz {r.judge})" if r.judge else "") for r in reports]
    names: list[str] = []
    for loaded in reports:
        names.extend(m.name for m in loaded.metrics if m.name not in names)
    rows = [["métrica", *headers]]
    for name in names:
        rows.append([name, *(_value(loaded.metric(name)) for loaded in reports)])
    out.write(_table(rows))
    for header, loaded in zip(headers, reports, strict=True):
        for annotation in loaded.annotations:
            out.write(f"{header}: {annotation}\n")
    return EXIT_OK


def _print_report(report: EvalReport, out: TextIO) -> None:
    out.write(f"conjunto {report.golden_set} · Assistant {report.assistant}")
    out.write(f" · juiz {report.judge}\n" if report.judge else " · sem juiz\n")
    rows = [["métrica", "valor", "variância", "n", "determinística"]]
    for metric in report.metrics:
        rows.append(
            [
                metric.name,
                _value(metric),
                "" if metric.variance is None else f"{metric.variance:.4f}",
                str(metric.n),
                "sim" if metric.deterministic else "",
            ]
        )
    out.write(_table(rows))
    for item in report.invalid:
        out.write(f"item inválido {item.id or '?'}: {item.reason}\n")
    for result in report.items:
        if result.failure:
            out.write(f"item {result.id} falhou: {result.failure}\n")
        for warning in result.warnings:
            out.write(f"item {result.id}: {warning}\n")


def _print_comparison(comparison: Comparison, out: TextIO) -> None:
    rows = [["métrica", "base", "atual", "delta", "tolerância", ""]]
    for delta in comparison.deltas:
        rows.append(
            [
                delta.name,
                _number(delta.baseline),
                _number(delta.current),
                "" if delta.delta is None else f"{delta.delta:+.4f}",
                f"{delta.tolerance:.4f}",
                "REGRESSÃO" if delta.regressed else "",
            ]
        )
    out.write("\n" + _table(rows))
    for name in comparison.missing:
        out.write(f"métrica da linha de base ausente nesta rodada: {name}\n")


def _value(metric: MetricValue | None) -> str:
    return "—" if metric is None else _number(metric.value)


def _number(value: float | None) -> str:
    return "ausente" if value is None else f"{value:.4f}"


def _table(rows: Sequence[Sequence[str]]) -> str:
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    return "".join(
        "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip() + "\n" for row in rows
    )
