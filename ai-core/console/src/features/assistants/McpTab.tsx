/** Aba MCP (013 US3, FR-007): ligar servidores MCP globais ao Assistant e marcar, a partir da descoberta, as tools
 * permitidas e as de escrita. Escrita bloqueada em Assistant público — a API também recusa; a tela explica. */

import { useMemo, useState } from "react";

import { isApiError } from "../../api/errors";
import { useDiscardOverride, useSaveMcp } from "../../api/hooks/assistants";
import { useMcpHealths, useMcpServers } from "../../api/hooks/mcp";
import type { AssistantView, McpHealth, McpSelection, McpServer } from "../../api/schemas";
import { mcpReason } from "../../i18n/pt-BR";
import { Badge } from "../../ui/Badge";
import { Button } from "../../ui/Button";
import { Checkbox } from "../../ui/Checkbox";
import { Icon } from "../../ui/icons";
import { Notice } from "../../ui/Notice";
import { Panel } from "../../ui/Panel";
import { EmptyState, LoadError, Skeleton } from "../../ui/States";
import { Toggle } from "../../ui/Toggle";
import { useAssistantContext } from "./AssistantDetail";
import styles from "./Editor.module.css";
import { DiscardButton, overrideMeta, SaveError } from "./editorParts";
import mcp from "./McpTab.module.css";
import { overrideOf, sentence } from "./status";

type Draft = { aliases: string[]; allowed: Set<string>; write: Set<string> };

function draftOf(view: AssistantView): Draft {
  const source: McpSelection = view.effective.mcp;
  return { aliases: [...source.aliases], allowed: new Set(source.allowed), write: new Set(source.write) };
}

function changesOf(draft: Draft, base: Draft): number {
  const aliasChanges = new Set(
    [...draft.aliases, ...base.aliases].filter((a) => draft.aliases.includes(a) !== base.aliases.includes(a)),
  ).size;
  const toolChanges = (field: "allowed" | "write") =>
    new Set([...draft[field], ...base[field]].filter((tool) => draft[field].has(tool) !== base[field].has(tool))).size;
  return aliasChanges + toolChanges("allowed") + toolChanges("write");
}

/** As tools de um servidor com o namespace dele: descobertas, dentro da allowlist do servidor, mais as já marcadas
 * (que continuam visíveis com o servidor fora do ar — US3 cenário 2). */
function toolsOf(server: McpServer, health: McpHealth | undefined, draft: Draft): string[] {
  const spaced = (name: string) => (name.startsWith(`${server.alias}.`) ? name : `${server.alias}.${name}`);
  const allow = server.policy ? new Set(server.policy.allowed_tools.map(spaced)) : null;
  const discovered = (health?.tools ?? []).map(spaced).filter((tool) => allow === null || allow.has(tool));
  const fromPolicy = health ? [] : [...(allow ?? [])];
  const marked = [...draft.allowed, ...draft.write].filter((tool) => tool.startsWith(`${server.alias}.`));
  return [...new Set([...discovered, ...fromPolicy, ...marked])].sort();
}

