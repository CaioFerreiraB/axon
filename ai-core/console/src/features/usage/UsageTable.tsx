/** A tabela por modelo ou por Assistant, começando na dobra (contrato de direção). Custo parcial: o valor e o selo.
 * Sem custo: o selo e, se o provider não informa o custo (ADR-036), o atalho para cadastrar o preço. */

import { Link } from "react-router";

import type { Price, Provider, UsageReport, UsageRow } from "../../api/schemas";
import { formatCompact, formatInstantDay, formatInteger, formatPrice, formatUsd } from "../../i18n/format";
import { Badge } from "../../ui/Badge";
import { Table, tableStyles as t } from "../../ui/Table";
import { keyLabel, reportsCost, type Series } from "./series";

function currentPrice(prices: Price[] | undefined, key: string): Price | undefined {
  return prices?.find((price) => `${price.provider}/${price.model}` === key && price.state === "current");
}

const PARTIAL_TITLE = "Parte das chamadas ficou sem preço ou sem custo informado: o valor cobre só o resto.";

function CostCell({ row, label, by, informed }: { row: UsageRow; label: string; by: string; informed: boolean }) {
  if (row.priced) {
    return <>{formatUsd(row.cost)}</>;
  }
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 12 }}>
      {row.cost !== null ? (
        <>
          <Badge tone="warn" title={PARTIAL_TITLE}>
            Parcial
          </Badge>
          {formatUsd(row.cost)}
        </>
      ) : (
        <Badge tone="warn">{informed ? "Não informado" : "Sem preço"}</Badge>
      )}
      {by === "model" && !informed ? (
        <Link to={`/uso/precos?modelo=${encodeURIComponent(label)}`}>Cadastrar</Link>
      ) : null}
    </span>
  );
}

export function UsageTable({
  report,
  series,
  prices,
  providers,
}: {
  report: UsageReport;
  series: Series[];
  prices?: Price[] | undefined;
  providers?: Provider[] | undefined;
}) {
  const by = report.query.by;
  const color = (label: string) => series.find((entry) => entry.keys.includes(label))?.color;
  const sum = (field: "calls" | "input_tokens" | "output_tokens") =>
    report.totals.reduce((acc, row) => acc + row[field], 0);
  return (
    <Table caption={by === "model" ? "Uso por modelo no período" : "Uso por Assistant no período"}>
      <thead>
        <tr>
          <th scope="col">{by === "model" ? "Modelo" : "Assistant"}</th>
          <th scope="col" className={t.num}>
            Chamadas
          </th>
          <th scope="col" className={`${t.num} ${t.wideOnly}`}>
            Tokens de entrada
          </th>
          <th scope="col" className={`${t.num} ${t.wideOnly}`}>
            Tokens de saída
          </th>
          <th scope="col" className={t.num}>
            Custo
          </th>
          {by === "model" ? (
            <th scope="col" className={`${t.num} ${t.wideOnly}`}>
              Preço vigente (US$ / 1 M)
            </th>
          ) : null}
        </tr>
      </thead>
      <tbody>
        {report.totals.map((row) => {
          const label = keyLabel(row.key, by);
          const price = by === "model" ? currentPrice(prices, label) : undefined;
          const informed = by === "model" && reportsCost(label, providers);
          const swatch = color(label);
          return (
            <tr key={label}>
              <th scope="row">
                <span style={{ display: "inline-flex", alignItems: "center", gap: 10 }}>
                  <span
                    aria-hidden="true"
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: 2,
                      flexShrink: 0,
                      background: swatch ?? "transparent",
                      border: swatch ? undefined : "1px solid var(--texto-terciario)",
                    }}
                  />
                  <span className={`${t.mono} ${t.primaryText}`} style={{ fontWeight: 400 }}>
                    {label}
                  </span>
                </span>
              </th>
              <td className={t.num}>{formatInteger(row.calls)}</td>
              <td className={`${t.num} ${t.wideOnly}`}>{formatCompact(row.input_tokens)}</td>
              <td className={`${t.num} ${t.wideOnly}`}>{formatCompact(row.output_tokens)}</td>
              <td className={t.num}>
                <CostCell row={row} label={label} by={by} informed={informed} />
              </td>
              {by === "model" ? (
                <td className={`${t.num} ${t.wideOnly}`} style={{ color: "var(--texto-secundario)" }}>
                  {informed
                    ? "informado pelo provedor"
                    : price
                      ? `${formatPrice(price.input)} · ${formatPrice(price.output)} desde ${formatInstantDay(`${price.effective_from}T12:00:00`)}`
                      : "—"}
                </td>
              ) : null}
            </tr>
          );
        })}
      </tbody>
      <tfoot>
        <tr>
          <td>Total do período</td>
          <td className={t.num}>{formatInteger(sum("calls"))}</td>
          <td className={`${t.num} ${t.wideOnly}`}>{formatCompact(sum("input_tokens"))}</td>
          <td className={`${t.num} ${t.wideOnly}`}>{formatCompact(sum("output_tokens"))}</td>
          <td className={t.num}>{formatUsd(report.total_cost ?? "0")}</td>
          {by === "model" ? <td className={t.wideOnly} /> : null}
        </tr>
      </tfoot>
    </Table>
  );
}
