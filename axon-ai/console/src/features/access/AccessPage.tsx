/** Acesso (013 US6, FR-013; US9): contas, grupos, formas de login e chaves de API dos sistemas — valem para o chat e
 * para a console. */

import { Outlet, useLocation, useNavigate } from "react-router";

import { Button } from "../../ui/Button";
import { Page, PageHeader } from "../../ui/Page";
import { TabNav } from "../../ui/TabNav";

export default function AccessPage() {
  const path = useLocation().pathname;
  const onUsers = path.endsWith("/usuarios");
  const onKeys = path.endsWith("/chaves");
  const navigate = useNavigate();
  return (
    <Page>
      <PageHeader
        title="Acesso"
        subtitle="Contas, grupos, formas de login e chaves de API da plataforma. Valem para o chat e para a console."
        actions={
          onUsers ? (
            <Button variant="primary" icon="mais" onClick={() => navigate("/acesso/usuarios?cadastrar=1")}>
              Cadastrar pessoa
            </Button>
          ) : onKeys ? (
            <Button variant="primary" icon="mais" onClick={() => navigate("/acesso/chaves?criar=1")}>
              Criar chave
            </Button>
          ) : null
        }
      />
      <TabNav
        label="Seções de acesso"
        tabs={[
          { to: "/acesso/usuarios", label: "Usuários" },
          { to: "/acesso/grupos", label: "Grupos" },
          { to: "/acesso/login", label: "Login" },
          { to: "/acesso/chaves", label: "Chaves de API" },
        ]}
      />
      <Outlet />
    </Page>
  );
}
