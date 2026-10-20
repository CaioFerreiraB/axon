/**
 * Custo, requisições ou tokens por dia, empilhados por modelo ou Assistant (013 FR-010, R2). SVG próprio com
 * `d3-scale`, nas regras da skill dataviz: barras de até 24 px, topo arredondado de 4 px e base reta, vão de 2 px entre segmentos, grade de
 * 1 px, marcos de mudança (preço novo, sobreposição gravada), dica pelo mouse e pelas setas do teclado, e a tabela
 * equivalente para leitores de tela.
 */

import { scaleBand, scaleLinear } from "d3-scale";
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent } from "react";

import { formatDayMonth, formatWeekdayDay } from "../../i18n/format";
import styles from "./DailyChart.module.css";
import type { DayStack, Hollow, Series } from "./series";

export type Marker = { day: string; label: string };

/** A legenda, no canto direito do cabeçalho do painel (desenho "Uso e custo"). */
export function ChartLegend({
  series,
  hollow = [],
  note = null,
}: {
  series: Series[];
  hollow?: Hollow[];
  note?: string | null;
}) {
  return (
    <ul className={styles.legend} aria-label="Legenda">
      {series.map((entry) => (
        <li key={entry.id} className={styles.legendItem}>
          <span className={styles.swatch} style={{ background: entry.color }} aria-hidden="true" />
          <span className={entry.id.startsWith("__") ? undefined : styles.mono}>{entry.label}</span>
          {entry.partial ? <span>· custo parcial</span> : null}
        </li>
      ))}
      {hollow.map(({ label, note: why }) => (
        <li key={label} className={styles.legendItem}>
          <span className={`${styles.swatch} ${styles.hollow}`} aria-hidden="true" />
          <span>
            {label} · {why}
          </span>
        </li>
      ))}
      {note ? <li className={styles.legendItem}>{note}</li> : null}
    </ul>
  );
}

const LABEL_CHAR = 6.4;
const LABEL_PAD = 22;
/** Distância do rótulo à linha do marco, folga entre rótulos e altura de cada fileira da faixa de rótulos. */
const LABEL_GAP = 6;
const LABEL_CLEAR = 8;
const LABEL_ROW = 26;

type MarkerSpan = { begin: number; end: number; line: number; row: number };

/** Rótulos dos marcos numa faixa acima das barras, em fileiras. Cada rótulo fica a 6 px da própria linha, de um lado
 * ou do outro, sem encostar em outro rótulo da fileira, sem cobrir a linha de outro marco que desce por ela e sem que
 * a própria linha atravesse um rótulo de baixo. Da direita para a esquerda, tentando os dois lados em cada fileira; a
 * largura é a medida, quando já houve uma renderização. */
export function placeMarkers<M extends { left: number; text: string }>(
  markers: M[],
  width: number,
  widths: Record<string, number>,
): (M & { flip: boolean; row: number })[] {
  const placed: MarkerSpan[] = [];
  const result = new Map<number, { flip: boolean; row: number }>();
  const order = markers.map((_, index) => index).sort((a, b) => (markers[b]?.left ?? 0) - (markers[a]?.left ?? 0));
  for (const index of order) {
    const marker = markers[index];
    if (!marker) {
      continue;
    }
    const size = widths[marker.text] ?? marker.text.length * LABEL_CHAR + LABEL_PAD;
    const span = (flip: boolean) => {
      const begin = flip ? marker.left - LABEL_GAP - size : marker.left + LABEL_GAP;
      return { begin, end: begin + size };
    };
    const fits = (flip: boolean) => span(flip).begin >= 0 && span(flip).end <= width;
    const sides = fits(false) || !fits(true) ? [false, true] : [true, false];
    const free = (row: number, flip: boolean) => {
      const { begin, end } = span(flip);
      return (
        fits(flip) &&
        !placed.some(
          (other) =>
            (other.row === row && end + LABEL_CLEAR > other.begin && begin < other.end + LABEL_CLEAR) ||
            (other.row <= row && other.line > begin - LABEL_CLEAR && other.line < end + LABEL_CLEAR) ||
            (other.row >= row && marker.left > other.begin - LABEL_CLEAR && marker.left < other.end + LABEL_CLEAR),
        )
      );
    };
    let choice = { flip: sides[0] ?? false, row: placed.length };
    search: for (let row = 0; row <= placed.length; row += 1) {
      for (const flip of sides) {
        if (free(row, flip)) {
          choice = { flip, row };
          break search;
        }
      }
    }
    const { begin, end } = span(choice.flip);
    placed.push({ begin, end, line: marker.left, row: choice.row });
    result.set(index, choice);
  }
  return markers.map((marker, index) => ({ ...marker, ...(result.get(index) ?? { flip: false, row: 0 }) }));
}

