# Feature Specification: Conjunto dourado e calibração do domínio escoteiro

**Feature Branch**: `105-scouting-evaluation`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §29 (conjunto dourado, começar pequeno), §21 (números a calibrar), §27 (benchmark de modelos), Parte IX (embedding, calibração), §31 Fase 6.

## Module Boundary *(mandatory)*

- **Módulo**: Scouting Evaluation — conteúdo do conjunto dourado do domínio, métricas de domínio e as decisões de calibração tomadas com base nele.
- **Repositório / distribuição**: `ai-scouting` → `src/ai_scouting/eval/`.
- **Consome (seams)**: Eval Harness e formato de conjunto dourado — 009; o Assistant `scouting` ponta a ponta, pelo harness em processo sobre o Execution Engine — o único caminho que fixa a data de referência (008 FR-012) — sem conhecer internals.
- **Expõe (seams)**: conjunto dourado versionado e métricas de domínio (ex.: taxa de documento vigente) — consumidos pelo harness (009) e pelo CI do `ai-scouting`.
- **Depende de infraestrutura (via portas)**: nenhuma além do Eval Harness (009), que executa os itens.
- **Não conhece**: implementação de retrieval, chunking ou flows — mede comportamento, não estrutura.
- **Substituição**: o conjunto dourado sobrevive a qualquer reescrita do pack — é justamente o que prova que a reescrita não piorou.
- **Insumo técnico**: [design.md](design.md); [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conjunto dourado de perguntas reais (Priority: P1)

O mantenedor cura 30–50 perguntas reais do domínio, cada uma com os documentos que devem ser recuperados, uma resposta de referência e as citações esperadas. O conjunto é versionado junto do pack.

**Why this priority**: Fase 6, antes de calibrar qualquer número. 30–50 perguntas reais valem mais que 500 sintéticas.

**Independent Test**: O harness valida o formato do conjunto e todos os documentos referenciados existem no corpus.

**Acceptance Scenarios**:

1. **Given** o conjunto dourado, **When** validado, **Then** cada item tem pergunta, documentos esperados, resposta de referência e citações esperadas, e referencia só documentos do corpus.
2. **Given** perguntas históricas no conjunto, **When** validado, **Then** elas marcam a data de referência esperada.

---

### User Story 2 - Linha de base registrada (Priority: P1)

A primeira rodada do harness com o conjunto dourado registra a linha de base de todas as métricas, incluindo as de domínio: taxa de documento vigente, acerto da derivação de contexto (101), taxa de citação resolvível e inventada.

**Why this priority**: Sem linha de base, não há como saber se uma mudança melhorou ou piorou.

**Independent Test**: A linha de base existe e é comparável com uma segunda rodada.

**Acceptance Scenarios**:

1. **Given** o pipeline RAG completo, **When** o harness roda pela primeira vez, **Then** a linha de base de todas as métricas fica registrada.

---

### User Story 3 - Calibração guiada por medição (Priority: P2)

Os números do RAG — candidatos, trechos após rerank, tamanho e sobreposição de chunk, limiar do portão de cobertura — são fixados a partir de rodadas comparativas, cada uma com relatório antes/depois.

**Why this priority**: Princípio X: calibrar sem medir é adivinhar.

**Independent Test**: Uma alteração de limiar do portão gera relatório com delta nas métricas.

**Acceptance Scenarios**:

1. **Given** duas configurações de tamanho de chunk, **When** comparadas, **Then** o relatório mostra o delta por métrica e a escolha fica registrada.

---

### User Story 4 - Escolha do modelo de embedding (Priority: P2)

Os candidatos de embedding para português são comparados com o conjunto dourado, considerando qualidade e custo no hardware alvo; a escolha é registrada.

**Why this priority**: Uma das decisões que mais afetam a qualidade final, e ainda em aberto.

**Independent Test**: Relatório comparativo dos candidatos com recall@k e custo de ingestão.

**Acceptance Scenarios**:

1. **Given** dois ou mais modelos de embedding, **When** comparados, **Then** o relatório mostra recall@k, MRR e custo, e a decisão é registrada.

---

### User Story 5 - Escolha do modelo de linguagem local (Priority: P3)

Os modelos locais candidatos são comparados em qualidade em português, confiabilidade de tool calling e fidelidade em RAG, além de desempenho.

**Why this priority**: Decide o default dos papéis de geração e controller.

**Independent Test**: Relatório comparativo dos candidatos com as métricas decisivas.

**Acceptance Scenarios**:

1. **Given** dois modelos locais, **When** comparados, **Then** o relatório inclui fidelidade em RAG e tool calling, não só desempenho.

---

### Edge Cases

- Pergunta cuja resposta mudou com uma nova versão de documento: o item antigo continua válido na sua data de referência (ADR-013); quando a mudança for relevante, acrescenta-se um item com a data nova, e o histórico é preservado.
- Item que se revela ambíguo: removido com justificativa registrada.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O conjunto dourado DEVE seguir o formato do harness (009) e ter entre 30 e 50 perguntas reais na primeira versão.
- **FR-002**: O conjunto DEVE incluir perguntas de consulta histórica e de fontes normativas.
- **FR-003**: O pack DEVE fornecer as métricas de domínio: taxa de documento vigente e acerto da derivação de contexto.
- **FR-004**: Toda decisão de calibração DEVE ter relatório antes/depois registrado.
- **FR-005**: O CI do `ai-scouting` DEVE rodar o conjunto em mudanças de chunking, prompt, retriever ou modelo.
- **FR-006**: Todo item DEVE fixar a data de referência da execução (ADR-013), para que o resultado não mude quando documentos forem revogados ou substituídos depois da curadoria.

### Key Entities

- **Scouting Golden Item**: pergunta, documentos esperados, resposta de referência, citações esperadas, data de referência (obrigatória em todo item).
- **Calibration Decision**: parâmetro, valores comparados, relatório, escolha, data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Linha de base registrada antes de qualquer mudança de calibração.
- **SC-002**: 100% das decisões de calibração têm relatório antes/depois.
- **SC-003**: A decisão de embedding é tomada com dados de pelo menos dois candidatos.

## Assumptions

- As perguntas vêm de dúvidas reais de escotistas e dirigentes, coletadas pelo mantenedor.
- A avaliação roda dentro de uma imagem de instalação que contém o `ai-core` e o `ai-scouting` (ex.: `ai-core eval run`); o `ai-scouting` continua dependendo só de `ai-core-contracts`.
- Faixas iniciais: 20–30 candidatos, 3–8 após rerank, 300–600 tokens para narrativo.
