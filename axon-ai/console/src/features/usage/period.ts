/** Períodos do dashboard (013 FR-010): 7, 30 ou 90 dias terminando no dia de hoje **no fuso da API**. */

export const PERIODS = [7, 30, 90] as const;
export type PeriodDays = (typeof PERIODS)[number];
export const DEFAULT_PERIOD: PeriodDays = 30;

export function parsePeriod(raw: string | null): PeriodDays {
  const value = Number(raw);
  return (PERIODS as readonly number[]).includes(value) ? (value as PeriodDays) : DEFAULT_PERIOD;
}

function toDate(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1));
}

function toDay(date: Date): string {
  return date.toISOString().slice(0, 10);
}

export function addDays(day: string, delta: number): string {
  const date = toDate(day);
  date.setUTCDate(date.getUTCDate() + delta);
  return toDay(date);
}

/** Dias inclusivos entre `from` e `to`. */
export function daysBetween(from: string, to: string): number {
  return Math.round((toDate(to).getTime() - toDate(from).getTime()) / 86_400_000) + 1;
}

/** Todos os dias do período, em ordem — o gráfico mostra também os dias sem chamada. */
export function eachDay(from: string, to: string): string[] {
  const out: string[] = [];
  for (let day = from; day <= to; day = addDays(day, 1)) {
    out.push(day);
  }
  return out;
}

/** O período anterior de mesma duração, para a comparação do custo. */
export function previousRange(from: string, to: string): { from: string; to: string } {
  const length = daysBetween(from, to);
  return { from: addDays(from, -length), to: addDays(from, -1) };
}
