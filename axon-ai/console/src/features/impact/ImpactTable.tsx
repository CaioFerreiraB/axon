/** A tabela por modelo ou por Assistant da página Meio ambiente (013 FR-034): o modelo do EcoLogits usado, com o selo
 * "Aproximado" quando o casamento foi por similaridade (ADR-056, item 3). Sem amostras de cor: os gráficos são por fase,
 * não por modelo. Abaixo de 1100 px, o modelo do EcoLogits desce para baixo do nome (DESIGN.md). */

import type { ImpactReport, ImpactRow } from "../../api/schemas";
import { formatInteger, formatMeasure } from "../../i18n/format";
import { Badge } from "../../ui/Badge";
import { Table, tableStyles as t } from "../../ui/Table";
import { keyLabel } from "../usage/series";
import styles from "./ImpactPage.module.css";

const APPROXIMATE_TITLE =
  "O nome deste modelo não está na base do EcoLogits: a estimativa usa o modelo mais parecido da mesma família.";

function perResponse(row: { metrics: ImpactRow["metrics"]; estimated_responses: number }): string {
  return row.estimated_responses === 0
    ? "—"
    : formatMeasure(Number(row.metrics.gwp_kgco2eq.mean) / row.estimated_responses, "co2");
}

function EcoModel({ row }: { row: ImpactRow }) {
  if (row.impact_model === null) {
    return <span className={styles.muted}>sem estimativa</span>;
  }
  return (
    <span className={styles.ecoModel}>
      <span className={t.mono}>{row.impact_model}</span>
      {row.match === "approximate" ? (
        <Badge tone="warn" dot title={APPROXIMATE_TITLE}>
          Aproximado
        </Badge>
      ) : null}
    </span>
  );
}

export function ImpactTable({ report }: { report: ImpactReport }) {
  const by = report.query.by;
  const totals = report.totals;
  return (
    <Table caption={by === "model" ? "Impacto por modelo no período" : "Impacto por Assistant no período"}>
      <thead>
        <tr>
          <th scope="col">{by === "model" ? "Modelo" : "Assistant"}</th>
          {by === "model" ? (
            <th scope="col" className={t.wideOnly}>
              Modelo do EcoLogits
            </th>
          ) : null}
          <th scope="col" className={t.num}>
            Chamadas
          </th>
          <th scope="col" className={`${t.num} ${t.wideOnly}`}>
            Energia
          </th>
          <th scope="col" className={t.num}>
            Emissões
          </th>
          <th scope="col" className={t.num}>
            Emissões por resposta
          </th>
          <th scope="col" className={`${t.num} ${t.wideOnly}`}>
            Água
          </th>
        </tr>
      </thead>
      <tbody>
        {report.rows.map((row) => {
          const label = keyLabel(row.key, by);
          return (
            <tr key={label}>
              <th scope="row">
                <span className={`${t.mono} ${t.primaryText}`} style={{ fontWeight: 400 }}>
                  {label}
                </span>
                {by === "model" ? (
                  <span className={styles.narrowOnly}>
                    EcoLogits: <EcoModel row={row} />
                  </span>
                ) : null}
              </th>
              {by === "model" ? (
                <td className={t.wideOnly}>
                  <EcoModel row={row} />
                </td>
              ) : null}
              <td className={t.num}>{formatInteger(row.calls)}</td>
              <td className={`${t.num} ${t.wideOnly}`}>{formatMeasure(row.metrics.energy_kwh.mean, "energy")}</td>
              <td className={t.num}>{formatMeasure(row.metrics.gwp_kgco2eq.mean, "co2")}</td>
              <td className={t.num}>{perResponse(row)}</td>
              <td className={`${t.num} ${t.wideOnly}`}>{formatMeasure(row.metrics.wcf_l.mean, "water")}</td>
            </tr>
          );
        })}
      </tbody>
      {totals ? (
        <tfoot>
          <tr>
            <td>Total do período</td>
            {by === "model" ? <td className={t.wideOnly} /> : null}
            <td className={t.num}>{formatInteger(totals.coverage.calls)}</td>
            <td className={`${t.num} ${t.wideOnly}`}>{formatMeasure(totals.metrics.energy_kwh.mean, "energy")}</td>
            <td className={t.num}>{formatMeasure(totals.metrics.gwp_kgco2eq.mean, "co2")}</td>
            <td className={t.num}>{perResponse(totals)}</td>
            <td className={`${t.num} ${t.wideOnly}`}>{formatMeasure(totals.metrics.wcf_l.mean, "water")}</td>
          </tr>
        </tfoot>
      ) : null}
    </Table>
  );
}
