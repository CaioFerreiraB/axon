/** Estados de toda tela (FR-015): carregando com a forma final, vazio que explica de onde vêm os dados, erro com nova
 * tentativa. */

import type { CSSProperties, ReactNode } from "react";

import { isApiError } from "../api/errors";
import { Notice } from "./Notice";
import styles from "./States.module.css";

export function Skeleton({
  width = "100%",
  height = 14,
  style,
}: {
  width?: number | string;
  height?: number | string;
  style?: CSSProperties;
}) {
  return <span className={styles.skeleton} style={{ width, height, ...style }} aria-hidden="true" />;
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={styles.empty}>
      <p className={styles.emptyTitle}>{title}</p>
      {children ? <p className={styles.emptyText}>{children}</p> : null}
      {action ? <div className={styles.emptyAction}>{action}</div> : null}
    </div>
  );
}

/** Erro de carregamento com o motivo da API e "Tentar de novo". */
export function LoadError({ what, error, onRetry }: { what: string; error: unknown; onRetry: () => void }) {
  const detail = isApiError(error)
    ? error.status
      ? `A API respondeu ${error.status}: ${error.message}`
      : error.message
    : "Algo deu errado ao carregar. Nada foi alterado.";
  return (
    <Notice
      tone="bad"
      title={`Não foi possível carregar ${what}`}
      action={{ label: "Tentar de novo", onClick: onRetry }}
      role="alert"
    >
      {detail}
    </Notice>
  );
}
