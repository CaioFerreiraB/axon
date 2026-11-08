/** A folha "Mais" do celular (013 FR-047, R38): as seções que não cabem na barra inferior, "Instalar app" quando o
 * navegador oferece, o tema (FR-019), a pessoa com "Sair" e, com marca da instalação, "com Axon" (FR-020). */

import { NavLink } from "react-router";

import { useMe } from "../api/hooks/me";
import { useAuth } from "../auth/AuthProvider";
import { initials } from "../i18n/format";
import { NAV_SECONDARY } from "../i18n/pt-BR";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";
import { Segmented } from "../ui/Segmented";
import { Sheet } from "../ui/Sheet";
import { AxonSymbol } from "./brand/Mark";
import styles from "./MoreSheet.module.css";
import { useInstallPrompt } from "./pwa/useInstallPrompt";
import { adminLabel, THEMES } from "./Sidebar";
import { useTheme, type ThemeChoice } from "./theme";

export function MoreSheet({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const me = useMe().data;
  const { signOut } = useAuth();
  const [theme, setTheme] = useTheme();
  const { install } = useInstallPrompt();
  const close = () => onOpenChange(false);
  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Mais">
      <nav aria-label="Mais seções" className={styles.list}>
        {NAV_SECONDARY.map((item) => (
          <NavLink key={item.to} to={item.to} className={styles.item} onClick={close}>
            <Icon name={item.icon} size={20} />
            <span className={styles.itemText}>{item.label}</span>
            <Icon name="direita" size={16} className={styles.chevron} />
          </NavLink>
        ))}
        {install ? (
          <button
            type="button"
            className={styles.item}
            onClick={() => {
              close();
              void install();
            }}
          >
            <Icon name="instalar" size={20} />
            <span className={styles.itemText}>
              Instalar app
              <span className={styles.itemHelp}>Abrir a console em janela própria</span>
            </span>
          </button>
        ) : null}
      </nav>
      <div className={styles.divider} />
      <div className={styles.row}>
        <span className={styles.rowLabel}>Tema</span>
        <Segmented<ThemeChoice> label="Tema" value={theme} onChange={setTheme} options={THEMES} />
      </div>
      {me ? (
        <>
          <div className={styles.divider} />
          <div className={styles.person}>
            <span className={styles.avatar} aria-hidden="true">
              {initials(me.name)}
            </span>
            <span className={styles.personText}>
              <span className={styles.personName}>{me.name}</span>
              <span className={styles.personMeta}>
                {[me.username, adminLabel(me.groups)].filter(Boolean).join(" · ")}
              </span>
            </span>
            <Button variant="secondary" icon="sair" onClick={() => void signOut()}>
              Sair
            </Button>
          </div>
        </>
      ) : null}
      {me?.instance.custom ? (
        <p className={styles.attribution}>
          <AxonSymbol size={16} />
          com Axon
        </p>
      ) : null}
    </Sheet>
  );
}
