/** O service worker da casca (013 FR-052; ADR-060): só no build de produção, depois do `load`, para não disputar a
 * primeira pintura. Navegador sem suporte (ou janela que o bloqueia) segue como site. */
export function registerServiceWorker(): void {
  if (!import.meta.env.PROD || !("serviceWorker" in navigator)) {
    return;
  }
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
      // Sem service worker, a console continua funcionando como site.
    });
  });
}
