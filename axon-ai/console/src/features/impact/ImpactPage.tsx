/** Meio ambiente (013 US11; ADR-056): o impacto ambiental estimado das chamadas de modelo, pelo mockup aprovado em
 * 2026-11-03. Período, agregação, origem e agrupamento ficam na URL, como em Uso e custo. Nada de cor decorativa: as
 * séries são uso (`serie-1`) e fabricação (`serie-2`), e verde, âmbar e vermelho só dizem estado (DESIGN.md). */

import { useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { fieldError } from "../../api/errors";
import { useImpact } from "../../api/hooks/impact";
import type {
  ImpactBucket,
  ImpactGrain,
  ImpactMetricName,
  ImpactReport,
  UsageGrouping,
  UsageOrigin,
} from "../../api/schemas";
import {
  formatChange,
  formatDayMonth,
  formatInteger,
  formatMeasure,
  formatPercent,
  formatTrees,
  measureFormatter,
  measureParts,
  plural,
  type Measure,
} from "../../i18n/format";
import { ORIGIN_TEXT } from "../../i18n/pt-BR";
import { Button } from "../../ui/Button";
import { Field, Select, TextInput } from "../../ui/Field";
import { Icon } from "../../ui/icons";
import { Page, PageHeader } from "../../ui/Page";
import { Panel } from "../../ui/Panel";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, LoadError } from "../../ui/States";
import { ChartLegend, DailyChart } from "../usage/DailyChart";
import { addDays, previousRange } from "../usage/period";
import type { DayStack, Series } from "../usage/series";
import strip from "../usage/StatStrip.module.css";
import { axisLabel, bucketLabel, GRAINS } from "./grain";
import styles from "./ImpactPage.module.css";
import { ImpactTable } from "./ImpactTable";

const PERIODS = [
  { value: "30", label: "30 dias" },
  { value: "90", label: "90 dias" },
  { value: "12m", label: "12 meses" },
  { value: "ano", label: "Ano atual" },
  { value: "personalizado", label: "Personalizado" },
] as const;
type Period = (typeof PERIODS)[number]["value"];

const GROUPINGS = [
  { value: "model", label: "Por modelo" },
  { value: "assistant", label: "Por Assistant" },
] as const;

const USE: Series = { id: "__uso__", label: "Uso", short: "Uso", color: "var(--serie-1)", keys: [] };
const EMBODIED: Series = {
  id: "__fabricacao__",
  label: "Fabricação",
  short: "Fabricação",
  color: "var(--serie-2)",
  keys: [],
};

/** Um gráfico por grandeza (FR-034). A fabricação só existe onde o EcoLogits a estima: GWP, ADPe e PE. */
type ChartSpec = {
  id: string;
  title: string;
  measure: Measure;
  total: ImpactMetricName;
  phases: readonly [ImpactMetricName, ImpactMetricName] | null;
  unitText: string;
  wide?: boolean;
};

const CHARTS: readonly ChartSpec[] = [
  {
    id: "emissoes",
    title: "Emissões",
    measure: "co2",
    total: "gwp_kgco2eq",
    phases: ["gwp_usage", "gwp_embodied"],
    unitText: "CO₂e",
    wide: true,
  },
  { id: "energia", title: "Energia", measure: "energy", total: "energy_kwh", phases: null, unitText: "energia" },
  { id: "agua", title: "Água", measure: "water", total: "wcf_l", phases: null, unitText: "água" },
  {
    id: "energia-primaria",
    title: "Energia primária (PE)",
    measure: "primary",
    total: "pe_mj",
    phases: ["pe_usage", "pe_embodied"],
    unitText: "energia primária",
  },
  {
    id: "recursos-abioticos",
    title: "Recursos abióticos (ADPe)",
    measure: "abiotic",
    total: "adpe_kgsbeq",
    phases: ["adpe_usage", "adpe_embodied"],
    unitText: "Sb eq",
  },
];

function isDay(text: string | null): text is string {
  return text !== null && /^\d{4}-\d{2}-\d{2}$/.test(text);
}

function value(bucket: ImpactBucket, name: ImpactMetricName): number {
  return Number(bucket.metrics[name].mean);
}

