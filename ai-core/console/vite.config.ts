/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Os prefixos da plataforma repassados ao core, sem reescrever o caminho — as mesmas regras do nginx da instalação
 * (specs/013-core-admin-console/contracts/serving.md). A SPA usa slugs em português, que nunca colidem com eles.
 */
const upstream = process.env.AI_CORE_UPSTREAM ?? "http://127.0.0.1:8000";
const proxy = Object.fromEntries(
  ["/v1/", "/private/v1/", "/admin/v1/", "/oauth2/", "/.well-known/"].map((prefix) => [
    prefix,
    { target: upstream, changeOrigin: false, xfwd: true },
  ]),
);

export default defineConfig({
  plugins: [react()],
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
