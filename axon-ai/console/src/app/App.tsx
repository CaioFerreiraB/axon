import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { RouterProvider } from "react-router/dom";

import { ApiProvider } from "../api/ApiProvider";
import { createQueryClient } from "../api/queryClient";
import { AuthProvider, useAuth, type SessionManager } from "../auth/AuthProvider";
import { Button } from "../ui/Button";
import { Notice } from "../ui/Notice";
import { createRouter } from "./router";
import { SessionScreen } from "./SessionScreen";

function Routed() {
  const { session } = useAuth();
  // O roteador nasce depois da sessão: a volta do login reescreve a URL antes dele ler a localização.
  const [router] = useState(createRouter);
  return (
    <ApiProvider session={session}>
      <RouterProvider router={router} />
    </ApiProvider>
  );
}

export function App({ manager }: { manager: SessionManager }) {
  const [queryClient] = useState(createQueryClient);
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider
        manager={manager}
        fallback={(state) =>
          state.status === "loading" ? (
            <SessionScreen status="loading" />
          ) : (
            <SessionScreen status="error">
              <Notice tone="bad" title="O login não foi concluído">
                {state.message}
              </Notice>
              <Button variant="primary" onClick={state.retry}>
                Entrar de novo
              </Button>
            </SessionScreen>
          )
        }
      >
        <Routed />
      </AuthProvider>
    </QueryClientProvider>
  );
}
