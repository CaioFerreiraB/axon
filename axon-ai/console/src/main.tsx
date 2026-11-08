import "./ui/global.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import { applyTheme } from "./app/theme";
import { registerServiceWorker } from "./app/pwa/registerServiceWorker";
import { createUserManager } from "./auth/userManager";

applyTheme();
registerServiceWorker();

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App manager={createUserManager()} />
    </StrictMode>,
  );
}
