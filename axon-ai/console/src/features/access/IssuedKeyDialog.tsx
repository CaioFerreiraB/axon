/** A chave em claro, mostrada uma única vez — na criação ou na rotação (013 US9, FR-025; ADR-040). Como a senha
 * temporária, é o caso de modal: foco protegido para um segredo que some ao fechar (013 R7, R23). */

import { useState } from "react";

import type { IssuedKey } from "../../api/schemas";
import { formatInstant } from "../../i18n/format";
import { Button } from "../../ui/Button";
import { Dialog } from "../../ui/Dialog";
import { Field, fieldStyles } from "../../ui/Field";
import styles from "./Access.module.css";

export function IssuedKeyDialog({
  issued,
  rotated,
  onClose,
}: {
  issued: IssuedKey | null;
  rotated: boolean;
  onClose: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const close = () => {
    setCopied(false);
    onClose();
  };
  return (
    <Dialog
      open={issued !== null}
      onOpenChange={(next) => (next ? undefined : close())}
      title={issued ? `${rotated ? "Segredo novo para" : "Chave criada para"} ${issued.subject}` : ""}
      description={
        rotated
          ? "Copie a chave agora: ela não aparece de novo. A anterior já não vale; troque-a no sistema."
          : "Copie a chave agora: ela não aparece de novo. Se ela se perder, rotacione o segredo."
      }
    >
      {issued ? (
        <>
          <div className={styles.secretRow}>
            <div className={styles.grow}>
              <Field label="Chave de API">
                {/* A chave inteira à vista, quebrada em linhas: o começo (axn_<identificador>) é o que a reconhece. */}
                <textarea
                  readOnly
                  rows={2}
                  value={issued.key}
                  spellCheck={false}
                  className={[fieldStyles.control, fieldStyles.mono, styles.secretKey].join(" ")}
                />
              </Field>
            </div>
            <Button
              icon={copied ? "confere" : "copiar"}
              onClick={() => {
                void navigator.clipboard?.writeText(issued.key).then(() => setCopied(true));
              }}
            >
              {copied ? "Copiada" : "Copiar"}
            </Button>
          </div>
          <dl className={styles.facts}>
            <dt>Sistema</dt>
            <dd className="mono">{issued.subject}</dd>
            <dt>Rótulo</dt>
            <dd>{issued.label ?? "—"}</dd>
            <dt>Identificador</dt>
            <dd className="mono">{issued.key_id}</dd>
            {issued.rotated_at ? (
              <>
                <dt>Rotacionada</dt>
                <dd>{formatInstant(issued.rotated_at)}</dd>
              </>
            ) : null}
          </dl>
          <div style={{ display: "flex", justifyContent: "flex-end", gap: 8, marginTop: 20 }}>
            <Button variant="primary" onClick={close}>
              Concluir
            </Button>
          </div>
        </>
      ) : null}
    </Dialog>
  );
}
