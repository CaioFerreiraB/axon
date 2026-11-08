/** Abas que são rotas (`/assistentes/:nome/modelos`, `/acesso/usuarios`): links com `aria-current`. */

import { useEffect, useRef } from "react";
import { NavLink, useLocation } from "react-router";

import styles from "./TabNav.module.css";

export function TabNav({ label, tabs }: { label: string; tabs: readonly { to: string; label: string }[] }) {
  const nav = useRef<HTMLElement>(null);
  const { pathname } = useLocation();
  // No celular as abas rolam de lado (013 FR-050): a ativa fica à vista, sem mexer na rolagem da página.
  useEffect(() => {
    const element = nav.current;
    const active = element?.querySelector<HTMLElement>('[aria-current="page"]');
    if (element && active && element.scrollWidth > element.clientWidth) {
      element.scrollLeft = active.offsetLeft - (element.clientWidth - active.offsetWidth) / 2;
    }
  }, [pathname]);
  return (
    <nav ref={nav} aria-label={label} className={styles.tabs}>
      {tabs.map((tab) => (
        <NavLink key={tab.to} to={tab.to} replace className={styles.tab} end>
          {tab.label}
        </NavLink>
      ))}
    </nav>
  );
}
