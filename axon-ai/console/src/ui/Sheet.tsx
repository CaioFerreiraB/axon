/** A folha que sobe de baixo no celular (013 FR-047, FR-049; R40): a base do "Mais". O `Dialog` usa os mesmos estilos
 * abaixo de 640px. Radix prende o foco, fecha com Esc e pelo véu, e devolve o foco a quem abriu. */

import * as RadixDialog from "@radix-ui/react-dialog";
import { useRef, type ReactNode } from "react";

import styles from "./Sheet.module.css";

export function Sheet({
  open,
  onOpenChange,
  title,
  children,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  children: ReactNode;
}) {
  // Quem abriu a folha (o "Mais") recebe o foco de volta ao fechar, como no Dialog.
  const origin = useRef<HTMLElement | null>(null);
  return (
    <RadixDialog.Root open={open} onOpenChange={onOpenChange}>
      <RadixDialog.Portal>
        <RadixDialog.Overlay className={styles.overlay} />
        <RadixDialog.Content
          className={styles.sheet}
          aria-describedby={undefined}
          onOpenAutoFocus={() => {
            origin.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
          }}
          onCloseAutoFocus={(event) => {
            if (origin.current?.isConnected) {
              event.preventDefault();
              origin.current.focus();
            }
          }}
        >
          <span className={styles.handle} aria-hidden="true" />
          <RadixDialog.Title className={styles.title}>{title}</RadixDialog.Title>
          {children}
        </RadixDialog.Content>
      </RadixDialog.Portal>
    </RadixDialog.Root>
  );
}
