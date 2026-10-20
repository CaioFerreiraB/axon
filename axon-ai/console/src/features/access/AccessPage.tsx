/** Acesso (013 US6, FR-013): contas, grupos e formas de login da plataforma — valem para o chat e para a console. */

import { Outlet, useLocation, useNavigate } from "react-router";

import { Button } from "../../ui/Button";
import { Page, PageHeader } from "../../ui/Page";
import { TabNav } from "../../ui/TabNav";

export default function AccessPage() {
  const onUsers = useLocation().pathname.endsWith("/usuarios");
  const navigate = useNavigate();
  return (
    <Page>
      <PageHeader
        title="Acesso"
        subtitle="Contas, grupos e formas de login da plataforma. Valem para o chat e para a console."
        actions={
          onUsers ? (
            <Button variant="primary" icon="mais" onClick={() => navigate("/acesso/usuarios?cadastrar=1")}>
              Cadastrar pessoa
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
        ]}
      />
      <Outlet />
    </Page>
  );
}
