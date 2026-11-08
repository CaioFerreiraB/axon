/**
 * Os ícones do app instalado (013 FR-051, R42; ADR-060): o símbolo Axon do `brand-kit/svg/` sobre fundo branco, renderizado
 * pelo Chromium do Playwright. Os PNGs ficam versionados em `public/icons/`; rode de novo só quando o símbolo mudar:
 *
 *   node scripts/pwa-icons.mjs
 */

import { readFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));
const symbol = await readFile(resolve(here, "../../../brand-kit/svg/axon-symbol.svg"), "utf8");
const out = resolve(here, "../public/icons");

/** `scale` é a fração do lado ocupada pelo símbolo. O maskable cabe na zona segura (círculo de 80% do lado). */
const ICONS = [
  { file: "icon-192.png", size: 192, scale: 0.72 },
  { file: "icon-512.png", size: 512, scale: 0.72 },
  { file: "icon-maskable-512.png", size: 512, scale: 0.56 },
  { file: "apple-touch-icon.png", size: 180, scale: 0.66 },
];

const browser = await chromium.launch();
try {
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  for (const { file, size, scale } of ICONS) {
    const side = Math.round(size * scale);
    await page.setViewportSize({ width: size, height: size });
    await page.setContent(
      `<!doctype html><html><body style="margin:0;width:${size}px;height:${size}px;display:grid;place-items:center;background:#ffffff">
        <div style="width:${side}px;height:${side}px">${symbol.replace("<svg ", `<svg width="${side}" height="${side}" `)}</div>
      </body></html>`,
    );
    await page.screenshot({ path: resolve(out, file), clip: { x: 0, y: 0, width: size, height: size } });
    console.log(`${file} (${size}px)`);
  }
} finally {
  await browser.close();
}
