import { keepPreviousData, useQuery } from "@tanstack/react-query";

import { useApi } from "../ApiProvider";
import { impactReportSchema, type ImpactGrain, type UsageGrouping, type UsageOrigin } from "../schemas";
import { keys } from "./keys";

export type ImpactParams = {
  from?: string;
  to?: string;
  grain?: ImpactGrain;
  by?: UsageGrouping;
  origin?: UsageOrigin;
};

function search(params: ImpactParams): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) {
      query.set(key, value);
    }
  }
  const text = query.toString();
  return text ? `?${text}` : "";
}

/** `GET /impact` (008 US12; ADR-056): o fuso padrão é o da instalação, que a resposta informa. */
export function useImpact(params: ImpactParams, options: { enabled?: boolean } = {}) {
  const api = useApi();
  return useQuery({
    queryKey: keys.impact(params),
    queryFn: () => api.get(`/impact${search(params)}`, impactReportSchema),
    placeholderData: keepPreviousData,
    enabled: options.enabled ?? true,
  });
}
