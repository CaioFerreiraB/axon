/** A barra inferior do celular (013 FR-047, R38): as quatro seções primárias e "Mais", que abre a folha com as outras,
 * o tema e a sessão. "Mais" fica marcado numa seção secundária. */

import { useState } from "react";
import { NavLink, useLocation } from "react-router";

import { NAV_PRIMARY, NAV_SECONDARY } from "../i18n/pt-BR";
import { Icon } from "../ui/icons";
import styles from "./BottomNav.module.css";
import { MoreSheet } from "./MoreSheet";

export function BottomNav() {
  const { pathname } = useLocation();
  const [more, setMore] = useState(false);
  const inSecondary = NAV_SECONDARY.some((item) => pathname === item.to || pathname.startsWith(`${item.to}/`));
  return (
    <>
      <nav className={styles.bar} aria-label="Seções">
        {NAV_PRIMARY.map((item) => (
          <NavLink key={item.to} to={item.to} className={styles.item}>
            <span className={styles.pill}>
              <Icon name={item.icon} size={20} />
            </span>
            <span className={styles.label}>{item.label}</span>
          </NavLink>
        ))}
        <button
          type="button"
          className={styles.item}
          aria-haspopup="dialog"
          aria-expanded={more}
          data-active={inSecondary || undefined}
          onClick={() => setMore(true)}
        >
          <span className={styles.pill}>
            <Icon name="mais_acoes" size={20} />
          </span>
          <span className={styles.label}>Mais</span>
        </button>
      </nav>
      <MoreSheet open={more} onOpenChange={setMore} />
    </>
  );
}
