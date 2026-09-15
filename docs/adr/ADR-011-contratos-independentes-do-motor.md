# ADR-011 — Contratos independentes do motor de execução

- **Status:** Aceita · 2026-09-14 (proposta em 2026-09-10; aceita junto com o [ADR-012](ADR-012-estilo-arquitetural-hexagonal.md))
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md), [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md), [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md), todas as specs `1xx`
- **Origem:** tradução de arch-v1 para SDD; requisito do mantenedor de poder reescrever o grafo do `ai-core` e o `ai-scouting` com facilidade

## Contexto

A arquitetura v1 tem duas inconsistências internas que acoplam os packs ao motor de execução:

1. **Estado.** §30 coloca `AgentState` em `ai-core-contracts/state.py` e exige que os contratos dependam só da stdlib. Mas §6 define `AgentState` com `from langgraph.graph.message import add_messages` — o que arrastaria LangGraph para todo pack. O mesmo `AgentState` aparece também em `ai_core/graph/state.py`. E `prepare_context(state: Mapping, …)` / `validate(state: Mapping, …)` dão aos packs acesso ao estado bruto do grafo: qualquer campo que um pack leia vira contrato implícito, e reorganizar o estado quebra packs.
2. **Escape hatch.** §7.4 permite que um pack contribua "um subgraph LangGraph compilado". Isso torna LangGraph parte do contrato de pack e impede trocar o framework do motor.

O mantenedor pretende reescrever por completo o grafo do `ai-core` em breve. Com os contratos acima, essa reescrita vazaria para todos os packs.

## Decisão

1. `AgentState` (com reducers do LangGraph) é **privado do core** e mora só em `ai_core/graph/state.py`. Não existe em `ai-core-contracts`.
2. `ai-core-contracts` define uma **Turn View**: uma projeção somente-leitura, estável e versionada da execução, com campos enumerados (pergunta, mensagens, chunks recuperados/reranqueados com proveniência, chunks efetivamente entregues à geração, resultados de tools, resposta, citações, a fatia do próprio pack e as fatias das dependências declaradas). Os hooks de pack recebem a Turn View, nunca o estado bruto.
3. Hooks que escrevem (`prepare_context`) **retornam** a atualização da própria fatia; o core faz o merge. Não há caminho de escrita fora da fatia.
4. O escape hatch passa a ser um protocolo `PackRoutine` agnóstico de framework: uma rotina assíncrona que recebe a própria fatia + campos declarados e devolve a própria fatia + saídas declaradas, com limites herdados. O core a adapta como passo do grafo.
5. Nomes de nós, forma do estado interno e escolha do framework de grafo **não fazem parte de nenhum seam**.

## Alternativas rejeitadas

*Manter `AgentState` nos contratos, sem reducers do LangGraph.* Resolve a dependência, mas mantém o estado bruto como contrato implícito: toda reorganização do grafo continuaria sendo breaking change para packs.

*Manter o subgraph LangGraph compilado como escape hatch.* Mais poderoso, mas amarra os contratos ao framework. O nível 3 de extensão é "excepcional" (arch-v1 §7); pagar esse acoplamento pelo caso raro não compensa.

## Consequências

- Reescrever o grafo — inclusive trocar LangGraph — não exige major em `ai-core-contracts` nem mudança em packs
- Os contratos voltam a ser só stdlib, como a própria arch-v1 exige
- Packs são testáveis com fixtures de Turn View, sem motor
- Custo: uma camada de projeção estado → Turn View no core, e a Turn View precisa de versionamento cuidadoso (campo novo = minor; remoção/renomeação = major)
- Custo: packs não podem ler campos arbitrários do estado — o que é exatamente a intenção

## Se for rejeitado

Emendar o princípio II da constituição (itens 4 e 5), a spec 001 (FR-008 a FR-011) e o `design.md` da spec 005.
