/** `GET /me` decide (013 R5): 200 abre o shell; 404 mostra o acesso negado, sem nenhuma outra chamada (SC-007). */

import type { ReactNode } from "react";

import { useMe } from "../api/hooks/me";
import { isApiError } from "../api/errors";
import { LoadError } from "../ui/States";
import { AccessDenied } from "./AccessDenied";
import { SessionScreen } from "./SessionScreen";

export function RequireAdmin({ children }: { children: ReactNode }) {
  const me = useMe();
  if (me.isPending) {
    return <SessionScreen status="loading" />;
  }
  if (me.isError) {
    if (isApiError(me.error) && me.error.isNotFound) {
      return <AccessDenied />;
    }
    return (
      <SessionScreen status="error">
        <LoadError what="a sessão" error={me.error} onRetry={() => void me.refetch()} />
      </SessionScreen>
    );
  }
  return <>{children}</>;
}
