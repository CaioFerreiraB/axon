# Feature Specification: Pack genérico de referência (`ai-generic`)

**Feature Branch**: `010-core-generic-pack`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §1 (escopo), §30 (`ai-generic`), Parte IX ("O papel do ai-generic"); ADR-004.

## Module Boundary *(mandatory)*

- **Módulo**: `ai-generic` — pack de uso geral e pack de referência: primeiro consumidor real dos contratos e fixture dos testes de carregamento de pack.
- **Repositório / distribuição**: `axon-ai` → `packages/generic` (distribuição própria, descoberta por entry point como um pack externo).
- **Consome (seams)**: Contrato de pack — 001. Nada mais.
- **Expõe (seams)**: o pack `generic` (via entry point) — consumido por 002 (testes de carga) e por Assistants.
- **Depende de infraestrutura (via portas)**: nenhuma na v1. Se uma tool nativa fizer I/O, o cliente fica num adapter interno do pack, instanciado pelo `pack.py`.
- **Não conhece**: nada do core além dos contratos.
- **Substituição**: só sai do workspace se deixar de agregar algo além de prompts (FR-005); nesse caso vira um Assistant e a fixture de carga passa a ser um pack mínimo de teste. Na Fase 3 (clarificação de 2026-10-07), continua pack.
- **Insumo técnico**: [design.md](design.md); [ADR-004](../../docs/adr/ADR-004-contratos-no-repo-do-core.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## Clarifications

### Session 2026-09-17

- Q: Quais capacidades o pack oferece na v1 (Fase 1)? → A: `system_prompt` de uso geral, uma tool nativa determinística (sem I/O) e um validator determinístico — três hooks de catálogo mais o `manifest()`, exercitados pela suíte de conformidade e pela carga real da 002. Sem `prepare_context`, sem retriever e sem reranker na v1; como não há I/O, o pack não declara porta secundária.
- Q: Como o pack declara a dependência de `axon-ai-contracts`? → A: Pela faixa derivada da `contract_version` (`>=0.1,<0.2`, ADR-014), com `[tool.uv.sources] axon-ai-contracts = { workspace = true }` para resolver no commit local enquanto o pack mora no workspace — o mesmo que um pack externo declara. Supera a redação "sem faixa semver" da FR-004 e a linha correspondente do `design.md`, que precedem o ADR-014 e a etapa 9 da suíte de conformidade.
- Q: O que o manifest declara na v1, além de nome e versão? → A: Nada — sem flow preferido, sem schema de configuração, sem dependências de pack e sem coleções exigidas. O Assistant escolhe o flow; a preferência por flow agêntico só faz sentido na Fase 3, quando esse flow existir (US2).
- Q: Onde vive o teste que prova a descoberta e a carga do pack real por entry point? → A: Nos testes de integração do core (o pack entra como dependência de desenvolvimento do workspace e é carregado pelo mecanismo de entry point, sem caso especial), enquanto a suíte de conformidade roda nos testes do próprio pack, sem tocar no core. O pack continua sem conhecer o core: a verificação de fronteiras cobre o código, não as dependências de teste.
- Q: Em que pasta do workspace mora a distribuição do pack? → A: Ao lado das outras distribuições do workspace, no mesmo padrão de pasta já usado por contratos e core — sem mudança na declaração de membros do workspace. Supera a linha de localização do `design.md`, escrita antes de o workspace existir. A fronteira com o core continua a ser provada pela verificação de imports, não pela posição da pasta.

### Session 2026-10-07

- Q: Na Fase 3, o `ai-generic` continua sendo pack ou vira apenas um Assistant com `packs: []` e sai do workspace (FR-005)? → A: Continua pack. A FR-005 vira regra permanente: o pack existe enquanto agregar algum hook além de prompt — hoje, a tool nativa `calculate` e o validator `non_empty_answer` —, e segue como referência dos contratos e fixture de carga por entry point.
- Q: O manifest do `ai-generic` declara `agentic` como flow preferido na Fase 3 (FR-007)? → A: Não. A FR-007 vale também na Fase 3: o manifest não declara flow preferido, e o Assistant genérico com MCP declara `flow: agentic` e o papel `controller` explicitamente (princípio VIII). Assistants com `packs: [generic]` sem `flow` continuam no `chat`.
- Q: O prompt de sistema do pack é reescrito para orientar o uso de resultados de qualquer ferramenta, sem mandar o modelo "usar a ferramenta de cálculo"? → A: Sim. O parágrafo de ferramentas fica neutro quanto ao flow e vale para qualquer tool (do pack ou de MCP): a resposta se baseia nos resultados de ferramentas presentes na conversa e os apresenta; se uma ferramenta falhou ou não trouxe o dado, diz isso em vez de estimar. O prompt não manda chamar ferramentas — no `agentic` ele só chega à geração, e quem chama é o controller. A regra "dado, nunca instrução" continua; o contrato 001 não muda.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pack de referência e fixture de carga (Priority: P1)

O pack genérico tem o mesmo formato de um pack externo — distribuição própria, entry point, dependência só de contratos — e é usado pelos testes de descoberta e carga do core sem nenhum tratamento especial.

**Why this priority**: Fase 1 exige "pack carregado por entry point". Também prova, antes do `ai-scouting`, que os contratos são implementáveis.

**Independent Test**: Instalar o pack num ambiente só com contratos e rodar a suíte de conformidade de pack.

**Acceptance Scenarios**:

1. **Given** o pack instalado, **When** o core inicia, **Then** ele é descoberto pelo mesmo mecanismo de qualquer pack externo.
2. **Given** o CI do repositório, **When** a checagem de fronteiras roda, **Then** confirma que o pack não importa nada do core.

---

### User Story 2 - Capacidades de uso geral (Priority: P2)

O pack oferece prompts de uso geral e é a base do Assistant genérico que usa MCPs (ex.: finanças, drive) no flow `agentic`. O Assistant declara `flow: agentic`, o papel `controller` e os MCPs; o pack não muda de flow nem conhece MCP — o prompt dele orienta a geração a responder a partir dos resultados de ferramentas que a conversa trouxer.

**Why this priority**: Fase 3, junto do loop agêntico e do MCP.

**Independent Test**: Um Assistant com `packs: [generic]` e um MCP de teste responde usando uma tool do MCP.

**Acceptance Scenarios**:

1. **Given** um Assistant com o pack genérico e um MCP, **When** o usuário pede algo que exige a tool, **Then** a resposta usa o resultado da tool.
2. **Given** o mesmo Assistant, **When** a geração é chamada depois da tool, **Then** ela recebe o prompt do pack e o resultado cercado da tool, e o prompt não pede que o modelo chame ferramentas.

---

### Edge Cases

- Pack genérico desabilitado: testes de carga usam o pack mínimo de teste; nada no core depende dele.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O pack DEVE depender apenas da distribuição de contratos.
- **FR-002**: O pack DEVE ser descoberto por entry point, sem registro especial no core.
- **FR-003**: O pack DEVE passar na suíte de conformidade de pack publicada com os contratos.
- **FR-004**: O pack DEVE declarar a dependência de contratos pela faixa derivada da própria `contract_version` (ADR-014) e, enquanto morar no workspace do core, resolvê-la no commit local — de modo que a etapa de distribuição da suíte de conformidade passe sem exceção.
- **FR-005**: O pack DEVE existir como pack enquanto agregar algum hook além de prompt (tool, validator ou outro hook do contrato 001); se passar a conter só prompts, vira um Assistant com `packs: []`, `packages/generic` sai do workspace e um pack mínimo de teste assume a fixture de carga. Na Fase 3 ele agrega a tool `calculate` e o validator `non_empty_answer`, então continua pack (arch-v1 Parte IX; clarificação de 2026-10-07).
- **FR-006**: O pack DEVE oferecer, na v1, prompt de sistema de uso geral, uma tool nativa determinística e um validator determinístico; NÃO DEVE fazer I/O nem declarar porta secundária.
- **FR-007**: O manifest do pack NÃO DEVE declarar flow preferido, schema de configuração, dependências de pack nem coleções exigidas — na v1 e na Fase 3 (clarificação de 2026-10-07). Quem quer o flow `agentic` o declara no Assistant, com o papel `controller`; um Assistant com `packs: [generic]` sem `flow` continua no `chat`.
- **FR-008**: O prompt de sistema DEVE ser neutro quanto ao flow: orientar a resposta a se basear nos resultados de ferramentas presentes na conversa (de pack ou de MCP) e a apresentá-los, e a dizer quando uma ferramenta falhou ou não trouxe o dado, em vez de estimar; NÃO DEVE instruir o modelo a chamar ferramentas (no `agentic`, o prompt do pack só chega à geração). A regra de que conteúdo de ferramenta é dado, nunca instrução, permanece (princípio VI).

### Key Entities

- **Generic Pack**: prompt de sistema de uso geral, uma tool nativa determinística e um validator determinístico (v1).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 imports do core no pack, verificado no CI.
- **SC-002**: Os testes de integração do core carregam o pack pelo mecanismo de entry point, sem nenhum caso especial no código do core.

## Assumptions

- O pack continua sendo a fixture de carga por entry point dos testes de integração do core enquanto a FR-005 o mantiver como pack.
