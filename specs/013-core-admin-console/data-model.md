# Data model — 013 Admin Console

A console não tem armazenamento próprio: o estado é o da API, em cache do TanStack Query, mais o rascunho de formulário
e a preferência de tema. Os tipos espelham [admin-api.md](../008-core-http-api/contracts/admin-api.md) como esquemas
`zod` em `src/api/schemas.ts`.

## Esquemas (um por recurso do contrato)

| Esquema | Fonte | Uso |
|---|---|---|
| `Me` | `GET /me` | shell, marca da instalação, decisão de acesso |
| `AssistantView`, `OverrideView`, `HistoryEntry`, `ModelCheck` | Assistants de sistema | lista, detalhe, abas |
| `McpServer`, `McpHealth` | servidores MCP | aba MCP e tela de servidores |
| `UsageReport`, `UsageDay`, `UsageRow` | uso | dashboard (dinheiro como string decimal → número só na exibição) |
| `Price` | preços | tabela de preços |
| `ObservabilityView`, `ConnectionCheck` | observabilidade | Langfuse e captura |
| `Account`, `IssuedPassword`, `Group`, `LoginSettings` | acesso | usuários, grupos, login |
| `ApiError` | envelope de erro | `status`, `code`, `param`, `message`, `current_version` |

## Estado de tela

| Estado | Onde vive | Regra |
|---|---|---|
| Sessão OIDC | `UserManager` com `InMemoryWebStorage` | nunca no armazenamento persistente (FR-002) |
| Tema | `localStorage["console.theme"]` = `light \| dark \| system` | a única coisa guardada no navegador (FR-019) |
| Rascunho de formulário | `react-hook-form` | sobrevive à renovação de token e a um `409` até a pessoa decidir |
| Filtros (período, agrupamento, origem, busca, aba) | parâmetros da URL | compartilháveis e voltam com o histórico do navegador |
| Senha temporária | estado do diálogo | descartada ao fechar; nunca em cache de consulta |


---

# Passada de 2026-10-20: identidade Axon (US8; research R15–R19)

| Item | Antes | Agora |
|---|---|---|
| `Me.instance` | `{ name, logo_url }` | `{ name, logo_url, custom }` — `custom` diz se a instalação tem marca própria (008, ADR-038) |
| padrão enquanto o `me` carrega | `{ name: "Agentic", logo_url: null }` | `{ name: "Axon", logo_url: null, custom: false }` |
| título da aba | "Console" | "<tela> · <instance.name>"; "Sem acesso · Axon" no acesso negado |
| pacote | `@agentic/console` | `@axon/console` |

## Fase 9 (2026-10-21): chaves de API e permissões (research R22–R27; ADR-040)

| Tipo (`src/api/schemas.ts`) | Forma |
|---|---|
| `Section` | `"models" \| "mcp" \| "auth"` |
| `AuthSelection` | `{ schemes: ("oidc" \| "api_key")[], allow: string[] }` |
| `AssistantView.yaml` / `.effective` | + `auth: AuthSelection` |
| `OverrideView.payload`, `HistoryEntry.payload` | + `AuthSelection` (`isAuthPayload`) |
| `ApiKey` | + `rotated_at: string \| null` |
| `IssuedKey` | `ApiKey & { key: string }` — só nas respostas da emissão e da rotação; nunca em cache |

Estado local da aba "Permissões": `{ schemes: Set<Scheme>, allow: string[] }`, o rascunho; a versão lida acompanha o
salvar (FR-008). Entrada: `*`, `user:<nome>`, `svc:<nome>` ou `group:<nome>`, sem espaço.
