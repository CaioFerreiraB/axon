/**
 * Formatos pt-BR (013 FR-016, R9): números com ponto de milhar, tokens compactos ("21,1 M"), dinheiro em USD
 * ("US$ 41,87") a partir da string decimal da API — convertida só para exibir — e datas.
 */

const integer = new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const twoDecimals = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const usd = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "USD" });

export function formatInteger(value: number): string {
  return integer.format(value);
}

/** 1.234 → "1,2 mil"; 21.100.000 → "21,1 M"; 1.200.000.000 → "1,2 B". Abaixo de mil, o número inteiro. */
export function formatCompact(value: number): string {
  const abs = Math.abs(value);
  if (abs < 1_000) {
    return integer.format(value);
  }
  if (abs < 1_000_000) {
    return `${oneDecimal.format(value / 1_000)} mil`;
  }
  if (abs < 1_000_000_000) {
    return `${oneDecimal.format(value / 1_000_000)} M`;
  }
  return `${oneDecimal.format(value / 1_000_000_000)} B`;
}

export function formatRatio(value: number): string {
  return twoDecimals.format(value);
}

/** Dinheiro da API (string decimal) em USD. Valores positivos abaixo de um centavo aparecem como "< US$ 0,01". */
export function formatUsd(value: string | number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  const number = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(number)) {
    return "—";
  }
  if (number > 0 && number < 0.005) {
    return `< ${usd.format(0.01)}`;
  }
  return usd.format(number);
}

/** Preço por milhão de tokens: "0,40". */
export function formatPrice(value: string): string {
  const number = Number(value);
  return Number.isFinite(number) ? twoDecimals.format(number) : value;
}

/** Variação percentual: "+8,2%"; `null` quando não há base de comparação. */
export function formatChange(current: number, previous: number): string | null {
  if (!Number.isFinite(previous) || previous === 0) {
    return null;
  }
  const change = ((current - previous) / previous) * 100;
  const sign = change > 0 ? "+" : change < 0 ? "−" : "";
  return `${sign}${oneDecimal.format(Math.abs(change))}%`;
}

function parseDay(day: string): Date {
  const [y, m, d] = day.split("-").map(Number);
  return new Date(Date.UTC(y ?? 1970, (m ?? 1) - 1, d ?? 1));
}

const dayMonth = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit", timeZone: "UTC" });
const fullDay = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  timeZone: "UTC",
});
const weekday = new Intl.DateTimeFormat("pt-BR", { weekday: "short", timeZone: "UTC" });

/** Um dia local da API ("2026-10-10") como "10/10". O dia já está no fuso da API: nada de converter. */
export function formatDayMonth(day: string): string {
  return dayMonth.format(parseDay(day));
}

export function formatFullDay(day: string): string {
  return fullDay.format(parseDay(day));
}

/** "sex, 10/10" — a dica do gráfico. */
export function formatWeekdayDay(day: string): string {
  const date = parseDay(day);
  return `${weekday.format(date).replace(".", "")}, ${dayMonth.format(date)}`;
}

/** Um instante da API ("2026-10-07T17:32:00+00:00") como "07/10 às 14:32", no fuso do navegador. */
export function formatInstant(iso: string, timeZone?: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const options: Intl.DateTimeFormatOptions = { day: "2-digit", month: "2-digit", timeZone };
  const time: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit", timeZone };
  return `${new Intl.DateTimeFormat("pt-BR", options).format(date)} às ${new Intl.DateTimeFormat("pt-BR", time).format(date)}`;
}

/** Só a data de um instante: "07/10". */
export function formatInstantDay(iso: string): string {
  const date = new Date(iso);
  return Number.isNaN(date.getTime())
    ? iso
    : new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "2-digit" }).format(date);
}

/** "hoje, 14:32", "ontem", "03/10" ou "nunca" — último acesso de uma conta. */
export function formatLastSeen(iso: string | null, now: Date = new Date()): string {
  if (iso === null) {
    return "nunca";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  const start = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const days = Math.round((start(now) - start(date)) / 86_400_000);
  if (days === 0) {
    return `hoje, ${new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" }).format(date)}`;
  }
  if (days === 1) {
    return "ontem";
  }
  return formatInstantDay(iso);
}

/** "há 12 s", "há 3 min", "há 2 h" ou a data — o último envio de um destino. */
export function formatAgo(iso: string, now: Date = new Date()): string {
  const seconds = Math.max(0, Math.round((now.getTime() - new Date(iso).getTime()) / 1000));
  if (seconds < 60) {
    return `há ${seconds} s`;
  }
  if (seconds < 3600) {
    return `há ${Math.round(seconds / 60)} min`;
  }
  if (seconds < 86_400) {
    return `há ${Math.round(seconds / 3600)} h`;
  }
  return formatInstantDay(iso);
}

/** "AS" para "Ana Souza"; "A" para "ana". */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const letters = parts.length > 1 ? [parts[0], parts[parts.length - 1]] : [parts[0] ?? "?"];
  return letters.map((part) => (part ?? "?").charAt(0).toUpperCase()).join("");
}

export function plural(count: number, one: string, many: string): string {
  return `${formatInteger(count)} ${count === 1 ? one : many}`;
}
