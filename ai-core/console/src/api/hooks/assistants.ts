import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../ApiProvider";
import {
  assistantListSchema,
  assistantViewSchema,
  historySchema,
  modelCheckSchema,
  providerListSchema,
  type AssistantView,
  type McpSelection,
  type Section,
} from "../schemas";
import { keys } from "./keys";

const path = (name: string) => `/assistants/${encodeURIComponent(name)}`;

export function useAssistants() {
  const api = useApi();
  return useQuery({
    queryKey: keys.assistants,
    queryFn: async () => (await api.get("/assistants", assistantListSchema)).data,
  });
}

export function useAssistant(name: string) {
  const api = useApi();
  return useQuery({ queryKey: keys.assistant(name), queryFn: () => api.get(path(name), assistantViewSchema) });
}

export function useHistory(name: string) {
  const api = useApi();
  return useQuery({
    queryKey: keys.history(name),
    queryFn: async () => (await api.get(`${path(name)}/history`, historySchema)).data,
  });
}

function useWrite<Vars>(name: string, write: (vars: Vars) => Promise<AssistantView>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: write,
    onSuccess: (view) => {
      client.setQueryData(keys.assistant(name), view);
      void client.invalidateQueries({ queryKey: keys.assistants, exact: true });
      void client.invalidateQueries({ queryKey: keys.history(name) });
    },
  });
}

export function useSaveModels(name: string) {
  const api = useApi();
  return useWrite(name, (vars: { roles: Record<string, string>; version: number | null }) =>
    api.send("PUT", `${path(name)}/models`, vars, assistantViewSchema),
  );
}

export function useSaveMcp(name: string) {
  const api = useApi();
  return useWrite(name, (vars: McpSelection & { version: number | null }) =>
    api.send("PUT", `${path(name)}/mcp`, vars, assistantViewSchema),
  );
}

export function useDiscardOverride(name: string) {
  const api = useApi();
  return useWrite(name, ({ section, version }: { section: Section; version: number }) =>
    api.send("DELETE", `${path(name)}/overrides/${section}?version=${version}`, undefined, assistantViewSchema),
  );
}

/** "Testar modelo" (008 R47): disponibilidade e tempo, sem salvar nada. */
export function useCheckModel(name: string) {
  const api = useApi();
  return useMutation({
    mutationFn: (vars: { role: string; model: string }) =>
      api.send("POST", `${path(name)}/models/check`, vars, modelCheckSchema),
  });
}

/** Os providers e a prontidão de cada um (ADR-035): a escolha de modelo só oferece os prontos. */
export function useProviders() {
  const api = useApi();
  return useQuery({
    queryKey: keys.providers,
    queryFn: async () => (await api.get("/providers", providerListSchema)).data,
    staleTime: 30_000,
  });
}
