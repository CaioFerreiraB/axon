# ADR-031 — Superfície de administração: admin é o grupo, com token da plataforma ou chave

- **Status:** Aceita · 2026-10-13
- **Specs afetadas:** [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md) (FR-001 e o seam
  `SCHEME_OF_SURFACE`; regra `is_admin`), [008-core-http-api](../../specs/008-core-http-api/spec.md) (FR-001: terceira
  superfície; rotas de administração), [012-core-identity](../../specs/012-core-identity/spec.md) (audiência dos tokens
  da console), [013-core-admin-console](../../specs/013-core-admin-console/spec.md)
- **Origem:** a console (ADR-029) entra com login de usuário (ADR-030), e hoje só chave de API administra

## Contexto

A 003 tem duas superfícies (FR-001): a pública (`/v1`) aceita só OIDC, e a privada (`/private/v1`) aceita só chave de
API (`SCHEME_OF_SURFACE`). As rotas de administração ficam na privada, e `is_admin` exige `scheme == "api_key"` e o
grupo de administração. Um usuário que entra por login nunca é admin.

A console entra pelo provedor da plataforma e precisa das rotas de administração com o token do usuário. Abrir a
superfície privada para OIDC mudaria o que ela promete a quem a usa hoje (automação por chave). Abrir as rotas de
administração na pública colocaria tokens repassados pelo Open WebUI ao alcance delas.

## Decisão

1. Uma terceira superfície, **administração** (`/admin/v1`), aceita **token da plataforma ou chave de API**. O seam
   `SCHEME_OF_SURFACE` passa a mapear superfície → conjunto de esquemas: pública `{oidc}`, privada `{api_key}`,
   administração `{oidc, api_key}`. Na administração, a credencial com o prefixo de chave da 003 segue o caminho de
   chave; qualquer outra, o de OIDC.
2. **Admin é membro do grupo de administração**, em qualquer esquema: `is_admin` deixa de olhar o esquema, porque cada
   superfície já limita os esquemas que aceita.
3. Na superfície de administração, credencial inválida é **401** (a console refaz o login); credencial válida sem o
   grupo de administração é **404**, como já é na privada (princípio IV).
4. Os tokens que a console recebe têm **audiência própria** (`ai-core-admin`), diferente da do Open WebUI (`ai-core`).
   A superfície de administração só aceita a audiência da console; a pública, só a do chat. Um token que o Open WebUI
   guarda não alcança rota de administração, mesmo sendo de um admin.
5. As rotas atuais da superfície privada (`/private/v1/packs`, `/admin/keys`, `/mcp`, `/health`) não mudam. A
   superfície de administração reúne o que a console usa, inclusive o que já existe na privada (o router de MCP global é
   montado nas duas).

## Alternativas rejeitadas

*Aceitar OIDC na superfície privada.* Mudaria a promessa da privada (só chave) e misturaria, na mesma superfície,
credenciais de máquina e de pessoa, com a mesma audiência dos tokens do chat.

*Rotas de administração na superfície pública, restritas ao grupo.* Qualquer token do Open WebUI de um admin bastaria
para administrar; um XSS ou um vazamento no Open WebUI viraria acesso administrativo.

*Um serviço separado (BFF) para a console, com sessão em cookie.* Mais um processo e mais um caminho de autorização a
manter, para um ganho que a audiência própria e os tokens só em memória já dão.

## Consequências

- O seam da 003 muda (`SCHEME_OF_SURFACE` e `is_admin`): a 008 é a consumidora afetada e se atualiza na mesma fase.
- A automação headless ganha a API de administração completa com chave de API: a console é dispensável.
- O verificador OIDC da 003 passa a conferir a audiência por superfície.
