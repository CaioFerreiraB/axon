import { useQueries } from "@tanstack/react-query";

import { useApi } from "../ApiProvider";
import { historySchema, type HistoryEntry } from "../schemas";
import { keys } from "./keys";

/** O histórico de vários Assistants em paralelo, em cache — os marcos de sobreposição do gráfico de uso (013 T028). */
export function useHistories(names: readonly string[]): { name: string; entries: HistoryEntry[] }[] {
  const api = useApi();
  const results = useQueries({
    queries: names.map((name) => ({
      queryKey: keys.history(name),
      queryFn: async () => (await api.get(`/assistants/${encodeURIComponent(name)}/history`, historySchema)).data,
      staleTime: 60_000,
    })),
  });
  return names.map((name, index) => ({ name, entries: results[index]?.data ?? [] }));
}
