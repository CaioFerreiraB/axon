# Feature Specification: Trace por requisição e harness de avaliação

**Feature Branch**: `009-core-observability-evaluation`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §29 (trace, harness, métricas), §27 (benchmark de modelos), §31 Fase 6; ADR-007.

## Module Boundary *(mandatory)*

- **Módulo**: Observability & Evaluation — trace estruturado de cada execução e harness genérico que roda conjuntos dourados fornecidos por packs.
- **Repositório / distribuição**: `ai-core` → `ai_core/observability/` (Trace Sink e consulta de trace) e `ai_core/eval/` (harness).
- **Consome (seams)**: Execution Engine (eventos) — 005, pelo harness; `Chunk` — 001.
- **Expõe (seams)**: **Trace Sink** (porta de emissão de dados de trace por requisição) — consumido por 004, 005 e 006; **Trace** (consulta por identificador de requisição) — consumido por 008 e pelo operador; **Eval Harness** com o **formato de conjunto dourado** — consumidos pelo CI e por packs (ex.: 105).
- **Depende de infraestrutura (via portas)**: backend de trace (exporter), armazenamento de linhas de base, juiz LLM (só offline).
- **Não conhece**: domínio (métricas específicas de domínio são fornecidas pelo pack), flows internos (lê apenas eventos e dados de trace), quem emite dados de trace além do que chega pelo Trace Sink.
- **Substituição**: preservar o Trace Sink, o formato do conjunto dourado e o formato de relatório; o backend de trace pode ser trocado (é adapter).
- **Insumo técnico**: [design.md](design.md); [ADR-007](../../docs/adr/ADR-007-citacao-mecanica.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entender por que uma execução se comportou assim (Priority: P1)

Cada requisição produz um trace com: Assistant resolvido, packs ativos, tools em catálogo, cada iteração do controller e sua ação, cada tool executada com latência e status, chunks recuperados com score, tokens por papel, validators e seus resultados, erros.

**Why this priority**: Sem trace, depurar por que o controller escolheu determinada tool é adivinhação. Útil desde a Fase 1.

**Independent Test**: Executar uma requisição agêntica e responder, só pelo trace, qual tool foi chamada em cada iteração e por quê o loop terminou.

**Acceptance Scenarios**:

1. **Given** uma execução concluída, **When** o operador consulta o trace pelo identificador da requisição, **Then** vê todos os campos listados.
2. **Given** uma chamada de tool com credencial, **When** registrada no trace, **Then** a credencial não aparece.

---

### User Story 2 - Medir a qualidade com um conjunto dourado (Priority: P1)

O harness roda um conjunto dourado fornecido por um pack — perguntas, documentos que devem ser recuperados, resposta de referência e citações esperadas — contra um Assistant, e calcula métricas de recuperação, rerank, geração, citação e operação.

**Why this priority**: Fase 6, e pré-requisito de qualquer calibração (princípio X). Sem harness não há empiria.

**Independent Test**: Rodar um conjunto dourado mínimo de teste contra o pack de referência e obter um relatório com todas as métricas.

**Acceptance Scenarios**:

1. **Given** um conjunto dourado, **When** o harness roda, **Then** produz recall@k, MRR, ganho de rerank, fidelidade, cobertura, taxa de citação resolvível, taxa de citação inventada, latência p50/p95 e tokens por resposta.
2. **Given** um pack que fornece métricas de domínio adicionais, **When** o harness roda, **Then** elas aparecem no mesmo relatório.

---

### User Story 3 - Barrar regressões no CI (Priority: P2)

O harness roda em CI a cada mudança de chunking, prompt, retriever ou modelo, compara com a linha de base registrada e falha quando uma métrica determinística regride além da tolerância.

**Why this priority**: É o que responde se uma mudança melhorou ou piorou — de outro modo impossível num sistema RAG.

**Independent Test**: Introduzir uma regressão proposital no retriever de teste; o CI falha apontando a métrica.

**Acceptance Scenarios**:

1. **Given** uma linha de base, **When** uma mudança derruba o recall@k além da tolerância, **Then** o CI falha e mostra o delta.
2. **Given** métricas avaliadas por LLM (fidelidade), **When** variam, **Then** são reportadas com variância e não bloqueiam sozinhas.

---

### User Story 4 - Comparar modelos com as métricas que importam (Priority: P3)

O mesmo harness compara modelos candidatos em tokens/s, tempo até o primeiro token, RAM, CPU, qualidade em português, confiabilidade de tool calling e fidelidade em RAG.

**Why this priority**: As duas últimas métricas são as decisivas e não aparecem em benchmarks padrão.

**Independent Test**: Rodar o benchmark com dois modelos locais e obter relatório comparativo.

**Acceptance Scenarios**:

1. **Given** dois modelos, **When** o benchmark roda, **Then** o relatório compara todas as métricas lado a lado.

---

### Edge Cases

- Item do conjunto dourado que referencia documento fora do corpus: sinalizado como item inválido, não como falha do sistema.
- Juiz LLM indisponível: métricas determinísticas continuam; as de juiz ficam marcadas como ausentes.
- Trace de execução com conteúdo sensível do usuário: retenção limitada e configurável; credenciais nunca registradas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Cada requisição DEVE gerar um trace com os campos da US1, acessível pelo identificador da requisição.
- **FR-002**: O trace NÃO DEVE conter credenciais.
- **FR-003**: O harness DEVE definir um formato de conjunto dourado com: pergunta, documentos esperados, resposta de referência, citações esperadas e data de referência do item (ADR-013), para que itens datados sejam reproduzíveis.
- **FR-004**: O harness DEVE calcular as métricas das camadas recuperação, rerank, geração, citação e operação (tabela no design).
- **FR-005**: O harness DEVE aceitar métricas de domínio fornecidas por packs.
- **FR-006**: Julgamento por LLM PODE ser usado aqui (offline) e NÃO DEVE ser usado no caminho da requisição.
- **FR-007**: O harness DEVE registrar linhas de base e comparar execuções, com tolerância configurável por métrica.
- **FR-008**: O harness DEVE poder rodar em CI com saída que falha o pipeline em regressão de métrica determinística.
- **FR-009**: O harness DEVE suportar benchmark comparativo de modelos.
- **FR-010**: O módulo DEVE oferecer o Trace Sink: uma porta de emissão pela qual 004, 005 e 006 registram dados de trace com o identificador da requisição, sem conhecer o backend (ADR-013).
- **FR-011**: A falha do backend de trace NÃO DEVE interromper nem atrasar perceptivelmente a execução; dados perdidos são sinalizados.

### Key Entities

- **Trace Sink**: porta de emissão de dados de trace, consumida pelos módulos que produzem esses dados.
- **Trace**: registro estruturado de uma execução.
- **Golden Set / Golden Item**: conjunto dourado e seus itens.
- **Eval Run / Baseline**: execução do harness e linha de base de comparação.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Qualquer pergunta do tipo "por que o controller escolheu X" é respondida só com o trace, em menos de 5 minutos.
- **SC-002**: Uma rodada de 50 perguntas conclui em tempo compatível com rodar a cada PR relevante (meta: até 30 minutos).
- **SC-003**: 100% das regressões determinísticas acima da tolerância são barradas no CI.
- **SC-004**: Toda mudança de calibração tem relatório antes/depois.

## Assumptions

- O conteúdo dos conjuntos dourados é responsabilidade do pack de domínio (ex.: spec 105); o core fornece só formato e runner.
- Instrumentação de trace é incremental desde a Fase 1; o harness completo entra na Fase 6.
- Backend de trace (arquivo, Postgres ou ferramenta de observabilidade) é decidido no plano; é adapter do Trace Sink. Candidata para a porta: a API do OpenTelemetry, com SDK e exporter como adapters (ADR-013).
- Trace e harness estão em lados opostos do hexágono (porta secundária × adapter primário); dividi-los em duas specs é opcional e, se feito, segue "Como reescrever um módulo" em `specs/README.md`.