function stacksOf(report: ImpactReport, spec: ChartSpec): DayStack[] {
  return report.buckets.map((bucket) => {
    const parts = spec.phases
      ? [
          { series: USE, value: value(bucket, spec.phases[0]), partial: false },
          { series: EMBODIED, value: value(bucket, spec.phases[1]), partial: false },
        ]
      : [{ series: USE, value: value(bucket, spec.total), partial: false }];
    const segments = parts.filter((part) => part.value > 0);
    return { day: bucket.start, segments, total: segments.reduce((sum, part) => sum + part.value, 0) };
  });
}

function MetricChart({
  spec,
  report,
  state,
  grain,
  per,
  originText,
}: {
  spec: ChartSpec;
  report: ImpactReport | undefined;
  state: "data" | "loading" | "empty";
  grain: ImpactGrain;
  per: string;
  originText: string;
}) {
  const stacks = useMemo(() => (report ? stacksOf(report, spec) : []), [report, spec]);
  const byStart = useMemo(() => new Map((report?.buckets ?? []).map((bucket) => [bucket.start, bucket])), [report]);
  const max = Math.max(0, ...stacks.map((stack) => stack.total));
  const format = measureFormatter(max, spec.measure);
  const totalText = report?.totals ? formatMeasure(report.totals.metrics[spec.total].mean, spec.measure) : null;
  const subtitle = spec.phases
    ? `${measureParts(max, spec.measure).unit} ${per}, por fase · ${totalText ? `${totalText} no período` : originText}`
    : `${measureParts(max, spec.measure).unit} ${per} · só a fase de uso · ${originText}`;
  const labelId = `grafico-${spec.id}`;
  return (
    <Panel
      title={`${spec.title} ${per}`}
      subtitle={subtitle}
      labelledBy={labelId}
      className={spec.wide ? styles.wideChart : styles.chart}
      aside={<ChartLegend series={spec.phases ? [USE, EMBODIED] : [USE]} />}
    >
      <DailyChart
        stacks={stacks}
        series={spec.phases ? [USE, EMBODIED] : [USE]}
        state={state}
        caption={`${spec.title} ${per}, em ${spec.unitText}${spec.phases ? ", por fase" : ""}`}
        format={format}
        axisFormat={(tick) => format(tick).split(" ", 1)[0] ?? ""}
        emptyDay="Sem chamadas estimadas neste período"
        axisLabel={(start) => axisLabel(start, grain)}
        tooltipLabel={(start) => {
          const bucket = byStart.get(start);
          return bucket ? `${bucketLabel(bucket.start, bucket.end, grain)} · média` : start;
        }}
        rowHeader="Período"
        labelStep={grain === "day" ? undefined : Math.max(1, Math.ceil(stacks.length / (spec.wide ? 8 : 6)))}
        height={spec.wide ? 230 : 190}
        emptyText={{
          title: "Nenhuma chamada estimada no período",
          text: "As estimativas aparecem aqui depois da primeira chamada de modelo.",
        }}
        tooltipExtra={(stack) => {
          const bucket = byStart.get(stack.day);
          if (!bucket) {
            return [];
          }
          const metric = bucket.metrics[spec.total];
          return [
            { label: "Faixa", value: `${format(Number(metric.min))} a ${format(Number(metric.max))}` },
            {
              label: "Chamadas",
              value: `${formatInteger(bucket.calls)} · ${plural(bucket.responses, "resposta", "respostas")}`,
            },
          ];
        }}
      />
    </Panel>
  );
}

function Hero({ amount, measure }: { amount: string | number; measure: Measure }) {
  const parts = measureParts(amount, measure);
  return (
    <span className={`${strip.value} ${strip.hero}`}>
      {parts.value} <span className={styles.heroUnit}>{parts.unit}</span>
    </span>
  );
}

