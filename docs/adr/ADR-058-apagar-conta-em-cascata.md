# ADR-058 — A administração apaga uma conta em cascata, e o nome volta a ficar livre (substitui o item 7 do 030)

- **Status:** Aceita · 2026-11-04
- **Specs afetadas:** [012-core-identity](../../specs/012-core-identity/spec.md) (FR-001; seam Account Admin: `delete`,
  `add_group`, `remove_group`; porta nova de apagamento; migração no schema `identity`),
  [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md) (seam novo de apagamento por subject:
  Assistants de usuário, chaves, `allow` das sobreposições), [007-core-mcp-integration](../../specs/007-core-mcp-integration/spec.md)
  (seam novo: servidores do dono), [008-core-http-api](../../specs/008-core-http-api/spec.md) (rotas novas em
  `/admin/v1`; seam novo: conversas e anexos do dono), [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md)
  (montagem dos apagadores; `axon users delete`, `axon users groups add|remove`),
  [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (apagar usuário; um grupo por vez)
- **Origem:** pedido do mantenedor (2026-11-04): criar **e apagar** usuários pela API e atribuir ou remover grupos;
  escolhido o apagamento em cascata, com o nome reaproveitável

## Contexto

O item 7 do ADR-030 decidiu que usuário nunca é apagado, só desativado: a ACL dos Assistants, os Assistants de usuário
(`~nome`), os servidores MCP de usuário e as conversas usam o subject `user:<nome>`, e um nome reaproveitado herdaria tudo
isso. A FR-001 da 012 o repete. Desativar corta o acesso (012 US6), mas deixa e-mail, nome, vínculo Google, conversas e
anexos guardados para sempre, e o nome preso.

Os dados de um usuário estão espalhados pelos módulos que os possuem, cada um no próprio schema (ADR-015):

| Módulo | Dado do subject |
|---|---|
| 012 | conta, associações a grupos, sessões, códigos, tokens de renovação, vínculo Google, falhas de login |
| 003 | Assistants de usuário (`owner`), chaves de API (`subject`), entradas `user:<nome>` no `auth.allow` das sobreposições |
| 007 | servidores MCP de usuário (`owner`) |
| 008 | conversas e anexos (`owner`; anexos já em cascata da conversa) |

A 012 não importa 003, 007 nem 008 (ADR-030 item 2), e a 008 não expõe seam Python hoje.

Atribuir ou remover um grupo hoje exige reescrever a lista inteira (`PATCH /users/{u}` com `groups`) ou os membros do
grupo (`PUT /groups/{g}/members`) — duas chamadas concorrentes de provisionamento se sobrescrevem.

## Decisão

1. **Uma conta pode ser apagada, e o nome volta a ficar livre.** Substitui o item 7 do ADR-030 e a frase
   correspondente da FR-001 da 012. Desativar continua existindo e continua sendo o caminho para "tirar o acesso e
   guardar".
2. **Cada módulo dono de dado de usuário publica o próprio apagamento por subject**, no seu `api.py`:
   `erase_subject(subject) -> ErasureReport` — idempotente (apagar de novo devolve zero), com contagens por tipo de dado
   e avisos. 003, 007 e 008 ganham esse seam; a 008 ganha o `http/api.py` só para ele. Nenhum módulo apaga dado de outro.
3. **A 012 orquestra pelo seu domínio, sem conhecer os outros:** `AccountAdmin.delete(username, *, actor) ->
   DeletionReport`, com a porta `SubjectDataEraser` em `identity/ports.py` (uma sequência de apagadores com nome). A
   composition root (011) a monta a partir dos seams do item 2 — é a única que conhece os quatro módulos.
4. **Ordem e retomada.** A conta passa a `deleting`: login recusado, sessões e tokens de renovação revogados, fora de
   todos os grupos. Depois, cada apagador roda; por fim, a 012 apaga a conta e o que ela guarda, e o nome fica livre.
   Se um apagador falhar, a conta fica em `deleting` (não loga, não aparece como ativa, nome ainda preso), a resposta diz
   o que foi apagado e o que faltou, e repetir o `DELETE` retoma. Não há transação entre schemas; a idempotência substitui
   a atomicidade.
5. **Proteções:** não se apaga a própria conta do ator, nem o último membro ativo do grupo de administração (FR-011),
   nem — para ator sem administração (ADR-057 item 4) — conta do grupo de administração.
6. **Fica guardado o que não é dado do usuário, mas registro da plataforma:** a auditoria de tools de escrita da 004
   (trilha de segurança; o subject fica como texto, com o instante), o uso, o custo e o impacto da 009 (não têm subject)
   e o trace em arquivo (retenção do operador). `updated_by` e atores em históricos ficam como texto. A 012 confirma ou
   revê este item no `/speckit-clarify`.
7. **O que a plataforma não pode mudar sai como aviso.** Entradas `user:<nome>` no `assistants.yaml` são configuração do
   operador: a 003 as aponta no relatório ("referências na configuração"), porque um usuário novo com o mesmo nome as
   herdaria. As do `auth.allow` das sobreposições, a 003 as remove (é estado de runtime dela).
8. **Access token já emitido vale até expirar** (10 min, ADR-030 item 4), como na desativação; a renovação não.
9. **Um grupo por vez:** `AccountAdmin.add_group(username, group, *, actor)` e `remove_group(...)`, idempotentes e sem
   versão (comutam com outras mudanças), expostos em `PUT` e `DELETE /admin/v1/users/{u}/groups/{g}`, com as regras de
   grupo protegido (FR-011) e de não escalar (ADR-057).

## Alternativas rejeitadas

*Lápide: apagar os dados pessoais da conta e prender o nome.* Mais simples (só a 012 e a revogação das chaves), mas
deixa conversas, anexos e Assistants do usuário guardados sem dono e não libera o nome — o mantenedor pediu o apagamento
de verdade.

*A 008 orquestra a cascata na rota.* A CLI (`axon users delete`) não passa pela 008 e ficaria com uma cascata diferente
ou nenhuma; o apagamento é regra do domínio de contas, não da API.

*Evento "conta apagada" assíncrono, consumido por cada módulo.* Exigiria um barramento e uma fila persistente que a
plataforma não tem; a porta síncrona com retomada dá o mesmo resultado com o que já existe.

*Apagar também a auditoria e o trace.* Destruiria a trilha que existe exatamente para investigar o que uma conta fez com
tools de escrita; e o trace em arquivo é do operador.

## Consequências

- Seams novos: apagamento por subject em 003, 007 e 008 (o primeiro seam Python da 008) e a porta `SubjectDataEraser`
  da 012; o seam Account Admin cresce (`delete`, `add_group`, `remove_group`) e a 012 ganha o estado `deleting`. A tabela
  de seams em `specs/README.md` acompanha.
- O import-linter continua provando que a 012 não importa os outros módulos: só a 011 liga os apagadores.
- Migração no schema `identity` (o estado `deleting`; o índice único do nome continua, porque a linha some no fim). Os demais schemas não
  mudam: as colunas `owner`/`subject` já existem.
- A 011 registra `axon users delete <nome>` (com confirmação) e `axon users groups add|remove`; a 013 ganha "Apagar
  usuário" (confirmação digitando o nome, relatório no fim) e o grupo um a um na ficha.
- O índice marca o ADR-030 com o item 7 substituído por este.
