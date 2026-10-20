/**
 * A sessão OIDC da console (013 R5): cliente público `console` da 012, código + PKCE, tokens só em memória
 * (`InMemoryWebStorage`, FR-002) e renovação pelo token de renovação, sem iframe. O estado do redirecionamento (o
 * verificador do PKCE) vive no `sessionStorage` só durante a ida ao login — a volta o apaga.
 */

import { InMemoryWebStorage, UserManager, WebStorageStateStore } from "oidc-client-ts";

export const CLIENT_ID = "console";
export const SCOPE = "openid profile email groups offline_access";

export function createUserManager(origin: string = window.location.origin): UserManager {
  return new UserManager({
    authority: origin,
    client_id: CLIENT_ID,
    redirect_uri: `${origin}/callback`,
    post_logout_redirect_uri: `${origin}/`,
    response_type: "code",
    scope: SCOPE,
    userStore: new WebStorageStateStore({ store: new InMemoryWebStorage() }),
    stateStore: new WebStorageStateStore({ store: window.sessionStorage }),
    automaticSilentRenew: true,
    monitorSession: false,
    loadUserInfo: false,
    revokeTokenTypes: ["refresh_token"],
  });
}

/** A rota atual, para voltar a ela depois do login (013 US1 cenário 1). */
export function currentRoute(): string {
  const { pathname, search, hash } = window.location;
  return pathname === "/callback" ? "/" : `${pathname}${search}${hash}`;
}
