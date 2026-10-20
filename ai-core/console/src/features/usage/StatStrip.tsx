/** A faixa única de números do desenho: o custo como figura principal, depois requisições, chamadas e tokens. */

import { Link } from "react-router";

import type { UsageReport } from "../../api/schemas";
import {
  formatChange,
  formatCompact,
  formatDayMonth,
  formatInteger,
  formatRatio,
  formatUsd,
  plural,
} from "../../i18n/format";
import { Icon } from "../../ui/icons";
import { daysBetween, previousRange } from "./period";
import styles from "./StatStrip.module.css";

type Props = { report?: UsageReport | undefined; state: "data" | "loading" | "error" };

export function StatStrip({ report, state }: Props) {
  if (state !== "data" || !report) {
    const note = state === "loading" ? "Carregando…" : "Indisponível";
    return (
      <section className={styles.strip} aria-label="Totais do período" aria-busy={state === "loading"}>
        {["Custo do período", "Requisições", "Chamadas de modelo", "Tokens"].map((label, index) => (
          <div key={label} className={styles.cell}>
            <span className={styles.label}>{label}</span>
            <span className={styles.dash} aria-hidden="true" />
            {index === 0 ? (
              <span className={styles.note}>{note}</span>
            ) : (
              <span className="visually-hidden">{note}</span>
            )}
          </div>
        ))}
      </section>
    );
  }
  const { query } = report;
  const calls = report.totals.reduce((sum, row) => sum + row.calls, 0);
  const input = report.totals.reduce((sum, row) => sum + row.input_tokens, 0);
  const output = report.totals.reduce((sum, row) => sum + row.output_tokens, 0);
  const days = daysBetween(query.from, query.to);
  const unpriced = report.totals.filter((row) => !row.priced).length;
  const previous = previousRange(query.from, query.to);
  const change =
    report.total_cost !== null && report.previous_total_cost !== null
      ? formatChange(Number(report.total_cost), Number(report.previous_total_cost))
      : null;
  const empty = calls === 0;
  return (
    <section className={styles.strip} aria-label="Totais do período">
      <div className={styles.cell}>
        <span className={styles.label}>Custo do período</span>
        <span className={`${styles.value} ${styles.hero}`}>{formatUsd(report.total_cost ?? "0")}</span>
        {empty ? (
          <span className={styles.note}>Sem chamadas no período</span>
        ) : change ? (
          <span className={styles.note}>
            {change} sobre {formatDayMonth(previous.from)} a {formatDayMonth(previous.to)}
          </span>
        ) : (
          <span className={styles.note}>Sem custo no período anterior para comparar</span>
        )}
        {report.incomplete ? (
          <Link to="/uso/precos" className={styles.warn}>
            <Icon name="alerta" size={14} />
            Incompleto: {plural(unpriced, "modelo sem preço", "modelos sem preço")}
          </Link>
        ) : null}
      </div>
      <div className={styles.cell}>
        <span className={styles.label}>Requisições</span>
        <span className={styles.value}>{formatInteger(report.requests)}</span>
        {empty ? null : <span className={styles.note}>{formatRatio(report.requests / days)} por dia</span>}
      </div>
      <div className={styles.cell}>
        <span className={styles.label}>Chamadas de modelo</span>
        <span className={styles.value}>{formatInteger(calls)}</span>
        {empty || report.requests === 0 ? null : (
          <span className={styles.note}>{formatRatio(calls / report.requests)} por requisição</span>
        )}
      </div>
      <div className={styles.cell}>
        <span className={styles.label}>Tokens</span>
        <span className={styles.value}>{formatCompact(input + output)}</span>
        {empty ? null : (
          <span className={styles.note}>
            {formatCompact(input)} entrada · {formatCompact(output)} saída
          </span>
        )}
      </div>
    </section>
  );
}
