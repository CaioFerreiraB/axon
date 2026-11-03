/** Os grãos da página Meio ambiente (013 FR-033, FR-035): o nome de cada um e os rótulos do eixo e da dica. Os baldes
 * vêm prontos da API (009 R48); aqui só se escreve cada um em pt-BR. */

import type { ImpactGrain } from "../../api/schemas";

export const GRAINS = [
  { value: "dia", grain: "day", label: "Dia", per: "por dia" },
  { value: "semana", grain: "week", label: "Semana", per: "por semana" },
  { value: "mes", grain: "month", label: "Mês", per: "por mês" },
  { value: "trimestre", grain: "quarter", label: "Trimestre", per: "por trimestre" },
  { value: "semestre", grain: "semester", label: "Semestre", per: "por semestre" },
] as const satisfies readonly { value: string; grain: ImpactGrain; label: string; per: string }[];

const MONTHS = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"] as const;

function parts(day: string): { year: number; month: number; date: number } {
  const [year, month, date] = day.split("-").map(Number);
  return { year: year ?? 1970, month: month ?? 1, date: date ?? 1 };
}

/** O número da semana ISO do dia (a semana da quinta-feira). */
export function isoWeek(day: string): number {
  const { year, month, date } = parts(day);
  const value = new Date(Date.UTC(year, month - 1, date));
  const weekday = (value.getUTCDay() + 6) % 7;
  value.setUTCDate(value.getUTCDate() - weekday + 3);
  const firstThursday = new Date(Date.UTC(value.getUTCFullYear(), 0, 4));
  const firstWeekday = (firstThursday.getUTCDay() + 6) % 7;
  firstThursday.setUTCDate(firstThursday.getUTCDate() - firstWeekday + 3);
  return 1 + Math.round((value.getTime() - firstThursday.getTime()) / (7 * 86_400_000));
}

function dayMonth(day: string): string {
  const { month, date } = parts(day);
  return `${date} ${MONTHS[month - 1]}`;
}

/** "3–9 nov", "27 out–2 nov". */
function range(start: string, end: string): string {
  const a = parts(start);
  const b = parts(end);
  if (start === end) {
    return dayMonth(start);
  }
  return a.month === b.month ? `${a.date}–${b.date} ${MONTHS[b.month - 1]}` : `${dayMonth(start)}–${dayMonth(end)}`;
}

/** O rótulo curto do eixo: "03/11", "S45", "nov/26", "T4 2026", "2º sem 2026". */
export function axisLabel(start: string, grain: ImpactGrain): string {
  const { year, month, date } = parts(start);
  const short = String(year).slice(2);
  switch (grain) {
    case "day":
      return `${String(date).padStart(2, "0")}/${String(month).padStart(2, "0")}`;
    case "week":
      return `S${isoWeek(start)}`;
    case "month":
      return `${MONTHS[month - 1]}/${short}`;
    case "quarter":
      return `T${Math.floor((month - 1) / 3) + 1} ${year}`;
    case "semester":
      return `${month <= 6 ? 1 : 2}º sem ${year}`;
  }
}

/** O título da dica e da linha da tabela acessível: "S45 · 3–9 nov", com o recorte do período. */
export function bucketLabel(start: string, end: string, grain: ImpactGrain): string {
  if (grain === "day") {
    return dayMonth(start);
  }
  if (grain === "week") {
    return `S${isoWeek(start)} · ${range(start, end)}`;
  }
  return `${axisLabel(start, grain)} · ${range(start, end)}`;
}
