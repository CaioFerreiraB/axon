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

### Session 2026-10-27

Revisão do RAG ([docs/revisao-rag-scouting-2026-10.md](../../docs/revisao-rag-scouting-2026-10.md)): "Qual o marco
simbólico dos 5 ramos?" chegava à geração com a formulação de um ramo só, embora as cinco estejam no corpus.

- Q: Como medir que a informação **chegou** à geração, se a evidência da 009 casa por documento e o `EvalChunk` (contrato 001) não traz texto? → A: Pelo conteúdo: o item declara em `extra.facts` os fatos que precisam chegar — texto do corpus, com redações alternativas —, e a métrica do pack `scouting:fact_recall` acha cada fato no texto dos trechos entregues, que o `pack.py` lê do artefato do índice e injeta na métrica. Determinística; nenhuma mudança de contrato. Só existe com o índice em memória (FR-013).
- Q: O conjunto de regressão substitui a semente ou a curadoria? → A: Não. É um segundo arquivo (`eval/regression.yaml`), com linha de base própria, que cobre **padrões** que a revisão achou — o mesmo conceito por ramo, paráfrases, agregados ("cada ramo"), comparação e regras do POR — e diz se uma mudança estrutural (ingestão, seleção, prompt) melhorou ou piorou a recuperação. Nenhuma calibração numérica se decide sobre ele (FR-001 continua valendo).
- Q: Os PDFs do corpus saíram do git (decisão do mantenedor em 2026-10-26). Como o CI confere que o artefato espelha o corpus? → A: Pelo que o catálogo decide — o conjunto de documentos, os metadados, a vigência derivada da linhagem e a proveniência —, sem reingerir; a reingestão byte a byte fica com quem tem os originais. A semente troca o documento retirado (s08, s09) pelo Manual do Escotista — Ramo Lobinho, e a cobertura exige os tipos normativos, não todos os títulos do catálogo.

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

### User Story 6 - Regressão da recuperação por fato e por faceta (Priority: P1)

Cada mudança no corpus, na ingestão, na recuperação ou no prompt roda um conjunto de perguntas cujos fatos precisam
chegar aos trechos entregues à geração — uma pergunta por ramo, paráfrases, perguntas que pedem os cinco ramos, uma
comparação e regras do POR —, comparado com a linha de base.

**Why this priority**: A revisão do RAG de 2026-10-27 achou falhas que a semente não via (ela casa evidência por
documento, e nenhuma pergunta pedia várias facetas). Sem uma medida pelo conteúdo, as correções da 102, da 101 e da 103
não teriam como provar ganho nem como evitar piora.

**Independent Test**: O conjunto roda pelo harness da 009 no perfil `test`, com o artefato e o e5, e a métrica
`scouting:fact_recall` sai no relatório, por item e agregada; a linha de base registra o estado antes das correções.

**Acceptance Scenarios**:

1. **Given** um item cujos fatos estão em trechos entregues, **When** medido, **Then** `fact_recall` é 1; com metade
   dos fatos, 0,5; sem trecho entregue, 0.
2. **Given** um fato que nenhum trecho do artefato contém, **When** o conjunto é validado, **Then** a validação falha
   nomeando o item e o fato.
3. **Given** uma mudança que faz um fato deixar de chegar, **When** o CI roda, **Then** a regressão determinística
   barra o job.
4. **Given** uma mudança no catálogo sem reingestão, **When** o CI roda sem os PDFs, **Then** a conferência do
   artefato contra o catálogo falha.

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
- **FR-014**: O pack DEVE fornecer a métrica determinística `fact_recall`: a fração dos fatos que o item declara em `extra.facts` (texto, ou lista de redações alternativas) presentes, palavra a palavra depois da normalização da 101, no texto dos trechos entregues à geração; item sem `extra.facts` não conta. O texto vem do artefato do índice, lido pelo `pack.py` só quando uma rodada consulta a métrica; com o Qdrant, a métrica não é declarada.
- **FR-015**: O conjunto de regressão da recuperação (`eval/regression.yaml`) DEVE cobrir, para os mesmos conceitos, perguntas individuais por ramo, paráfrases, agregados com os cinco ramos, comparação e regras normativas (`extra.group`); todo fato DEVE existir no texto do artefato, validado sem o core; tem linha de base própria e roda no CI ao lado da semente.
- **FR-016**: Sem os PDFs no git, o CI DEVE conferir o artefato contra o catálogo — os mesmos documentos e, para cada um, metadados, vigência derivada da linhagem e proveniência —, no lugar da reingestão a partir dos originais (que continua sendo `axon-scouting-corpus ingest`, na máquina de quem os tem).

### Key Entities

- **Scouting Golden Item**: pergunta, documentos esperados, resposta de referência, citações esperadas, data de referência (obrigatória em todo item) e, em `extra.context`, o contexto esperado da derivação (opcional).
- **Calibration Decision**: parâmetro, valores comparados, relatório, escolha, data.
- **Regression Item**: pergunta, data de referência, grupo (`individual`, `agregado`, `comparativo`, `normativo`) e os fatos que precisam chegar à geração.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Linha de base registrada antes de qualquer mudança de calibração.
- **SC-002**: 100% das decisões de calibração têm relatório antes/depois.
- **SC-003**: A decisão de embedding é tomada com dados de pelo menos dois candidatos.
- **SC-004**: A linha de base do conjunto de regressão é registrada antes de qualquer correção estrutural do RAG (102, 101, 103), e cada correção mostra o `fact_recall` antes e depois.

## Assumptions

- As perguntas da versão curada vêm de dúvidas reais de escotistas e dirigentes, coletadas pelo mantenedor, depois do desenvolvimento; até lá vale a semente provisória (FR-001).
- A avaliação roda dentro de uma imagem de instalação que contém o `axon-ai` e o `axon-scouting` (ex.: `axon eval run`); o `axon-scouting` continua dependendo só de `axon-ai-contracts`. Na Fase 6 a CI e o mantenedor rodam pelo grupo `platform`; a imagem ganha o core com o harness numa passada de encaixe da 002 (research R9).
- Faixas iniciais: 20–30 candidatos, 3–8 após rerank, 300–600 tokens para narrativo.
