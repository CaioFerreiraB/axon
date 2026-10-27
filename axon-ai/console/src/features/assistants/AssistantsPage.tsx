/** Assistants de sistema (013 FR-004): estado, modelos efetivos, MCPs e as marcas "sobreposto", "sobreposição
 * inativa" e "travado". Busca e filtro na URL. */

import { useSearchParams } from "react-router";
import { Link } from "react-router";

import { useAssistants } from "../../api/hooks/assistants";
import { refOfRole, type AssistantView } from "../../api/schemas";
import { formatInstantDay, plural } from "../../i18n/format";
import { SECTION_TEXT } from "../../i18n/pt-BR";
import { Badge } from "../../ui/Badge";
import { TextInput } from "../../ui/Field";
import { Icon } from "../../ui/icons";
import { Page, PageHeader } from "../../ui/Page";
import { Panel } from "../../ui/Panel";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, LoadError, Skeleton } from "../../ui/States";
import { Table, tableStyles as t } from "../../ui/Table";
import styles from "./AssistantsPage.module.css";
import { healthOf, overrideOf, StatusBadge, statusReason, who } from "./status";

const FILTERS = [
  { value: "todos", label: "Todos" },
  { value: "sobrepostos", label: "Sobrepostos" },
  { value: "problema", label: "Com problema" },
] as const;
type Filter = (typeof FILTERS)[number]["value"];

function matches(view: AssistantView, filter: Filter, query: string): boolean {
  const text = `${view.name} ${view.description ?? ""}`.toLowerCase();
  if (query && !text.includes(query.toLowerCase())) {
    return false;
  }
  if (filter === "sobrepostos") {
    return view.overrides.some((override) => override.state === "active");
  }
  if (filter === "problema") {
    return healthOf(view) !== "available";
  }
  return true;
}

function Row({ view }: { view: AssistantView }) {
  const models = overrideOf(view, "models");
  const generation = refOfRole(view.effective.models.generation) ?? "—";
  const reason = statusReason(view);
  return (
    <tr className={styles.row}>
      <th scope="row" style={{ fontWeight: 400 }}>
        <Link to={`/assistentes/${encodeURIComponent(view.name)}`} className={styles.name}>
          {view.name}
        </Link>
        {view.description ? <span className={t.secondaryText}>{view.description}</span> : null}
      </th>
      <td className={t.wideOnly} style={{ color: "var(--texto-secundario)" }}>
        {view.flow ?? "—"}
      </td>
      <td className={styles.model}>
        <span className={`${t.mono} ${t.truncate}`} title={generation}>
          {generation}
        </span>
        {models?.state === "active" ? (
          <span className={styles.overridden}>
            Sobreposto por {who(models.updated_by)} · {formatInstantDay(models.updated_at)}
          </span>
        ) : null}
      </td>
      <td className={t.wideOnly} style={{ color: "var(--texto-secundario)" }}>
        {view.effective.mcp.aliases.join(", ") || "—"}
      </td>
      <td>
        <span className={styles.chips}>
          {view.overridable.length === 0 ? (
            <Badge icon="cadeado">Travado</Badge>
          ) : (
            view.overridable.map((section) => <Badge key={section}>{SECTION_TEXT[section]}</Badge>)
          )}
        </span>
      </td>
      <td>
        <StatusBadge view={view} />
        {reason ? <span className={styles.reason}>{reason}</span> : null}
      </td>
      <td className={t.chevron} aria-hidden="true">
        <Icon name="direita" />
      </td>
    </tr>
  );
}

export default function AssistantsPage() {
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const filter = (FILTERS.find((f) => f.value === params.get("filtro"))?.value ?? "todos") as Filter;
  const assistants = useAssistants();
  const set = (key: string, value: string, fallback: string) => {
    const next = new URLSearchParams(params);
    if (value === fallback) {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setParams(next, { replace: true });
  };
  const all = assistants.data ?? [];
  const shown = all.filter((view) => matches(view, filter, query.trim()));
  const overridden = all.filter((view) => view.overrides.some((o) => o.state === "active")).length;
  const unavailable = all.filter((view) => !view.status.available).length;

  return (
    <Page>
      <PageHeader
        title="Assistentes"
        subtitle="Assistants de sistema do assistants.yaml. O que o YAML não libera em overrides só muda por novo deploy."
      />
      <div className={styles.toolbar}>
        <div className={styles.search}>
          <Icon name="busca" className={styles.searchIcon} />
          <TextInput
            type="search"
            className={styles.searchInput}
            placeholder="Buscar Assistant"
            aria-label="Buscar Assistant"
            value={query}
            onChange={(event) => set("q", event.target.value, "")}
          />
        </div>
        <Segmented<Filter>
          label="Filtrar"
          value={filter}
          onChange={(value) => set("filtro", value, "todos")}
          options={FILTERS}
        />
        {assistants.data ? (
          <span className={styles.summary}>
            {plural(all.length, "Assistant", "Assistants")} · {overridden} com sobreposição ativa ·{" "}
            {plural(unavailable, "indisponível", "indisponíveis")}
          </span>
        ) : null}
      </div>
      {assistants.isError ? (
        <LoadError what="os Assistants" error={assistants.error} onRetry={() => void assistants.refetch()} />
      ) : assistants.isPending ? (
        <Skeleton height={260} style={{ borderRadius: 8 }} />
      ) : all.length === 0 ? (
        <Panel>
          <EmptyState title="Nenhum Assistant de sistema">
            Os Assistants de sistema vêm do assistants.yaml da instalação. Declare um e faça o deploy.
          </EmptyState>
        </Panel>
      ) : shown.length === 0 ? (
        <Panel>
          <EmptyState title="Nenhum Assistant neste filtro">Mude a busca ou o filtro para ver os outros.</EmptyState>
        </Panel>
      ) : (
        <Table caption="Assistants de sistema">
          <thead>
            <tr>
              <th scope="col">Assistant</th>
              <th scope="col" className={t.wideOnly}>
                Flow
              </th>
              <th scope="col">Modelo de geração</th>
              <th scope="col" className={t.wideOnly}>
                MCP
              </th>
              <th scope="col">Sobreponível</th>
              <th scope="col">Estado</th>
              <th scope="col">
                <span className="visually-hidden">Abrir</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {shown.map((view) => (
              <Row key={view.name} view={view} />
            ))}
          </tbody>
        </Table>
      )}
    </Page>
  );
}
