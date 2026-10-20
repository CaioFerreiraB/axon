import "./ui/global.css";

import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./app/App";
import { applyTheme } from "./app/theme";
import { createUserManager } from "./auth/userManager";

applyTheme();

const root = document.getElementById("root");
if (root) {
  createRoot(root).render(
    <StrictMode>
      <App manager={createUserManager()} />
    </StrictMode>,
  );
}
