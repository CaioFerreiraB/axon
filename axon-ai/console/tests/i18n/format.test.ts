import { describe, expect, it } from "vitest";

import {
  formatChange,
  formatCompact,
  formatDayMonth,
  formatInteger,
  formatLastSeen,
  formatPrice,
  formatUsd,
  formatWeekdayDay,
  initials,
} from "../../src/i18n/format";

describe("formatos pt-BR (013 FR-016)", () => {
  it("números e tokens compactos", () => {
    expect(formatInteger(3214)).toBe("3.214");
    expect(formatCompact(21_100_000)).toBe("21,1 M");
    expect(formatCompact(783_400)).toBe("783,4 mil");
    expect(formatCompact(512)).toBe("512");
  });

  it("dinheiro em USD a partir da string decimal", () => {
    expect(formatUsd("41.870000").replace(/\s/g, " ")).toBe("US$ 41,87");
    expect(formatUsd("0").replace(/\s/g, " ")).toBe("US$ 0,00");
    expect(formatUsd("0.0007")).toContain("< ");
    expect(formatUsd(null)).toBe("—");
    expect(formatPrice("0.40")).toBe("0,40");
  });

  it("variação contra o período anterior", () => {
    expect(formatChange(41.87, 38.69)).toBe("+8,2%");
    expect(formatChange(10, 0)).toBeNull();
  });

  it("dias do fuso da API, sem converter", () => {
    expect(formatDayMonth("2026-10-10")).toBe("10/10");
    expect(formatWeekdayDay("2026-10-10")).toBe("sáb, 10/10");
  });

  it("último acesso e iniciais", () => {
    const now = new Date(2026, 9, 14, 15, 0);
    expect(formatLastSeen(null, now)).toBe("nunca");
    expect(formatLastSeen(new Date(2026, 9, 13, 9, 0).toISOString(), now)).toBe("ontem");
    expect(initials("Ana Souza")).toBe("AS");
    expect(initials("ana")).toBe("A");
  });
});
