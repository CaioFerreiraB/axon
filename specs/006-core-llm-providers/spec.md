# Feature Specification: Providers de LLM e modelo por papel

**Feature Branch**: `006-core-llm-providers`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §5 (`LLMProvider`), §16 (elo 6), §26 (providers e modelo por papel), §27 (Ollama e hardware alvo); ADR-008. Fase 9 (2026-10-13): toque declarado — o evento de conteúdo da chamada de modelo (ADR-034).

## Module Boundary *(mandatory)*

- **Módulo**: LLM Providers — implementações de provider e o roteador que resolve provider + modelo por papel, aplicando a allowlist do Assistant.
- **Repositório / distribuição**: `axon-ai` → `axon_ai/llm/` (providers em `adapters/`).
- **Consome (seams)**: contrato `LLMProvider` — 001; Trace Sink — 009. A política de modelos chega pronta, como `ModelPolicy` deste módulo: montada pela 011 na Fase 1 e pela 003, dentro do Execution Grant, a partir da Fase 2 ([ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)).
- **Expõe (seams)**: **Model Router** (`for_execution(política, requisição)` → `for_role(papel) → cliente de modelo`, mais a verificação de saúde) — consumido por 005 e, para saúde e montagem, pela composition root (011).
- **Depende de infraestrutura (via portas)**: provedores de modelo, local e remotos (adapters de `LLMProvider`); segredos (credenciais dos providers remotos).
- **Não conhece**: flows, packs, prompts, domínio.
- **Substituição**: preservar o Model Router e o contrato `LLMProvider`; providers podem ser adicionados ou trocados livremente (são adapters).
- **Insumo técnico**: [design.md](design.md); [ADR-008](../../docs/adr/ADR-008-modelo-por-papel.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md), [ADR-020](../../docs/adr/ADR-020-segredos-uma-fonte-por-perfil-uma-porta-por-modulo.md) (segredos, Fase 3), [ADR-034](../../docs/adr/ADR-034-trace-com-destinos-e-conteudo-opcional.md) (evento de conteúdo, Fase 9).

## Clarifications

### Session 2026-09-18

- Q: Na Fase 1 o Execution Grant (003) ainda não existe. De onde o roteador tira a política de modelos por papel? → A: A política é um value object publicado no `api.py` deste módulo (**Model Policy**: modelo por papel + allowlist), com que o roteador é construído. Na Fase 1 quem o monta a partir da configuração do operador é a composition root (011); a partir da Fase 2 a própria 006 o deriva do Execution Grant, o que preserva a direção 006 → 003 do grafo de dependências e mantém o seam inalterado entre as fases. O roteador continua puro e testável sem 003. *(Superada em parte pelo [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md): quem monta a política a partir da Fase 2 é a 003, dentro do grant, e a seta passa a 003 → 006; o seam continua inalterado.)*
- Q: Quem emite o evento de chamada de modelo no Trace Sink, e o tempo até o primeiro token entra já na Fase 1? → A: Emite o cliente devolvido pelo roteador, que instrumenta a própria chamada — assim nenhum consumidor precisa lembrar de medir e SC-002 vale por construção. Na Fase 1 vão provider, modelo, papel, tokens e latência, que é o que o evento `ModelCall` da 009 já carrega; o tempo até o primeiro token entra com a US6 (Fase 3) como campo aditivo na 009, sem editar aquela spec fora da fase dela.
- Q: Como o adapter do provider local fala com o Ollama? → A: Pelo SDK oficial da OpenAI em modo assíncrono, com o endereço base apontando para a camada compatível do Ollama, como o `design.md` prevê. Streaming, tool calls e restrição de formato de saída vêm prontos, e os adapters de OpenAI e OpenRouter (Fase 3) reaproveitam quase tudo. O SDK fica confinado a `adapters/` (princípio XIII).
- Q: A verificação de saúde dos providers (FR-009) entra na Fase 1? → A: Sim, sob demanda — pergunta ao provider se o modelo declarado existe e responde disponível/indisponível com o motivo. Nunca é etapa bloqueante do boot: a plataforma sobe sem o provider local no ar (inclusive na suíte de testes) e o erro aparece na consulta de saúde e na primeira chamada.
- Q: No hardware alvo uma geração legítima leva minutos. Que timeout distingue isso de um stream travado? → A: Dois prazos por provider, ambos configuráveis: timeout de conexão, curto (provider fora do ar falha em segundos), e timeout de inatividade entre pedaços do stream. Não há teto de tempo total — resposta longa e saudável nunca é cortada, e stream travado falha com erro que nomeia provider e modelo.

### Session 2026-10-02

