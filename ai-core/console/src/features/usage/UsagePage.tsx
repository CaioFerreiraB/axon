/** Uso e custo (013 US4): a tela inicial. Período, agrupamento e origem ficam na URL (data-model, "Estado de tela"). */

import { useMemo } from "react";
import { Link, useSearchParams } from "react-router";

import { useAssistants } from "../../api/hooks/assistants";
import { useHistories } from "../../api/hooks/history";
import { usePrices, useUsage } from "../../api/hooks/usage";
import { isMcpPayload, type UsageGrouping, type UsageOrigin } from "../../api/schemas";
import { formatDayMonth } from "../../i18n/format";
import { ORIGIN_TEXT } from "../../i18n/pt-BR";
import { Select } from "../../ui/Field";
import { Icon } from "../../ui/icons";
import { Page, PageHeader } from "../../ui/Page";
import { Panel } from "../../ui/Panel";
import { Segmented } from "../../ui/Segmented";
import { LoadError } from "../../ui/States";
import { ChartLegend, DailyCostChart, type Marker } from "./DailyCostChart";
import { addDays, eachDay, parsePeriod, PERIODS, type PeriodDays } from "./period";
import { seriesOf, stacksOf } from "./series";
import { StatStrip } from "./StatStrip";
import styles from "./UsagePage.module.css";
import { UsageTable } from "./UsageTable";

const GROUPINGS = [
  { value: "model", label: "Por modelo" },
  { value: "assistant", label: "Por Assistant" },
] as const;

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
  const assistants = useAssistants();
  const histories = useHistories((assistants.data ?? []).map((a) => a.name));

  const view = useMemo(() => {
    if (!report) {
      return null;
    }
    const allDays = eachDay(report.query.from, report.query.to);
    const { series, unpriced } = seriesOf(report);
    return { allDays, series, unpriced, stacks: stacksOf(report, series, allDays) };
  }, [report]);

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
      <StatStrip report={report} state={state} />
      <Panel
        title="Custo por dia"
        subtitle={`US$ por dia, empilhado por ${groupLabel} · ${ORIGIN_TEXT[origin]}`}
        labelledBy="custo-por-dia"
        aside={view ? <ChartLegend series={view.series} unpriced={view.unpriced} /> : null}
      >
        <DailyCostChart
          stacks={
            view?.stacks ??
            eachDay(addDays(anchor ?? "2026-01-30", -(days - 1)), anchor ?? "2026-01-30").map((day) => ({
              day,
              segments: [],
              total: 0,
            }))
          }
          series={view?.series ?? []}
          markers={markers}
          state={state === "loading" ? "loading" : state === "error" || empty ? "empty" : "data"}
          caption={`Custo por dia em US$, por ${groupLabel}`}
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
          <UsageTable report={report} series={view?.series ?? []} prices={prices.data} />
        </section>
      ) : null}
    </Page>
  );
}
