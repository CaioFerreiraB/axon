/** Chaves de API dos sistemas (013 US9; ADR-040). A chave em claro vem só nas respostas da emissão e da rotação e
 * nunca vai para o cache: a mutação não guarda o resultado (`gcTime: 0`) e a lista é relida, não escrita (013 R23). */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../ApiProvider";
import { apiKeyListSchema, apiKeySchema, issuedKeySchema, type IssuedKey } from "../schemas";
import { keys } from "./keys";

const keyPath = (keyId: string) => `/keys/${encodeURIComponent(keyId)}`;

export function useApiKeys() {
  const api = useApi();
  return useQuery({ queryKey: keys.apiKeys, queryFn: async () => (await api.get("/keys", apiKeyListSchema)).data });
}

function useKeyWrite<Vars, Result>(write: (vars: Vars) => Promise<Result>, { keepResult = true } = {}) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: write,
    gcTime: keepResult ? undefined : 0,
    onSettled: () => void client.invalidateQueries({ queryKey: keys.apiKeys }),
  });
}

export function useCreateKey() {
  const api = useApi();
  return useKeyWrite(
    (draft: { subject: string; label?: string }): Promise<IssuedKey> =>
      api.send("POST", "/keys", draft, issuedKeySchema),
    { keepResult: false },
  );
}

export function useRotateKey() {
  const api = useApi();
  return useKeyWrite(
    (keyId: string): Promise<IssuedKey> => api.send("POST", `${keyPath(keyId)}/rotate`, undefined, issuedKeySchema),
    { keepResult: false },
  );
}

export function useRevokeKey() {
  const api = useApi();
  return useKeyWrite((keyId: string) => api.send("DELETE", keyPath(keyId), undefined, apiKeySchema));
}
