import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../ApiProvider";
import {
  priceListSchema,
  priceSchema,
  unpricedSchema,
  usageReportSchema,
  type UsageGrouping,
  type UsageOrigin,
} from "../schemas";
import { keys } from "./keys";

export type UsageParams = { from?: string; to?: string; by: UsageGrouping; origin: UsageOrigin; days?: number };

function search(params: Record<string, string | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      query.set(key, value);
    }
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

/** `GET /usage`: o fuso padrão é o da instalação, que a resposta informa (013 FR-010). */
export function useUsage(params: { from?: string; to?: string; by: UsageGrouping; origin: UsageOrigin }) {
  const api = useApi();
  return useQuery({
    queryKey: keys.usage(params),
    queryFn: () => api.get(`/usage${search(params)}`, usageReportSchema),
    placeholderData: keepPreviousData,
  });
}

export function usePrices() {
  const api = useApi();
  return useQuery({ queryKey: keys.prices, queryFn: async () => (await api.get("/prices", priceListSchema)).data });
}

export function useUnpriced(params: { from?: string; to?: string }) {
  const api = useApi();
  return useQuery({
    queryKey: keys.unpriced(params),
    queryFn: async () => (await api.get(`/prices/unpriced${search(params)}`, unpricedSchema)).data,
  });
}

export function useAddPrice() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (price: { provider: string; model: string; input: string; output: string; effective_from: string }) =>
      api.send("POST", "/prices", price, priceSchema),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.prices });
      void client.invalidateQueries({ queryKey: ["usage"] });
    },
  });
}
