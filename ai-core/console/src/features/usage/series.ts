/**
 * As séries do gráfico a partir do relatório (013 R2): só o que tem preço entra no custo; até quatro séries com as
 * cores validadas, em ordem de custo do período; além disso, "Outros" (nunca uma cor gerada). O que não tem preço
 * aparece na legenda vazado, "fora do custo".
 */

import type { UsageReport } from "../../api/schemas";

export type Series = { id: string; label: string; short: string; color: string; keys: string[] };

const COLORS = ["var(--serie-1)", "var(--serie-2)", "var(--serie-3)", "var(--serie-4)"] as const;
export const OTHERS = "__outros__";

export function keyLabel(key: string | null, by: "model" | "assistant"): string {
  if (key === null) {
    return by === "assistant" ? "fora de Assistant" : "—";
  }
  return key;
}

function shortLabel(key: string, by: "model" | "assistant"): string {
  return by === "model" ? (key.split("/").pop() ?? key) : key;
}

export function seriesOf(report: UsageReport): { series: Series[]; unpriced: string[] } {
  const by = report.query.by;
  const priced = report.totals
    .filter((row) => row.priced && row.cost !== null && Number(row.cost) > 0)
    .sort((a, b) => Number(b.cost) - Number(a.cost));
  const unpriced = report.totals.filter((row) => !row.priced).map((row) => keyLabel(row.key, by));
  const named = priced.length > COLORS.length ? priced.slice(0, COLORS.length - 1) : priced;
  const series: Series[] = named.map((row, index) => {
    const label = keyLabel(row.key, by);
    return { id: label, label, short: shortLabel(label, by), color: COLORS[index] ?? COLORS[3], keys: [label] };
  });
  if (priced.length > COLORS.length) {
    const rest = priced.slice(COLORS.length - 1).map((row) => keyLabel(row.key, by));
    series.push({ id: OTHERS, label: `Outros (${rest.length})`, short: "outros", color: COLORS[3], keys: rest });
  }
  return { series, unpriced };
}

export type DayStack = { day: string; segments: { series: Series; cost: number }[]; total: number };

export function stacksOf(report: UsageReport, series: Series[], days: string[]): DayStack[] {
  const byDay = new Map(report.days.map((entry) => [entry.day, entry.rows]));
  const by = report.query.by;
  return days.map((day) => {
    const rows = byDay.get(day) ?? [];
    const costOf = (keys: string[]) =>
      rows
        .filter((row) => row.cost !== null && keys.includes(keyLabel(row.key, by)))
        .reduce((sum, row) => sum + Number(row.cost), 0);
    const segments = series.map((entry) => ({ series: entry, cost: costOf(entry.keys) })).filter((s) => s.cost > 0);
    return { day, segments, total: segments.reduce((sum, s) => sum + s.cost, 0) };
  });
}
