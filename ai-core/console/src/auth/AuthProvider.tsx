/**
 * A sessão para o resto da console. Sem usuário em memória, vai ao login da 012 — com a sessão de 30 dias do
 * provedor, ele devolve o código sem mostrar o formulário — e volta à rota pedida. O cliente da API recebe a sessão
 * como porta (`Session`): token atual, renovação e novo login.
 */

import type { User, UserManager } from "oidc-client-ts";
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

import type { Session } from "../api/client";
import { currentRoute } from "./userManager";

export type SessionManager = Pick<
  UserManager,
  | "getUser"
  | "signinRedirect"
  | "signinRedirectCallback"
  | "signinSilent"
  | "signoutRedirect"
  | "revokeTokens"
  | "removeUser"
  | "events"
>;

type AuthState = { status: "loading" } | { status: "signed-in"; user: User } | { status: "error"; message: string };

type AuthContextValue = {
  user: User;
  session: Session;
  signOut: () => Promise<void>;
  signInAgain: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({
  manager,
  children,
  fallback,
}: {
  manager: SessionManager;
  children: ReactNode;
  fallback: (state: { status: "loading" } | { status: "error"; message: string; retry: () => void }) => ReactNode;
}) {
  const [state, setState] = useState<AuthState>({ status: "loading" });
  const userRef = useRef<User | null>(null);

  const remember = useCallback((user: User | null) => {
    userRef.current = user;
    setState(user ? { status: "signed-in", user } : { status: "loading" });
  }, []);

  const signIn = useCallback(async () => {
    // A 012 exige `nonce` (oidc.md); a biblioteca o guarda no estado e o confere no id_token.
    await manager.signinRedirect({ state: currentRoute(), nonce: randomNonce() });
  }, [manager]);

  const start = useCallback(async () => {
    setState({ status: "loading" });
    try {
      if (window.location.pathname === "/callback") {
        // Também no retorno com erro: a biblioteca apaga o estado do redirecionamento e traz a mensagem do provedor.
        const user = await manager.signinRedirectCallback();
        const target = typeof user.state === "string" && user.state.startsWith("/") ? user.state : "/";
        window.history.replaceState(null, "", target);
        remember(user);
        return;
      }
      const existing = await manager.getUser();
      if (existing && !existing.expired) {
        remember(existing);
        return;
      }
      await signIn();
    } catch (error) {
      const message = error instanceof Error ? error.message : "O login não foi concluído.";
      setState({ status: "error", message });
    }
  }, [manager, remember, signIn]);

  const started = useRef(false);
  useEffect(() => {
    // Uma vez só: o código de autorização vale uma troca (o StrictMode monta o efeito duas vezes).
    if (started.current) {
      return;
    }
    started.current = true;
    void start();
  }, [start]);

  useEffect(() => {
    const loaded = (user: User) => remember(user);
    manager.events.addUserLoaded(loaded);
    return () => manager.events.removeUserLoaded(loaded);
  }, [manager, remember]);

  const session = useMemo<Session>(
    () => ({
      token: () => userRef.current?.access_token ?? null,
      renew: async () => {
        try {
          const user = await manager.signinSilent();
          if (user) {
            userRef.current = user;
            return user.access_token;
          }
          return null;
        } catch {
          return null;
        }
      },
      relogin: signIn,
    }),
    [manager, signIn],
  );

  const signOut = useCallback(async () => {
    const user = userRef.current;
    try {
      await manager.revokeTokens(["refresh_token"]);
    } catch {
      // A sessão no provedor termina no logout de qualquer forma; revogar é cortesia.
    }
    await manager.signoutRedirect({ id_token_hint: user?.id_token });
  }, [manager]);

  if (state.status !== "signed-in") {
    return <>{fallback(state.status === "error" ? { ...state, retry: () => void signIn() } : state)}</>;
  }
  return (
    <AuthContext.Provider value={{ user: state.user, session, signOut, signInAgain: signIn }}>
      {children}
    </AuthContext.Provider>
  );
}

function randomNonce(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (value === null) {
    throw new Error("useAuth fora do AuthProvider");
  }
  return value;
}
