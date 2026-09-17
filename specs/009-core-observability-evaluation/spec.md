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

## Clarifications

### Session 2026-09-17

- Q: O seam Trace Sink é um contrato próprio do projeto ou a API do OpenTelemetry usada diretamente como porta? → A: Contrato próprio, com value objects do projeto — quem emite (004, 005, 006) importa apenas o seam deste módulo e nenhuma biblioteca de observabilidade. OpenTelemetry, se for adotado, entra como adapter do exporter, que é onde o backend pode ser trocado. Resolve a candidata em aberto do `design.md` e do ADR-013, preservando a semântica do seam.
- Q: Como os dados chegam ao Trace Sink? → A: Um único método de emissão que recebe um evento tipado; cada tipo de dado de trace é um value object publicado pelo módulo. Instrumentar um módulo novo é acrescentar um tipo de evento, sem alterar o seam — o que evita um ADR por fase, já que os emissores chegam em fases diferentes.
- Q: Quais tipos de evento existem na Fase 1, se tools, iterações do controller e recuperação só chegam nas Fases 3 e 5? → A: Apenas os dos módulos que existem na fase: execução iniciada e concluída (assistant, packs ativos, flow, desfecho), chamada de modelo (provider, modelo, papel, tokens, latência), execução de validator e erro. Os demais campos da US1 entram como tipos novos nas fases dos módulos que os produzem. Emitir é responsabilidade de quem produz o dado (005, 006 e, depois, 004); esta spec entrega o seam, os tipos, o exporter e a consulta.
- Q: Como o módulo garante que credencial nunca aparece no trace? → A: Em duas camadas — os tipos de evento não têm campo onde um segredo caiba, e o que é texto livre (hoje, a mensagem de erro) passa por redação antes de sair do processo: nomes de chave conhecidos em qualquer mapeamento e padrões de credencial no texto, substituídos por marcador. A regra é pura e testável sem backend.
- Q: Os eventos vão para o backend um a um, na hora, ou acumulados por requisição e gravados no fim? → A: Um a um, na hora, um evento por registro — o trace sobrevive a queda, travamento ou encerramento forçado no meio da execução, que é quando ele mais importa, e uma execução longa é observável enquanto corre. A consulta por identificador de requisição agrega os registros na leitura.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entender por que uma execução se comportou assim (Priority: P1)

Cada requisição produz um trace com: Assistant resolvido, packs ativos, tools em catálogo, cada iteração do controller e sua ação, cada tool executada com latência e status, chunks recuperados com score, tokens por papel, validators e seus resultados, erros. Cada campo aparece a partir da fase do módulo que o produz; na Fase 1, o trace cobre execução iniciada e concluída, chamada de modelo, execução de validator e erro (FR-001).

**Why this priority**: Sem trace, depurar por que o controller escolheu determinada tool é adivinhação. Útil desde a Fase 1.

**Independent Test**: Na Fase 1, executar uma conversa e responder, só pelo trace, qual modelo atendeu cada papel, quantos tokens custou, quais packs estavam ativos e como a execução terminou. A partir da Fase 3, a mesma pergunta sobre uma requisição agêntica: qual tool foi chamada em cada iteração e por que o loop terminou.

**Acceptance Scenarios**:

1. **Given** uma execução concluída, **When** o operador consulta o trace pelo identificador da requisição, **Then** vê os campos produzidos pelos módulos existentes, na ordem em que aconteceram.
2. **Given** um dado de trace que carrega credencial — mensagem de erro de provider na Fase 1, argumentos de tool a partir da Fase 3 —, **When** registrado, **Then** a credencial não aparece no trace, e sim um marcador de redação.
3. **Given** uma execução interrompida no meio (queda ou encerramento forçado), **When** o trace é consultado, **Then** os eventos já emitidos estão lá.

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

- **FR-001**: Cada requisição DEVE gerar um trace acessível pelo identificador da requisição, com os campos da US1 que os módulos existentes na fase produzem — na Fase 1: execução iniciada e concluída (assistant, packs ativos, flow, desfecho), chamada de modelo (provider, modelo, papel, tokens, latência), execução de validator e erro.
- **FR-002**: O trace NÃO DEVE conter credenciais: nenhum tipo de evento DEVE ter campo destinado a segredo, e todo texto livre e todo mapeamento de atributos DEVEM passar por redação de nomes de chave conhecidos e de padrões de credencial antes de sair do processo.
- **FR-003**: O harness DEVE definir um formato de conjunto dourado com: pergunta, documentos esperados, resposta de referência, citações esperadas e data de referência do item (ADR-013), para que itens datados sejam reproduzíveis.
- **FR-004**: O harness DEVE calcular as métricas das camadas recuperação, rerank, geração, citação e operação (tabela no design).
- **FR-005**: O harness DEVE aceitar métricas de domínio fornecidas por packs.
- **FR-006**: Julgamento por LLM PODE ser usado aqui (offline) e NÃO DEVE ser usado no caminho da requisição.
- **FR-007**: O harness DEVE registrar linhas de base e comparar execuções, com tolerância configurável por métrica.
- **FR-008**: O harness DEVE poder rodar em CI com saída que falha o pipeline em regressão de métrica determinística.
- **FR-009**: O harness DEVE suportar benchmark comparativo de modelos.
- **FR-010**: O módulo DEVE oferecer o Trace Sink: uma porta de emissão pela qual 004, 005 e 006 registram dados de trace com o identificador da requisição, sem conhecer o backend (ADR-013).
- **FR-011**: A falha do backend de trace NÃO DEVE interromper nem atrasar perceptivelmente a execução; dados perdidos são sinalizados.
- **FR-012**: Cada dado de trace DEVE ser entregue ao backend no momento da emissão, um registro por evento, de modo que o trace de uma execução interrompida permaneça consultável e uma execução em andamento seja observável.
- **FR-013**: O seam de emissão DEVE receber eventos tipados publicados por este módulo e NÃO DEVE expor tipos de biblioteca de observabilidade; acrescentar um tipo de evento NÃO DEVE alterar o seam.

### Key Entities

- **Trace Sink**: porta de emissão de dados de trace, consumida pelos módulos que produzem esses dados.
- **Trace Event**: um dado de trace tipado, publicado por este módulo; um tipo por espécie de acontecimento (execução, chamada de modelo, validação, erro, e adiante tool e recuperação).
- **Trace**: registro estruturado de uma execução — os eventos de um identificador de requisição, agregados na consulta.
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
- Backend de trace (arquivo, Postgres ou ferramenta de observabilidade) é decidido no plano; é adapter do exporter. A candidata "API do OpenTelemetry como porta" foi resolvida na clarificação de 2026-09-17: o seam é contrato próprio, e OpenTelemetry, se entrar, é adapter.
- Trace e harness estão em lados opostos do hexágono (porta secundária × adapter primário); dividi-los em duas specs é opcional e, se feito, segue "Como reescrever um módulo" em `specs/README.md`.
