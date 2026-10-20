/**
 * As séries do gráfico a partir do relatório (013 R2), na métrica escolhida: custo, requisições ou tokens. Até quatro
 * séries com as cores validadas, em ordem do valor no período; além disso, "Outros" (nunca uma cor gerada). No custo,
 * entra também o custo parcial (parte das chamadas sem preço ou sem custo informado); o que não tem custo nenhum
 * aparece na legenda vazado, fora do custo. Requisições por modelo não se empilham (ADR-036): uma requisição pode usar
 * mais de um modelo, e a barra é a das requisições distintas do dia.
 */

import type { Provider, UsageReport, UsageRow } from "../../api/schemas";

export type Metric = "cost" | "requests" | "tokens";
export type TokenKind = "total" | "input" | "output";
export type ChartView = { metric: Metric; tokens: TokenKind };

export type Series = { id: string; label: string; short: string; color: string; keys: string[]; partial?: boolean };
/** Chave usada no período sem custo nenhum: na legenda, vazada, com o motivo. */
export type Hollow = { label: string; note: string };

const COLORS = ["var(--serie-1)", "var(--serie-2)", "var(--serie-3)", "var(--serie-4)"] as const;
export const OTHERS = "__outros__";
export const DISTINCT_REQUESTS = "__requisicoes__";

export function keyLabel(key: string | null, by: "model" | "assistant"): string {
  if (key === null) {
    return by === "assistant" ? "fora de Assistant" : "—";
  }
  return key;
}

function shortLabel(key: string, by: "model" | "assistant"): string {
  return by === "model" ? (key.split("/").pop() ?? key) : key;
}

/** O provider de `provider/modelo` informa o custo de cada chamada (ADR-036): não há preço de tabela a cadastrar. */
export function reportsCost(key: string, providers: Provider[] | undefined): boolean {
  const name = key.split("/")[0];
  return (providers ?? []).some((provider) => provider.name === name && provider.reports_cost);
}

export function valueOf(row: UsageRow, view: ChartView): number {
  if (view.metric === "cost") {
    return row.cost === null ? 0 : Number(row.cost);
  }
  if (view.metric === "requests") {
    return row.requests;
  }
  if (view.tokens === "input") {
    return row.input_tokens;
  }
  return view.tokens === "output" ? row.output_tokens : row.input_tokens + row.output_tokens;
}

/** Custo parcial: a linha tem custo, mas parte das chamadas ficou sem preço ou sem custo informado. */
function partial(row: UsageRow, view: ChartView): boolean {
  return view.metric === "cost" && !row.priced && row.cost !== null;
}

export function stacked(view: ChartView, by: "model" | "assistant"): boolean {
  return !(view.metric === "requests" && by === "model");
}

export function seriesOf(
  report: UsageReport,
  view: ChartView,
  providers?: Provider[] | undefined,
): { series: Series[]; hollow: Hollow[]; note: string | null } {
  const by = report.query.by;
  if (!stacked(view, by)) {
    return {
      series: [
        { id: DISTINCT_REQUESTS, label: "Requisições distintas", short: "requisições", color: COLORS[0], keys: [] },
      ],
      hollow: [],
      note: "uma requisição pode usar mais de um modelo",
    };
  }
  const ranked = report.totals
    .filter((row) => valueOf(row, view) > 0)
    .sort((a, b) => valueOf(b, view) - valueOf(a, view));
  const hollow =
    view.metric === "cost"
      ? report.totals
          .filter((row) => row.cost === null)
          .map((row) => {
            const label = keyLabel(row.key, by);
            const informed = by === "model" && reportsCost(label, providers);
            return { label, note: informed ? "custo não informado" : "sem preço, fora do custo" };
          })
      : [];
  const named = ranked.length > COLORS.length ? ranked.slice(0, COLORS.length - 1) : ranked;
  const series: Series[] = named.map((row, index) => {
    const label = keyLabel(row.key, by);
    return {
      id: label,
      label,
      short: shortLabel(label, by),
      color: COLORS[index] ?? COLORS[3],
      keys: [label],
      partial: partial(row, view),
    };
  });
  if (ranked.length > COLORS.length) {
    const rest = ranked.slice(COLORS.length - 1);
    series.push({
      id: OTHERS,
      label: `Outros (${rest.length})`,
      short: "outros",
      color: COLORS[3],
      keys: rest.map((row) => keyLabel(row.key, by)),
      partial: rest.some((row) => partial(row, view)),
    });
  }
  return { series, hollow, note: null };
}

export type Segment = { series: Series; value: number; partial: boolean };
export type DayStack = { day: string; segments: Segment[]; total: number };

export function stacksOf(report: UsageReport, series: Series[], days: string[], view: ChartView): DayStack[] {
  const byDay = new Map(report.days.map((entry) => [entry.day, entry]));
  const by = report.query.by;
  return days.map((day) => {
    const entry = byDay.get(day);
    const only = series[0];
    if (only?.id === DISTINCT_REQUESTS) {
      const value = entry?.requests ?? 0;
      return { day, segments: value > 0 ? [{ series: only, value, partial: false }] : [], total: value };
    }
    const rows = entry?.rows ?? [];
    const segments = series
      .map((item) => {
        const matching = rows.filter((row) => item.keys.includes(keyLabel(row.key, by)));
        return {
          series: item,
          value: matching.reduce((sum, row) => sum + valueOf(row, view), 0),
          partial: matching.some((row) => partial(row, view)),
        };
      })
      .filter((segment) => segment.value > 0);
    return { day, segments, total: segments.reduce((sum, segment) => sum + segment.value, 0) };
  });
}
