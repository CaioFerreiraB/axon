/** 013 US13 (FR-051, FR-052, FR-053; SC-013): a console instalável — manifest e ícones, o service worker da casca, a
 * página "Sem conexão" e nada da API no cache. Projeto `pwa`, o único com o service worker ligado. */

import { expect, test } from "@playwright/test";

import { login } from "./fixtures/session";

test("manifest e ícones", async ({ request }) => {
  // O index.html, sem passar pelo login (a página redireciona ao emissor assim que roda).
  const html = await (await request.get("/")).text();
  expect(html).toContain('<link rel="manifest" href="/manifest.webmanifest" />');
  expect(html).toContain('<link rel="apple-touch-icon" href="/icons/apple-touch-icon.png" />');
  expect(html).toMatch(/<meta name="viewport" content="[^"]*viewport-fit=cover/);
  const response = await request.get("/manifest.webmanifest");
  expect(response.status()).toBe(200);
  const manifest = await response.json();
  expect(manifest).toMatchObject({
    id: "/",
    name: "Axon Console",
    short_name: "Axon",
    start_url: "/uso",
    scope: "/",
    display: "standalone",
  });
  const purposes = new Set<string>();
  for (const icon of manifest.icons as { src: string; sizes: string; purpose: string }[]) {
    const image = await request.get(icon.src);
    expect(image.status(), icon.src).toBe(200);
    expect(image.headers()["content-type"]).toBe("image/png");
    const bytes = await image.body();
    const [width, height] = [bytes.readUInt32BE(16), bytes.readUInt32BE(20)];
    expect(`${width}x${height}`, icon.src).toBe(icon.sizes);
    purposes.add(`${icon.sizes} ${icon.purpose}`);
  }
  expect([...purposes].sort()).toEqual(["192x192 any", "512x512 any", "512x512 maskable"]);
  const apple = await request.get("/icons/apple-touch-icon.png");
  expect((await apple.body()).readUInt32BE(16)).toBe(180);
});

test("o service worker guarda a casca, nunca a API, e sem rede mostra Sem conexão", async ({ page, context }) => {
  await login(page, "/uso");
  await page.getByRole("heading", { name: "Uso e custo" }).waitFor();
  const scope = await page.evaluate(async () => (await navigator.serviceWorker.ready).scope);
  expect(scope).toBe("http://127.0.0.1:4173/");
  await expect
    .poll(() =>
      page.evaluate(async () => (await caches.keys()).filter((key) => key.startsWith("axon-console-")).length),
    )
    .toBe(1);
  const cached = await page.evaluate(async () => {
    const urls: string[] = [];
    for (const key of await caches.keys()) {
      for (const request of await (await caches.open(key)).keys()) {
        urls.push(new URL(request.url).pathname);
      }
    }
    return urls;
  });
  expect(cached).toContain("/offline.html");
  expect(cached.some((path) => path.startsWith("/assets/"))).toBe(true);
  expect(cached.filter((path) => /^\/(v1|private\/v1|admin\/v1|oauth2|\.well-known|static)\//.test(path))).toEqual([]);
  expect(cached).not.toContain("/index.html");

  await context.setOffline(true);
  await page.goto("/assistentes").catch(() => undefined);
  await expect(page.getByRole("heading", { name: "Sem conexão" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Tentar de novo" })).toHaveAttribute("href", "/");
  await context.setOffline(false);
});

test("o theme-color segue o tema escolhido na console", async ({ page }) => {
  await login(page, "/uso");
  await page.getByRole("radio", { name: "Tema escuro" }).click();
  const colors = await page
    .locator('meta[name="theme-color"]')
    .evaluateAll((metas) => metas.map((meta) => (meta as HTMLMetaElement).content));
  expect(colors).toEqual(["#0b0f19", "#0b0f19"]);
  await page.getByRole("radio", { name: "Seguir o sistema" }).click();
});
