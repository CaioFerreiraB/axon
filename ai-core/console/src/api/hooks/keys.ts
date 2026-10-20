/** As chaves de cache por recurso, para invalidar só o que uma escrita muda. */
export const keys = {
  me: ["me"] as const,
  assistants: ["assistants"] as const,
  assistant: (name: string) => ["assistants", name] as const,
  history: (name: string) => ["assistants", name, "history"] as const,
  mcp: ["mcp"] as const,
  mcpHealth: (alias: string) => ["mcp", alias, "health"] as const,
  usage: (params: object) => ["usage", params] as const,
  prices: ["prices"] as const,
  unpriced: (params: object) => ["prices", "unpriced", params] as const,
  observability: ["observability"] as const,
  users: (params: object) => ["users", params] as const,
  usersAll: ["users"] as const,
  groups: ["groups"] as const,
  login: ["login-settings"] as const,
};
