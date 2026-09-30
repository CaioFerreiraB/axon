# ADR-016 — O Execution Grant carrega a política de modelos da 006: seta 003 → 006

- **Status:** Aceita · 2026-09-30
- **Specs afetadas:** [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md),
  [006-core-llm-providers](../../specs/006-core-llm-providers/spec.md) (Module Boundary, FR-002, Key Entity, R1),
  [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md) (nenhuma mudança: é quem já exige a forma),
  [specs/README.md](../../specs/README.md) (grafo e tabela de seams)
- **Origem:** `/speckit-analyze` da 003 (achado C1), em 2026-09-30

## Contexto

Três decisões aceitas na Fase 1 não fecham entre si:

1. O `Protocol` `ExecutionGrant` da 005 (research R3 dela) exige `models: ModelPolicy` — o value object publicado no
   `api.py` da 006. Quem produz o grant a partir da Fase 2 é a 003; logo, a 003 precisa construir uma `ModelPolicy`, e
   para isso importar o `api.py` da 006.
2. A clarificação de 2026-09-18 da 006 e a research R1 dela dizem o oposto: "a partir da Fase 2 a própria 006 deriva a
   política do Execution Grant, o que preserva a direção 006 → 003". O grafo de `specs/README.md` tem a seta `006 → 003`.
3. O plano da 006 ("Seam Notes") e o contrato do Model Router registram a terceira versão: "a 003 passa a produzir a
   `ModelPolicy` como parte do Execution Grant; o seam não muda", com a 003 entre os consumidores do seam a partir da
   Fase 2.

Para cumprir o item 2, a 006 teria de receber o grant — o seam `for_execution(policy=…)` mudaria, e o `Protocol` da 005
também, já implementados e aceitos. Para cumprir o item 1, a direção documentada entre 003 e 006 precisa ser revista,
e o princípio II exige ADR para isso.

## Decisão

1. O Execution Grant da 003 carrega `models: ModelPolicy`, construída pela 003 a partir do Assistant — papéis declarados,
   allowlist e, quando houver, o modelo pedido pela requisição dentro da allowlist.
2. A 003 importa do `api.py` da 006 **apenas value objects**: `ModelPolicy`, `ModelRef`, `ModelRole`. Nunca o roteador,
   nunca `service.py`, `domain/` ou `adapters/` da 006.
3. A seta passa a ser **003 → 006**. A 006 não consome Principal nem Execution Grant: recebe a política pronta, como na
   Fase 1. Na tabela de seams, a 006 sai dos consumidores de *Principal + Execution Grant* e a 003 entra nos do *Model
   Router* (value objects da política).
4. O import-linter proíbe `ai_core.llm` de importar `ai_core.assistants`. Não há ciclo, e o contrato impede que surja.

Não é uma inversão de dependência por interface — nada é abstraído para trocar a direção. É a correção da seta para a
direção que o `Protocol` da 005 e o plano da 006 já implicavam; o grafo perde a seta `006 → 003` em vez de ganhar um
ciclo.

## Alternativas rejeitadas

*A 006 deriva a política do grant (a versão da clarificação da 006).* Muda o seam do Model Router
(`for_execution(grant=…)`) e o `Protocol` da 005, ambos implementados e aceitos; e põe a 006 — um módulo de runtime de
modelos — em contato com Principal e ACL, que não lhe dizem respeito.

*A 003 publica um value object próprio de modelos, e a 005 converte.* A 005 passaria a conhecer dois formatos da mesma
política e a importar a 003 para convertê-los; o `Protocol` dela mudaria do mesmo jeito.

*Mover `ModelPolicy` para `ai-core-contracts` (001).* Os contratos são a fronteira com packs; política de modelos por
Assistant é assunto interno do core, e entraria na superfície versionada sem nenhum pack precisar dela.

## Consequências

- Nenhuma mudança de código em 005 nem em 006: o seam do Model Router e o `Protocol` da 005 continuam como estão.
- A 003 constrói a política e é responsável por ela ser válida (allowlist não vazia, papéis dentro da allowlist); a
  006 continua conferindo a allowlist em cada chamada — duas linhas de defesa, com a mesma regra, verificada por uma
  suíte de paridade na 003.
- Textos da 006 que dizem "a 006 deriva a política do grant" ficam superados nesse ponto e são anotados com remissão a
  este ADR; a clarificação original fica registrada como histórico.
