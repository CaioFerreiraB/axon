/** Peças comuns às abas que editam sobreposições: rodapé com autor e versão, confirmação de descarte na própria tela
 * (013 FR-009) e o aviso de conflito de versão com o rascunho preservado (FR-008). */

import { useState, type ReactNode } from "react";

import { isApiError } from "../../api/errors";
import { isAuthPayload, isMcpPayload, type OverrideView } from "../../api/schemas";
import { formatInstant, formatInstantDay } from "../../i18n/format";
import { Button } from "../../ui/Button";
import { Notice } from "../../ui/Notice";
import styles from "./Editor.module.css";
import { authSummary, who } from "./status";

export function changesText(count: number): string {
  return count === 0 ? "" : count === 1 ? "1 alteração não salva" : `${count} alterações não salvas`;
}

export function overrideMeta(override: OverrideView | undefined, none: string, changes: number): string {
  const pending = changesText(changes);
  if (!override) {
    return [none, pending].filter(Boolean).join(" · ");
  }
  const stored = override.payload
    ? isAuthPayload(override.payload)
      ? authSummary(override.payload)
      : isMcpPayload(override.payload)
        ? override.payload.aliases.join(", ") || "nenhum servidor"
        : Object.entries(override.payload)
            .map(([role, ref]) => `${role} = ${ref}`)
            .join(", ")
    : null;
  const base =
    override.state === "inactive"
      ? `Guardada: ${stored ? `${stored}, ` : ""}por ${who(override.updated_by)} em ${formatInstantDay(override.updated_at)} · versão ${override.version}`
      : `Sobreposto por ${who(override.updated_by)} em ${formatInstant(override.updated_at)} · versão ${override.version}`;
  return [base, pending].filter(Boolean).join(" · ");
}

export function DiscardButton({
  override,
  onConfirm,
  busy,
}: {
  override: OverrideView;
  onConfirm: () => void;
  busy: boolean;
}) {
  const [asking, setAsking] = useState(false);
  const label = override.state === "inactive" ? "Apagar sobreposição guardada" : "Descartar sobreposição";
  if (!asking) {
    return (
      <Button variant="ghost" onClick={() => setAsking(true)}>
        {label}
      </Button>
    );
  }
  return (
    <span className={styles.confirm} role="group" aria-label="Confirmar o descarte">
      O Assistant volta ao YAML.
      <Button variant="ghost" size="sm" onClick={() => setAsking(false)} autoFocus>
        Cancelar
      </Button>
      <Button variant="danger" size="sm" busy={busy} onClick={onConfirm}>
        {override.state === "inactive" ? "Apagar" : "Descartar"}
      </Button>
    </span>
  );
}

/** Erro de gravação que não tem campo: conflito de versão (com "Recarregar") ou o motivo da API. */
export function SaveError({ error, onReload }: { error: unknown; onReload: () => void }): ReactNode {
  if (!error) {
    return null;
  }
  if (isApiError(error) && error.isVersionConflict) {
    return (
      <Notice
        tone="warn"
        title="Outra pessoa salvou antes"
        action={{ label: "Recarregar e manter meu rascunho", onClick: onReload }}
        role="alert"
      >
        A sobreposição mudou desde que você abriu a tela (versão {error.currentVersion ?? "nova"}). Seu rascunho
        continua aqui; recarregue para ver o que mudou e salve de novo.
      </Notice>
    );
  }
  const message = isApiError(error) ? error.message : "A gravação falhou. Nada foi alterado.";
  return (
    <Notice tone="bad" title="Não foi possível salvar" role="alert">
      {message}
    </Notice>
  );
}
