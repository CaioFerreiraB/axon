import { http, HttpResponse } from "msw";

import * as f from "./fixtures";

const api = (path: string) => `*/admin/v1${path}`;

export const handlers = [
  http.get(api("/me"), () => HttpResponse.json(f.me)),
  http.get(api("/assistants"), () => HttpResponse.json({ data: [f.documentos, f.geral, f.rascunho] })),
  http.get(api("/assistants/:name"), ({ params }) => {
    const view = [f.geral, f.rascunho, f.documentos].find((item) => item.name === params.name);
    return view
      ? HttpResponse.json(view)
      : HttpResponse.json(
          { error: { message: "recurso não encontrado", type: "not_found_error", code: "not_found" } },
          { status: 404 },
        );
  }),
  http.get(api("/assistants/:name/history"), () => HttpResponse.json({ data: [] })),
  http.get(api("/mcp"), () => HttpResponse.json({ data: f.servers })),
  http.get(api("/mcp/:alias/health"), ({ params }) => HttpResponse.json(f.healths[String(params.alias)])),
  http.get(api("/usage"), () => HttpResponse.json(f.report)),
  http.get(api("/prices"), () => HttpResponse.json({ data: f.prices })),
  http.get(api("/prices/unpriced"), () => HttpResponse.json({ data: ["ollama/qwen3:1.7b"] })),
  http.get(api("/observability"), () => HttpResponse.json(f.observability)),
  http.get(api("/users"), () => HttpResponse.json(f.accounts)),
  http.get(api("/groups"), () => HttpResponse.json({ data: f.groups })),
  http.get(api("/login-settings"), () => HttpResponse.json(f.login)),
];

export function apiError(status: number, code: string, message: string, extra: Record<string, unknown> = {}) {
  return HttpResponse.json({ error: { message, type: "error", code, param: null, ...extra } }, { status });
}
