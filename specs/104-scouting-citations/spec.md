# Feature Specification: Citações verificadas e aviso de vigência

**Feature Branch**: `104-scouting-citations`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §23 (citações e verificação mecânica), §22 ("Na resposta"), §8 (`validate_answer`); ADR-007.

## Module Boundary *(mandatory)*

- **Módulo**: Scouting Citations — validators determinísticos que garantem que toda citação existe no contexto da geração e que fontes não vigentes são sinalizadas.
- **Repositório / distribuição**: `axon-scouting` → `src/axon_scouting/validators/`.
- **Consome (seams)**: `AnswerValidator`, `ValidationResult` e Turn View — 001 (em especial o conjunto de chunks entregues à geração); modelo de chunk indexado (valores de status de vigência) — 102.
- **Expõe (seams)**: validators `citation_integrity` e `validity_notice` — consumidos pelo pack (101) e executados pelo core.
- **Depende de infraestrutura (via portas)**: nenhuma — validators são funções puras sobre a Turn View.
- **Não conhece**: como os chunks foram recuperados (103), o core, flows, modelos.
- **Substituição**: depende só do identificador de chunk e da Turn View; continua válido se o retrieval for trocado por GraphRAG, desde que os chunks/relações tenham identificador e proveniência.
- **Insumo técnico**: [design.md](design.md); [ADR-007](../../docs/adr/ADR-007-citacao-mecanica.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## Clarifications

### Session 2026-10-07

- Q: Na Fase 4, sem corpus, os validators `citation_integrity` e `validity_notice` já ficam ativos no pack `scouting`? → A: Não. Na Fase 4 os dois são implementados por completo e testados com fixtures de Turn View que trazem `generation_context` sintético; o `pack.py` (101) só os publica na Fase 5, junto com o retriever e a sintaxe de citação no prompt (FR-007; FR-010 da 101). Sem corpus, todas as respostas seriam "não fundamentadas", e o aviso repetiria o que o prompt da Fase 4 já manda dizer.
- Q: Citação válida de trecho com status de vigência vazio ou desconhecido conta como vigente (FR-004)? → A: Não. Só `vigente` dispensa aviso. Status vazio ou fora dos valores da 102 recebe o aviso "vigência não confirmada"; `revogado`, `substituído` e `rascunho` recebem o aviso nomeando documento e status (princípio VII).
- Q: Como as citações válidas aparecem no texto entregue: `[[id]]`, referência numerada ou fora do texto? → A: Cada citação válida vira `[n]`, numerada pela ordem da primeira aparição — a mesma ordem da lista de citações; a repetida reaproveita o número; as inválidas saem do texto. A lista estruturada (`citations`) traz a proveniência de cada `[n]`.
- Q: Com streaming, como a citação inventada deixa de chegar ao cliente (pendência R11)? → A: `citation_integrity` implementa `open_stream` (contratos `0.1.1`, ADR-024): segura o texto só enquanto um marcador `[[` pode estar aberto, com o espaço antes dele, e libera `[n]` ou nada quando ele fecha; `finish` é a validação em lote sobre a resposta inteira. `validity_notice` continua em lote — o aviso que ele acrescenta sai como token pelo motor.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Citação inventada nunca chega ao usuário (Priority: P1)

Toda citação emitida pelo modelo precisa corresponder a um trecho que esteve de fato no contexto daquela geração. Citação que não corresponde é removida e registrada.

**Why this priority**: Citação inventada é o modo de falha mais grave do domínio, porque é convincente. A checagem é mecânica e custa zero tokens.

**Independent Test**: Uma resposta com três citações, uma delas inventada; após validação, restam duas e o erro registra a removida.

**Acceptance Scenarios**:

1. **Given** uma resposta que cita um identificador ausente do contexto de geração, **When** validada, **Then** a citação é removida e registrada em erros.
2. **Given** uma citação a um chunk recuperado mas cortado do contexto por limite de tokens, **When** validada, **Then** é removida — só vale o que foi entregue à geração.

---

### User Story 2 - Resposta sem fundamento é marcada (Priority: P1)

Se nenhuma citação sobrevive à validação, a resposta é marcada como não fundamentada, de forma visível ao usuário.

**Why this priority**: O usuário precisa saber quando a resposta não se apoia no corpus.

**Independent Test**: Uma resposta cujas citações são todas inválidas recebe a marcação.

**Acceptance Scenarios**:

1. **Given** uma resposta sem citações válidas, **When** validada, **Then** recebe a marcação "não fundamentada" e um aviso visível.

---

### User Story 3 - Fonte não vigente sempre sinalizada (Priority: P1)

Quando uma citação válida aponta para documento não vigente (revogado ou substituído), a resposta precisa dizer isso explicitamente. Se o modelo não disse, o validator acrescenta o aviso padrão.

**Why this priority**: Citar norma revogada sem aviso é o pior erro possível neste domínio.

**Independent Test**: Uma resposta que cita a versão 2023 substituída sem aviso recebe o aviso padrão nomeando documento e status.

**Acceptance Scenarios**:

1. **Given** citação válida de documento `substituído`, **When** a resposta não contém o aviso, **Then** o validator acrescenta o aviso padrão.
2. **Given** a mesma situação com aviso já presente, **When** validada, **Then** a resposta não é duplicada.

---

### User Story 4 - Proveniência exibível (Priority: P2)

Cada citação sobrevivente carrega documento, versão, status, seção e página, para que a interface possa exibi-la.

**Why this priority**: Citação só é útil se o usuário puder conferir a fonte.

**Independent Test**: As citações do evento final contêm os cinco campos.

**Acceptance Scenarios**:

1. **Given** uma resposta validada, **When** entregue, **Then** cada citação traz documento, versão, status, seção e página.
2. **Given** um trecho citado cujo documento tem endereço público (`source_url`), **When** a resposta é validada, **Then** a citação traz `url` com o endereço e a página do trecho (`#page=N`), que a interface usa para abrir o original; sem endereço `http(s)`, a citação sai sem `url` (ADR-051).

---

### Edge Cases

- A mesma citação repetida: deduplicada na lista, mantida no texto com o mesmo número `[n]`.
- Trecho citado sem status de vigência (ou com status fora de `vigente`, `revogado`, `substituído`, `rascunho`): aviso de "vigência não confirmada" — nunca tratado como vigente.
- Identificador com variação de formatação (espaços, caixa): normalizado antes da comparação, segundo a sintaxe definida no design.
- Resposta que não usa a sintaxe de citação: tratada como sem citações → "não fundamentada".
- Validator nunca chama modelo (garantido pelo contrato 001: o contexto de validator não expõe modelos).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O validator de integridade DEVE extrair as citações da resposta segundo a sintaxe definida para o pack.
- **FR-002**: Cada citação DEVE ser comparada ao conjunto de identificadores entregues à geração (Turn View); as não correspondentes DEVEM ser removidas e registradas.
- **FR-003**: Sem citações válidas, a resposta DEVE receber a marcação "não fundamentada" e um aviso visível.
- **FR-004**: Citação válida de documento não vigente DEVE resultar em aviso explícito na resposta, acrescentado pelo validator quando ausente. Só o status `vigente` dispensa o aviso; status vazio ou desconhecido recebe o aviso de "vigência não confirmada" (clarificação de 2026-10-07).
- **FR-005**: As citações sobreviventes DEVEM carregar documento, versão, status, seção e página.
- **FR-009**: No texto entregue, cada citação válida DEVE aparecer como `[n]`, numerada pela ordem da primeira aparição e na mesma ordem da lista de citações (repetida reaproveita o número); marcadores de citação inválida DEVEM sair do texto (clarificação de 2026-10-07).
- **FR-006**: Os validators DEVEM ser determinísticos e não chamar modelos.
- **FR-008**: Na Fase 4 os validators DEVEM existir no pacote do pack, completos e testados com Turn Views sintéticas, e NÃO DEVEM ser publicados pelo pack; a publicação (pelo `pack.py` da 101) acontece na Fase 5, com a recuperação e a sintaxe de citação nas instruções (clarificação de 2026-10-07).
- **FR-007**: As instruções do pack (101) DEVEM ensinar ao modelo a sintaxe de citação.
- **FR-010**: A citação sobrevivente DEVE levar `url` (contratos `0.2.3`): o `source_url` dos metadados do trecho (102), só `http` ou `https` com host, com o fragmento `#page=N` quando o trecho tem página ([ADR-051](../../docs/adr/ADR-051-link-da-citacao-e-fontes-no-open-webui.md)). Sem endereço válido, a citação sai sem `url`.

### Key Entities

- **Citation**: identificador de chunk + proveniência + o link do original (`url`, FR-010).
- **Validity Notice**: texto padrão de aviso de fonte não vigente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 citações inventadas em respostas entregues (garantido mecanicamente; medido no harness).
- **SC-002**: 100% das respostas que citam fonte não vigente contêm o aviso.
- **SC-003**: A validação não adiciona atraso perceptível à resposta.

## Assumptions

- A distorção de um trecho realmente citado não é detectada aqui; é coberta pela métrica de fidelidade no harness offline (ADR-007).
- Se outro pack precisar da mesma verificação, ela pode ser promovida a utilitário reutilizável (decisão futura, via ADR).
