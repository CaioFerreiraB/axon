import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../ApiProvider";
import { mcpHealthSchema, mcpListSchema, mcpServerSchema } from "../schemas";
import type { McpServer } from "../schemas";
import { keys } from "./keys";

export type McpDraft = {
  alias: string;
  transport: "http" | "sse";
  endpoint: string;
  description?: string;
  auth?: { type: "none" | "bearer"; credential?: string } | { type: "delegated" };
  user_access?: boolean;
  policy: { allowed_tools: string[]; write_tools: string[] };
};

export function useMcpServers() {
  const api = useApi();
  return useQuery({ queryKey: keys.mcp, queryFn: async () => (await api.get("/mcp", mcpListSchema)).data });
}

/** A saúde de cada servidor traz as tools descobertas (a aba MCP do Assistant as usa). */
export function useMcpHealths(servers: readonly McpServer[]) {
  const api = useApi();
  return useQueries({
    queries: servers.map(({ alias, auth }) => ({
      queryKey: [...keys.mcpHealth(alias), auth.type],
      queryFn: () => api.get(`/mcp/${encodeURIComponent(alias)}/health`, mcpHealthSchema),
      // A console não possui a autorização confidencial de uma execução delegada.
      enabled: auth.type !== "delegated",
      staleTime: 60_000,
      retry: false,
    })),
  });
}

function useMcpWrite<Vars>(write: (vars: Vars) => Promise<unknown>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: write,
    onSuccess: () => void client.invalidateQueries({ queryKey: keys.mcp }),
  });
}

export function useCreateMcp() {
  const api = useApi();
  return useMcpWrite((draft: McpDraft) => api.send("POST", "/mcp", draft, mcpServerSchema));
}

export function useUpdateMcp() {
  const api = useApi();
  return useMcpWrite((draft: McpDraft) =>
    api.send("PUT", `/mcp/${encodeURIComponent(draft.alias)}`, draft, mcpServerSchema),
  );
}

export function useDeleteMcp() {
  const api = useApi();
  return useMcpWrite((alias: string) => api.send("DELETE", `/mcp/${encodeURIComponent(alias)}`));
}
