/** "Instalar app" na folha "Mais" (013 FR-047): só quando o navegador oferece a instalação (`beforeinstallprompt`,
 * Chromium). No Safari, que não tem o evento, a pessoa instala pelo "Adicionar à Tela de Início". */

import { useCallback, useSyncExternalStore } from "react";

interface InstallPromptEvent extends Event {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

let deferred: InstallPromptEvent | null = null;
const listeners = new Set<() => void>();
const notify = () => listeners.forEach((listener) => listener());

if (typeof window !== "undefined") {
  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferred = event as InstallPromptEvent;
    notify();
  });
  window.addEventListener("appinstalled", () => {
    deferred = null;
    notify();
  });
}

/** `install` é `null` quando não há o que oferecer (já instalado, navegador sem o evento ou pedido já usado). */
export function useInstallPrompt(): { install: (() => Promise<void>) | null } {
  const available = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => deferred !== null,
    () => false,
  );
  const install = useCallback(async () => {
    const event = deferred;
    if (!event) {
      return;
    }
    deferred = null;
    notify();
    await event.prompt();
    await event.userChoice;
  }, []);
  return { install: available ? install : null };
}
