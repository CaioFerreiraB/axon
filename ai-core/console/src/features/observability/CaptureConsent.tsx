import { useId, useState } from "react";

import { Button } from "../../ui/Button";
import { Checkbox } from "../../ui/Checkbox";
import { Icon } from "../../ui/icons";
import styles from "./ObservabilityPage.module.css";

/** Ligar a captura de texto exige ler e confirmar o aviso de privacidade na própria tela (013 FR-012; 009 US7). */
export function CaptureConsent({
  busy,
  onCancel,
  onConfirm,
}: {
  busy: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const [read, setRead] = useState(false);
  const titleId = useId();
  return (
    <div className={styles.consent} role="group" aria-labelledby={titleId}>
      <Icon name="alerta" />
      <div className={styles.consentBody}>
        <p className={styles.consentTitle} id={titleId}>
          O texto pode conter dados pessoais
        </p>
        <p className={styles.consentText}>
          Perguntas e respostas de quem usa o chat passam a ser guardadas no Langfuse. A plataforma apaga credenciais do
          texto, mas não apaga nomes, documentos ou outros dados pessoais. Ligue só se a sua política de dados permitir.
        </p>
        <div className={styles.consentActions}>
          <Checkbox
            label="Li e quero capturar o texto"
            checked={read}
            onChange={(event) => setRead(event.target.checked)}
          />
          <span className={styles.spacer} />
          <Button variant="ghost" onClick={onCancel}>
            Cancelar
          </Button>
          <Button variant="primary" disabled={!read} busy={busy} onClick={onConfirm}>
            Ligar captura
          </Button>
        </div>
      </div>
    </div>
  );
}
