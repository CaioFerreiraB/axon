# ADR-001 — Topologia fixa em vez de Graph Builder dinâmico

- **Status:** Aceita · 2026-09-10
- **Specs afetadas:** [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md), [001-core-contracts](../../specs/001-core-contracts/spec.md), [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md)
- **Origem:** arch-v1 Parte VIII

## Contexto

A proposta original previa que packs declarassem extensões em pontos nomeados (`CONTEXT_PROCESSOR`, `RETRIEVER`, `TOOLS`, `GENERATORS`, `VALIDATORS`…), um `Graph Builder` compusesse um `Graph Plan`, um `Graph Validator` o checasse, e o resultado fosse compilado para LangGraph.

## Decisão

O core escreve as topologias à mão. Packs registram capacidades consumidas por nós fixos. `Graph Builder`, `Graph Plan` e `Graph Validator` não existem.

## Alternativas rejeitadas

*Manter o builder dinâmico.* A validação proposta era estrutural — START existe, há caminho até END, sem órfãos, arestas válidas. Todas essas propriedades são verdadeiras em grafos semanticamente absurdos: um grafo que roda `rerank` antes de `retrieve`, ou `prepare_context` depois do controller, passa nos oito checks. **A falha real é semântica, e validação estrutural não a alcança.** Além disso, N packs × M extension points gera topologias exponenciais, cada uma um sistema distinto que precisaria da própria avaliação de qualidade — o que torna a matriz de teste inviável e produz bugs que só aparecem em combinações específicas.

*Topologia única, sem seleção.* Simples demais: o scouting perderia o caminho `rag_first` determinístico e pagaria uma chamada de controller onde não precisa.

## Consequências

- Uma topologia por vez para testar, instrumentar e depurar
- Composição de packs sempre válida por construção
- Três componentes de infraestrutura deixam de ser escritos
- Custo: uma topologia nova exige mudança no core — aceitável, porque topologias são poucas e a decisão de criar uma deve ser deliberada
- Nota de modularidade (2026-09-10): como a topologia é privada do core, reescrever o grafo inteiro é mudança confinada à spec 005 — ver [ADR-011](ADR-011-contratos-independentes-do-motor.md).
