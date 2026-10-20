import { QueryClient } from "@tanstack/react-query";

import { isApiError } from "./errors";

/** Erro do cliente (4xx) não se repete; rede e 5xx, até duas vezes. Sem nova leitura ao focar a janela: a versão que
 * a tela leu é a que vai na escrita (FR-008). */
export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: (count, error) => !(isApiError(error) && error.status >= 400 && error.status < 500) && count < 2,
        refetchOnWindowFocus: false,
        staleTime: 15_000,
      },
      mutations: { retry: false },
    },
  });
}
