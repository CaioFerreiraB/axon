/**
 * O cliente da API de administração — a porta de saída da console (design.md, "Portas e adapters"). O único lugar
 * com `fetch`: mesma origem, `Authorization: Bearer`, uma renovação e uma nova tentativa no 401, depois o login de
 * novo. O envelope de erro vira `ApiError`; a resposta passa pelo esquema do contrato (013 R6).
 */

import type { z } from "zod";

import { ApiError } from "./errors";
import { errorEnvelopeSchema } from "./schemas";

export const ADMIN_PREFIX = "/admin/v1";

export interface Session {
  /** O token de acesso atual, ou `null` sem sessão. */
  token(): string | null;
  /** Renova pelo token de renovação; `null` quando a sessão no provedor acabou. */
  renew(): Promise<string | null>;
  /** Refaz o login e volta à rota atual (013 US1 cenário 3). */
  relogin(): Promise<void>;
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface ApiClient {
  get<T>(path: string, schema: z.ZodType<T>): Promise<T>;
  send<T>(method: Method, path: string, body: unknown, schema: z.ZodType<T>): Promise<T>;
  send(method: Method, path: string, body?: unknown): Promise<void>;
}

export function createApiClient(session: Session, base = ADMIN_PREFIX): ApiClient {
  async function request(method: Method, path: string, body: unknown, token: string | null): Promise<Response> {
    const headers: Record<string, string> = { Accept: "application/json" };
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
    if (body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    try {
      return await fetch(`${base}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        credentials: "same-origin",
        cache: "no-store",
      });
    } catch {
      throw new ApiError(0, "network", "Não foi possível falar com a plataforma. Confira a conexão e tente de novo.");
    }
  }

  async function call(method: Method, path: string, body: unknown): Promise<Response> {
    let response = await request(method, path, body, session.token());
    if (response.status === 401) {
      const renewed = await session.renew();
      if (renewed) {
        response = await request(method, path, body, renewed);
      }
      if (response.status === 401) {
        await session.relogin();
        throw new ApiError(401, "invalid_credential", "A sessão acabou. Entrando de novo…");
      }
    }
    if (!response.ok) {
      throw await toError(response);
    }
    return response;
  }

  async function parse<T>(response: Response, schema: z.ZodType<T>): Promise<T> {
    const json: unknown = await response.json();
    const parsed = schema.safeParse(json);
    if (!parsed.success) {
      throw new ApiError(
        response.status,
        "contract",
        "A resposta da plataforma não tem o formato esperado por esta console. Atualize a console ou a plataforma.",
      );
    }
    return parsed.data;
  }

  return {
    async get<T>(path: string, schema: z.ZodType<T>): Promise<T> {
      return parse(await call("GET", path, undefined), schema);
    },
    async send<T>(method: Method, path: string, body?: unknown, schema?: z.ZodType<T>): Promise<T | undefined> {
      const response = await call(method, path, body);
      if (schema === undefined || response.status === 204) {
        return undefined;
      }
      return parse(response, schema);
    },
  } as ApiClient;
}

async function toError(response: Response): Promise<ApiError> {
  let json: unknown;
  try {
    json = await response.json();
  } catch {
    json = null;
  }
  const envelope = errorEnvelopeSchema.safeParse(json);
  if (!envelope.success) {
    return new ApiError(response.status, "unknown", `A plataforma respondeu ${response.status}. Tente de novo.`);
  }
  const { message, code, param, current_version } = envelope.data.error;
  return new ApiError(response.status, code ?? "unknown", message, {
    param: param ?? null,
    currentVersion: current_version ?? null,
  });
}