const HEIGHT = 230;
const AXIS_LEFT = 48;
const AXIS_BOTTOM = 24;
const BAR_MAX = 24;
const RADIUS = 4;

function niceMax(value: number): number {
  if (value <= 0) {
    return 3;
  }
  const scale = scaleLinear().domain([0, value]).nice(3);
  return scale.domain()[1] ?? value;
}

/** O topo arredondado só no segmento de cima; a base fica reta, ancorada na linha de base. */
function barPath(x: number, y: number, width: number, height: number, roundTop: boolean): string {
  const r = roundTop ? Math.min(RADIUS, width / 2, height) : 0;
  return [
    `M${x},${y + height}`,
    `V${y + r}`,
    r ? `Q${x},${y} ${x + r},${y}` : "",
    `H${x + width - r}`,
    r ? `Q${x + width},${y} ${x + width},${y + r}` : "",
    `V${y + height}`,
    "Z",
  ].join("");
}

export function DailyChart({
  stacks,
  series,
  markers = [],
  state = "data",
  caption,
  dayLabels = true,
  format,
  axisFormat,
  integer = false,
  emptyDay,
}: {
  stacks: DayStack[];
  series: Series[];
  markers?: Marker[];
  state?: "data" | "loading" | "empty";
  caption: string;
  /** Sem relatório ainda (carregando, erro), os dias do eixo não são conhecidos e não aparecem. */
  dayLabels?: boolean;
  /** O valor na dica e na tabela equivalente ("US$ 2,08", "1.802", "21,1 mil"). */
  format: (value: number) => string;
  /** O rótulo de uma marca do eixo, sem o zero. */
  axisFormat: (value: number) => string;
  /** Contagens: o eixo só marca inteiros. */
  integer?: boolean;
  /** A dica de um dia sem valor: "Sem custo neste dia". */
  emptyDay: string;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  const [active, setActive] = useState<number | null>(null);
  const [labelWidths, setLabelWidths] = useState<Record<string, number>>({});
  const descriptionId = useId();

  useEffect(() => {
    const element = containerRef.current;
    if (!element || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(([entry]) => {
      if (entry) {
        setWidth(Math.max(320, Math.round(entry.contentRect.width)));
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const markerTexts = markers.map((marker) => `${formatDayMonth(marker.day)} · ${marker.label}`).join("\n");
  useEffect(() => {
    const element = containerRef.current;
    if (!element || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(() => {
      const next: Record<string, number> = {};
      element.querySelectorAll<HTMLElement>("[data-marker-label]").forEach((label) => {
        next[label.dataset.markerLabel ?? ""] = label.offsetWidth;
      });
      setLabelWidths((current) =>
        Object.keys(next).length === Object.keys(current).length &&
        Object.entries(next).every(([text, size]) => current[text] === size)
          ? current
          : next,
      );
    });
    element.querySelectorAll("[data-marker-label]").forEach((label) => observer.observe(label));
    return () => observer.disconnect();
  }, [markerTexts]);

  const x = useMemo(
    () =>
      scaleBand<string>()
        .domain(stacks.map((s) => s.day))
        .range([AXIS_LEFT, width])
        .paddingInner(0.3)
        .paddingOuter(0.15),
    [stacks, width],
  );
  const placedMarkers = placeMarkers(
    markers
      .filter((marker) => x(marker.day) !== undefined)
      .map((marker) => ({
        ...marker,
        left: (x(marker.day) ?? 0) + x.bandwidth() / 2,
        text: `${formatDayMonth(marker.day)} · ${marker.label}`,
      })),
    width,
    labelWidths,
  );
  // A faixa dos rótulos fica acima do máximo do eixo: as barras mantêm a altura, e o gráfico cresce.
  const band = placedMarkers.length > 0 ? (Math.max(...placedMarkers.map((marker) => marker.row)) + 1) * LABEL_ROW : 0;
  const height = HEIGHT + band;
  const plotHeight = height - AXIS_BOTTOM;
  const maxTotal = state === "data" ? Math.max(0, ...stacks.map((s) => s.total)) : 0;
  const top = niceMax(maxTotal);
  const y = useMemo(
    () =>
      scaleLinear()
        .domain([0, top])
        .range([plotHeight, band + 8]),
    [top, plotHeight, band],
  );
  const barWidth = Math.min(BAR_MAX, x.bandwidth());
  const ticks = y.ticks(3).filter((tick) => !integer || Number.isInteger(tick));
  const labelEvery = stacks.length > 45 ? 14 : 7;

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (stacks.length === 0) {
      return;
    }
    const last = stacks.length - 1;
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      event.preventDefault();
      const step = event.key === "ArrowRight" ? 1 : -1;
      setActive((current) => Math.min(last, Math.max(0, (current ?? (step > 0 ? -1 : last + 1)) + step)));
    } else if (event.key === "Home") {
      event.preventDefault();
      setActive(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setActive(last);
    } else if (event.key === "Escape") {
      setActive(null);
    }
  };

  const activeStack = active !== null ? stacks[active] : undefined;
  const activeX = activeStack ? (x(activeStack.day) ?? 0) + x.bandwidth() / 2 : 0;
  const tooltipLeft = Math.min(Math.max(activeX + 16, AXIS_LEFT), width - 216);

  return (
    <div className={styles.chart}>
      <div
        ref={containerRef}
        className={styles.plot}
        role="img"
        aria-label={caption}
        aria-describedby={descriptionId}
        tabIndex={state === "data" && stacks.length > 0 ? 0 : -1}
        onKeyDown={onKeyDown}
        onMouseLeave={() => setActive(null)}
        onBlur={() => setActive(null)}
      >
        <svg className={styles.svg} width={width} height={height} aria-hidden="true">
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                className={styles.grid}
                x1={AXIS_LEFT}
                x2={width}
                y1={Math.round(y(tick)) + 0.5}
                y2={Math.round(y(tick)) + 0.5}
              />
              <text className={styles.axis} x={0} y={y(tick) + 4}>
                {tick === 0 ? "0" : axisFormat(tick)}
              </text>
            </g>
          ))}
          {state !== "empty" &&
            stacks.map((stack, index) => {
              const bandX = x(stack.day) ?? 0;
              const barX = bandX + (x.bandwidth() - barWidth) / 2;
              if (state === "loading") {
                const fake = (0.25 + ((index * 37) % 60) / 100) * plotHeight * 0.7;
                return (
                  <rect
                    key={stack.day}
                    x={barX}
                    y={plotHeight - fake}
                    width={barWidth}
                    height={fake}
                    rx={RADIUS}
                    fill="var(--fundo-realce)"
                  />
                );
              }
              let cursor = plotHeight;
              const segments = stack.segments.map((segment, segmentIndex) => {
                const height = Math.max(1, plotHeight - y(segment.value));
                const segmentTop = cursor - height;
                const isTop = segmentIndex === stack.segments.length - 1;
                const path = (
                  <path
                    key={segment.series.id}
                    d={barPath(barX, segmentTop, barWidth, height, isTop)}
                    fill={segment.series.color}
                  />
                );
                const gap =
                  segmentIndex > 0 ? (
                    <line
                      key={`${segment.series.id}-vao`}
                      className={styles.gap}
                      x1={barX}
                      x2={barX + barWidth}
                      y1={cursor}
                      y2={cursor}
                    />
                  ) : null;
                cursor = segmentTop;
                return [path, gap];
              });
              return (
                <g key={stack.day} onMouseEnter={() => setActive(index)}>
                  <rect
                    x={bandX - (x.step() - x.bandwidth()) / 2}
                    y={0}
                    width={x.step()}
                    height={plotHeight}
                    className={active === index ? styles.hover : undefined}
                    fill={active === index ? undefined : "transparent"}
                  />
                  {segments}
                </g>
              );
            })}
          {placedMarkers.map((marker) => (
            <line
              key={`${marker.day}-${marker.label}`}
              className={styles.marker}
              x1={Math.round(marker.left) + 0.5}
              x2={Math.round(marker.left) + 0.5}
              y1={marker.row * LABEL_ROW + 2}
              y2={plotHeight}
            />
          ))}
          <line className={styles.grid} x1={AXIS_LEFT} x2={width} y1={plotHeight + 0.5} y2={plotHeight + 0.5} />
          {stacks.map((stack, index) =>
            dayLabels &&
            (index % labelEvery === 0 ||
              (index === stacks.length - 1 && index - Math.floor(index / labelEvery) * labelEvery > labelEvery / 2)) ? (
              <text
                key={`rotulo-${stack.day}`}
                className={styles.axis}
                x={(x(stack.day) ?? 0) + x.bandwidth() / 2}
                y={height - 6}
                textAnchor="middle"
              >
                {formatDayMonth(stack.day)}
              </text>
            ) : null,
          )}
        </svg>
        {placedMarkers.map((marker) => (
          <span
            key={`rotulo-${marker.day}-${marker.label}`}
            data-marker-label={marker.text}
            className={marker.flip ? `${styles.markerLabel} ${styles.flipped}` : styles.markerLabel}
            style={{
              left: marker.flip ? Math.round(marker.left) - LABEL_GAP : Math.round(marker.left) + LABEL_GAP + 1,
              top: marker.row * LABEL_ROW,
            }}
          >
            {marker.text}
          </span>
        ))}
        {state === "empty" ? (
          <div className={styles.overlay}>
            <p className={styles.overlayTitle}>Nenhuma chamada de modelo neste período</p>
            <p className={styles.overlayText}>O uso aparece aqui assim que a primeira conversa acontecer.</p>
          </div>
        ) : null}
        {activeStack && state === "data" ? (
          <div className={styles.tooltip} style={{ left: tooltipLeft, top: band + 96 }} role="status">
            <p className={styles.tooltipDay}>{formatWeekdayDay(activeStack.day)}</p>
            {activeStack.segments.length === 0 ? (
              <p>{emptyDay}</p>
            ) : (
              [...activeStack.segments].reverse().map((segment) => (
                <div key={segment.series.id} className={styles.tooltipRow}>
                  <span className={styles.swatch} style={{ background: segment.series.color }} aria-hidden="true" />
                  <span className={segment.series.id.startsWith("__") ? undefined : styles.mono}>
                    {segment.series.short}
                    {segment.partial ? <span className={styles.partial}> · parcial</span> : null}
                  </span>
                  <span>{format(segment.value)}</span>
                </div>
              ))
            )}
            <div className={styles.tooltipTotal}>
              <span>Total</span>
              <strong>{format(activeStack.total)}</strong>
            </div>
          </div>
        ) : null}
      </div>
      {/* Tabela ignora a altura de 1 px do visually-hidden: o invólucro é que some. */}
      <div id={descriptionId} className="visually-hidden">
        <table>
          <caption>{caption}</caption>
          <thead>
            <tr>
              <th scope="col">Dia</th>
              {series.map((entry) => (
                <th key={entry.id} scope="col">
                  {entry.label}
                </th>
              ))}
              <th scope="col">Total</th>
            </tr>
          </thead>
          <tbody>
            {state === "data"
              ? stacks.map((stack) => (
                  <tr key={stack.day}>
                    <th scope="row">{formatWeekdayDay(stack.day)}</th>
                    {series.map((entry) => (
                      <td key={entry.id}>{format(stack.segments.find((s) => s.series.id === entry.id)?.value ?? 0)}</td>
                    ))}
                    <td>{format(stack.total)}</td>
                  </tr>
                ))
              : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
