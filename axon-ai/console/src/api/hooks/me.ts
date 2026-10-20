import { useQuery } from "@tanstack/react-query";

import { useApi } from "../ApiProvider";
import { meSchema } from "../schemas";
import { keys } from "./keys";

/** `GET /me`: 200 abre o shell; 404 é a página de acesso negado (013 FR-003, SC-007). */
export function useMe() {
  const api = useApi();
  return useQuery({ queryKey: keys.me, queryFn: () => api.get("/me", meSchema), staleTime: 60_000 });
}
