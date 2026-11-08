/** O cabeçalho de app do celular (013 FR-046, R38): a marca compacta — o símbolo Axon, ou o logotipo ou a inicial da
 * instalação — e o título da tela; numa tela de detalhe, o "voltar" no lugar da marca. O título é o do `PageHeader`,
 * cujo `h1` continua no conteúdo para o leitor de tela; aqui ele é só visual. */

import { Link } from "react-router";

import { useMe } from "../api/hooks/me";
import { Icon } from "../ui/icons";
import type { PageChrome } from "../ui/Page";
import styles from "./AppBar.module.css";
import { AxonSymbol } from "./brand/Mark";
import { Brand } from "./Sidebar";

export function AppBar({ chrome }: { chrome: PageChrome | null }) {
  const instance = useMe().data?.instance;
  return (
    <header className={styles.bar}>
      {chrome?.back ? (
        <Link to={chrome.back.to} className={styles.back} aria-label={`Voltar para ${chrome.back.label}`}>
          <Icon name="esquerda" size={22} />
        </Link>
      ) : instance?.custom ? (
        <span className={styles.mark}>
          <Brand name={instance.name} logoUrl={instance.logo_url} />
        </span>
      ) : (
        <span className={styles.mark}>
          <AxonSymbol size={26} />
        </span>
      )}
      <span className={styles.title} aria-hidden="true">
        {chrome?.title ?? ""}
      </span>
    </header>
  );
}
