/** 013 FR-021 (ADR-038, item 4; ADR-039): os pares de texto dos tokens atendem AA nos dois temas, inclusive o hover do
 * botão primário. */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

const CSS = readFileSync(resolve(process.cwd(), "src/ui/tokens.css"), "utf8");

const PAIRS: [string, string][] = [
  ["texto-primario", "fundo-base"],
  ["texto-primario", "fundo-sutil"],
  ["texto-secundario", "fundo-base"],
  ["texto-secundario", "fundo-sutil"],
  ["texto-terciario", "fundo-base"],
  ["texto-terciario", "fundo-sutil"],
  ["acao-texto", "fundo-base"],
  ["texto-sobre-acao", "acao-base"],
  ["texto-sobre-acao", "acao-hover"],
  ["estado-ok-texto", "estado-ok-fundo"],
  ["estado-aviso-texto", "estado-aviso-fundo"],
  ["estado-erro-texto", "estado-erro-fundo"],
  ["foco", "fundo-base"],
  ["foco", "fundo-sutil"],
];

function tokens(block: string): Record<string, string> {
  return Object.fromEntries([...block.matchAll(/--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]));
}

function block(selector: string): string {
  const start = CSS.indexOf(selector);
  expect(start).toBeGreaterThanOrEqual(0);
  return CSS.slice(start, CSS.indexOf("}", start));
}

const light = tokens(CSS.slice(0, CSS.indexOf(':root[data-theme="dark"]')));
const themes: Record<string, Record<string, string>> = {
  claro: light,
  "escuro escolhido": { ...light, ...tokens(block(':root[data-theme="dark"]')) },
  "escuro do sistema": { ...light, ...tokens(block(':root:not([data-theme="light"])')) },
};

function token(theme: string, name: string): string {
  const value = themes[theme]?.[name];
  if (value === undefined) {
    throw new Error(`token ${name} ausente no tema ${theme}`);
  }
  return value;
}

function linear(channel: number): number {
  return channel <= 0.03928 ? channel / 12.92 : ((channel + 0.055) / 1.055) ** 2.4;
}

function luminance(hex: string): number {
  const channel = (start: number) => linear(parseInt(hex.slice(start, start + 2), 16) / 255);
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

function ratio(a: string, b: string): number {
  const high = Math.max(luminance(a), luminance(b));
  const low = Math.min(luminance(a), luminance(b));
  return (high + 0.05) / (low + 0.05);
}

describe.each(Object.keys(themes))("tema %s", (theme) => {
  it.each(PAIRS)("%s sobre %s atende AA", (text, ground) => {
    expect(ratio(token(theme, text), token(theme, ground))).toBeGreaterThanOrEqual(4.5);
  });
});

it("o fundo escuro é o axon-night", () => {
  expect(token("escuro escolhido", "fundo-base").toLowerCase()).toBe("#0b0f19");
});