function SummaryStrip({ report, state }: { report: ImpactReport | undefined; state: "data" | "loading" | "error" }) {
  const totals = report?.totals;
  if (state !== "data" || !report || !totals) {
    const note = state === "loading" ? "Carregando…" : "Indisponível";
    return (
      <section className={strip.strip} aria-label="Impacto do período" aria-busy={state === "loading"}>
        {["Emissões (GWP)", "Energia", "Água", "Árvores para compensar"].map((label, index) => (
          <div key={label} className={strip.cell}>
            <span className={strip.label}>{label}</span>
            <span className={strip.dash} aria-hidden="true" />
            {index === 0 ? <span className={strip.note}>{note}</span> : <span className="visually-hidden">{note}</span>}
          </div>
        ))}
      </section>
    );
  }
  const { metrics, coverage } = totals;
  const previous = previousRange(report.query.from, report.query.to);
  const change = report.previous_totals
    ? formatChange(Number(metrics.gwp_kgco2eq.mean), Number(report.previous_totals.metrics.gwp_kgco2eq.mean))
    : null;
  const empty = coverage.estimated === 0;
  const range = (name: ImpactMetricName, measure: Measure) =>
    `faixa de ${formatMeasure(metrics[name].min, measure)} a ${formatMeasure(metrics[name].max, measure)}`;
  return (
    <section className={strip.strip} aria-label="Impacto do período">
      <div className={strip.cell}>
        <span className={strip.label}>Emissões (GWP)</span>
        <Hero amount={metrics.gwp_kgco2eq.mean} measure="co2" />
        {empty ? (
          <span className={strip.note}>Nenhuma chamada estimada no período</span>
        ) : (
          <>
            <span className={strip.note}>{range("gwp_kgco2eq", "co2")}</span>
            {change ? (
              <span className={strip.note}>
                {change} sobre {formatDayMonth(previous.from)} a {formatDayMonth(previous.to)}
              </span>
            ) : null}
          </>
        )}
        {coverage.unestimated > 0 ? (
          <span className={strip.warn}>
            <Icon name="alerta" size={14} />
            Parcial: {formatPercent(coverage.unestimated / coverage.eligible)} das chamadas sem estimativa
          </span>
        ) : null}
      </div>
      <div className={strip.cell}>
        <span className={strip.label}>Energia</span>
        <span className={strip.value}>{formatMeasure(metrics.energy_kwh.mean, "energy")}</span>
        {empty ? null : <span className={strip.note}>{range("energy_kwh", "energy")}</span>}
      </div>
      <div className={strip.cell}>
        <span className={strip.label}>Água</span>
        <span className={strip.value}>{formatMeasure(metrics.wcf_l.mean, "water")}</span>
        {empty ? null : <span className={strip.note}>{range("wcf_l", "water")}</span>}
      </div>
      <div className={strip.cell}>
        <span className={strip.label}>Árvores para compensar</span>
        <span className={strip.value}>{formatTrees(totals.trees)}</span>
        <span className={strip.note}>Mata Atlântica, {report.method.tree_years} anos</span>
        <span className={strip.note}>{formatMeasure(report.method.tree_kg_co2e, "co2")} por árvore</span>
      </div>
    </section>
  );
}

function IntensityStrip({ report }: { report: ImpactReport }) {
  const totals = report.totals;
  if (!totals) {
    return null;
  }
  const { metrics, coverage, estimated_responses: responses, estimated_output_tokens: tokens } = totals;
  const per = (name: ImpactMetricName, measure: Measure) => {
    if (responses === 0) {
      return { value: "—", note: null };
    }
    const metric = metrics[name];
    return {
      value: formatMeasure(Number(metric.mean) / responses, measure),
      note: `faixa de ${formatMeasure(Number(metric.min) / responses, measure)} a ${formatMeasure(Number(metric.max) / responses, measure)}`,
    };
  };
  const cells = [
    { label: "Emissões por resposta", ...per("gwp_kgco2eq", "co2") },
    { label: "Energia por resposta", ...per("energy_kwh", "energy") },
    { label: "Água por resposta", ...per("wcf_l", "water") },
    {
      label: "Emissões por mil tokens gerados",
      value: tokens === 0 ? "—" : formatMeasure((Number(metrics.gwp_kgco2eq.mean) / tokens) * 1000, "co2"),
      note: tokens === 0 ? null : `${formatInteger(tokens)} tokens de saída estimados`,
    },
    {
      label: "Cobertura",
      value: coverage.eligible === 0 ? "—" : formatPercent(coverage.estimated / coverage.eligible),
      note:
        coverage.eligible === 0
          ? null
          : `${plural(coverage.approximate, "por aproximação", "por aproximação")} · ${plural(coverage.unestimated, "sem estimativa", "sem estimativa")}`,
    },
  ];
  return (
    <section className={`${strip.strip} ${styles.intensity}`} aria-label="Intensidade">
      {cells.map((cell) => (
        <div key={cell.label} className={strip.cell}>
          <span className={strip.label}>{cell.label}</span>
          <span className={strip.value}>{cell.value}</span>
          {cell.note ? <span className={strip.note}>{cell.note}</span> : null}
        </div>
      ))}
    </section>
  );
}

