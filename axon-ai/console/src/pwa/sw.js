/**
 * O service worker da console (013 FR-052, R41; ADR-060, item 5): guarda só a casca. É um modelo: o plugin
 * `pwaServiceWorker` do `vite.config.ts` troca `__VERSION__` e `__PRECACHE__` no build e o emite como `/sw.js`.
 *
 * - Instalação: só a página "Sem conexão" e o que ela usa são obrigatórios; o resto do build entra no cache quando o
 *   download dá certo, sem impedir a instalação.
 * - Navegação: sempre pela rede; sem rede, `offline.html` (nunca o `index.html` do cache — a sessão OIDC fica só em
 *   memória, e sem rede o login não completa).
 * - `/assets/`: do cache primeiro (nomes com hash, imutáveis). `/icons/` e `offline.css`, sem hash: pela rede primeiro,
 *   atualizando o cache, que só responde sem rede.
 * - Os prefixos do core, o que não é GET e o que é de outra origem não passam por aqui: nenhuma resposta da API e nenhum
 *   token entra no cache.
 */

const VERSION = "__VERSION__";
const PRECACHE = __PRECACHE__;
const CACHE = `axon-console-${VERSION}`;
const OFFLINE = "/offline.html";
const REQUIRED = [OFFLINE, "/offline.css", "/icons/axon-symbol.svg", "/icons/axon-symbol-light.svg"];
const CORE_PREFIXES = ["/v1/", "/private/v1/", "/admin/v1/", "/oauth2/", "/.well-known/", "/static/"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then(async (cache) => {
      await cache.addAll(REQUIRED);
      await Promise.allSettled(PRECACHE.filter((path) => !REQUIRED.includes(path)).map((path) => cache.add(path)));
    }),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key.startsWith("axon-console-") && key !== CACHE).map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

/** Pela rede, guardando a resposta boa; sem rede, o que estiver no cache. */
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE);
      await cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    throw error;
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") {
    return;
  }
  const url = new URL(request.url);
  if (url.origin !== self.location.origin || CORE_PREFIXES.some((prefix) => url.pathname.startsWith(prefix))) {
    return;
  }
  if (request.mode === "navigate") {
    event.respondWith(fetch(request).catch(() => caches.match(OFFLINE)));
    return;
  }
  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(caches.match(request).then((hit) => hit ?? fetch(request)));
    return;
  }
  if (url.pathname.startsWith("/icons/") || url.pathname === "/offline.css") {
    event.respondWith(networkFirst(request));
  }
});
