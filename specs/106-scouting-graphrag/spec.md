# Feature Specification: GraphRAG do scouting (futuro)

**Feature Branch**: `106-scouting-graphrag`

**Created**: 2026-09-10

**Status**: Draft (futuro — Fase 8)

**Input**: Tradução de arch-v1 §24 (GraphRAG futuro), Parte IX (ontologia); princípio IX.

## Module Boundary *(mandatory)*

- **Módulo**: Scouting GraphRAG — retriever que combina grafo de conhecimento e busca vetorial, atrás do mesmo contrato de retriever.
- **Repositório / distribuição**: `ai-scouting` → `src/ai_scouting/rag/graph/`.
- **Consome (seams)**: contrato `Retriever` e `Chunk` — 001; Índice do scouting (modelo + porta `ChunkIndex`) — 102 (proveniência e trechos de suporte); pode compor o retriever de 103.
- **Expõe (seams)**: um `Retriever` alternativo — consumido por 101 por configuração.
- **Depende de infraestrutura (via portas)**: armazenamento do grafo de conhecimento; extração assistida por modelo, apenas offline.
- **Não conhece**: o core, flows, validators.
- **Substituição**: é, ele próprio, a demonstração de substituição: entra no lugar de 103 sem mudar 101, 104 nem o core.
- **Insumo técnico**: [design.md](design.md); [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Perguntas relacionais respondidas pelo grafo (Priority: P2)

Perguntas que atravessam relações ("que atividades trabalham as competências ligadas ao objetivo X do Programa Educativo?") são respondidas por um retriever que navega o grafo de conhecimento e recupera os trechos de suporte.

**Why this priority**: Fase 8 — evolução depois que o RAG híbrido estiver medido.

**Independent Test**: Para perguntas relacionais do conjunto dourado, o retriever de grafo supera o híbrido em recall@k.

**Acceptance Scenarios**:

1. **Given** o grafo populado, **When** uma pergunta relacional chega, **Then** o retriever devolve trechos que cobrem toda a cadeia de relações.
2. **Given** a troca de 103 por 106 na configuração do pack, **When** o pack roda, **Then** nenhuma mudança é necessária no core, em 101 ou em 104.

---

### User Story 2 - Relações com proveniência e origem distinguida (Priority: P2)

Cada relação guarda de onde veio. Relações presentes na fonte são distinguidas de relações inferidas por modelo, e as duas não são citadas do mesmo jeito.

**Why this priority**: Princípio IX — são epistemologicamente diferentes.

**Independent Test**: Toda relação do grafo tem proveniência e tipo de origem; relações inferidas nunca aparecem como citação de fonte.

**Acceptance Scenarios**:

1. **Given** uma relação inferida por modelo, **When** usada numa resposta, **Then** é apresentada como inferência, não como citação de documento.

---

### Edge Cases

- Relação inferida contradiz a fonte: a fonte prevalece; a relação é sinalizada para curadoria.
- Documento de suporte de uma relação é substituído: a relação herda o status de vigência.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O retriever DEVE implementar o mesmo contrato `Retriever` de 103.
- **FR-002**: Toda relação DEVE ter proveniência (documento, versão, trecho) e tipo de origem (`fonte`, `inferida`).
- **FR-003**: Relações inferidas NÃO DEVEM ser citadas como fonte.
- **FR-004**: A ontologia DEVE ser definida antes da implementação: [NEEDS CLARIFICATION: quais entidades e relações modelar (Programa Educativo, Objetivo, Competência, Atividade, Manual, Norma…) e quanto o modelo pode propor versus quanto exige curadoria humana?]

### Key Entities

- **Entity**: nó do grafo (ex.: Objetivo, Competência, Atividade).
- **Relation**: aresta com tipo, proveniência e tipo de origem.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Trocar o retriever do pack para GraphRAG exige só configuração no `ai-scouting`; 0 mudanças no core.
- **SC-002**: 100% das relações têm proveniência e tipo de origem.

## Assumptions

- Modelos de linguagem podem auxiliar na extração de entidades, relações, agrupamento e sinônimos, sempre com a origem registrada.
