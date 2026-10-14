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
