# Feature Specification: Conjunto dourado e calibração do domínio escoteiro

**Feature Branch**: `105-scouting-evaluation`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §29 (conjunto dourado, começar pequeno), §21 (números a calibrar), §27 (benchmark de modelos), Parte IX (embedding, calibração), §31 Fase 6.

## Module Boundary *(mandatory)*

- **Módulo**: Scouting Evaluation — conteúdo do conjunto dourado do domínio, métricas de domínio e as decisões de calibração tomadas com base nele.
- **Repositório / distribuição**: `axon-scouting` → `src/axon_scouting/eval/`.
- **Consome (seams)**: Eval Harness e formato de conjunto dourado — 009; o Assistant `scouting` ponta a ponta, pelo harness em processo sobre o Execution Engine — o único caminho que fixa a data de referência (008 FR-012) — sem conhecer internals.
- **Expõe (seams)**: conjunto dourado versionado e métricas de domínio (ex.: taxa de documento vigente) — consumidos pelo harness (009) e pelo CI do `axon-scouting`.
- **Depende de infraestrutura (via portas)**: nenhuma além do Eval Harness (009), que executa os itens.
- **Não conhece**: implementação de retrieval, chunking ou flows — mede comportamento, não estrutura.
- **Substituição**: o conjunto dourado sobrevive a qualquer reescrita do pack — é justamente o que prova que a reescrita não piorou.
- **Insumo técnico**: [design.md](design.md); [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

## Clarifications

### Session 2026-10-13

- Q: Com a curadoria e a calibração adiadas pelo mantenedor, o que a 105 entrega agora, antes do conjunto dourado curado? → A: A infraestrutura — métricas de domínio no pack, validação do conjunto contra o catálogo do corpus, o comando de avaliação e o CI — com um **conjunto semente provisório** de 8 a 12 perguntas escritas a partir dos documentos do corpus, marcado como provisório e sem nenhuma decisão de calibração tomada sobre ele. A US2 registra a linha de base da semente; as US3–US5 (calibração, embedding, modelo local) esperam a curadoria, que substitui a semente pelas 30–50 perguntas reais.
- Q: O que o CI do `axon-scouting` roda com o conjunto de avaliação, e quando? → A: Um job `eval` disparado quando mudam `corpus/`, `rag/`, `prompts/`, `pack.py`, `eval/` ou as dependências: Qdrant de serviço, e5 em cache por sha256, ingestão do corpus real e `axon eval run` com o gerador simulado do perfil `test` (sem modelo pago, sem juiz), comparando com a linha de base da semente — só as métricas determinísticas barram.
- Q: Como o pack mede o "acerto da derivação de contexto" (ramo, temas, tipos de documento e vigência da 101), se o harness só vê o que a execução produziu? → A: O item declara o esperado em `extra.context` (ramo, temas, tipos, vigência — só os campos declarados contam); a métrica do pack refaz a derivação pura da 101 para a pergunta e a data do item e devolve a fração de campos que casam; item sem `extra.context` não conta. Métrica determinística; nenhuma mudança no core.

### Session 2026-10-21

- Q: Como se compara o `pplx` ao `e5` ([ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md), item 7)? → A: Pelo mesmo conjunto dourado, numa rodada por modelo — `eval/packs.yaml` (e5) e `eval/packs-pplx.yaml` (pplx, com `AXON_SCOUTING_EMBEDDING_API_KEY`) — e `axon eval compare` dos dois relatórios, pelas métricas determinísticas (recall@k, MRR). O embedder é configuração do pack, que vale para a instalação inteira; por isso são duas rodadas com o mesmo Assistant, e não dois Assistants na mesma plataforma. O default só muda depois disso.
- Q: A linha de base muda com o índice em memória? → A: Não: o artefato em memória dá os mesmos números do Qdrant no conjunto semente (as mesmas fórmulas), e o workflow `eval` deixa de subir um Qdrant e de ingerir.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conjunto dourado de perguntas reais (Priority: P1)

O mantenedor cura 30–50 perguntas reais do domínio, cada uma com os documentos que devem ser recuperados, uma resposta de referência e as citações esperadas. O conjunto é versionado junto do pack.

**Why this priority**: Fase 6, antes de calibrar qualquer número. 30–50 perguntas reais valem mais que 500 sintéticas.

**Independent Test**: O harness valida o formato do conjunto e todos os documentos referenciados existem no corpus. Nesta fase, sobre o conjunto semente provisório; a curadoria troca o conteúdo, não o formato nem a validação.

**Acceptance Scenarios**:

1. **Given** o conjunto dourado, **When** validado, **Then** cada item tem pergunta, documentos esperados, resposta de referência e citações esperadas, e referencia só documentos do corpus.
2. **Given** perguntas históricas no conjunto, **When** validado, **Then** elas marcam a data de referência esperada.

---

### User Story 2 - Linha de base registrada (Priority: P1)

A primeira rodada do harness com o conjunto dourado registra a linha de base de todas as métricas, incluindo as de domínio: taxa de documento vigente, acerto da derivação de contexto (101), taxa de citação resolvível e inventada.

**Why this priority**: Sem linha de base, não há como saber se uma mudança melhorou ou piorou.

**Independent Test**: A linha de base existe e é comparável com uma segunda rodada. Nesta fase, é a linha de base da semente — refeita quando a curadoria chegar.

**Acceptance Scenarios**:

1. **Given** o pipeline RAG completo, **When** o harness roda pela primeira vez, **Then** a linha de base de todas as métricas fica registrada.

---

### User Story 3 - Calibração guiada por medição (Priority: P2)

> Adiada até o conjunto curado (clarificação de 2026-10-13): calibrar sobre a semente provisória seria ajustar números a
> perguntas que ninguém fez.

Os números do RAG — candidatos, trechos após rerank, tamanho e sobreposição de chunk, limiar do portão de cobertura — são fixados a partir de rodadas comparativas, cada uma com relatório antes/depois.

**Why this priority**: Princípio X: calibrar sem medir é adivinhar.

**Independent Test**: Uma alteração de limiar do portão gera relatório com delta nas métricas.

**Acceptance Scenarios**:

1. **Given** duas configurações de tamanho de chunk, **When** comparadas, **Then** o relatório mostra o delta por métrica e a escolha fica registrada.

---

### User Story 4 - Escolha do modelo de embedding (Priority: P2)

> Adiada até o conjunto curado (clarificação de 2026-10-13).

Os candidatos de embedding para português são comparados com o conjunto dourado, considerando qualidade e custo no hardware alvo; a escolha é registrada.

**Why this priority**: Uma das decisões que mais afetam a qualidade final, e ainda em aberto.

**Independent Test**: Relatório comparativo dos candidatos com recall@k e custo de ingestão.

**Acceptance Scenarios**:

1. **Given** dois ou mais modelos de embedding, **When** comparados, **Then** o relatório mostra recall@k, MRR e custo, e a decisão é registrada.

---

### User Story 5 - Escolha do modelo de linguagem local (Priority: P3)

> Adiada até o conjunto curado (clarificação de 2026-10-13).

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

- **FR-001**: O conjunto dourado DEVE seguir o formato do harness (009) e ter entre 30 e 50 perguntas reais na primeira versão curada. Até a curadoria, um **conjunto semente provisório** de 8 a 12 perguntas, escritas a partir dos documentos do corpus e marcadas como provisórias no próprio arquivo, prova o pipeline e alimenta o CI; nenhuma decisão de calibração DEVE ser tomada sobre a semente (clarificação de 2026-10-13).
- **FR-002**: O conjunto DEVE incluir perguntas de consulta histórica e de fontes normativas.
- **FR-003**: O pack DEVE fornecer as métricas de domínio, pelo hook `eval_metrics` do contrato 001 (ADR-027): taxa de documento vigente e acerto da derivação de contexto. O acerto da derivação compara o contexto esperado que o item declara em `extra.context` (ramo, temas, tipos de documento, vigência; só os campos declarados) com a derivação da 101 refeita para a pergunta e a data do item, e vale a fração de campos que casam; item sem `extra.context` não conta.
- **FR-004**: Toda decisão de calibração DEVE ter relatório antes/depois registrado.
- **FR-005**: O CI do `axon-scouting` DEVE rodar o conjunto em mudanças de chunking, prompt, retriever ou modelo — um job disparado por mudanças em `corpus/`, `rag/`, `prompts/`, `pack.py`, `eval/` ou nas dependências, com Qdrant de serviço, o e5 em cache por sha256, a ingestão do corpus real e o gerador simulado do perfil `test` (sem modelo pago nem juiz), comparando com a linha de base; só as métricas determinísticas barram. Rodadas com modelo real e juiz são manuais.
- **FR-006**: Todo item DEVE fixar a data de referência da execução (ADR-013), para que o resultado não mude quando documentos forem revogados ou substituídos depois da curadoria.
- **FR-013**: A avaliação DEVE rodar sobre o artefato do índice em memória, sem serviço, e oferecer a configuração da rodada com o embedder `pplx`, para a comparação dos modelos por `axon eval compare`.

### Key Entities

- **Scouting Golden Item**: pergunta, documentos esperados, resposta de referência, citações esperadas, data de referência (obrigatória em todo item) e, em `extra.context`, o contexto esperado da derivação (opcional).
- **Calibration Decision**: parâmetro, valores comparados, relatório, escolha, data.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Linha de base registrada antes de qualquer mudança de calibração.
- **SC-002**: 100% das decisões de calibração têm relatório antes/depois.
- **SC-003**: A decisão de embedding é tomada com dados de pelo menos dois candidatos.

## Assumptions

- As perguntas da versão curada vêm de dúvidas reais de escotistas e dirigentes, coletadas pelo mantenedor, depois do desenvolvimento; até lá vale a semente provisória (FR-001).
- A avaliação roda dentro de uma imagem de instalação que contém o `axon-ai` e o `axon-scouting` (ex.: `axon eval run`); o `axon-scouting` continua dependendo só de `axon-ai-contracts`. Na Fase 6 a CI e o mantenedor rodam pelo grupo `platform`; a imagem ganha o core com o harness numa passada de encaixe da 002 (research R9).
- Faixas iniciais: 20–30 candidatos, 3–8 após rerank, 300–600 tokens para narrativo.
