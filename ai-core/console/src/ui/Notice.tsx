import type { ReactNode } from "react";
import { Link } from "react-router";

import { Icon, type IconName } from "./icons";
import styles from "./Notice.module.css";

type Tone = "info" | "warn" | "bad" | "ok" | "neutral";

const ICONS: Record<Tone, IconName> = {
  info: "info",
  warn: "alerta",
  bad: "alerta",
  ok: "confere",
  neutral: "cadeado",
};

type Action = { label: string; onClick: () => void } | { label: string; to: string };

export function Notice({
  tone = "info",
  title,
  children,
  action,
  icon,
  role,
}: {
  tone?: Tone;
  title: ReactNode;
  children?: ReactNode;
  action?: Action;
  icon?: IconName;
  role?: "alert" | "status";
}) {
  return (
    <div className={`${styles.notice} ${styles[tone]}`} role={role}>
      <Icon name={icon ?? ICONS[tone]} className={styles.icon} />
      <div className={styles.body}>
        <p className={styles.title}>{title}</p>
        {children ? <div className={styles.text}>{children}</div> : null}
        {action ? (
          "to" in action ? (
            <Link to={action.to} className={styles.action}>
              {action.label}
              <Icon name="direita" size={14} />
            </Link>
          ) : (
            <button type="button" onClick={action.onClick} className={styles.action}>
              {action.label}
              <Icon name="direita" size={14} />
            </button>
          )
        ) : null}
      </div>
    </div>
  );
}
