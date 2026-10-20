import { useRouteError } from "react-router";

import { Page, PageHeader } from "../ui/Page";
import { Notice } from "../ui/Notice";

/** A fronteira de erro das rotas: nada aplicado é dado como salvo; recarregar recomeça a tela. */
export function RouteError() {
  const error = useRouteError();
  const message = error instanceof Error ? error.message : "Erro inesperado.";
  return (
    <Page>
      <PageHeader title="Algo deu errado nesta tela" />
      <Notice
        tone="bad"
        title="A tela parou por um erro"
        action={{ label: "Recarregar", onClick: () => window.location.reload() }}
      >
        {message} Nada que não tenha aparecido como salvo foi aplicado.
      </Notice>
    </Page>
  );
}

export function NotFoundPage() {
  return (
    <Page>
      <PageHeader title="Página não encontrada" subtitle="O endereço não corresponde a nenhuma tela da console." />
      <Notice
        tone="neutral"
        icon="info"
        title="Volte pela navegação ao lado"
        action={{ label: "Ir para Uso e custo", to: "/uso" }}
      />
    </Page>
  );
}