- Q: Quais identificadores de modelo contam como "roteamento automático" e onde a recusa acontece? → A: No provider `openrouter`, todo modelo do namespace `openrouter/…` (o `openrouter/auto` e qualquer roteador futuro; também os modelos "stealth" temporários, opacos e sem SLA) é recusado na construção do `ModelRef`, com mensagem que pede modelo explícito. Sufixos de variante do próprio modelo (`:free`, `:nitro`, `:floor`) são aceitos. Como toda referência a modelo passa pelo `ModelRef`, a regra vale de uma vez na declaração do Assistant, na escolha de modelo pela requisição e na saúde, sem editar a 003.
- Q: O que acontece quando a credencial do OpenAI ou do OpenRouter não está configurada no ambiente? → A: A credencial vem de uma variável por provider (`AXON_OPENAI_API_KEY`, `AXON_OPENROUTER_API_KEY`), lida por uma porta de segredos cujo adapter a 011 escolhe. O provider é registrado mesmo sem ela: a saúde relata indisponível com o motivo "sem credencial" e o nome da variável, e toda chamada falha antes de qualquer acesso à rede com erro explícito que nomeia provider, modelo e variável. O boot não falha, e nem a 003 nem os seams mudam.
- Q: Como o roteador garante que o papel `controller` sempre recebe a restrição de formato, e o que acontece quando o provider ou o modelo não consegue cumpri-la? → A: Em três camadas. (1) O roteador recusa, antes da rede, chamada do papel `controller` sem `response_format`. (2) Cada adapter envia a forma mais rígida do provider: `strict: true` no `json_schema` e, no OpenRouter, `provider.require_parameters: true`, para só ir a upstream que suporte a restrição. (3) A recusa do provider (modelo sem suporte, esquema fora do modo estrito) vira erro explícito que nomeia provider e modelo, sem reenviar sem restrição. Consequência aceita: com o esquema atual do motor (`anyOf` na raiz, que o modo estrito da OpenAI recusa), OpenAI como controller do `agentic` falha explicitamente até a 005 ajustar o esquema; Ollama e OpenRouter funcionam.

### Session 2026-10-07

- Q: Os aliases de versão do OpenRouter (`~autor/família-latest`, que apontam sempre para o modelo mais recente de uma família) contam como roteamento automático? → A: Não, e são aceitos. O alias nomeia o autor e a família; o OpenRouter não escolhe o modelo por requisição. Quem quiser fixar a versão declara o id concreto. Decidido depois de um teste real em que `openrouter/~z-ai/glm-flash-latest` atendeu os papéis `controller` e `generation`.
- Q: Como a OpenAI serve de controller, se o modo estrito dela exige raiz objeto, todo campo em `required` e `additionalProperties: false`? → A: O adapter da OpenAI — e o do OpenRouter para modelos `openai/…` — converte o esquema para o subconjunto estrito na ida (raiz embrulhada em `value`, opcional vira obrigatório e anulável, `additionalProperties: false`, `oneOf` → `anyOf`) e desfaz a conversão na volta; o que não tem equivalente estrito é recusado antes da rede (ADR-023, supera a R19 "o esquema não é reescrito").

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
2. **Given** uma requisição que escolhe `openrouter/openrouter/auto` e uma allowlist com `openrouter/*`, **When** resolvida, **Then** é rejeitada com a mesma mensagem — a allowlist não libera roteamento automático.
3. **Given** `openrouter/qwen/qwen3-8b:free`, **When** validado, **Then** é aceito: o sufixo escolhe a variante do mesmo modelo, não outro modelo.

---

### User Story 4 - Saída estruturada para decisões de controle (Priority: P2)

O papel `controller` sempre chama o modelo com restrição de formato de saída. Se o provider/modelo não suporta a restrição, o roteador falha explicitamente — nunca degrada para texto livre.

**Why this priority**: Modelos pequenos não produzem JSON confiável sem constraint.

**Independent Test**: Chamar o papel controller com um esquema de ação; a resposta é sempre parseável segundo o esquema.

**Acceptance Scenarios**:

