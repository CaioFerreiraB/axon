# ADR-057 — A chave de API tem escopos: inferência, usuários e administração (refina o 031 e o 040)

- **Status:** Aceita · 2026-11-04
- **Specs afetadas:** [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md) (seams Authenticator e
  API Key Admin: `Principal`, `ApiKeyInfo`, `issue`; migração no schema `assistants`),
  [008-core-http-api](../../specs/008-core-http-api/spec.md) (escopo exigido por rota em `/private/v1` e `/admin/v1`;
  contratos `admin-api.md` e da superfície privada), [012-core-identity](../../specs/012-core-identity/spec.md) (seam
  Account Admin: operações em nome de ator sem administração), [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md)
  (`axon keys create --scope`), [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (escopos na emissão
  e na listagem de chaves)
- **Origem:** pedido do mantenedor (2026-11-04): gerenciar usuários e grupos pela API com uma chave que escolha o escopo
  — gerenciar usuários ou usar inferência — sem dar a um sistema de provisionamento a administração inteira

## Contexto

O acesso de uma chave hoje é tudo ou nada. Qualquer chave ativa faz inferência em `/private/v1` (chat, `/chat`,
`/models`, conversas, MCP do próprio subject), dentro da ACL de cada Assistant. A chave cujos grupos incluem o grupo de
administração alcança, além disso, toda a `/admin/v1` e as rotas de administração da privada (`/packs`, `/admin/keys`,
MCP global) — ADR-031, item 2: admin é o grupo, em qualquer esquema. O grupo de administração numa chave só é concedido
pela CLI (ADR-040 e clarificação da 003).

As rotas de contas e grupos (`/admin/v1/users*`, `/admin/v1/groups*`, seam Account Admin da 012) já existem. Um sistema
que só precisa provisionar contas — o cadastro de uma organização que cria e desliga pessoas — teria de receber uma chave
de administrador: troca preços, Langfuse, sobreposições de Assistants, emite chaves, e ainda conversa com qualquer
Assistant que a ACL lhe conceda. E uma chave que só deveria conversar, se emitida com o grupo errado, administra.

## Decisão

1. **Três escopos, conjunto fechado:** `inference`, `users` e `admin`. `Scope = Literal["inference", "users", "admin"]`
   no `api.py` da 003. Toda chave tem um conjunto não vazio de escopos, fixado na emissão.
   - `inference` — as rotas de execução e o que o usuário da API tem de seu na privada: chat completions, `POST /chat`,
     `/models`, conversas e anexos, `/private/v1/mcp` dos servidores do próprio subject.
   - `users` — contas e grupos em `/admin/v1` (`/users*`, `/groups*`) e `GET /admin/v1/me`.
   - `admin` — toda a `/admin/v1` e as rotas de administração da privada (`/packs`, `/admin/keys`, MCP global).
     Inclui `users`; **não** inclui `inference`.
   - `/private/v1/health` vale para qualquer chave, como hoje.
2. **O `Principal` carrega os escopos.** `Principal.scopes: frozenset[Scope] | None`: o conjunto da chave no esquema
   `api_key`; `None` no esquema `oidc`, que continua regido só pelo grupo (console e `/v1` não mudam). `ApiKeyInfo`
   ganha `scopes`, e `ApiKeyAdmin.issue` ganha `scopes` (sem ele, `{inference}`).
3. **Administrar exige o escopo e o grupo.** Com chave, `is_admin` passa a ser "grupo de administração **e** escopo
   `admin`"; com OIDC, só o grupo. O escopo `admin` só é aceito em chave que tem o grupo de administração, e por isso só
   pela CLI — a mesma regra do grupo (ADR-040). `users` e `inference` podem ser concedidos pela administração
   (`POST /admin/v1/keys`, console) ou pela CLI.
4. **O escopo `users` basta para gerenciar contas — sem o grupo de administração**, com a regra de não escalar: o ator
   que não administra não cria, altera, apaga, redefine a senha, desativa, reativa nem desfaz o vínculo Google de conta
   que está no grupo de administração; não põe nem tira ninguém desse grupo; não apaga nem renomeia o grupo; e não
   alcança nenhuma rota fora de contas e grupos (chaves inclusive). A 008 diz à 012 se o ator administra
   (`actor_can_admin`), e a 012 aplica a regra no próprio domínio — a 012 não conhece escopos nem chaves.
5. **Faltar o escopo é 404 de rota inexistente**, como falta de grupo hoje (ADR-031 item 3, FR-024 da 008). Recusa por
   não escalar, numa rota que o escopo alcança, é **403** com o campo nomeado: a rota existe para esse ator, e o motivo
   lhe é útil.
6. **Escopos são imutáveis na chave**, como subject e grupos: a rotação os preserva; mudar é emitir outra chave e revogar
   a antiga (um sistema pode ter mais de uma chave ativa, ADR-040).
7. **Migração sem quebra:** toda chave existente recebe `{inference}`; a que tem o grupo de administração recebe
   `{inference, admin}`. Depois da migração, nenhuma requisição que passava deixa de passar.
8. **O mapa rota → escopo é política pura da 008** (`http/domain/scopes.py`), declarado por rota no decorador da
   administração e no router da privada. Rota nova sem escopo declarado falha no teste do mapa, não em produção.

## Alternativas rejeitadas

*Só dois escopos (`inference`, `users`), com o grupo de administração ainda valendo tudo.* Uma chave de admin
continuaria fazendo inferência e uma chave de inferência com o grupo continuaria administrando; o escopo não restringiria
justamente a chave mais poderosa.

*Escopos finos por rota (`users:read`, `users:write`, `prices:write`…).* Nenhum caso de uso pede isso hoje; o conjunto
fechado de três cobre o pedido, e crescer o `Literal` é aditivo quando houver necessidade.

*`users` exigindo o grupo de administração.* O sistema de provisionamento voltaria a ser administrador; o escopo só
restringiria quem já pode tudo.

*Escopos também no token OIDC (claim `scope`).* A console é de quem administra, e o Open WebUI só conversa; a audiência
própria da console (ADR-031 item 4) já separa os dois. Dar a pessoas a gestão de contas sem administração seria um grupo
novo — fica para quando houver pedido.

*Rotas de contas numa superfície própria (`/private/v1/users`).* Duplicaria formatos, erros e o contrato que a console
já usa em `/admin/v1`.

## Consequências

- Dois seams da 003 mudam de forma aditiva (`Principal.scopes`, `ApiKeyInfo.scopes`, `issue(scopes=…)`), e um muda de
  comportamento (`is_admin` com chave exige o escopo). A 008 é a consumidora e se atualiza na mesma passada; a linha
  desses seams em `specs/README.md` acompanha.
- O seam Account Admin da 012 ganha o parâmetro do ator que não administra nas operações de escrita.
- O schema `assistants` ganha a migração dos escopos, com o preenchimento do item 7; a conformidade contra o Postgres a
  cobre.
- A 011 passa `--scope` (repetível) em `axon keys create` e mostra os escopos em `axon keys list`; a 013 escolhe os
  escopos na emissão (sem `admin`) e os mostra na lista.
- O caso de uso que motivou — apagar a conta e atribuir ou remover um grupo de um usuário — está no ADR-058.
