# Feature Specification: Pack genérico de referência (`ai-generic`)

**Feature Branch**: `010-core-generic-pack`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §1 (escopo), §30 (`ai-generic`), Parte IX ("O papel do ai-generic"); ADR-004.

## Module Boundary *(mandatory)*

- **Módulo**: `ai-generic` — pack de uso geral e pack de referência: primeiro consumidor real dos contratos e fixture dos testes de carregamento de pack.
- **Repositório / distribuição**: `ai-core` → `packages/generic` (distribuição própria, descoberta por entry point como um pack externo).
- **Consome (seams)**: Contrato de pack — 001. Nada mais.
- **Expõe (seams)**: o pack `generic` (via entry point) — consumido por 002 (testes de carga) e por Assistants.
- **Depende de infraestrutura (via portas)**: nenhuma na v1. Se uma tool nativa fizer I/O, o cliente fica num adapter interno do pack, instanciado pelo `pack.py`.
- **Não conhece**: nada do core além dos contratos.
- **Substituição**: pode ser removido se virar apenas um Assistant (ver clarificação abaixo); nesse caso a fixture de carga passa a ser um pack mínimo de teste.
- **Insumo técnico**: [design.md](design.md); [ADR-004](../../docs/adr/ADR-004-contratos-no-repo-do-core.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## Clarifications

### Session 2026-09-17

- Q: Quais capacidades o pack oferece na v1 (Fase 1)? → A: `system_prompt` de uso geral, uma tool nativa determinística (sem I/O) e um validator determinístico — três hooks de catálogo mais o `manifest()`, exercitados pela suíte de conformidade e pela carga real da 002. Sem `prepare_context`, sem retriever e sem reranker na v1; como não há I/O, o pack não declara porta secundária.
- Q: Como o pack declara a dependência de `ai-core-contracts`? → A: Pela faixa derivada da `contract_version` (`>=0.1,<0.2`, ADR-014), com `[tool.uv.sources] ai-core-contracts = { workspace = true }` para resolver no commit local enquanto o pack mora no workspace — o mesmo que um pack externo declara. Supera a redação "sem faixa semver" da FR-004 e a linha correspondente do `design.md`, que precedem o ADR-014 e a etapa 9 da suíte de conformidade.
- Q: O que o manifest declara na v1, além de nome e versão? → A: Nada — sem flow preferido, sem schema de configuração, sem dependências de pack e sem coleções exigidas. O Assistant escolhe o flow; a preferência por flow agêntico só faz sentido na Fase 3, quando esse flow existir (US2).
- Q: Onde vive o teste que prova a descoberta e a carga do pack real por entry point? → A: Nos testes de integração do core (o pack entra como dependência de desenvolvimento do workspace e é carregado pelo mecanismo de entry point, sem caso especial), enquanto a suíte de conformidade roda nos testes do próprio pack, sem tocar no core. O pack continua sem conhecer o core: a verificação de fronteiras cobre o código, não as dependências de teste.
- Q: Em que pasta do workspace mora a distribuição do pack? → A: Ao lado das outras distribuições do workspace, no mesmo padrão de pasta já usado por contratos e core — sem mudança na declaração de membros do workspace. Supera a linha de localização do `design.md`, escrita antes de o workspace existir. A fronteira com o core continua a ser provada pela verificação de imports, não pela posição da pasta.

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

O pack oferece prompts de uso geral e é a base do Assistant genérico que usa MCPs (ex.: finanças, drive) no flow `agentic`.

**Why this priority**: Fase 3, junto do loop agêntico e do MCP.

**Independent Test**: Um Assistant com `packs: [generic]` e um MCP de teste responde usando uma tool do MCP.

**Acceptance Scenarios**:

1. **Given** um Assistant com o pack genérico e um MCP, **When** o usuário pede algo que exige a tool, **Then** a resposta usa o resultado da tool.

---

### Edge Cases

- Pack genérico desabilitado: testes de carga usam o pack mínimo de teste; nada no core depende dele.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O pack DEVE depender apenas da distribuição de contratos.
- **FR-002**: O pack DEVE ser descoberto por entry point, sem registro especial no core.
- **FR-003**: O pack DEVE passar na suíte de conformidade de pack publicada com os contratos.
- **FR-004**: O pack DEVE declarar a dependência de contratos pela faixa derivada da própria `contract_version` (ADR-014) e, enquanto morar no workspace do core, resolvê-la no commit local — de modo que a etapa de distribuição da suíte de conformidade passe sem exceção.
- **FR-005**: O pack DEVE existir como pack enquanto agregar algo além de prompts: [NEEDS CLARIFICATION: se, na Fase 3, o pack só contiver prompts, ele vira apenas um Assistant com `packs: []` e `packages/generic` sai do workspace? (arch-v1 Parte IX)]
- **FR-006**: O pack DEVE oferecer, na v1, prompt de sistema de uso geral, uma tool nativa determinística e um validator determinístico; NÃO DEVE fazer I/O nem declarar porta secundária.
- **FR-007**: O manifest do pack NÃO DEVE declarar flow preferido, schema de configuração, dependências de pack nem coleções exigidas na v1.

### Key Entities

- **Generic Pack**: prompt de sistema de uso geral, uma tool nativa determinística e um validator determinístico (v1).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 imports do core no pack, verificado no CI.
- **SC-002**: Os testes de integração do core carregam o pack pelo mecanismo de entry point, sem nenhum caso especial no código do core.

## Assumptions

- Até a decisão da Fase 3, o pack existe e é a fixture de carga.
