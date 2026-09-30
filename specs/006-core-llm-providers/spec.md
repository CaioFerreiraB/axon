# Feature Specification: Providers de LLM e modelo por papel

**Feature Branch**: `006-core-llm-providers`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §5 (`LLMProvider`), §16 (elo 6), §26 (providers e modelo por papel), §27 (Ollama e hardware alvo); ADR-008.

## Module Boundary *(mandatory)*

- **Módulo**: LLM Providers — implementações de provider e o roteador que resolve provider + modelo por papel, aplicando a allowlist do Assistant.
- **Repositório / distribuição**: `ai-core` → `ai_core/llm/` (providers em `adapters/`).
- **Consome (seams)**: contrato `LLMProvider` — 001; Trace Sink — 009. A política de modelos chega pronta, como `ModelPolicy` deste módulo: montada pela 011 na Fase 1 e pela 003, dentro do Execution Grant, a partir da Fase 2 ([ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)).
- **Expõe (seams)**: **Model Router** (`for_execution(política, requisição)` → `for_role(papel) → cliente de modelo`, mais a verificação de saúde) — consumido por 005 e, para saúde e montagem, pela composition root (011).
- **Depende de infraestrutura (via portas)**: provedores de modelo, local e remotos (adapters de `LLMProvider`); segredos (credenciais dos providers remotos).
- **Não conhece**: flows, packs, prompts, domínio.
- **Substituição**: preservar o Model Router e o contrato `LLMProvider`; providers podem ser adicionados ou trocados livremente (são adapters).
- **Insumo técnico**: [design.md](design.md); [ADR-008](../../docs/adr/ADR-008-modelo-por-papel.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

## Clarifications

### Session 2026-09-18

- Q: Na Fase 1 o Execution Grant (003) ainda não existe. De onde o roteador tira a política de modelos por papel? → A: A política é um value object publicado no `api.py` deste módulo (**Model Policy**: modelo por papel + allowlist), com que o roteador é construído. Na Fase 1 quem o monta a partir da configuração do operador é a composition root (011); a partir da Fase 2 a própria 006 o deriva do Execution Grant, o que preserva a direção 006 → 003 do grafo de dependências e mantém o seam inalterado entre as fases. O roteador continua puro e testável sem 003. *(Superada em parte pelo [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md): quem monta a política a partir da Fase 2 é a 003, dentro do grant, e a seta passa a 003 → 006; o seam continua inalterado.)*
- Q: Quem emite o evento de chamada de modelo no Trace Sink, e o tempo até o primeiro token entra já na Fase 1? → A: Emite o cliente devolvido pelo roteador, que instrumenta a própria chamada — assim nenhum consumidor precisa lembrar de medir e SC-002 vale por construção. Na Fase 1 vão provider, modelo, papel, tokens e latência, que é o que o evento `ModelCall` da 009 já carrega; o tempo até o primeiro token entra com a US6 (Fase 3) como campo aditivo na 009, sem editar aquela spec fora da fase dela.
- Q: Como o adapter do provider local fala com o Ollama? → A: Pelo SDK oficial da OpenAI em modo assíncrono, com o endereço base apontando para a camada compatível do Ollama, como o `design.md` prevê. Streaming, tool calls e restrição de formato de saída vêm prontos, e os adapters de OpenAI e OpenRouter (Fase 3) reaproveitam quase tudo. O SDK fica confinado a `adapters/` (princípio XIII).
- Q: A verificação de saúde dos providers (FR-009) entra na Fase 1? → A: Sim, sob demanda — pergunta ao provider se o modelo declarado existe e responde disponível/indisponível com o motivo. Nunca é etapa bloqueante do boot: a plataforma sobe sem o provider local no ar (inclusive na suíte de testes) e o erro aparece na consulta de saúde e na primeira chamada.
- Q: No hardware alvo uma geração legítima leva minutos. Que timeout distingue isso de um stream travado? → A: Dois prazos por provider, ambos configuráveis: timeout de conexão, curto (provider fora do ar falha em segundos), e timeout de inatividade entre pedaços do stream. Não há teto de tempo total — resposta longa e saudável nunca é cortada, e stream travado falha com erro que nomeia provider e modelo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Geração local em streaming (Priority: P1)

O motor pede ao roteador o modelo do papel `generation`; o roteador devolve um cliente para o provider local, que gera a resposta em streaming.

**Why this priority**: Fase 1 — a primeira conversa ponta a ponta usa modelo local.

**Independent Test**: Com o provider local no ar e um modelo pequeno disponível, gerar uma resposta em streaming e observar tokens incrementais.

**Acceptance Scenarios**:

1. **Given** uma Model Policy com `generation: ollama/qwen3:1.7b`, **When** o motor gera, **Then** os tokens chegam incrementalmente.
2. **Given** o provider local fora do ar, **When** o motor gera, **Then** recebe erro explícito que nomeia provider e modelo.

---

### User Story 2 - Modelo por papel (Priority: P1)

Cada Assistant declara modelos por papel — `controller`, `generation` e, opcionalmente, `rerank`. O roteador resolve cada papel de forma independente: o controller pode usar um modelo remoto forte e a geração, um modelo local.

**Why this priority**: ADR-008 — é o que torna viável o loop agêntico no hardware alvo.

**Independent Test**: Uma Model Policy com controller remoto e geração local; cada papel resolve para o provider certo.

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

Todo modelo usado — o default do Assistant ou o escolhido na requisição — é conferido contra a allowlist da Model Policy (que chega no grant).

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

- Modelo declarado não disponível no provider local: erro explícito na verificação de saúde e na primeira chamada.
- Provider fora do ar quando a saúde é verificada: a verificação relata indisponível com o motivo, sem impedir o boot.
- Provider remoto responde com limite de taxa: erro explícito; não há fallback automático para outro provider na v1.
- Stream interrompido pelo provider: o erro é propagado ao motor.
- Stream que para de entregar pedaços sem fechar: o timeout de inatividade encerra a chamada com erro explícito.
- Modelos gratuitos do OpenRouter: aceitos como fallback declarado, sem garantia de SLA.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE oferecer providers para Ollama (local), OpenAI e OpenRouter, todos cumprindo o contrato `LLMProvider`.
- **FR-002**: O roteador DEVE resolver provider e modelo por papel a partir da **Model Policy** com que foi construído — montada pela composition root (011) a partir da configuração na Fase 1 e pela 003, dentro do Execution Grant, a partir da Fase 2 ([ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)).
- **FR-003**: O roteador DEVE aplicar a allowlist de provider/modelo da Model Policy a toda resolução.
- **FR-004**: Modelos de roteamento automático DEVEM ser rejeitados na validação.
- **FR-005**: O papel `controller` DEVE sempre usar restrição de formato de saída; ausência de suporte DEVE resultar em erro explícito.
- **FR-006**: Todos os providers DEVEM suportar streaming.
- **FR-007**: O sistema NÃO DEVE fazer fallback automático entre providers na v1.
- **FR-008**: O cliente devolvido pelo roteador DEVE emitir, pelo Trace Sink (009), uma entrada por chamada com provider, modelo, papel, tokens de entrada/saída e latência. O tempo até o primeiro token entra com a US6 (Fase 3), como campo aditivo do evento de chamada de modelo da 009.
- **FR-009**: O sistema DEVE oferecer verificação de saúde, sob demanda, dos providers e modelos configurados, informando disponível/indisponível com o motivo. A verificação NÃO DEVE ser etapa bloqueante do boot.
- **FR-010**: Todo provider DEVE aplicar um timeout de conexão e um timeout de inatividade entre pedaços do stream, ambos configuráveis por provider, e NÃO DEVE impor teto de tempo total à chamada. Estouro de qualquer um dos dois DEVE resultar em erro explícito que nomeia provider e modelo.

### Key Entities

- **Model Policy**: modelo por papel + allowlist. Value object publicado por este módulo; a composition root (011) o monta a partir da configuração na Fase 1 e a 003 o monta, dentro do Execution Grant, a partir da Fase 2 ([ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)).
- **Model Role**: `controller`, `generation`, `rerank`.
- **Provider**: implementação de acesso a modelos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Trocar o modelo de qualquer papel de um Assistant exige só mudança de configuração, zero código.
- **SC-002**: 100% das chamadas de modelo são rastreáveis a (provider, modelo, papel).
- **SC-003**: 0 chamadas de controller sem restrição de formato de saída.
- **SC-004**: Adicionar um provider novo não exige mudança em nenhuma outra spec.

## Assumptions

- O provider local usa a camada compatível com OpenAI do Ollama, pelo SDK oficial da OpenAI em modo assíncrono, o que deixa sua implementação quase idêntica à do provider OpenAI. O SDK só aparece em `adapters/`.
- A escolha final de modelos (Qwen3 1.7B vs Gemma 4 E2B) é decidida por medição na spec 105/009, não aqui.
- Credenciais de providers externos vêm do ambiente ou do secret store do operador, por uma porta de segredos cujo adapter é escolhido pela composition root (011).
- Um provider simulado, também adapter de `LLMProvider`, atende o perfil de teste da 011.
