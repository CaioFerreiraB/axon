/** T011 — o cliente da API: Bearer, 401 → renova e tenta de novo, depois login; envelope de erro → ApiError. */

import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { z } from "zod";

import { createApiClient, type Session } from "../../src/api/client";
import { ApiError, fieldError } from "../../src/api/errors";
import { server } from "../msw/server";

const ok = z.object({ ok: z.boolean() });

function sessionWith(overrides: Partial<Session> = {}): Session {
  return { token: () => "velho", renew: vi.fn(async () => "novo"), relogin: vi.fn(async () => {}), ...overrides };
}

describe("cliente da API", () => {
  it("manda o token e valida a resposta", async () => {
    let seen = "";
    server.use(
      http.get("*/admin/v1/coisa", ({ request }) => {
        seen = request.headers.get("authorization") ?? "";
        return HttpResponse.json({ ok: true });
      }),
    );
    await expect(createApiClient(sessionWith()).get("/coisa", ok)).resolves.toEqual({ ok: true });
    expect(seen).toBe("Bearer velho");
  });

  it("401 renova uma vez e repete com o token novo", async () => {
    const tokens: string[] = [];
    server.use(
      http.get("*/admin/v1/coisa", ({ request }) => {
        const token = request.headers.get("authorization") ?? "";
        tokens.push(token);
        return token === "Bearer novo" ? HttpResponse.json({ ok: true }) : new HttpResponse(null, { status: 401 });
      }),
    );
    const session = sessionWith();
    await expect(createApiClient(session).get("/coisa", ok)).resolves.toEqual({ ok: true });
    expect(tokens).toEqual(["Bearer velho", "Bearer novo"]);
    expect(session.relogin).not.toHaveBeenCalled();
  });

  it("401 sem renovação possível refaz o login", async () => {
    server.use(http.get("*/admin/v1/coisa", () => new HttpResponse(null, { status: 401 })));
    const session = sessionWith({ renew: vi.fn(async () => null) });
    await expect(createApiClient(session).get("/coisa", ok)).rejects.toBeInstanceOf(ApiError);
    expect(session.relogin).toHaveBeenCalledOnce();
  });

  it("o envelope de erro vira ApiError com param e versão atual", async () => {
    server.use(
      http.put("*/admin/v1/coisa", () =>
        HttpResponse.json(
          {
            error: {
              message: "os ajustes mudaram",
              type: "conflict_error",
              code: "version_conflict",
              param: "version",
              current_version: 5,
            },
          },
          { status: 409 },
        ),
      ),
    );
    const error = await createApiClient(sessionWith())
      .send("PUT", "/coisa", { version: 4 }, ok)
      .catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).isVersionConflict).toBe(true);
    expect((error as ApiError).currentVersion).toBe(5);
  });

  it("422 nomeia o campo — inclusive o papel dentro de roles", async () => {
    server.use(
      http.put("*/admin/v1/coisa", () =>
        HttpResponse.json(
          {
            error: {
              message: "fora da allowlist",
              type: "invalid_request_error",
              code: "invalid_field",
              param: "roles.generation",
            },
          },
          { status: 422 },
        ),
      ),
    );
    const error = await createApiClient(sessionWith())
      .send("PUT", "/coisa", {}, ok)
      .catch((e: unknown) => e);
    expect(fieldError(error, "roles.generation")).toBe("fora da allowlist");
    expect(fieldError(error, "roles")).toBe("fora da allowlist");
    expect(fieldError(error, "email")).toBeUndefined();
  });

  it("resposta fora do contrato é erro explícito", async () => {
    server.use(http.get("*/admin/v1/coisa", () => HttpResponse.json({ ok: "sim" })));
    const error = await createApiClient(sessionWith())
      .get("/coisa", ok)
      .catch((e: unknown) => e);
    expect((error as ApiError).code).toBe("contract");
  });

  it("204 não tem corpo", async () => {
    server.use(http.delete("*/admin/v1/coisa", () => new HttpResponse(null, { status: 204 })));
    await expect(createApiClient(sessionWith()).send("DELETE", "/coisa")).resolves.toBeUndefined();
  });
});
