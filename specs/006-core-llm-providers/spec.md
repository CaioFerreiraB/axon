# Feature Specification: Providers de LLM e modelo por papel

**Feature Branch**: `006-core-llm-providers`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §5 (`LLMProvider`), §16 (elo 6), §26 (providers e modelo por papel), §27 (Ollama e hardware alvo); ADR-008.

## Module Boundary *(mandatory)*

- **Módulo**: LLM Providers — implementações de provider e o roteador que resolve provider + modelo por papel, aplicando a allowlist do Assistant.
- **Repositório / distribuição**: `ai-core` → `ai_core/llm/` (providers em `adapters/`).
- **Consome (seams)**: contrato `LLMProvider` — 001; Execution Grant (política de modelos) — 003; Trace Sink — 009.
- **Expõe (seams)**: **Model Router** (`for_role(papel) → cliente de modelo`) — consumido por 005.
- **Depende de infraestrutura (via portas)**: provedores de modelo, local e remotos (adapters de `LLMProvider`); segredos (credenciais dos providers remotos).
- **Não conhece**: flows, packs, prompts, domínio.
- **Substituição**: preservar o Model Router e o contrato `LLMProvider`; providers podem ser adicionados ou trocados livremente (são adapters).
- **Insumo técnico**: [design.md](design.md); [ADR-008](../../docs/adr/ADR-008-modelo-por-papel.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Geração local em streaming (Priority: P1)

O motor pede ao roteador o modelo do papel `generation`; o roteador devolve um cliente para o provider local, que gera a resposta em streaming.

**Why this priority**: Fase 1 — a primeira conversa ponta a ponta usa modelo local.

**Independent Test**: Com o provider local no ar e um modelo pequeno disponível, gerar uma resposta em streaming e observar tokens incrementais.

**Acceptance Scenarios**:

1. **Given** um grant com `generation: ollama/qwen3:1.7b`, **When** o motor gera, **Then** os tokens chegam incrementalmente.
2. **Given** o provider local fora do ar, **When** o motor gera, **Then** recebe erro explícito que nomeia provider e modelo.

---

### User Story 2 - Modelo por papel (Priority: P1)

Cada Assistant declara modelos por papel — `controller`, `generation` e, opcionalmente, `rerank`. O roteador resolve cada papel de forma independente: o controller pode usar um modelo remoto forte e a geração, um modelo local.

**Why this priority**: ADR-008 — é o que torna viável o loop agêntico no hardware alvo.

**Independent Test**: Um grant com controller remoto e geração local; cada papel resolve para o provider certo.

**Acceptance Scenarios**:

1. **Given** `controller: openrouter/qwen/qwen3-8b` e `generation: ollama/qwen3:1.7b`, **When** o motor pede cada papel, **Then** recebe clientes de providers diferentes.
2. **Given** um papel não declarado (`rerank`), **When** pedido, **Then** o roteador informa "não configurado" em vez de escolher um modelo sozinho.

---

### User Story 3 - Providers externos com modelo explícito (Priority: P2)

Além do provider local, o sistema suporta OpenAI e OpenRouter. Modelos são sempre explícitos; variantes de roteamento automático de modelo são rejeitadas na validação do Assistant.

**Why this priority**: Fase 3 — controller remoto. Previsibilidade é requisito de avaliação.

**Independent Test**: Um Assistant com `openrouter/auto` falha na validação; com um modelo explícito, funciona.

**Acceptance Scenarios**:

1. **Given** um Assistant que declara modelo de roteamento automático, **When** validado, **Then** é rejeitado com mensagem explícita.

---

### User Story 4 - Saída estruturada para decisões de controle (Priority: P2)

O papel `controller` sempre chama o modelo com restrição de formato de saída. Se o provider/modelo não suporta a restrição, o roteador falha explicitamente — nunca degrada para texto livre.

**Why this priority**: Modelos pequenos não produzem JSON confiável sem constraint.

**Independent Test**: Chamar o papel controller com um esquema de ação; a resposta é sempre parseável segundo o esquema.

**Acceptance Scenarios**:

1. **Given** um esquema de ação, **When** o controller é chamado, **Then** a restrição de formato é enviada ao provider.
2. **Given** um provider sem suporte a restrição, **When** usado como controller, **Then** o erro é explícito.

---

### User Story 5 - Allowlist de provider e modelo (Priority: P2)

Todo modelo usado — o default do Assistant ou o escolhido na requisição — é conferido contra a allowlist do grant.

**Why this priority**: Elo 6 da cadeia de enforcement.

**Independent Test**: Uma requisição escolhe um modelo fora da allowlist e é rejeitada.

**Acceptance Scenarios**:

1. **Given** allowlist `["ollama/*"]`, **When** um papel resolveria para `openai/...`, **Then** a resolução é rejeitada como "modelo não permitido".

---

### User Story 6 - Métricas de uso por papel (Priority: P3)

Cada chamada informa ao trace provider, modelo, papel, tokens de entrada e saída, latência e tempo até o primeiro token.

**Why this priority**: Base para o benchmark de modelos e para a métrica "tokens por resposta" (009).

**Independent Test**: Após uma execução, o trace contém uma entrada por chamada de modelo com todos os campos.

**Acceptance Scenarios**:

1. **Given** uma execução agêntica, **When** concluída, **Then** o trace tem as chamadas de controller e de geração separadas por papel.

---

### Edge Cases

- Modelo declarado não disponível no provider local: erro explícito no health check e na primeira chamada.
- Provider remoto responde com limite de taxa: erro explícito; não há fallback automático para outro provider na v1.
- Stream interrompido pelo provider: o erro é propagado ao motor.
- Modelos gratuitos do OpenRouter: aceitos como fallback declarado, sem garantia de SLA.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE oferecer providers para Ollama (local), OpenAI e OpenRouter, todos cumprindo o contrato `LLMProvider`.
- **FR-002**: O roteador DEVE resolver provider e modelo por papel a partir da política do grant.
- **FR-003**: O roteador DEVE aplicar a allowlist de provider/modelo do grant a toda resolução.
- **FR-004**: Modelos de roteamento automático DEVEM ser rejeitados na validação.
- **FR-005**: O papel `controller` DEVE sempre usar restrição de formato de saída; ausência de suporte DEVE resultar em erro explícito.
- **FR-006**: Todos os providers DEVEM suportar streaming.
- **FR-007**: O sistema NÃO DEVE fazer fallback automático entre providers na v1.
- **FR-008**: Cada chamada DEVE emitir, pelo Trace Sink (009): provider, modelo, papel, tokens de entrada/saída, latência e tempo até o primeiro token.
- **FR-009**: O sistema DEVE oferecer verificação de saúde dos providers e modelos configurados.

### Key Entities

- **Model Policy**: modelo por papel + allowlist (vem do grant).
- **Model Role**: `controller`, `generation`, `rerank`.
- **Provider**: implementação de acesso a modelos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Trocar o modelo de qualquer papel de um Assistant exige só mudança de configuração, zero código.
- **SC-002**: 100% das chamadas de modelo são rastreáveis a (provider, modelo, papel).
- **SC-003**: 0 chamadas de controller sem restrição de formato de saída.
- **SC-004**: Adicionar um provider novo não exige mudança em nenhuma outra spec.

## Assumptions

- O provider local usa a camada compatível com OpenAI do Ollama, o que deixa sua implementação quase idêntica à do provider OpenAI.
- A escolha final de modelos (Qwen3 1.7B vs Gemma 4 E2B) é decidida por medição na spec 105/009, não aqui.
- Credenciais de providers externos vêm do ambiente ou do secret store do operador, por uma porta de segredos cujo adapter é escolhido pela composition root (011).
- Um provider simulado, também adapter de `LLMProvider`, atende o perfil de teste da 011.
