/** A barra lateral de 240 px do desenho: a marca (FR-020, ADR-038) — Axon, ou a da instalação com "com Axon" no rodapé —,
 * navegação, tema (FR-019) e quem está na sessão, com "Sair". */

import { NavLink } from "react-router";

import { useMe } from "../api/hooks/me";
import { useAuth } from "../auth/AuthProvider";
import { initials } from "../i18n/format";
import { NAV } from "../i18n/pt-BR";
import { Button } from "../ui/Button";
import { Icon } from "../ui/icons";
import { Segmented } from "../ui/Segmented";
import { AxonSymbol, AxonWordmark } from "./brand/Mark";
import styles from "./Sidebar.module.css";
import { useTheme, type ThemeChoice } from "./theme";

const THEMES = [
  { value: "light", label: "Tema claro", icon: "sol" },
  { value: "dark", label: "Tema escuro", icon: "lua" },
  { value: "system", label: "Seguir o sistema", icon: "atualizar" },
] as const;

export function Brand({ name, logoUrl }: { name: string; logoUrl: string | null }) {
  return logoUrl ? (
    <img className={styles.logoImage} src={logoUrl} alt="" />
  ) : (
    <span className={styles.logo} aria-hidden="true">
      {initials(name).charAt(0)}
    </span>
  );
}

export function Sidebar() {
  const me = useMe().data;
  const { signOut } = useAuth();
  const [theme, setTheme] = useTheme();
  const instance = me?.instance ?? { name: "Axon", logo_url: null, custom: false };
  const admin = me?.groups.includes("admin") ? "admin" : (me?.groups[0] ?? "");
  return (
    <aside className={styles.sidebar} aria-label="Navegação da console">
      {instance.custom ? (
        <div className={styles.brand}>
          <Brand name={instance.name} logoUrl={instance.logo_url} />
          <div className={styles.brandText}>
            <span className={styles.name}>{instance.name}</span>
            <span className={styles.product}>Console</span>
          </div>
        </div>
      ) : (
        <div className={styles.brand}>
          <AxonSymbol size={32} />
          <div className={styles.brandText}>
            <AxonWordmark height={13} />
            <span className={styles.product}>Console</span>
          </div>
        </div>
      )}
      <nav className={styles.nav} aria-label="Seções">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={styles.item}
            title={item.label}
            end={item.to === "/uso" ? false : undefined}
          >
            <Icon name={item.icon} />
            <span className={styles.label}>{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className={styles.footer}>
        <div className={styles.themeRow}>
          <span className={styles.themeLabel} id="tema-rotulo">
            Tema
          </span>
          <Segmented<ThemeChoice>
            label="Tema"
            value={theme}
            onChange={setTheme}
            options={THEMES}
            className={styles.themeGroup}
          />
        </div>
        {me ? (
          <div className={styles.user}>
            <span className={styles.avatar} aria-hidden="true">
              {initials(me.name)}
            </span>
            <div className={styles.userText}>
              <span className={styles.userName}>{me.name}</span>
              <span className={styles.userMeta}>{[me.username, admin].filter(Boolean).join(" · ")}</span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              icon="sair"
              aria-label="Sair"
              title="Sair"
              onClick={() => void signOut()}
            />
          </div>
        ) : null}
        {instance.custom ? (
          <p className={styles.attribution}>
            <AxonSymbol size={16} />
            <span className={styles.attributionText}>com Axon</span>
          </p>
        ) : null}
      </div>
    </aside>
  );
}
