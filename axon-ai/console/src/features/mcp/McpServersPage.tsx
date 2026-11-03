/** Servidores MCP globais (013 US7, FR-014): origem, estado, motivo e tools. Os do arquivo do operador só mudam por
 * deploy; nenhum valor de credencial aparece. */

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router";

import { useAssistants } from "../../api/hooks/assistants";
import { useDeleteMcp, useMcpHealths, useMcpServers } from "../../api/hooks/mcp";
import type { McpHealth, McpServer } from "../../api/schemas";
import { mcpReason } from "../../i18n/pt-BR";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { TextInput } from "../../ui/Field";
import { Icon } from "../../ui/icons";
import { Notice } from "../../ui/Notice";
import { Page, PageHeader } from "../../ui/Page";
import { Panel } from "../../ui/Panel";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, LoadError, Skeleton } from "../../ui/States";
import { Table, tableStyles as t } from "../../ui/Table";
import { McpServerDetails, McpServerForm } from "./McpServerForm";
import styles from "./McpServersPage.module.css";

const FILTERS = [
  { value: "todos", label: "Todos" },
  { value: "api", label: "API" },
  { value: "arquivo", label: "Arquivo do operador" },
] as const;
type Filter = (typeof FILTERS)[number]["value"];

function RowMenu({ alias, onEdit, onDelete }: { alias: string; onEdit: () => void; onDelete: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) {
      return;
    }
    const close = (event: MouseEvent) => {
      if (!ref.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, [open]);
  return (
    <div className={styles.menu} ref={ref} onKeyDown={(event) => event.key === "Escape" && setOpen(false)}>
      <Button
        variant="ghost"
        size="sm"
        icon="mais_acoes"
        aria-label={`Ações de ${alias}`}
        aria-expanded={open}
        aria-haspopup="true"
        onClick={() => setOpen((value) => !value)}
      />
      {open ? (
        <div className={styles.menuList}>
          <button type="button" className={styles.menuItem} autoFocus onClick={() => (setOpen(false), onEdit())}>
            Editar
          </button>
          <button
            type="button"
            className={`${styles.menuItem} ${styles.danger}`}
            onClick={() => (setOpen(false), onDelete())}
          >
            Remover
          </button>
        </div>
      ) : null}
    </div>
  );
}

/** Um endereço que quebra só depois de "/" ou ".", nunca no meio de um nome (a cópia do texto não muda). */
function breakable(text: string) {
  return text.split(/(?<=[/.])/).flatMap((part, index) => (index ? [<wbr key={index} />, part] : [part]));
}

function stateOf(server: McpServer, health: McpHealth | undefined): { ok: boolean; reason: string | null } {
  if (!server.available) {
    return { ok: false, reason: server.reason };
  }
  if (health && !health.ok) {
    return { ok: false, reason: health.detail };
  }
  return { ok: true, reason: null };
}

export default function McpServersPage() {
  const [params, setParams] = useSearchParams();
  const query = (params.get("q") ?? "").toLowerCase();
  const filter = (FILTERS.find((f) => f.value === params.get("filtro"))?.value ?? "todos") as Filter;
  const servers = useMcpServers();
  const globals = (servers.data ?? []).filter((server) => server.scope === "global");
  const healths = useMcpHealths(globals);
  const assistants = useAssistants();
  const remove = useDeleteMcp();
  const [editing, setEditing] = useState<McpServer | "novo" | null>(null);
  const [viewing, setViewing] = useState<McpServer | null>(null);
  const [removing, setRemoving] = useState<string | null>(null);
  const set = (key: string, value: string, fallback: string) => {
    const next = new URLSearchParams(params);
    if (value === fallback) {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setParams(next, { replace: true });
  };
  const usedBy = (alias: string) =>
    (assistants.data ?? []).filter((view) => view.effective.mcp.aliases.includes(alias)).map((view) => view.name);
  const shown = globals
    .map((server, index) => ({ server, health: healths[index]?.data }))
    .filter(({ server }) =>
      filter === "api" ? server.origin === "registry" : filter === "arquivo" ? server.origin === "file" : true,
    )
    .filter(({ server }) => !query || `${server.alias} ${server.description ?? ""}`.toLowerCase().includes(query));

  return (
    <Page>
      <PageHeader
        title="Servidores MCP"
        subtitle="Servidores globais. Os do arquivo do operador (mcp.yaml) só mudam por novo deploy."
        actions={
          <Button variant="primary" icon="mais" disabled={editing !== null} onClick={() => setEditing("novo")}>
            Novo servidor
          </Button>
        }
      />
      {editing ? (
        <McpServerForm server={editing === "novo" ? undefined : editing} onDone={() => setEditing(null)} />
      ) : null}
      {viewing ? <McpServerDetails server={viewing} onClose={() => setViewing(null)} /> : null}
      {removing ? (
        <Notice tone="warn" title={`Remover o servidor ${removing}?`} role="alert">
          <span className={styles.confirm}>
            Assistants que o usam ficam indisponíveis até alguém trocar a configuração.
            <Button variant="ghost" size="sm" onClick={() => setRemoving(null)} autoFocus>
              Cancelar
            </Button>
            <Button
              variant="danger"
              size="sm"
              busy={remove.isPending}
              onClick={() => remove.mutate(removing, { onSuccess: () => setRemoving(null) })}
            >
              Remover
            </Button>
          </span>
          {remove.error instanceof Error ? <p>{remove.error.message}</p> : null}
        </Notice>
      ) : null}
      <div className={styles.toolbar}>
        <div className={styles.search}>
          <Icon name="busca" className={styles.searchIcon} />
          <TextInput
            type="search"
            className={styles.searchInput}
            placeholder="Buscar servidor"
            aria-label="Buscar servidor"
            value={params.get("q") ?? ""}
            onChange={(event) => set("q", event.target.value, "")}
          />
        </div>
        <Segmented<Filter>
          label="Origem"
          value={filter}
          onChange={(value) => set("filtro", value, "todos")}
          options={FILTERS}
        />
      </div>
      {servers.isError ? (
        <LoadError what="os servidores MCP" error={servers.error} onRetry={() => void servers.refetch()} />
      ) : servers.isPending ? (
        <Skeleton height={220} style={{ borderRadius: 8 }} />
      ) : globals.length === 0 ? (
        <Panel>
          <EmptyState
            title="Nenhum servidor MCP global"
            action={
              <Button icon="mais" onClick={() => setEditing("novo")}>
                Novo servidor
              </Button>
            }
          >
            Servidores cadastrados aqui ou no mcp.yaml da instalação podem ser ligados aos Assistants.
          </EmptyState>
        </Panel>
      ) : (
        <Table caption="Servidores MCP globais">
          <thead>
            <tr>
              <th scope="col">Servidor</th>
              <th scope="col" className={styles.originColumn}>
                Origem
              </th>
              <th scope="col" className={t.wideOnly}>
                Transporte
              </th>
              <th scope="col" className={t.wideOnly}>
                Endereço
              </th>
              <th scope="col" className={`${t.num} ${t.wideOnly}`}>
                Tools
              </th>
              <th scope="col">Estado</th>
              <th scope="col">
                <span className="visually-hidden">Ações</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {shown.map(({ server, health }) => {
              const state = stateOf(server, health);
              const users = usedBy(server.alias);
              return (
                <tr key={server.alias}>
                  <th scope="row" style={{ fontWeight: 400 }}>
                    <span className={styles.alias}>{server.alias}</span>
                    {server.description ? <span className={t.secondaryText}>{server.description}</span> : null}
                    {/* Na tela estreita, o endereço vem sob o nome, no lugar da coluna. */}
                    <span className={`${styles.endpointText} ${styles.endpointInline}`}>
                      {breakable(server.endpoint ?? server.command ?? "—")}
                    </span>
                  </th>
                  <td>
                    {server.origin === "file" ? (
                      <Badge icon="cadeado">mcp.yaml · somente leitura</Badge>
                    ) : (
                      <Badge>API</Badge>
                    )}
                  </td>
                  <td className={t.wideOnly} style={{ color: "var(--texto-secundario)" }}>
                    {server.transport ?? "—"}
                  </td>
                  <td className={`${styles.endpoint} ${t.wideOnly}`}>
                    <span
                      className={`${styles.endpointText} ${t.truncate}`}
                      title={server.endpoint ?? server.command ?? ""}
                    >
                      {server.endpoint ?? server.command ?? "—"}
                    </span>
                  </td>
                  <td className={`${t.num} ${t.wideOnly}`}>{health && health.ok ? health.tools.length : "—"}</td>
                  <td>
                    <Badge tone={!state.ok ? "bad" : server.auth.type === "delegated" ? "neutral" : "ok"} dot>
                      {!state.ok ? "Indisponível" : server.auth.type === "delegated" ? "Por execução" : "Disponível"}
                    </Badge>
                    <span className={styles.usage}>
                      {state.reason
                        ? mcpReason(state.reason, "curta")
                        : users.length > 0
                          ? `Usado por ${users.join(", ")}`
                          : "Não usado"}
                    </span>
                  </td>
                  <td className={t.chevron}>
                    {server.origin === "registry" ? (
                      <RowMenu
                        alias={server.alias}
                        onEdit={() => setEditing(server)}
                        onDelete={() => setRemoving(server.alias)}
                      />
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        icon="direita"
                        aria-label={`Ver ${server.alias}, somente leitura`}
                        title="Ver a configuração"
                        aria-expanded={viewing?.alias === server.alias}
                        onClick={() => setViewing(viewing?.alias === server.alias ? null : server)}
                      />
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      )}
    </Page>
  );
}
