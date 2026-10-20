import { createContext, useContext, useMemo, type ReactNode } from "react";

import { createApiClient, type ApiClient, type Session } from "./client";

const ApiContext = createContext<ApiClient | null>(null);

export function ApiProvider({ session, children }: { session: Session; children: ReactNode }) {
  const client = useMemo(() => createApiClient(session), [session]);
  return <ApiContext.Provider value={client}>{children}</ApiContext.Provider>;
}

export function useApi(): ApiClient {
  const client = useContext(ApiContext);
  if (client === null) {
    throw new Error("useApi fora do ApiProvider");
  }
  return client;
}
