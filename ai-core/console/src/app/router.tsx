/** As rotas de contracts/screens.md, cada tela carregada sob demanda. `/` abre o uso e custo. */

import { lazy } from "react";
import { createBrowserRouter, Navigate } from "react-router";

import { RequireAdmin } from "./RequireAdmin";
import { NotFoundPage, RouteError } from "./RouteError";
import { Shell } from "./Shell";

const UsagePage = lazy(() => import("../features/usage/UsagePage"));
const PricesPage = lazy(() => import("../features/usage/PricesPage"));
const AssistantsPage = lazy(() => import("../features/assistants/AssistantsPage"));
const AssistantDetail = lazy(() => import("../features/assistants/AssistantDetail"));
const ModelsTab = lazy(() => import("../features/assistants/ModelsTab"));
const McpTab = lazy(() => import("../features/assistants/McpTab"));
const HistoryTab = lazy(() => import("../features/assistants/HistoryTab"));
const McpServersPage = lazy(() => import("../features/mcp/McpServersPage"));
const ObservabilityPage = lazy(() => import("../features/observability/ObservabilityPage"));
const AccessPage = lazy(() => import("../features/access/AccessPage"));
const UsersTab = lazy(() => import("../features/access/UsersTab"));
const GroupsTab = lazy(() => import("../features/access/GroupsTab"));
const LoginTab = lazy(() => import("../features/access/LoginTab"));

export function createRouter() {
  return createBrowserRouter([
    {
      element: (
        <RequireAdmin>
          <Shell />
        </RequireAdmin>
      ),
      errorElement: <RouteError />,
      children: [
        { index: true, element: <Navigate to="/uso" replace /> },
        { path: "uso", element: <UsagePage /> },
        { path: "uso/precos", element: <PricesPage /> },
        { path: "assistentes", element: <AssistantsPage /> },
        {
          path: "assistentes/:nome",
          element: <AssistantDetail />,
          children: [
            { index: true, element: <Navigate to="modelos" replace /> },
            { path: "modelos", element: <ModelsTab /> },
            { path: "mcp", element: <McpTab /> },
            { path: "historico", element: <HistoryTab /> },
          ],
        },
        { path: "servidores-mcp", element: <McpServersPage /> },
        { path: "observabilidade", element: <ObservabilityPage /> },
        {
          path: "acesso",
          element: <AccessPage />,
          children: [
            { index: true, element: <Navigate to="usuarios" replace /> },
            { path: "usuarios", element: <UsersTab /> },
            { path: "grupos", element: <GroupsTab /> },
            { path: "login", element: <LoginTab /> },
          ],
        },
        { path: "*", element: <NotFoundPage /> },
      ],
    },
  ]);
}