/** A caixa do período personalizado (mockup "Meio ambiente — período personalizado"): De e Até, Cancelar e Aplicar. */
function CustomPeriod({
  from,
  to,
  error,
  onApply,
  onCancel,
}: {
  from: string;
  to: string;
  error: unknown;
  onApply: (from: string, to: string) => void;
  onCancel: () => void;
}) {
  const [start, setStart] = useState(from);
  const [end, setEnd] = useState(to);
  return (
    <form
      className={styles.popover}
      aria-label="Período personalizado"
      onSubmit={(event) => {
        event.preventDefault();
        onApply(start, end);
      }}
    >
      <div className={styles.dates}>
        <Field label="De" error={fieldError(error, "from")}>
          <TextInput type="date" value={start} required onChange={(event) => setStart(event.target.value)} />
        </Field>
        <Field label="Até" error={fieldError(error, "to") ?? fieldError(error, "grain")}>
          <TextInput type="date" value={end} required onChange={(event) => setEnd(event.target.value)} />
        </Field>
      </div>
      <div className={styles.popoverActions}>
        <Button variant="ghost" onClick={onCancel}>
          Cancelar
        </Button>
        <Button variant="primary" type="submit">
          Aplicar
        </Button>
      </div>
    </form>
  );
}

export default function ImpactPage() {
  const [params, setParams] = useSearchParams();
  const period: Period = PERIODS.find((p) => p.value === params.get("periodo"))?.value ?? "30";
  const grainOption = GRAINS.find((g) => g.value === params.get("agregacao")) ?? GRAINS[0];
  const grain = grainOption.grain;
  const by: UsageGrouping = params.get("por") === "assistant" ? "assistant" : "model";
  const origin: UsageOrigin =
    (["production", "evaluation", "all"] as const).find((o) => o === params.get("origem")) ?? "production";
  const customFrom = params.get("de");
  const customTo = params.get("ate");
  const [picking, setPicking] = useState(false);

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [key, entry] of Object.entries(changes)) {
      if (entry === null) {
        next.delete(key);
      } else {
        next.set(key, entry);
      }
    }
    setParams(next, { replace: true });
  };

  // Os 30 dias são o padrão da API, no fuso dela; os outros períodos terminam no mesmo dia que ela informa.
  const base = useImpact({ grain, by, origin });
  const anchor = base.data?.query.to;
  const range = useMemo(() => {
    if (period === "personalizado") {
      return isDay(customFrom) && isDay(customTo) ? { from: customFrom, to: customTo } : null;
    }
    if (!anchor || period === "30") {
      return null;
    }
    if (period === "ano") {
      return { from: `${anchor.slice(0, 4)}-01-01`, to: anchor };
    }
    return { from: addDays(anchor, period === "90" ? -89 : -364), to: anchor };
  }, [period, anchor, customFrom, customTo]);
  const ranged = useImpact({ ...range, grain, by, origin }, { enabled: range !== null });
  const usesBase = range === null;
  const current = usesBase ? base : ranged;
  const report = current.data;

  const failed = current.isError;
  const state: "data" | "loading" | "error" = failed ? "error" : !report ? "loading" : "data";
  const disabled = report?.enabled === false;
  const empty = report?.totals ? report.totals.coverage.estimated === 0 : false;
  const chartState = state === "loading" ? "loading" : state === "error" || empty || disabled ? "empty" : "data";
  const originText = ORIGIN_TEXT[origin];
  const subtitle = report
    ? `${formatDayMonth(report.query.from)} a ${formatDayMonth(report.query.to)} · fuso ${report.query.tz}`
    : "Carregando o período…";

  return (
    <Page>
      <PageHeader
        title="Meio ambiente"
        subtitle={subtitle}
        actions={
          <div className={styles.filters}>
            <div className={styles.periodWrap}>
              <Segmented<Period>
                label="Período"
                value={period}
                onChange={(next) => {
                  if (next === "personalizado") {
                    setPicking(true);
                    return;
                  }
                  setPicking(false);
                  update({ periodo: next === "30" ? null : next, de: null, ate: null });
                }}
                options={PERIODS}
              />
              {picking ? (
                <CustomPeriod
                  from={customFrom ?? report?.query.from ?? ""}
                  to={customTo ?? report?.query.to ?? ""}
                  error={period === "personalizado" ? ranged.error : null}
                  onCancel={() => setPicking(false)}
                  onApply={(from, to) => {
                    update({ periodo: "personalizado", de: from, ate: to });
                    setPicking(false);
                  }}
                />
              ) : null}
            </div>
            <Segmented<string>
              label="Agregação"
              value={grainOption.value}
              onChange={(next) => update({ agregacao: next === "dia" ? null : next })}
              options={GRAINS}
            />
            <Select
              compact
              aria-label="Origem das chamadas"
              className={styles.origin}
              value={origin}
              onChange={(event) => update({ origem: event.target.value === "production" ? null : event.target.value })}
            >
              {(["production", "evaluation", "all"] as const).map((entry) => (
                <option key={entry} value={entry}>
                  Origem: {ORIGIN_TEXT[entry]}
                </option>
              ))}
            </Select>
          </div>
        }
      />
      {failed ? (
        <LoadError what="o impacto ambiental" error={current.error} onRetry={() => void current.refetch()} />
      ) : null}
      {disabled ? (
        <EmptyState title="A estimativa do impacto ambiental está desligada nesta instalação">
          A instalação definiu <code>AXON_IMPACT_ENABLED=false</code>. Com ela ligada, cada chamada de modelo passa a
          ser estimada pelo EcoLogits, e as antigas entram com <code>axon usage impact-backfill</code>.
        </EmptyState>
      ) : (
        <>
          <SummaryStrip report={report} state={state} />
          {report && state === "data" ? <IntensityStrip report={report} /> : null}
          <div className={styles.charts}>
            {CHARTS.map((spec) => (
              <MetricChart
                key={spec.id}
                spec={spec}
                report={state === "data" ? report : undefined}
                state={chartState}
                grain={grain}
                per={grainOption.per}
                originText={originText}
              />
            ))}
          </div>
          {report && state === "data" && !empty ? (
            <section aria-labelledby="tabela-impacto">
              <div className={styles.sectionHead}>
                <h2 className={styles.sectionTitle} id="tabela-impacto">
                  {by === "model" ? "Por modelo" : "Por Assistant"}
                </h2>
                <Segmented<UsageGrouping>
                  label="Agrupar a tabela"
                  value={by}
                  onChange={(next) => update({ por: next === "model" ? null : next })}
                  options={GROUPINGS}
                />
              </div>
              <ImpactTable report={report} />
            </section>
          ) : null}
          {report && state === "data" ? (
            <p className={styles.method}>
              Estimativas do EcoLogits {report.method.ecologits_version ?? ""}, calculadas por chamada a partir do
              modelo, dos tokens de saída e da latência, com a zona elétrica do provedor. As faixas mostram a incerteza
              do método; totais, gráficos e tabela usam o valor médio. A fabricação só é estimada para emissões, energia
              primária e recursos abióticos. Árvores: {formatMeasure(report.method.tree_kg_co2e, "co2")} por árvore da
              Mata Atlântica em {report.method.tree_years} anos (Programa Plante Árvore).
              {report.clipped_from
                ? ` O período começa em ${formatDayMonth(report.clipped_from)}: as chamadas anteriores já saíram da retenção.`
                : ""}
            </p>
          ) : null}
        </>
      )}
    </Page>
  );
}
