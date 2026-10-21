/** 013 FR-023 (ADR-038, item 6; research R15): os arquivos da marca da console são os do `brand-kit`, sem redesenho. */

import { readdirSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const CONSOLE_BRAND = resolve(process.cwd(), "src/brand") + "/";
const BRAND_KIT = resolve(process.cwd(), "../../brand-kit/svg") + "/";

describe("arquivos da marca", () => {
  const names = readdirSync(CONSOLE_BRAND).filter((name) => name.endsWith(".svg"));

  it("estão todos os que a console usa", () => {
    expect(names.sort()).toEqual(
      [
        "axon-lockup-dark.svg",
        "axon-lockup-light.svg",
        "axon-symbol-light.svg",
        "axon-symbol.svg",
        "axon-wordmark-dark.svg",
        "axon-wordmark-light.svg",
        "favicon.svg",
      ].sort(),
    );
  });

  it.each(names)("%s é igual ao do brand-kit", (name) => {
    expect(readFileSync(CONSOLE_BRAND + name, "utf8")).toBe(readFileSync(BRAND_KIT + name, "utf8"));
  });
});
