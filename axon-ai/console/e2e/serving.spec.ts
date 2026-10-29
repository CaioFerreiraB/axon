/** T036 (013, contracts/serving.md): o nginx da instalação — SPA com fallback, cache, CSP e o repasse sem reescrita
 * ao core, com SSE pedaço a pedaço. Roda contra `e2e/serve_nginx.sh` (`CONSOLE_NGINX_URL`); sem ele, é pulado. */

import { expect, test } from "@playwright/test";

import { TEST_API_KEY } from "./fixtures/session";

const nginx = process.env.CONSOLE_NGINX_URL;
test.skip(!nginx, "defina CONSOLE_NGINX_URL (e2e/serve_nginx.sh) para testar o nginx");

const CSP =
  "default-src 'self'; img-src 'self' data:; style-src 'self'; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'";

test("a SPA: index.html sem cache, rota da SPA cai no index, arquivos com hash imutáveis", async ({ request }) => {
  const index = await request.get(`${nginx}/`);
  expect(index.status()).toBe(200);
  expect(index.headers()["cache-control"]).toBe("no-cache");
  expect(index.headers()["content-security-policy"]).toBe(CSP);
  expect(index.headers()["x-content-type-options"]).toBe("nosniff");
  expect(index.headers()["referrer-policy"]).toBe("no-referrer");
  expect(index.headers()["strict-transport-security"]).toBeUndefined();
  const html = await index.text();
  const asset = /src="(\/assets\/[^"]+\.js)"/.exec(html)?.[1];
  expect(asset).toBeTruthy();

  const route = await request.get(`${nginx}/assistentes/geral/modelos`);
  expect(await route.text()).toBe(html);

  const script = await request.get(`${nginx}${asset}`);
  expect(script.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
  expect((await request.get(`${nginx}/assets/nao-existe.js`)).status()).toBe(404);
});

test("HSTS só atrás de https", async ({ request }) => {
  const behind = await request.get(`${nginx}/`, { headers: { "X-Forwarded-Proto": "https" } });
  expect(behind.headers()["strict-transport-security"]).toBe("max-age=31536000");
});

test("os prefixos do core passam sem reescrever, com os cabeçalhos do core", async ({ request }) => {
  const discovery = await request.get(`${nginx}/.well-known/openid-configuration`);
  expect(discovery.status()).toBe(200);
  expect((await discovery.json()).issuer).toBeTruthy();
  const me = await request.get(`${nginx}/admin/v1/me`);
  expect(me.status()).toBe(401);
  expect(me.headers()["cache-control"]).toBe("no-store");
  expect(me.headers()["content-security-policy"]).toBeUndefined();
  const keyed = await request.get(`${nginx}/admin/v1/me`, { headers: { Authorization: `Bearer ${TEST_API_KEY}` } });
  expect(keyed.status()).toBe(200);
});

test("os scripts dos gráficos passam pelo repasse, imutáveis e com CORS (ADR-052)", async ({ request }) => {
  const echarts = await request.get(`${nginx}/static/echarts/6.1.0/langPT-br.js`);
  expect(echarts.status()).toBe(200);
  expect(echarts.headers()["cache-control"]).toBe("public, max-age=31536000, immutable");
  expect(echarts.headers()["access-control-allow-origin"]).toBe("*");
  expect(echarts.headers()["content-security-policy"]).toBeUndefined();
});

test("SSE do chat chega pelo repasse", async ({ request }) => {
  const response = await request.post(`${nginx}/private/v1/chat/completions`, {
    headers: { Authorization: `Bearer ${TEST_API_KEY}` },
    data: { model: "rascunho", stream: true, messages: [{ role: "user", content: "oi" }] },
  });
  expect(response.status()).toBe(200);
  expect(response.headers()["content-type"]).toContain("text/event-stream");
  expect(await response.text()).toContain("data: [DONE]");
});
