import { http, HttpResponse } from "msw";

import * as f from "./fixtures";

const api = (path: string) => `*/admin/v1${path}`;

/** A conta da fixture pelo nome; a primeira, se não houver. */
function accountOf(username: unknown): (typeof f.accounts.data)[number] {
  const [first] = f.accounts.data;
  const found = f.accounts.data.find((item) => item.username === username) ?? first;
  if (found === undefined) {
    throw new Error("a fixture de contas está vazia");
  }
  return found;
}

export const handlers = [
  http.get(api("/me"), () => HttpResponse.json(f.me)),
  http.get(api("/assistants"), () =>
    HttpResponse.json({ data: [f.aberto, f.documentos, f.geral, f.rascunho, f.restrito] }),
  ),
  http.get(api("/assistants/:name"), ({ params }) => {
    const view = [f.geral, f.rascunho, f.documentos, f.aberto, f.restrito].find((item) => item.name === params.name);
    return view
      ? HttpResponse.json(view)
      : HttpResponse.json(
          { error: { message: "recurso não encontrado", type: "not_found_error", code: "not_found" } },
          { status: 404 },
        );
  }),
  http.get(api("/assistants/:name/history"), () => HttpResponse.json({ data: [] })),
  http.get(api("/providers"), () => HttpResponse.json({ data: f.providers })),
  http.get(api("/mcp"), () => HttpResponse.json({ data: f.servers })),
  http.get(api("/mcp/:alias/health"), ({ params }) => HttpResponse.json(f.healths[String(params.alias)])),
  http.get(api("/usage"), () => HttpResponse.json(f.report)),
  http.get(api("/impact"), () => HttpResponse.json(f.impactReport)),
  http.get(api("/prices"), () => HttpResponse.json({ data: f.prices })),
  http.get(api("/prices/unpriced"), () => HttpResponse.json({ data: ["ollama/qwen3:1.7b"] })),
  http.get(api("/observability"), () => HttpResponse.json(f.observability)),
  http.get(api("/users"), () => HttpResponse.json(f.accounts)),
  http.get(api("/groups"), () => HttpResponse.json({ data: f.groups })),
  http.get(api("/login-settings"), () => HttpResponse.json(f.login)),
  http.get(api("/keys"), () => HttpResponse.json({ data: f.apiKeys })),
  // incremento 9.7 (008 US13): apagar uma conta e um grupo de cada vez
  http.delete(api("/users/:username"), ({ params }) =>
    HttpResponse.json({ ...f.deletionReport, username: String(params.username) }),
  ),
  http.put(api("/users/:username/groups/:group"), ({ params }) => {
    const account = accountOf(params.username);
    return HttpResponse.json({ ...account, groups: [...new Set([...account.groups, String(params.group)])].sort() });
  }),
  http.delete(api("/users/:username/groups/:group"), ({ params }) => {
    const account = accountOf(params.username);
    return HttpResponse.json({ ...account, groups: account.groups.filter((group) => group !== params.group) });
  }),
];

export function apiError(status: number, code: string, message: string, extra: Record<string, unknown> = {}) {
  return HttpResponse.json({ error: { message, type: "error", code, param: null, ...extra } }, { status });
}