1. **Given** um esquema de ação, **When** o controller é chamado, **Then** a restrição de formato é enviada ao provider na forma mais rígida dele (`strict: true`; no OpenRouter, também `require_parameters`).
2. **Given** um provider ou modelo sem suporte a restrição, ou um esquema que o modo estrito dele recusa, **When** usado como controller, **Then** o erro é explícito, nomeia provider e modelo, e a chamada não é refeita sem restrição.
3. **Given** uma chamada do papel `controller` sem `response_format`, **When** feita, **Then** o roteador a recusa antes de qualquer acesso à rede.

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
- Provider remoto sem credencial configurada: a plataforma sobe; a saúde relata indisponível com "sem credencial" e o nome da variável, e cada chamada falha antes da rede com erro que nomeia provider, modelo e variável. O valor da credencial nunca aparece em erro, log ou trace.
- Provider remoto responde com limite de taxa: erro explícito; não há fallback automático para outro provider na v1.
- Stream interrompido pelo provider: o erro é propagado ao motor.
- Stream que para de entregar pedaços sem fechar: o timeout de inatividade encerra a chamada com erro explícito.
- Modelos gratuitos do OpenRouter: aceitos quando declarados explicitamente (sufixo `:free`), sem garantia de SLA.
- Esquema do controller que o modo estrito do provider recusa (por exemplo, `anyOf` na raiz na OpenAI): erro explícito nomeando provider e modelo; o esquema é do motor (005), e a 006 não o reescreve.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE oferecer providers para Ollama (local), OpenAI e OpenRouter, todos cumprindo o contrato `LLMProvider`.
- **FR-002**: O roteador DEVE resolver provider e modelo por papel a partir da **Model Policy** com que foi construído — montada pela composition root (011) a partir da configuração na Fase 1 e pela 003, dentro do Execution Grant, a partir da Fase 2 ([ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)).
- **FR-003**: O roteador DEVE aplicar a allowlist de provider/modelo da Model Policy a toda resolução.
- **FR-004**: Modelos de roteamento automático DEVEM ser rejeitados na construção da referência de modelo (`ModelRef`), o que os recusa na validação do Assistant, na escolha de modelo pela requisição e na saúde. No provider `openrouter`, roteamento automático é todo modelo do namespace `openrouter/…` e a forma curta `auto` (`openrouter/auto` lido como provider `openrouter`, modelo `auto`); sufixos de variante (`:free`, `:nitro`, `:floor`) não contam, nem os aliases de versão `~autor/família-latest` (clarificação de 2026-10-07). A mensagem DEVE pedir um modelo explícito.
- **FR-005**: O papel `controller` DEVE sempre usar restrição de formato de saída. O roteador DEVE recusar, antes da rede, chamada do `controller` sem `response_format`; cada provider DEVE enviar a restrição na forma mais rígida que oferece (`strict: true` no `json_schema`; no OpenRouter, também `provider.require_parameters: true`). Recusa do provider — modelo sem suporte ou esquema fora do modo estrito — DEVE resultar em erro explícito que nomeia provider e modelo, e a chamada NÃO DEVE ser refeita sem a restrição. Para a OpenAI (e modelos `openai/…` via OpenRouter), o adapter DEVE converter o esquema para o subconjunto estrito e desfazer a conversão na resposta, recusando antes da rede o que não tem equivalente estrito (clarificação de 2026-10-07; ADR-023).
- **FR-006**: Todos os providers DEVEM suportar streaming.
- **FR-007**: O sistema NÃO DEVE fazer fallback automático entre providers na v1.
- **FR-008**: O cliente devolvido pelo roteador DEVE emitir, pelo Trace Sink (009), uma entrada por chamada com provider, modelo, papel, tokens de entrada/saída e latência. O tempo até o primeiro token entra com a US6 (Fase 3), como campo aditivo do evento de chamada de modelo da 009.
- **FR-009**: O sistema DEVE oferecer verificação de saúde, sob demanda, dos providers e modelos configurados, informando disponível/indisponível com o motivo. A verificação NÃO DEVE ser etapa bloqueante do boot.
- **FR-010**: Todo provider DEVE aplicar um timeout de conexão e um timeout de inatividade entre pedaços do stream, ambos configuráveis por provider, e NÃO DEVE impor teto de tempo total à chamada. Estouro de qualquer um dos dois DEVE resultar em erro explícito que nomeia provider e modelo.
- **FR-011**: Provider remoto sem credencial DEVE ser registrado mesmo assim e relatado indisponível na verificação de saúde, com o motivo "sem credencial" e o nome da variável esperada. Toda chamada a ele DEVE falhar antes de qualquer acesso à rede, com erro explícito que nomeia provider, modelo e variável. A ausência NÃO DEVE impedir o boot, e o valor de uma credencial NÃO DEVE aparecer em erro, log ou trace.
- **FR-012**: Junto com cada entrada da FR-008, o cliente DEVE emitir pelo Trace Sink o evento de conteúdo da chamada (`ModelExchange` da 009): as mensagens enviadas e a saída devolvida — em streaming, a saída acumulada ao fim do stream. O que fazer com ele (descartar, redigir, cortar, entregar só a destinos que aceitam conteúdo) é da 009; este módulo só o produz. Credenciais e cabeçalhos de autenticação NÃO DEVEM fazer parte dele. *(Fase 9, [ADR-034](../../docs/adr/ADR-034-trace-com-destinos-e-conteudo-opcional.md).)*

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
- Credenciais de providers externos vêm de uma variável por provider (`AXON_OPENAI_API_KEY`, `AXON_OPENROUTER_API_KEY`), por uma porta de segredos cujo adapter é escolhido pela composition root (011); um secret store do operador é outro adapter da mesma porta.
- Um provider simulado, também adapter de `LLMProvider`, atende o perfil de teste da 011.
