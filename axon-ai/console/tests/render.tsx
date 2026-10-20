/** Monta uma tela com os provedores reais (TanStack Query, cliente da API sobre o MSW) e uma sessão falsa. */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { User } from "oidc-client-ts";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router";
import { vi } from "vitest";

import { ApiProvider } from "../src/api/ApiProvider";
import type { Session } from "../src/api/client";
import { AuthProvider, type SessionManager } from "../src/auth/AuthProvider";

export const fakeUser = {
  access_token: "token-da-console",
  id_token: "id-token",
  expired: false,
  state: undefined,
  profile: { sub: "id-ana", preferred_username: "ana", name: "Ana Souza", email: "ana@exemplo.org" },
} as unknown as User;

export function fakeManager(overrides: Partial<SessionManager> = {}): SessionManager {
  return {
    getUser: vi.fn(async () => fakeUser),
    signinRedirect: vi.fn(async () => {}),
    signinRedirectCallback: vi.fn(async () => fakeUser),
    signinSilent: vi.fn(async () => fakeUser),
    signoutRedirect: vi.fn(async () => {}),
    revokeTokens: vi.fn(async () => {}),
    removeUser: vi.fn(async () => {}),
    events: { addUserLoaded: vi.fn(), removeUserLoaded: vi.fn() },
    ...overrides,
  } as unknown as SessionManager;
}

export const session: Session = { token: () => "token-da-console", renew: async () => null, relogin: async () => {} };

export function renderAt(
  path: string,
  routes: { path: string; element: ReactElement; children?: { path: string; element: ReactElement }[] }[],
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AuthProvider manager={fakeManager()} fallback={() => <p>entrando</p>}>
        <ApiProvider session={session}>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              {routes.map((route) => (
                <Route key={route.path} path={route.path} element={route.element}>
                  {route.children?.map((child) => (
                    <Route key={child.path} path={child.path} element={child.element} />
                  ))}
                </Route>
              ))}
            </Routes>
          </MemoryRouter>
        </ApiProvider>
      </AuthProvider>
    </QueryClientProvider>,
  );
}
