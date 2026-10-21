/** Aba Histórico (013 FR-005; 003 FR-021): sobreposições gravadas e descartadas, com autor, data e versão. */

import { useHistory } from "../../api/hooks/assistants";
import { isAuthPayload, isMcpPayload, type HistoryEntry } from "../../api/schemas";
import { formatInstant } from "../../i18n/format";
import { SECTION_TEXT } from "../../i18n/pt-BR";
import { Badge } from "../../ui/Badge";
import { Panel } from "../../ui/Panel";
import { EmptyState, LoadError, Skeleton } from "../../ui/States";
import { Table, tableStyles as t } from "../../ui/Table";
import { useAssistantContext } from "./AssistantDetail";
import { authSummary, who } from "./status";

function content(entry: HistoryEntry): string {
  if (entry.payload === null) {
    return "—";
  }
  if (isAuthPayload(entry.payload)) {
    return authSummary(entry.payload);
  }
  if (isMcpPayload(entry.payload)) {
    const tools = entry.payload.allowed.length;
    return `${entry.payload.aliases.join(", ") || "nenhum servidor"} · ${tools} ${tools === 1 ? "tool" : "tools"}`;
  }
  return Object.entries(entry.payload)
    .map(([role, ref]) => `${role} = ${ref}`)
    .join(" · ");
}

export default function HistoryTab() {
  const { view } = useAssistantContext();
  const history = useHistory(view.name);
  if (history.isError) {
    return <LoadError what="o histórico" error={history.error} onRetry={() => void history.refetch()} />;
  }
  if (history.isPending) {
    return <Skeleton height={160} style={{ borderRadius: 8 }} />;
  }
  if (history.data.length === 0) {
    return (
      <Panel>
        <EmptyState title="Nenhuma sobreposição gravada">
          Cada vez que alguém salva ou descarta uma sobreposição de {view.name}, ela aparece aqui com autor, data e
          versão.
        </EmptyState>
      </Panel>
    );
  }
  const entries = [...history.data].sort((a, b) => b.at.localeCompare(a.at));
  return (
    <Table caption={`Histórico de sobreposições de ${view.name}`}>
      <thead>
        <tr>
          <th scope="col">Quando</th>
          <th scope="col">Seção</th>
          <th scope="col">Ação</th>
          <th scope="col">Conteúdo</th>
          <th scope="col">Por</th>
          <th scope="col" className={t.num}>
            Versão
          </th>
        </tr>
      </thead>
      <tbody>
        {entries.map((entry) => (
          <tr key={`${entry.section}-${entry.version}-${entry.at}`}>
            <td style={{ whiteSpace: "nowrap" }}>{formatInstant(entry.at)}</td>
            <td>{SECTION_TEXT[entry.section]}</td>
            <td>{entry.action === "saved" ? <Badge tone="accent">Gravada</Badge> : <Badge>Descartada</Badge>}</td>
            <td className={t.mono}>{content(entry)}</td>
            <td style={{ color: "var(--texto-secundario)" }}>{who(entry.actor)}</td>
            <td className={t.num}>{entry.version}</td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
