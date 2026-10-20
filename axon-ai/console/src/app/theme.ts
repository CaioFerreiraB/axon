/** Tema claro, escuro ou o do sistema (013 FR-019): a única preferência guardada no navegador. */

import { useCallback, useSyncExternalStore } from "react";

export type ThemeChoice = "light" | "dark" | "system";
export const THEME_KEY = "console.theme";

const listeners = new Set<() => void>();

export function readTheme(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(THEME_KEY);
    return stored === "light" || stored === "dark" ? stored : "system";
  } catch {
    return "system";
  }
}

export function applyTheme(choice: ThemeChoice = readTheme()): void {
  const root = document.documentElement;
  if (choice === "system") {
    root.removeAttribute("data-theme");
  } else {
    root.setAttribute("data-theme", choice);
  }
}

export function setTheme(choice: ThemeChoice): void {
  try {
    if (choice === "system") {
      window.localStorage.removeItem(THEME_KEY);
    } else {
      window.localStorage.setItem(THEME_KEY, choice);
    }
  } catch {
    // Sem armazenamento (janela privada): o tema vale nesta aba.
  }
  applyTheme(choice);
  current = choice;
  listeners.forEach((listener) => listener());
}

let current: ThemeChoice = typeof window === "undefined" ? "system" : readTheme();

export function useTheme(): [ThemeChoice, (choice: ThemeChoice) => void] {
  const choice = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
    () => "system" as ThemeChoice,
  );
  return [choice, useCallback((next: ThemeChoice) => setTheme(next), [])];
}
