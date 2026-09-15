# Feature Specification: Registry e cliente MCP

**Feature Branch**: `007-core-mcp-integration`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §5 (`MCPClient`), §16 (elo 4), §17 (MCP Registry e rede), §18, §28; ADR-003.

## Module Boundary *(mandatory)*

- **Módulo**: MCP Integration — registro de servidores MCP (globais e de usuário), resolução server-side de endpoint e credencial, e cliente MCP com políticas de segurança e de rede.
- **Repositório / distribuição**: `ai-core` → `ai_core/mcp/`.
- **Consome (seams)**: contrato `MCPClient` e `ToolSpec` — 001; Principal e Execution Grant — 003.
- **Expõe (seams)**: **MCP Registry** (CRUD por escopo, aliases, políticas) — consumido por 003 (validação de aliases) e 008 (endpoints); **cliente MCP restrito** a aliases autorizados — consumido por 004.
- **Depende de infraestrutura (via portas)**: armazenamento do registry, segredos (credenciais dos servidores), transporte MCP, resolução de nomes (DNS).
- **Não conhece**: flows, packs, prompts, domínio.
- **Substituição**: preservar o registry por alias e o cliente restrito; transporte e armazenamento podem mudar (são adapters).
- **Insumo técnico**: [design.md](design.md); [ADR-003](../../docs/adr/ADR-003-mcp-usuario-pack-operador.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operador registra um MCP global sem código nem restart (Priority: P1)

O operador registra um servidor MCP com alias, transporte, endpoint, tipo de autenticação, referência de credencial e política. As tools são descobertas em runtime; Assistants passam a referenciar o alias.

**Why this priority**: Fase 3. MCP é protocolo: adicionar um MCP é dado puro.

**Independent Test**: Registrar um MCP de teste com a instalação em execução; uma execução nova de um Assistant que referencia o alias vê as tools, sem restart.

**Acceptance Scenarios**:

1. **Given** um MCP recém-registrado, **When** uma execução nova começa, **Then** as tools permitidas são descobertas e disponibilizadas.
2. **Given** um MCP desabilitado no registry, **When** a validação de Assistants roda, **Then** os Assistants que o referenciam são sinalizados com erro explícito.

---

### User Story 2 - Credencial por referência, resolvida no servidor (Priority: P1)

O registry guarda apenas uma referência ao secret store, nunca o segredo. A credencial é resolvida no servidor no momento da chamada e nunca trafega na requisição do usuário.

**Why this priority**: Evita credencial em texto plano no banco e em logs.

**Independent Test**: Inspecionar o armazenamento e os logs após chamadas autenticadas; nenhum segredo aparece.

**Acceptance Scenarios**:

1. **Given** um MCP autenticado, **When** registrado, **Then** o armazenamento contém só a referência da credencial.
2. **Given** uma chamada ao MCP, **When** executada, **Then** a credencial é obtida no servidor e não aparece no trace.

---

### User Story 3 - Cliente restrito a aliases autorizados (Priority: P1)

O cliente MCP entregue a uma execução conhece somente os aliases do grant. Ele nunca aceita endereços vindos da requisição ou do modelo.

**Why this priority**: Elo 4 da cadeia de enforcement.

**Independent Test**: Tentar executar tool de um alias fora do grant; o cliente responde "servidor desconhecido".

**Acceptance Scenarios**:

1. **Given** um grant com `mcp: [finance]`, **When** algo tenta usar `drive`, **Then** o resultado é "servidor desconhecido".

---

### User Story 4 - Usuário registra MCPs próprios (Priority: P2)

Um usuário registra servidores MCP de escopo `user`, visíveis apenas para ele e utilizáveis nos seus Assistants. MCPs de usuário são sempre remotos.

**Why this priority**: Nível 2 de extensão (ADR-003) — é como o usuário pluga código próprio sem tocar no processo do core.

**Independent Test**: O usuário A registra um MCP; o usuário B não o lista nem consegue referenciá-lo.

**Acceptance Scenarios**:

1. **Given** um MCP de escopo `user` de A, **When** B lista MCPs, **Then** não o vê.
2. **Given** um usuário, **When** tenta registrar MCP com transporte `stdio`, **Then** é rejeitado — `stdio` executaria comando no host do core.

---

### User Story 5 - Política por servidor (Priority: P2)

Cada servidor tem política: timeout, tamanho máximo de resposta, allowlist de tools expostas e lista de tools de escrita.

**Why this priority**: Um servidor pode expor 50 tools; o Assistant deve ver só as 3 que precisa.

**Independent Test**: Um servidor com allowlist de 3 tools de 50 expõe só 3 à descoberta.

**Acceptance Scenarios**:

1. **Given** allowlist de 3 tools, **When** a descoberta roda, **Then** retorna só as 3, com a marca de escrita das que estão em `write_tools`.

---

### User Story 6 - Proteções de rede (Priority: P2)

O cliente aplica allowlist de hosts, bloqueia `localhost` e faixas de IP privadas (inclusive quando alcançadas por DNS ou redirecionamento), e aplica timeout e limite de tamanho.

**Why this priority**: Qualquer pessoa poderá instalar a plataforma; SSRF é o ataque óbvio contra MCPs de usuário.

**Independent Test**: Uma suíte de vetores de SSRF (IPs privados, localhost, DNS que resolve para IP privado, redirecionamento) é 100% bloqueada.

**Acceptance Scenarios**:

1. **Given** um MCP de usuário cujo host resolve para faixa privada, **When** o cliente conecta, **Then** a conexão é bloqueada.
2. **Given** um redirecionamento para `localhost`, **When** seguido, **Then** é bloqueado.

---

### Edge Cases

- Servidor fora do ar na descoberta: tools ausentes naquela execução, fato registrado e sinalizado (spec 004).
- Servidor muda a lista de tools: reflete após expirar o cache; tools fora da allowlist continuam ausentes.
- Referência de credencial inválida: erro explícito na chamada e no health check do registry.
- Operador registra MCP `stdio` global: permitido (o operador é a fronteira de confiança), com o comando fixado no registro.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O registry DEVE armazenar por servidor: alias, transporte (`stdio`, `http`, `sse`), endpoint, tipo de autenticação, referência de credencial, dono, escopo (`global`, `user`), habilitado e política (timeout, tamanho máximo, allowlist de tools, tools de escrita).
- **FR-002**: Adicionar, alterar ou desabilitar um servidor NÃO DEVE exigir código nem restart.
- **FR-003**: O registry NÃO DEVE armazenar segredos; apenas referências resolvidas no servidor.
- **FR-004**: Credenciais NÃO DEVEM trafegar em requisições de usuário nem aparecer em trace ou log.
- **FR-005**: O cliente DEVE aceitar apenas aliases autorizados pelo grant e resolver endpoint e credencial no servidor.
- **FR-006**: MCPs de escopo `user` DEVEM ser visíveis e utilizáveis apenas pelo dono.
- **FR-007**: A descoberta DEVE retornar apenas as tools da allowlist do servidor, marcando as de escrita.
- **FR-008**: O cliente DEVE aplicar timeout e tamanho máximo por chamada.
- **FR-009**: O cliente DEVE aplicar allowlist de hosts e bloquear localhost e faixas privadas, inclusive via DNS e redirecionamento.
- **FR-010**: A descoberta DEVE usar cache com tempo de vida configurável.
- **FR-011**: O registry DEVE oferecer health check por servidor.
- **FR-012**: MCPs de escopo `user` NÃO DEVEM usar transporte `stdio`.

### Key Entities

- **MCP Server**: alias, transporte, endpoint, autenticação, referência de credencial, dono, escopo, habilitado, política.
- **Security Policy**: timeout, tamanho máximo, allowlist de tools, tools de escrita.
- **Credential Reference**: ponteiro para o secret store.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 segredos no armazenamento e nos logs (varredura automatizada).
- **SC-002**: 100% dos vetores da suíte de SSRF bloqueados.
- **SC-003**: Um MCP novo fica disponível para execuções novas dentro do tempo de vida do cache, sem restart.
- **SC-004**: 0 vazamentos de MCP de usuário para outro usuário em testes de isolamento.

## Assumptions

- O secret store é fornecido pela instalação (variáveis de ambiente ou serviço de segredos), por uma porta de segredos; a escolha do adapter fica no plano e o wiring na composition root (011).
- MCPs globais são registrados pela superfície privada (spec 008); MCPs de usuário, pela pública.
- O registry usa armazenamento persistente a partir da Fase 3 (adapter Postgres; em memória antes).
