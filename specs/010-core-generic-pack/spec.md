# Feature Specification: Pack genérico de referência (`ai-generic`)

**Feature Branch**: `010-core-generic-pack`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §1 (escopo), §30 (`ai-generic`), Parte IX ("O papel do ai-generic"); ADR-004.

## Module Boundary *(mandatory)*

- **Módulo**: `ai-generic` — pack de uso geral e pack de referência: primeiro consumidor real dos contratos e fixture dos testes de carregamento de pack.
- **Repositório / distribuição**: `ai-core` → `packs/generic` (distribuição própria, descoberta por entry point como um pack externo).
- **Consome (seams)**: Contrato de pack — 001. Nada mais.
- **Expõe (seams)**: o pack `generic` (via entry point) — consumido por 002 (testes de carga) e por Assistants.
- **Depende de infraestrutura (via portas)**: nenhuma na v1. Se uma tool nativa fizer I/O, o cliente fica num adapter interno do pack, instanciado pelo `pack.py`.
- **Não conhece**: nada do core além dos contratos.
- **Substituição**: pode ser removido se virar apenas um Assistant (ver clarificação abaixo); nesse caso a fixture de carga passa a ser um pack mínimo de teste.
- **Insumo técnico**: [design.md](design.md); [ADR-004](../../docs/adr/ADR-004-contratos-no-repo-do-core.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

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
- **FR-004**: O pack DEVE ser testado contra os contratos do mesmo commit (sem faixa semver).
- **FR-005**: O pack DEVE existir como pack enquanto agregar algo além de prompts: [NEEDS CLARIFICATION: se, na Fase 3, o pack só contiver prompts, ele vira apenas um Assistant com `packs: []` e `packs/generic` sai do workspace? (arch-v1 Parte IX)]

### Key Entities

- **Generic Pack**: prompts gerais e, possivelmente, tools nativas simples.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 imports do core no pack, verificado no CI.
- **SC-002**: Os testes de carga do core usam o pack sem nenhum caso especial no código.

## Assumptions

- Até a decisão da Fase 3, o pack existe e é a fixture de carga.
