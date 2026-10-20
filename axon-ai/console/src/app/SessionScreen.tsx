import type { ReactNode } from "react";

import styles from "./SessionScreen.module.css";

/** Entre a abertura e a sessão pronta: "Entrando…", ou o erro do login com o caminho de volta. */
export function SessionScreen({ status, children }: { status: "loading" | "error"; children?: ReactNode }) {
  return (
    <div className={styles.screen}>
      <div className={styles.box} aria-live="polite" aria-busy={status === "loading"}>
        {status === "loading" ? (
          <>
            <span className={styles.spinner} aria-hidden="true" />
            <span>Entrando…</span>
          </>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
