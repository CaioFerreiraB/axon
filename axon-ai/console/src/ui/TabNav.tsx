/** Abas que são rotas (`/assistentes/:nome/modelos`, `/acesso/usuarios`): links com `aria-current`. */

import { NavLink } from "react-router";

import styles from "./TabNav.module.css";

export function TabNav({ label, tabs }: { label: string; tabs: readonly { to: string; label: string }[] }) {
  return (
    <nav aria-label={label} className={styles.tabs}>
      {tabs.map((tab) => (
        <NavLink key={tab.to} to={tab.to} replace className={styles.tab} end>
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
