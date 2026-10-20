/** Uso e custo (013 US4): a tela inicial. Período, agrupamento, origem e a métrica do gráfico ficam na URL (data-model,
 * "Estado de tela"). */

import { useMemo } from "react";
import { Link, useSearchParams } from "react-router";

import { useAssistants, useProviders } from "../../api/hooks/assistants";
import { useHistories } from "../../api/hooks/history";
import { usePrices, useUnpriced, useUsage } from "../../api/hooks/usage";
import { isMcpPayload, type UsageGrouping, type UsageOrigin } from "../../api/schemas";
import { formatCompact, formatDayMonth, formatInteger, formatUsd } from "../../i18n/format";
import { ORIGIN_TEXT } from "../../i18n/pt-BR";
import { Select } from "../../ui/Field";
import { Icon } from "../../ui/icons";
import { Page, PageHeader } from "../../ui/Page";
import { Panel } from "../../ui/Panel";
import { Segmented } from "../../ui/Segmented";
import { LoadError } from "../../ui/States";
import { ChartLegend, DailyChart, type Marker } from "./DailyChart";
import { addDays, eachDay, parsePeriod, PERIODS, type PeriodDays } from "./period";
import { seriesOf, stacked, stacksOf, type ChartView, type Metric, type TokenKind } from "./series";
import { StatStrip } from "./StatStrip";
import styles from "./UsagePage.module.css";
import { UsageTable } from "./UsageTable";

const GROUPINGS = [
  { value: "model", label: "Por modelo" },
  { value: "assistant", label: "Por Assistant" },
] as const;

/** A métrica do gráfico e o nome dela na URL. */
const METRICS = [
  { value: "custo", metric: "cost", label: "Custo" },
  { value: "requisicoes", metric: "requests", label: "Requisições" },
  { value: "tokens", metric: "tokens", label: "Tokens" },
] as const satisfies readonly { value: string; metric: Metric; label: string }[];

const TOKEN_KINDS = [
  { value: "total", kind: "total", label: "Total", text: "entrada e saída" },
  { value: "entrada", kind: "input", label: "Entrada", text: "entrada" },
  { value: "saida", kind: "output", label: "Saída", text: "saída" },
] as const satisfies readonly { value: string; kind: TokenKind; label: string; text: string }[];

/** Título, formatos e textos do gráfico em cada métrica. */
function chartText(view: ChartView, tokenText: string) {
  if (view.metric === "cost") {
    return {
      title: "Custo por dia",
      caption: "Custo por dia em US$",
      unit: "US$ por dia",
      format: (value: number) => formatUsd(value),
      axis: (value: number) => `US$ ${value.toLocaleString("pt-BR")}`,
      emptyDay: "Sem custo neste dia",
    };
  }
  if (view.metric === "requests") {
    return {
      title: "Requisições por dia",
      caption: "Requisições distintas por dia",
      unit: "Requisições distintas",
      format: formatInteger,
      axis: formatInteger,
      emptyDay: "Sem requisições neste dia",
    };
  }
  return {
    title: "Tokens por dia",
    caption: `Tokens de ${tokenText} por dia`,
    unit: `Tokens de ${tokenText}`,
    format: formatCompact,
    axis: formatCompact,
    emptyDay: "Sem tokens neste dia",
  };
}

function dayIn(iso: string, timeZone: string): string {
  // en-CA formata como AAAA-MM-DD: o dia do instante no fuso dos dados.
  return new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).format(
    new Date(iso),
  );
}

