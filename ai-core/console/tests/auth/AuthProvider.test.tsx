/** T010 — a sessão: sem usuário vai ao login com a rota pedida e um nonce; a volta do login restaura a rota; erro do
 * provedor aparece com "Entrar de novo". Nada de token no armazenamento do navegador (FR-002). */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AuthProvider, useAuth } from "../../src/auth/AuthProvider";
import { fakeManager, fakeUser } from "../render";

function Who() {
  const { user } = useAuth();
  return <p>sessão de {String(user.profile.preferred_username)}</p>;
}

function mount(manager: ReturnType<typeof fakeManager>) {
  return render(
    <AuthProvider
      manager={manager}
      fallback={(state) => <p>{state.status === "error" ? `erro: ${state.message}` : "entrando"}</p>}
    >
      <Who />
    </AuthProvider>,
  );
}

describe("AuthProvider", () => {
  it("sem usuário em memória vai ao login com a rota atual e um nonce", async () => {
    window.history.replaceState(null, "", "/assistentes/geral/modelos?x=1");
    const manager = fakeManager({ getUser: vi.fn(async () => null) });
    mount(manager);
    await waitFor(() => expect(manager.signinRedirect).toHaveBeenCalledOnce());
    const args = vi.mocked(manager.signinRedirect).mock.calls[0]?.[0];
    expect(args?.state).toBe("/assistentes/geral/modelos?x=1");
    expect(args?.nonce).toMatch(/^[0-9a-f]{32}$/);
    expect(screen.getByText("entrando")).toBeInTheDocument();
  });

  it("a volta do login abre a sessão e restaura a rota pedida", async () => {
    window.history.replaceState(null, "", "/callback?code=c&state=s");
    const manager = fakeManager({
      signinRedirectCallback: vi.fn(async () => ({ ...fakeUser, state: "/uso?dias=7" }) as typeof fakeUser),
    });
    mount(manager);
    expect(await screen.findByText("sessão de ana")).toBeInTheDocument();
    expect(window.location.pathname + window.location.search).toBe("/uso?dias=7");
    expect(Object.keys(window.localStorage)).toEqual([]);
  });

  it("erro do provedor mostra a mensagem", async () => {
    window.history.replaceState(null, "", "/callback?error=access_denied");
    const manager = fakeManager({
      signinRedirectCallback: vi.fn(async () => Promise.reject(new Error("acesso negado pelo provedor"))),
    });
    mount(manager);
    expect(await screen.findByText("erro: acesso negado pelo provedor")).toBeInTheDocument();
  });
});
