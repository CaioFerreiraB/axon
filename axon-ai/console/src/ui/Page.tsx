import { createContext, useContext, useEffect, type ReactNode } from "react";
import { Link } from "react-router";

import { Icon } from "./icons";
import styles from "./Page.module.css";

/** O nome depois do título da tela na aba: o da instalação, "Axon" por padrão (013 FR-020, research R18). */
export const PageTitleSuffix = createContext("Axon");

/** O que o cabeçalho de app do celular mostra (013 FR-046, R38): o título da tela e, numa tela de detalhe, o "voltar".
 * O `PageHeader` publica; a casca (`Shell`) guarda e o `AppBar` desenha. */
export type PageChrome = { title: string; back?: { to: string; label: string } };
export const PageChromeSetter = createContext<(chrome: PageChrome | null) => void>(() => undefined);

export function Page({ children }: { children: ReactNode }) {
  return <div className={styles.page}>{children}</div>;
}

export function PageHeader({
  title,
  subtitle,
  badge,
  actions,
  back,
}: {
  title: ReactNode;
  subtitle?: ReactNode;
  badge?: ReactNode;
  actions?: ReactNode;
  back?: { to: string; label: string };
}) {
  const suffix = useContext(PageTitleSuffix);
  const setChrome = useContext(PageChromeSetter);
  useEffect(() => {
    if (typeof title === "string") {
      document.title = `${title} · ${suffix}`;
    }
  }, [title, suffix]);
  const backTo = back?.to;
  const backLabel = back?.label;
  useEffect(() => {
    setChrome({
      title: typeof title === "string" ? title : "",
      back: backTo && backLabel ? { to: backTo, label: backLabel } : undefined,
    });
    return () => setChrome(null);
  }, [setChrome, title, backTo, backLabel]);
  return (
    <header className={styles.header}>
      <div className={styles.headings}>
        {back ? (
          <Link to={back.to} className={styles.back}>
            <Icon name="esquerda" size={14} />
            {back.label}
          </Link>
        ) : null}
        <div className={styles.titleRow}>
          <h1 className={styles.title}>{title}</h1>
          {badge}
        </div>
        {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
      </div>
      {/* Numa tela de detalhe (com "voltar"), as ações ficam na linha do subtítulo, como no desenho. */}
      {actions ? <div className={back ? `${styles.actions} ${styles.atBase}` : styles.actions}>{actions}</div> : null}
    </header>
  );
}
