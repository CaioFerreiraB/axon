import type { Scope } from "../../api/schemas";
import { SCOPE_TEXT } from "../../i18n/pt-BR";
import styles from "./Access.module.css";

/** Os escopos da chave em português; a administração diz que só se concede pela linha de comando (013 R31). */
export function ScopeList({ scopes }: { scopes: Scope[] }) {
  const ordered = (["inference", "users", "admin"] as const).filter((scope) => scopes.includes(scope));
  return (
    <ul className={styles.scopeList}>
      {ordered.map((scope) => (
        <li key={scope}>
          {SCOPE_TEXT[scope]}
          {scope === "admin" ? <span className={styles.scopeNote}> — só pela linha de comando</span> : null}
        </li>
      ))}
    </ul>
  );
}
