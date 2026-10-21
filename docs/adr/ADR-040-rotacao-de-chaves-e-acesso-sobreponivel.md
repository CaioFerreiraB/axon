# ADR-040 — A administração rotaciona o segredo de uma chave de API e sobrepõe o acesso de Assistants de sistema (amplia o 032)

- **Status:** Aceita · 2026-10-21
- **Specs afetadas:** [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md) (FR-015, FR-018 a
  FR-022; seams API Key Admin e System Assistant Admin; migrações no schema `assistants`),
  [008-core-http-api](../../specs/008-core-http-api/spec.md) (rotas de `/admin/v1`; contrato `admin-api.md`),
  [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (registro do subcomando `axon keys rotate`),
  [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (tela de chaves; aba de acesso no Assistant)
- **Origem:** pedido do mantenedor (2026-10-21): gerir chaves de API pela console — criar para um sistema, listar,
  revogar e rotacionar — e editar pela console quem pode usar um Assistant de sistema (`auth.schemes` e `auth.allow`)

## Contexto

O seam API Key Admin da 003 emite, lista e revoga (`issue`, `keys`, `revoke`). A chave é `axn_<key_id>_<segredo>`; o
armazenamento guarda o SHA-256 da chave inteira, e a autenticação busca pelo `key_id` e compara o hash. Não há rotação:
trocar um segredo vazado é emitir outra chave e revogar a antiga, com `key_id` novo.

O ADR-032 fechou o conjunto de seções sobreponíveis em `{models, mcp}`. A seção `auth` (`schemes` e `allow`) só muda por
deploy. Dar acesso a um sistema novo ou a um grupo exige, então, editar o `assistants.yaml` e reimplantar — justamente o
que o ADR-032 tirou do caminho para modelos e MCPs.

Na plataforma, "sistema" não é uma entidade: é o subject `svc:<nome>` de uma chave de API. Não há cadastro de sistemas.
A 003 não importa a 012 (contas e grupos), e a ACL de hoje não confere se um subject ou grupo de `allow` existe: uma
entrada que não casa ninguém não concede nada.

## Decisão

1. **Rotação troca o segredo e mantém o `key_id`.** O seam API Key Admin ganha `rotate(*, actor, key_id) ->
   IssuedApiKey`: um segredo novo, mostrado uma vez, como na emissão; o subject, os grupos e o rótulo não mudam;
   `ApiKeyInfo` ganha `rotated_at`. A troca do hash é atômica no armazenamento e só vale para chave ativa; chave
   revogada ou inexistente não rotaciona. A operação existe também para o operador (`axon keys rotate`).
2. **O segredo antigo morre na hora, sem janela de convivência.** A rotação serve ao segredo vazado. Trocar sem queda
   já é possível sem nada novo: emitir uma segunda chave para o mesmo sistema, trocar no sistema, revogar a primeira.
   Por isso **um sistema pode ter mais de uma chave ativa**, distinguidas pelo rótulo.
3. **Sistema continua não sendo entidade.** A lista de sistemas que a administração mostra é derivada das chaves
   (subjects `svc:…`); nenhum cadastro, armazenamento ou seam novo.
4. **`auth` entra no conjunto fechado de seções:** `{models, mcp, auth}`. A sobreposição de `auth` substitui a seção
   inteira (`schemes` e `allow`) e segue tudo o que o ADR-032 e a clarificação de 2026-10-13 da 003 decidiram: só com
   `auth` em `overrides` no YAML; impressão digital da seção; inativa, com o motivo, se o deploy a tirar de `overrides` ou
   mudar a seção; autor, versão, histórico e conflito com versão desatualizada; vale na resolução seguinte, sem restart.
   Motivo de indisponibilidade prefixado por `override.auth`.
5. **O teto do acesso é o opt-in do YAML e as regras de sempre, não a seção do YAML.** A sobreposição pode ampliar ou
   restringir o acesso, dentro das validações da configuração efetiva (FR-011, FR-012): `schemes` não vazio, entre `oidc`
   e `api_key`; `allow` não vazio, com `*`, `user:…`, `svc:…` ou `group:…`; `*` proibido em Assistant privado.
   `visibility` **não** é sobreponível: continua só por deploy, porque é ela que decide `*` e tools de escrita.
6. **Acesso não é administração.** `auth` decide quem usa o Assistant em `/v1` e `/private/v1`; quem o administra é o
   grupo de administração em `/admin/v1` (ADR-031). Nenhuma sobreposição de `auth` tranca um admin fora da
   administração do Assistant: ele sempre pode corrigir ou descartar.
7. **A 003 não confere a existência das entradas de `allow`**, como já não confere no YAML: a ACL falha fechada (entrada
   que não casa ninguém não concede nada), e conferir exigiria a seta 003 → 012. Quem quiser apontar entradas sem
   correspondência (sistema sem chave ativa, grupo apagado) cruza as listas que a administração já expõe — isso é
   apresentação, na 013.

Ficam para o `/speckit-clarify` da 003 e da 013: o padrão do nome do sistema na emissão pela administração; se a tela
concede grupos na emissão, e como trata o grupo de administração; e o que o seletor de entradas de `allow` oferece.

## Alternativas rejeitadas

*Rotação como chave nova com o mesmo subject, revogando a antiga.* É exatamente "emitir + revogar", que já existe; perde
a continuidade do `key_id` (listagem, histórico e o futuro "último uso" por chave) e não acrescenta nada.

*Janela de convivência na rotação.* Exige dois hashes válidos com prazo e a expiração automática do antigo — é a
expiração de chaves, fora de escopo e com ADR próprio. Fazê-la pela metade agora prenderia a forma daquela decisão.

*Sobreposição de `auth` que só restringe a seção do YAML.* Dar acesso a um sistema novo continuaria exigindo deploy, que
é o motivo do pedido. O operador já controla o risco pelo opt-in: sem `auth` em `overrides`, nada muda.

*Liberar `visibility` junto.* Mudaria as regras de segurança do Assistant (FR-012: `*` e tools de escrita) por uma tela;
fica no deploy.

*Cadastro de sistemas.* Mais um armazenamento e um seam sem regra que dependa deles hoje; o subject das chaves basta.

*Indisponibilizar o Assistant cuja `allow` aponta para grupo ou sistema inexistente.* Acoplaria a 003 à 012 e
derrubaria um Assistant inteiro por causa de uma entrada que, na ACL, já não concede nada.

## Consequências

- Dois seams da 003 mudam, de forma aditiva: API Key Admin (`rotate`, `ApiKeyInfo.rotated_at`) e System Assistant
  Admin (seção `auth`: gravar, ver o YAML, a sobreposição e o efetivo). A 008 é a consumidora e se atualiza na mesma
  fase; a linha dos dois seams em `specs/README.md` acompanha.
- O schema `assistants` ganha migrações novas: a coluna da rotação nas chaves e `auth` no conjunto de seções das
  sobreposições. A conformidade contra o Postgres cobre as duas.
- A 011 registra `axon keys rotate`; nada mais muda na composição.
- A console ganha a tela de chaves e a aba de acesso, só sobre `/admin/v1`.
- Expiração, "último uso" e o subject no trace e no uso ficam para outro ADR. Nada aqui os impede: o `key_id` é estável
  entre rotações, a rotação é a única operação que troca o hash (uma janela de convivência entraria nela sem mudar a
  assinatura), e o subject `svc:…` já chega no `Principal` de cada requisição.
