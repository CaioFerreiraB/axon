/** O detalhe de um Assistant (013 FR-005): cabeçalho com o estado, anterior e próximo, e as abas Modelos, MCP,
 * Permissões e Histórico — cada aba é uma rota. */

import { Outlet, useLocation, useNavigate, useOutletContext, useParams } from "react-router";

import { isApiError } from "../../api/errors";
import { useAssistant, useAssistants } from "../../api/hooks/assistants";
import type { AssistantView } from "../../api/schemas";
import { VISIBILITY_TEXT } from "../../i18n/pt-BR";
import { Button } from "../../ui/Button";
import { Notice } from "../../ui/Notice";
import { Page, PageHeader } from "../../ui/Page";
import { LoadError, Skeleton } from "../../ui/States";
import { TabNav } from "../../ui/TabNav";
import { StatusBadge } from "./status";

export type AssistantContext = { view: AssistantView; refetch: () => Promise<unknown> };

export function useAssistantContext(): AssistantContext {
  return useOutletContext<AssistantContext>();
}

export default function AssistantDetail() {
  const name = useParams().nome ?? "";
  const assistant = useAssistant(name);
  const list = useAssistants();
  const navigate = useNavigate();
  const tab = useLocation().pathname.split("/").pop() ?? "modelos";
  const names = (list.data ?? []).map((view) => view.name);
  const index = names.indexOf(name);
  const go = (offset: number) => {
    const target = names[index + offset];
    if (target) {
      navigate(`/assistentes/${encodeURIComponent(target)}/${tab}`);
    }
  };
  const base = `/assistentes/${encodeURIComponent(name)}`;
  const view = assistant.data;

  if (assistant.isError) {
    return (
      <Page>
        <PageHeader back={{ to: "/assistentes", label: "Assistentes" }} title={name} />
        {isApiError(assistant.error) && assistant.error.isNotFound ? (
          <Notice
            tone="neutral"
            icon="info"
            title="Este Assistant não existe"
            action={{ label: "Voltar à lista", to: "/assistentes" }}
          >
            Ele pode ter saído do assistants.yaml no último deploy.
          </Notice>
        ) : (
          <LoadError what="o Assistant" error={assistant.error} onRetry={() => void assistant.refetch()} />
        )}
      </Page>
    );
  }

  return (
    <Page>
      <PageHeader
        back={{ to: "/assistentes", label: "Assistentes" }}
        title={name}
        badge={view ? <StatusBadge view={view} /> : null}
        subtitle={
          view
            ? [view.description, view.flow ? `flow ${view.flow}` : null, VISIBILITY_TEXT[view.visibility]]
                .filter(Boolean)
                .join(" · ")
            : undefined
        }
        actions={
          names.length > 1 ? (
            <>
              <Button
                icon="esquerda"
                aria-label="Assistant anterior"
                title="Anterior"
                disabled={index <= 0}
                onClick={() => go(-1)}
              />
              <Button
                icon="direita"
                aria-label="Próximo Assistant"
                title="Próximo"
                disabled={index < 0 || index >= names.length - 1}
                onClick={() => go(1)}
              />
            </>
          ) : null
        }
      />
      <TabNav
        label="Seções do Assistant"
        tabs={[
          { to: `${base}/modelos`, label: "Modelos" },
          { to: `${base}/mcp`, label: "MCP" },
          { to: `${base}/permissoes`, label: "Permissões" },
          { to: `${base}/historico`, label: "Histórico" },
        ]}
      />
      {view ? (
        // A chave remonta a aba ao trocar de Assistant (anterior/próximo): o rascunho recomeça do zero.
        <div key={view.name} style={{ display: "contents" }}>
          <Outlet context={{ view, refetch: assistant.refetch } satisfies AssistantContext} />
        </div>
      ) : (
        <div aria-busy="true" aria-label="Carregando">
          <Skeleton height={64} style={{ borderRadius: 8 }} />
          <Skeleton height={280} style={{ marginTop: 20, borderRadius: 8 }} />
        </div>
      )}
    </Page>
  );
}
