import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../ApiProvider";
import { connectionCheckSchema, observabilitySchema, type Observability } from "../schemas";
import { keys } from "./keys";

export function useObservability() {
  const api = useApi();
  return useQuery({ queryKey: keys.observability, queryFn: () => api.get("/observability", observabilitySchema) });
}

function useSettingsWrite<Vars>(write: (vars: Vars) => Promise<Observability>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: write,
    onSuccess: (view) => client.setQueryData(keys.observability, view),
  });
}

export type LangfuseChange = {
  enabled?: boolean;
  host?: string;
  public_key?: string;
  secret_key?: string;
  version: number;
};

export function useSaveLangfuse() {
  const api = useApi();
  return useSettingsWrite((change: LangfuseChange) =>
    api.send("PUT", "/observability/langfuse", change, observabilitySchema),
  );
}

export function useSaveCapture() {
  const api = useApi();
  return useSettingsWrite((change: { enabled: boolean; acknowledged?: boolean; version: number }) =>
    api.send("PUT", "/observability/capture", change, observabilitySchema),
  );
}

/** "Testar conexão": com o que está sendo digitado ou com os ajustes salvos. Nunca devolve o segredo. */
export function useTestLangfuse() {
  const api = useApi();
  return useMutation({
    mutationFn: (fields: { host?: string; public_key?: string; secret_key?: string }) =>
      api.send("POST", "/observability/langfuse/test", fields, connectionCheckSchema),
  });
}
