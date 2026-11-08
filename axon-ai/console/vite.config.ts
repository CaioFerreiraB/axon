/// <reference types="vitest/config" />
import { createHash } from "node:crypto";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

import react from "@vitejs/plugin-react";
import { defineConfig, type Plugin } from "vite";

/** Os arquivos de `public/` que a casca precisa sem rede: a página "Sem conexão", o manifest e os ícones. */
const PUBLIC_SHELL = /^(offline\.(html|css)|manifest\.webmanifest|icons\/.+)$/;

function listFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? listFiles(path) : [path];
  });
}

/**
 * O service worker da casca (013 FR-052, R41; ADR-060): emite `sw.js` a partir do modelo `src/pwa/sw.js`, com a lista
 * de arquivos do build e o nome do cache pela impressão digital dela — um deploy novo é um cache novo.
 */
function pwaServiceWorker(): Plugin {
  let publicDir = "";
  return {
    name: "axon-pwa-service-worker",
    apply: "build",
    configResolved(config) {
      publicDir = config.publicDir;
    },
    generateBundle(_options, bundle) {
      const hash = createHash("sha256");
      const fromBundle = Object.keys(bundle).filter((file) => file !== "index.html" && !file.endsWith(".map"));
      const fromPublic = listFiles(publicDir)
        .map((path) => relative(publicDir, path).split("\\").join("/"))
        .filter((file) => PUBLIC_SHELL.test(file));
      for (const file of fromPublic) {
        hash.update(readFileSync(join(publicDir, file)));
      }
      const precache = [...fromBundle, ...fromPublic].map((file) => `/${file}`).sort();
      // O que o service worker exige na instalação (a página "Sem conexão"); o resto é opcional (src/pwa/sw.js).
      for (const required of [
        "/offline.html",
        "/offline.css",
        "/icons/axon-symbol.svg",
        "/icons/axon-symbol-light.svg",
      ]) {
        if (!precache.includes(required)) {
          this.error(`public/: falta ${required}, que a página "Sem conexão" usa`);
        }
      }
      hash.update(precache.join("\n"));
      const source = readFileSync(new URL("./src/pwa/sw.js", import.meta.url), "utf8")
        .replace(
          'const VERSION = "__VERSION__";',
          `const VERSION = ${JSON.stringify(hash.digest("hex").slice(0, 16))};`,
        )
        .replace("const PRECACHE = __PRECACHE__;", `const PRECACHE = ${JSON.stringify(precache)};`);
      if (source.includes("__VERSION__;") || source.includes("= __PRECACHE__")) {
        this.error("src/pwa/sw.js: os marcadores __VERSION__ e __PRECACHE__ não foram trocados");
      }
      this.emitFile({ type: "asset", fileName: "sw.js", source });
    },
  };
}

/**
 * Os prefixos da plataforma repassados ao core, sem reescrever o caminho — as mesmas regras do nginx da instalação
 * (specs/013-core-admin-console/contracts/serving.md). A SPA usa slugs em português, que nunca colidem com eles.
 */
const upstream = process.env.AXON_UPSTREAM ?? "http://127.0.0.1:8000";
const proxy = Object.fromEntries(
  ["/v1/", "/private/v1/", "/admin/v1/", "/oauth2/", "/.well-known/"].map((prefix) => [
    prefix,
    { target: upstream, changeOrigin: false, xfwd: true },
  ]),
);

export default defineConfig({
  plugins: [react(), pwaServiceWorker()],
  server: { host: "127.0.0.1", port: 5173, strictPort: true, proxy },
  preview: { host: "127.0.0.1", port: 4173, strictPort: true, proxy },
  build: { target: "es2023", sourcemap: false, assetsInlineLimit: 0 },
  test: {
    environment: "jsdom",
    include: ["tests/**/*.test.{ts,tsx}"],
    setupFiles: ["tests/setup.ts"],
    css: { modules: { classNameStrategy: "non-scoped" } },
    restoreMocks: true,
    maxWorkers: 4,
  },
});
