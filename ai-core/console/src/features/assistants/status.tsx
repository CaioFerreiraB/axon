/** O estado de um Assistant como a API o descreve (003): disponível, indisponível com motivos, sobreposição ativa ou
 * inativa, seção travada. A console só mostra — não decide (013 FR-001). */

import type { AssistantView, OverrideView, Section } from "../../api/schemas";
import { STATE_TEXT } from "../../i18n/pt-BR";
import { Badge } from "../../ui/Badge";

export function overrideOf(view: AssistantView, section: Section): OverrideView | undefined {
  return view.overrides.find((override) => override.section === section);
}

/** O motivo da API como frase: maiúscula no começo e ponto no fim. */
export function sentence(text: string): string {
  const trimmed = text.trim();
  if (!trimmed) {
    return trimmed;
  }
  const capital = trimmed.charAt(0).toUpperCase() + trimmed.slice(1);
  return /[.!?]$/.test(capital) ? capital : `${capital}.`;
}

export function who(subject: string): string {
  return subject.split(":").pop() ?? subject;
}

export type Health = "available" | "unavailable" | "inactive";

export function healthOf(view: AssistantView): Health {
  if (!view.status.available) {
    return "unavailable";
  }
  return view.overrides.some((override) => override.state === "inactive") ? "inactive" : "available";
}

export function StatusBadge({ view }: { view: AssistantView }) {
  const health = healthOf(view);
  if (health === "unavailable") {
    return (
      <Badge tone="bad" dot>
        {STATE_TEXT.unavailable}
      </Badge>
    );
  }
  if (health === "inactive") {
    return (
      <Badge tone="warn" dot>
        {STATE_TEXT.inactive}
      </Badge>
    );
  }
  return (
    <Badge tone="ok" dot>
      {STATE_TEXT.available}
    </Badge>
  );
}

/** O motivo curto ao lado do estado: o primeiro motivo da API ou o da sobreposição inativa. */
export function statusReason(view: AssistantView): string | null {
  if (!view.status.available) {
    return view.status.reasons[0] ?? null;
  }
  return view.overrides.find((override) => override.state === "inactive")?.reason ?? null;
}
