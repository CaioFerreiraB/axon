import type { ReactNode } from "react";

import styles from "./Badge.module.css";
import { Icon, type IconName } from "./icons";

export type Tone = "ok" | "bad" | "warn" | "accent" | "neutral";

export function Badge({
  tone = "neutral",
  dot = false,
  icon,
  children,
  title,
}: {
  tone?: Tone;
  dot?: boolean;
  icon?: IconName;
  children: ReactNode;
  title?: string;
}) {
  return (
    <span className={`${styles.badge} ${styles[tone]}`} title={title}>
      {dot ? <span className={styles.dot} aria-hidden="true" /> : null}
      {icon ? <Icon name={icon} size={12} /> : null}
      {children}
    </span>
  );
}

/** "Definido na instalação": o campo vem de variável de ambiente e só é lido (ADR-033). */
export function InstallationBadge() {
  return (
    <Badge tone="neutral" icon="cadeado">
      Definido na instalação
    </Badge>
  );
}
