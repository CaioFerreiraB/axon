/** 013 FR-053: a barra do navegador e a de status do app instalado seguem o tema escolhido na console. */

import { afterEach, beforeEach, describe, expect, it } from "vitest";

import { applyTheme } from "../../src/app/theme";

function metas() {
  return Array.from(document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')).map((meta) => meta.content);
}

describe("theme-color", () => {
  beforeEach(() => {
    document.head.innerHTML = `
      <meta name="theme-color" content="#ffffff" media="(prefers-color-scheme: light)" />
      <meta name="theme-color" content="#0b0f19" media="(prefers-color-scheme: dark)" />`;
  });
  afterEach(() => {
    document.head.innerHTML = "";
    document.documentElement.removeAttribute("data-theme");
  });

  it("escuro escolhido: as duas meta no escuro", () => {
    applyTheme("dark");
    expect(metas()).toEqual(["#0b0f19", "#0b0f19"]);
  });

  it("claro escolhido: as duas no claro", () => {
    applyTheme("light");
    expect(metas()).toEqual(["#ffffff", "#ffffff"]);
  });

  it("sistema: cada uma volta à da própria mídia", () => {
    applyTheme("dark");
    applyTheme("system");
    expect(metas()).toEqual(["#ffffff", "#0b0f19"]);
  });
});
