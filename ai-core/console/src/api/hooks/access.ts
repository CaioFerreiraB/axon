import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "../ApiProvider";
import {
  accountPageSchema,
  accountSchema,
  groupListSchema,
  groupSchema,
  issuedSchema,
  loginSettingsSchema,
} from "../schemas";
import { keys } from "./keys";

export type UsersParams = { query?: string; state: "active" | "disabled" | "all"; cursor?: string };

const userPath = (username: string) => `/users/${encodeURIComponent(username)}`;

export function useUsers(params: UsersParams) {
  const api = useApi();
  return useQuery({
    queryKey: keys.users(params),
    queryFn: () => {
      const query = new URLSearchParams({ state: params.state, limit: "50" });
      if (params.query) {
        query.set("query", params.query);
      }
      if (params.cursor) {
        query.set("cursor", params.cursor);
      }
      return api.get(`/users?${query.toString()}`, accountPageSchema);
    },
    placeholderData: keepPreviousData,
  });
}

function useAccountWrite<Vars, Result>(write: (vars: Vars) => Promise<Result>, { keepResult = true } = {}) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: write,
    // A senha temporária vive só no diálogo: nada dela fica no cache (013 R7).
    gcTime: keepResult ? undefined : 0,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: keys.usersAll });
      void client.invalidateQueries({ queryKey: keys.groups });
    },
  });
}

export type PersonDraft = { username: string; email: string; name: string; groups: string[]; google_only: boolean };

export function useCreateUser() {
  const api = useApi();
  return useAccountWrite((draft: PersonDraft) => api.send("POST", "/users", draft, issuedSchema), {
    keepResult: false,
  });
}

export function useUpdateUser() {
  const api = useApi();
  return useAccountWrite(
    ({ username, ...patch }: { username: string; email?: string; name?: string; groups?: string[]; version: number }) =>
      api.send("PATCH", userPath(username), patch, accountSchema),
  );
}

export function useResetPassword() {
  const api = useApi();
  return useAccountWrite(
    (username: string) => api.send("POST", `${userPath(username)}/password`, undefined, issuedSchema),
    {
      keepResult: false,
    },
  );
}

export function useSetActive() {
  const api = useApi();
  return useAccountWrite(({ username, active }: { username: string; active: boolean }) =>
    api.send("POST", `${userPath(username)}/${active ? "enable" : "disable"}`, undefined, accountSchema),
  );
}

export function useUnlinkGoogle() {
  const api = useApi();
  return useAccountWrite((username: string) =>
    api.send("DELETE", `${userPath(username)}/google`, undefined, accountSchema),
  );
}

export function useGroups() {
  const api = useApi();
  return useQuery({ queryKey: keys.groups, queryFn: async () => (await api.get("/groups", groupListSchema)).data });
}

export function useCreateGroup() {
  const api = useApi();
  return useAccountWrite((name: string) => api.send("POST", "/groups", { name }, groupSchema));
}

export function useDeleteGroup() {
  const api = useApi();
  return useAccountWrite((name: string) => api.send("DELETE", `/groups/${encodeURIComponent(name)}`));
}

export function useSetMembers() {
  const api = useApi();
  return useAccountWrite(({ name, usernames }: { name: string; usernames: string[] }) =>
    api.send("PUT", `/groups/${encodeURIComponent(name)}/members`, { usernames }, groupSchema),
  );
}

export function useLoginSettings() {
  const api = useApi();
  return useQuery({ queryKey: keys.login, queryFn: () => api.get("/login-settings", loginSettingsSchema) });
}

export function useSaveLoginSettings() {
  const api = useApi();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (change: { google_enabled: boolean; version: number }) =>
      api.send("PUT", "/login-settings", change, loginSettingsSchema),
    onSuccess: (view) => client.setQueryData(keys.login, view),
  });
}