function ServerCard({
  server,
  health,
  healthError,
  draft,
  setDraft,
  editable,
  isPublic,
}: {
  server: McpServer;
  health: McpHealth | undefined;
  healthError: unknown;
  draft: Draft;
  setDraft: (update: (draft: Draft) => Draft) => void;
  editable: boolean;
  isPublic: boolean;
}) {
  const on = draft.aliases.includes(server.alias);
  const tools = toolsOf(server, health, draft);
  const writeTools = new Set(
    (server.policy?.write_tools ?? []).map((t) => (t.startsWith(`${server.alias}.`) ? t : `${server.alias}.${t}`)),
  );
  const ok = server.available && (health ? health.ok : !healthError);
  const reason = !ok
    ? (server.reason ?? health?.detail ?? (isApiError(healthError) ? healthError.message : "o servidor não respondeu"))
    : null;
  const allowedCount = tools.filter((tool) => draft.allowed.has(tool)).length;
  const origin = server.origin === "file" ? "do arquivo do operador (mcp.yaml)" : server.endpoint;

  const toggleServer = (checked: boolean) =>
    setDraft((current) => {
      const prefix = `${server.alias}.`;
      return checked
        ? { ...current, aliases: [...current.aliases, server.alias] }
        : {
            aliases: current.aliases.filter((alias) => alias !== server.alias),
            allowed: new Set([...current.allowed].filter((tool) => !tool.startsWith(prefix))),
            write: new Set([...current.write].filter((tool) => !tool.startsWith(prefix))),
          };
    });
  const toggleTool = (tool: string, field: "allowed" | "write", checked: boolean) =>
    setDraft((current) => {
      const allowed = new Set(current.allowed);
      const write = new Set(current.write);
      if (field === "allowed") {
        if (checked) {
          allowed.add(tool);
        } else {
          allowed.delete(tool);
          write.delete(tool);
        }
      } else if (checked) {
        write.add(tool);
        allowed.add(tool);
      } else {
        write.delete(tool);
      }
      return { ...current, allowed, write };
    });

  return (
    <section className={mcp.server} aria-label={`Servidor ${server.alias}`}>
      <div className={mcp.head}>
        <Toggle checked={on} onChange={toggleServer} disabled={!editable} label={`Usar o servidor ${server.alias}`} />
        <div className={mcp.title}>
          <div className={mcp.nameRow}>
            <span className={mcp.alias}>{server.alias}</span>
            <Badge tone={ok ? "ok" : "bad"} dot>
              {ok ? "Disponível" : "Indisponível"}
            </Badge>
          </div>
          <span className={mcp.description}>{[server.description, origin].filter(Boolean).join(" · ")}</span>
        </div>
        {on && tools.length > 0 ? (
          <span className={mcp.count}>
            {allowedCount} de {tools.length} tools permitidas
          </span>
        ) : null}
      </div>
      {reason ? (
        <p className={mcp.reason}>
          {mcpReason(reason, "completa")}
          {tools.length === 0 ? " As tools aparecem quando o servidor responder." : ""}
        </p>
      ) : null}
      {on && tools.length > 0 ? (
        <table className={mcp.tools}>
          <caption className="visually-hidden">Tools de {server.alias}</caption>
          <thead>
            <tr>
              <th scope="col">Tool</th>
              <th scope="col" className={mcp.flagCell}>
                Permitida
              </th>
              <th scope="col" className={mcp.flagCell}>
                Escrita
              </th>
            </tr>
          </thead>
          <tbody>
            {tools.map((tool) => {
              const discovered = !health || health.tools.some((name) => tool.endsWith(`.${name}`) || tool === name);
              return (
                <tr key={tool}>
                  <td>
                    <span className={mcp.toolName}>{tool}</span>
                    {!discovered ? <span className={mcp.missing}>não anunciada pelo servidor agora</span> : null}
                  </td>
                  <td className={mcp.flagCell}>
                    <Checkbox
                      aria-label={`Permitir ${tool}`}
                      checked={draft.allowed.has(tool)}
                      disabled={!editable}
                      onChange={(event) => toggleTool(tool, "allowed", event.target.checked)}
                    />
                  </td>
                  <td className={mcp.flagCell}>
                    <span className={mcp.flagRow}>
                      <Checkbox
                        aria-label={
                          isPublic ? `Escrita de ${tool} bloqueada em Assistant público` : `Permitir escrita de ${tool}`
                        }
                        checked={draft.write.has(tool)}
                        disabled={!editable || isPublic}
                        onChange={(event) => toggleTool(tool, "write", event.target.checked)}
                      />
                      {writeTools.has(tool) ? <Badge>Escreve</Badge> : null}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      ) : null}
    </section>
  );
}

export default function McpTab() {
  const { view, refetch } = useAssistantContext();
  const editable = view.overridable.includes("mcp");
  const override = overrideOf(view, "mcp");
  const isPublic = view.visibility === "public";
  const servers = useMcpServers();
  const globals = useMemo(() => (servers.data ?? []).filter((server) => server.scope === "global"), [servers.data]);
  const healths = useMcpHealths(globals.map((server) => server.alias));
  const [draft, setDraftState] = useState<Draft>(() => draftOf(view));
  const [baseVersion, setBaseVersion] = useState<number | null>(override?.version ?? null);
  const save = useSaveMcp(view.name);
  const discard = useDiscardOverride(view.name);

  const base = draftOf(view);
  const changes = changesOf(draft, base);
  const setDraft = (update: (draft: Draft) => Draft) => setDraftState((current) => update(current));
  const unknownAliases = draft.aliases.filter((alias) => !globals.some((server) => server.alias === alias));

  const onSave = () =>
    save.mutate(
      {
        aliases: draft.aliases,
        allowed: [...draft.allowed].sort(),
        write: [...draft.write].sort(),
        version: baseVersion,
      },
      {
        onSuccess: (next) => {
          setDraftState(draftOf(next));
          setBaseVersion(overrideOf(next, "mcp")?.version ?? null);
        },
      },
    );

  return (
    <div className={styles.stack}>
      {!editable ? (
        <Notice tone="neutral" title="Os MCPs deste Assistant só mudam por novo deploy">
          O assistants.yaml não inclui mcp em overrides. Para liberar a escolha pela console, acrescente overrides:
          [mcp] e faça o deploy.
        </Notice>
      ) : override?.state === "inactive" ? (
        <Notice
          tone="warn"
          title="Sobreposição inativa: o deploy mudou esta seção"
          action={{ label: "Ver a sobreposição guardada", to: "../historico" }}
        >
          {sentence(override.reason ?? "A sobreposição foi feita sobre outro YAML.")} Vale o que o deploy define até
          alguém gravar de novo.
        </Notice>
      ) : isPublic ? (
        <Notice tone="info" title="Assistant público: tools de escrita não podem ser marcadas">
          A plataforma recusa escrita em Assistants públicos. As entradas de pack em allowed_tools continuam como no
          YAML.
        </Notice>
      ) : null}
      {servers.isError ? (
        <LoadError what="os servidores MCP" error={servers.error} onRetry={() => void servers.refetch()} />
      ) : servers.isPending ? (
        <Skeleton height={180} style={{ borderRadius: 8 }} />
      ) : globals.length === 0 ? (
        <Panel>
          <EmptyState title="Nenhum servidor MCP global">
            Cadastre servidores em Servidores MCP (ou no mcp.yaml da instalação) para ligá-los aos Assistants.
          </EmptyState>
        </Panel>
      ) : (
        globals.map((server, index) => (
          <ServerCard
            key={server.alias}
            server={server}
            health={healths[index]?.data}
            healthError={healths[index]?.error}
            draft={draft}
            setDraft={setDraft}
            editable={editable}
            isPublic={isPublic}
          />
        ))
      )}
      {unknownAliases.length > 0 ? (
        <Notice tone="bad" title="Servidor que não existe mais">
          {unknownAliases.join(", ")} está na configuração deste Assistant, mas não entre os servidores globais.
          Desligue-o ou restaure o servidor.
        </Notice>
      ) : null}
      <SaveError
        error={save.error ?? discard.error}
        onReload={() =>
          void refetch().then((fresh) => {
            const next = (fresh as { data?: AssistantView }).data;
            if (next) {
              setBaseVersion(overrideOf(next, "mcp")?.version ?? null);
            }
            save.reset();
          })
        }
      />
      <div className={styles.footer}>
        <span className={styles.meta}>
          {editable
            ? overrideMeta(override, "Sem sobreposição de MCP: vale o YAML", changes)
            : "Valores do assistants.yaml deste deploy."}
        </span>
        {editable ? (
          <div className={styles.actions}>
            {changes > 0 ? (
              <Button variant="ghost" onClick={() => setDraftState(draftOf(view))}>
                Desfazer alterações
              </Button>
            ) : override ? (
              <DiscardButton
                override={override}
                busy={discard.isPending}
                onConfirm={() =>
                  discard.mutate(
                    { section: "mcp", version: override.version },
                    {
                      onSuccess: (next) => {
                        setDraftState(draftOf(next));
                        setBaseVersion(null);
                      },
                    },
                  )
                }
              />
            ) : null}
            <Button variant="primary" disabled={changes === 0} busy={save.isPending} onClick={onSave}>
              Salvar sobreposição
            </Button>
          </div>
        ) : null}
      </div>
      {editable && isPublic && [...draft.write].length > 0 ? (
        <p className={styles.hint}>
          <Icon name="alerta" size={12} /> Há tools de escrita na configuração; a plataforma vai recusar ao salvar.
        </p>
      ) : null}
    </div>
  );
}
