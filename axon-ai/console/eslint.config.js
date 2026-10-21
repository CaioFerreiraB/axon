import js from "@eslint/js";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

/**
 * Fronteira da console (design.md, "Portas e adapters"): telas não chamam `fetch` nem o cliente OIDC — só os hooks de
 * `src/api/` e de `src/auth/`.
 */
const boundary = {
  "no-restricted-globals": [
    "error",
    { name: "fetch", message: "Rede só em src/api/ (o cliente da API) — use os hooks de src/api/hooks." },
  ],
  "no-restricted-imports": [
    "error",
    { paths: [{ name: "oidc-client-ts", message: "A sessão OIDC só existe em src/auth/." }] },
  ],
};

export default tseslint.config(
  { ignores: ["dist", "node_modules", "test-results", "playwright-report", "coverage"] },
  js.configs.recommended,
  ...tseslint.configs.strict,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: { globals: { ...globals.browser }, ecmaVersion: 2023 },
    plugins: { "react-hooks": reactHooks },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
  { files: ["src/**/*.{ts,tsx}"], ignores: ["src/api/**", "src/auth/**"], rules: boundary },
  // Nada da console vai para o registro do navegador: a chave de API mostrada uma vez não pode vazar por ali (013 R23).
  { files: ["src/**/*.{ts,tsx}"], rules: { "no-console": "error" } },
  {
    files: ["tests/**", "e2e/**", "*.config.{ts,js}"],
    languageOptions: { globals: { ...globals.node, ...globals.browser } },
  },
);
