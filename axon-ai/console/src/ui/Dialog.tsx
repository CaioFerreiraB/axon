/** O modal da console, só para segredo mostrado uma vez — a senha temporária (013 R7) e a chave de API (R23) —, que
 * pede foco protegido. Radix prende o foco e o devolve a quem abriu (FR-017). */

import * as RadixDialog from "@radix-ui/react-dialog";
import { useRef, type ReactNode } from "react";

import { Button } from "./Button";
import styles from "./Dialog.module.css";

export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  footer,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: ReactNode;
  description?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
}) {
  // Quem tinha o foco ao abrir recebe-o de volta ao fechar — inclusive quando o diálogo abre por mudança de rota.
  const origin = useRef<HTMLElement | null>(null);
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={styles.overlay} />
        <RadixDialog.Content
          className={styles.content}
          onOpenAutoFocus={(event) => {
            origin.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
            const field = (event.currentTarget as HTMLElement | null)?.querySelector<HTMLElement>(
              "input, select, textarea",
            );
            if (field) {
              event.preventDefault();
              field.focus();
            }
          }}
          onCloseAutoFocus={(event) => {
            if (origin.current?.isConnected) {
              event.preventDefault();
              origin.current.focus();
            }
          }}
        >
          <div className={styles.header}>
            <RadixDialog.Title className={styles.title}>{title}</RadixDialog.Title>
            <RadixDialog.Close asChild>
              <Button variant="ghost" size="sm" icon="fechar" aria-label="Fechar" className={styles.close} />
            </RadixDialog.Close>
          </div>
          {description ? (
            <RadixDialog.Description className={styles.description}>{description}</RadixDialog.Description>
          ) : (
            <RadixDialog.Description className="visually-hidden">{title}</RadixDialog.Description>
          )}
          {children}
          {footer ? <div className={styles.footer}>{footer}</div> : null}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
