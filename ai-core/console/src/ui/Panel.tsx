import type { ReactNode } from "react";

import styles from "./Panel.module.css";

export function Panel({
  title,
  subtitle,
  aside,
  children,
  className,
  labelledBy,
}: {
  title?: ReactNode;
  subtitle?: ReactNode;
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  labelledBy?: string;
}) {
  return (
    <section className={[styles.panel, className].filter(Boolean).join(" ")} aria-labelledby={labelledBy}>
      {title || aside ? (
        <header className={styles.header}>
          <div>
            {title ? (
              <h2 className={styles.title} id={labelledBy}>
                {title}
              </h2>
            ) : null}
            {subtitle ? <p className={styles.subtitle}>{subtitle}</p> : null}
          </div>
          {aside}
        </header>
      ) : null}
      <div className={styles.body}>{children}</div>
    </section>
  );
}

export const panelStyles = styles;
