/** "Sua conta não tem acesso à console" (013 FR-003): sem barra lateral e sem dado administrativo (SC-007) — só o
 * que o próprio token diz de quem entrou. */

import { useAuth } from "../auth/AuthProvider";
import { Button } from "../ui/Button";
import styles from "./AccessDenied.module.css";
import { Brand } from "./Sidebar";

export function AccessDenied() {
  const { user, signOut } = useAuth();
  const profile = user.profile;
  const who = String(profile.preferred_username ?? profile.name ?? "você");
  const email = typeof profile.email === "string" ? ` (${profile.email})` : "";
  return (
    <div className={styles.screen}>
      <main className={styles.card}>
        <div className={styles.brand}>
          <Brand name="Agentic" logoUrl={null} />
          Agentic
        </div>
        <h1 className={styles.title}>Sua conta não tem acesso à console</h1>
        <p className={styles.text}>
          Você entrou como {who}
          {email}, que não está no grupo de administração. O chat continua disponível; para administrar a plataforma,
          peça a um admin para incluir você no grupo.
        </p>
        <div className={styles.actions}>
          <Button variant="primary" icon="sair" onClick={() => void signOut()}>
            Sair
          </Button>
          <Button variant="ghost" onClick={() => void signOut()}>
            Entrar com outra conta
          </Button>
        </div>
      </main>
    </div>
  );
}