export default function UsagePage() {
  const [params, setParams] = useSearchParams();
  const days = parsePeriod(params.get("dias"));
  const by: UsageGrouping = params.get("por") === "assistant" ? "assistant" : "model";
  const origin: UsageOrigin =
    (["production", "evaluation", "all"] as const).find((o) => o === params.get("origem")) ?? "production";
  const metric = METRICS.find((m) => m.value === params.get("metrica")) ?? METRICS[0];
  const tokenKind = TOKEN_KINDS.find((k) => k.value === params.get("tokens")) ?? TOKEN_KINDS[0];
  const chartView = useMemo<ChartView>(
    () => ({ metric: metric.metric, tokens: tokenKind.kind }),
    [metric.metric, tokenKind.kind],
  );

  const update = (key: string, value: string, fallback: string) => {
    const next = new URLSearchParams(params);
    if (value === fallback) {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setParams(next, { replace: true });
  };

  // O padrão da API é o de 30 dias no fuso dela; os outros períodos terminam no mesmo dia que ela informa.
  const base = useUsage({ by, origin });
  const anchor = base.data?.query.to;
  const ranged = useUsage(
    days !== 30 && anchor ? { from: addDays(anchor, -(days - 1)), to: anchor, by, origin } : { by, origin },
  );
  const usage = days === 30 ? base : ranged;
  const report = days === 30 || anchor ? usage.data : undefined;
  const prices = usePrices();
  const providers = useProviders();
  const unpriced = useUnpriced(report ? { from: report.query.from, to: report.query.to } : {});
  const assistants = useAssistants();
  const histories = useHistories((assistants.data ?? []).map((a) => a.name));

  const view = useMemo(() => {
    if (!report) {
      return null;
    }
    const allDays = eachDay(report.query.from, report.query.to);
    const { series, hollow, note } = seriesOf(report, chartView, providers.data);
    return { series, hollow, note, stacks: stacksOf(report, series, allDays, chartView) };
  }, [report, chartView, providers.data]);

  const markers = useMemo<Marker[]>(() => {
    if (!report) {
      return [];
    }
    const { from, to, tz } = report.query;
    const inRange = (day: string) => day >= from && day <= to;
    const priceMarkers = (prices.data ?? [])
      .filter((price) => inRange(price.effective_from) && price.effective_from !== from)
      .map((price) => ({
        day: price.effective_from,
        label: `preço novo do ${price.model.split("/").pop() ?? price.model}`,
      }));
    const overrideMarkers = histories.flatMap(({ name, entries }) =>
      entries
        .filter((entry) => entry.section === "models")
        .map((entry) => {
          const who = entry.actor.split(":").pop() ?? entry.actor;
          const roles = entry.payload && !isMcpPayload(entry.payload) ? Object.keys(entry.payload) : [];
          const what =
            entry.action === "discarded"
              ? `${who} voltou o ${name} ao YAML`
              : roles.length === 1 && roles[0] === "generation"
                ? `${who} trocou a geração do ${name}`
                : `${who} trocou modelos do ${name}`;
          return { day: dayIn(entry.at, tz), label: what };
        })
        .filter((marker) => inRange(marker.day)),
    );
    return [...priceMarkers, ...overrideMarkers].sort((a, b) => a.day.localeCompare(b.day)).slice(-4);
  }, [report, prices.data, histories]);

  const failed = usage.isError || base.isError;
  const state = failed ? "error" : !report ? "loading" : "data";
  const empty = report ? report.totals.every((row) => row.calls === 0) : false;
  const groupLabel = by === "model" ? "modelo" : "Assistant";
  const text = chartText(chartView, tokenKind.text);
  const chartSubtitle = stacked(chartView, by)
    ? `${text.unit}, empilhado por ${groupLabel} · ${ORIGIN_TEXT[origin]}`
    : `${text.unit} por dia · ${ORIGIN_TEXT[origin]}`;
  const subtitle = report
    ? `${formatDayMonth(report.query.from)} a ${formatDayMonth(report.query.to)} · fuso ${report.query.tz}`
    : "Carregando o período…";

  return (
    <Page>
      <PageHeader
        title="Uso e custo"
        subtitle={subtitle}
        actions={
          <div className={styles.filters}>
            <Segmented<string>
              label="Período"
              value={String(days)}
              onChange={(value) => update("dias", value, "30")}
              options={PERIODS.map((p: PeriodDays) => ({ value: String(p), label: `${p} dias` }))}
            />
            <Segmented<UsageGrouping>
              label="Agrupar"
              value={by}
              onChange={(value) => update("por", value, "model")}
              options={GROUPINGS}
            />
            <Select
              compact
              aria-label="Origem das chamadas"
              className={styles.origin}
              value={origin}
              onChange={(event) => update("origem", event.target.value, "production")}
            >
              {(["production", "evaluation", "all"] as const).map((value) => (
                <option key={value} value={value}>
                  Origem: {ORIGIN_TEXT[value]}
                </option>
              ))}
            </Select>
          </div>
        }
      />
      {failed ? (
        <LoadError
          what="o uso"
          error={usage.error ?? base.error}
          onRetry={() => {
            void base.refetch();
            void ranged.refetch();
          }}
        />
      ) : null}
      <StatStrip report={report} state={state} providers={providers.data} unpriced={unpriced.data} />
      <Panel
        title={text.title}
        subtitle={chartSubtitle}
        labelledBy="grafico-por-dia"
        className={styles.chartPanel}
        aside={
          <div className={styles.chartAside}>
            <div className={styles.metrics}>
              <Segmented<string>
                label="Métrica do gráfico"
                value={metric.value}
                onChange={(value) => {
                  const next = new URLSearchParams(params);
                  if (value === "custo") {
                    next.delete("metrica");
                  } else {
                    next.set("metrica", value);
                  }
                  if (value !== "tokens") {
                    next.delete("tokens");
                  }
                  setParams(next, { replace: true });
                }}
                options={METRICS}
              />
              {metric.metric === "tokens" ? (
                <Segmented<string>
                  label="Tokens"
                  value={tokenKind.value}
                  onChange={(value) => update("tokens", value, "total")}
                  options={TOKEN_KINDS}
                />
              ) : null}
            </div>
            {view ? <ChartLegend series={view.series} hollow={view.hollow} note={view.note} /> : null}
          </div>
        }
      >
        <DailyChart
          stacks={
            view?.stacks ??
            eachDay(addDays(anchor ?? "2026-01-30", -(days - 1)), anchor ?? "2026-01-30").map((day) => ({
              day,
              segments: [],
              total: 0,
            }))
          }
          format={text.format}
          axisFormat={text.axis}
          integer={chartView.metric !== "cost"}
          emptyDay={text.emptyDay}
          series={view?.series ?? []}
          markers={markers}
          state={state === "loading" ? "loading" : state === "error" || empty ? "empty" : "data"}
          caption={stacked(chartView, by) ? `${text.caption}, por ${groupLabel}` : text.caption}
          dayLabels={Boolean(report)}
        />
      </Panel>
      {report && !empty ? (
        <section aria-labelledby="tabela-uso">
          <div className={styles.sectionHead}>
            <h2 className={styles.sectionTitle} id="tabela-uso">
              {by === "model" ? "Por modelo" : "Por Assistant"}
            </h2>
            <Link to="/uso/precos" className={styles.link}>
              Tabela de preços
              <Icon name="direita" size={14} />
            </Link>
          </div>
          <UsageTable report={report} series={view?.series ?? []} prices={prices.data} providers={providers.data} />
        </section>
      ) : null}
    </Page>
  );
}
