# Feature Specification: Registry e cliente MCP

**Feature Branch**: `007-core-mcp-integration`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §5 (`MCPClient`), §16 (elo 4), §17 (MCP Registry e rede), §18, §28; ADR-003.

## Module Boundary *(mandatory)*

- **Módulo**: MCP Integration — registro de servidores MCP (globais e de usuário), resolução server-side de endpoint e credencial, e cliente MCP com políticas de segurança e de rede.
- **Repositório / distribuição**: `axon-ai` → `axon_ai/mcp/`.
- **Consome (seams)**: contrato `MCPClient` e `ToolSpec` — 001; Principal e Execution Grant — 003.
- **Expõe (seams)**: **MCP Registry** (CRUD por escopo, aliases, políticas) — consumido por 003 (validação de aliases) e 008 (endpoints); **cliente MCP restrito** a aliases autorizados — consumido por 004.
- **Depende de infraestrutura (via portas)**: armazenamento do registry, segredos (credenciais dos servidores), transporte MCP, resolução de nomes (DNS).
- **Não conhece**: flows, packs, prompts, domínio.
- **Substituição**: preservar o registry por alias e o cliente restrito; transporte e armazenamento podem mudar (são adapters).
- **Insumo técnico**: [design.md](design.md); [ADR-003](../../docs/adr/ADR-003-mcp-usuario-pack-operador.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## Clarifications

### Session 2026-10-01

- Q: Por qual canal o operador registra MCPs globais, em especial os de transporte `stdio` (que executam um comando no host do core)? → A: `http` e `sse` globais pela superfície privada, ao vivo e sem restart; `stdio` só pelo arquivo de configuração do operador, montado na imagem e lido no boot (mudar exige restart), nunca pela API, em escopo nenhum. É a tabela do ADR-003: servidor remoto é dado; comando no host é nível de operador.
- Q: O bloqueio de `localhost` e de faixas de IP privadas vale também para os MCPs globais do operador, que costumam rodar na rede interna? → A: Vale para todos. O operador libera hosts internos específicos pela configuração da imagem (ambiente ou arquivo), nunca pela API; só MCPs globais alcançam um host liberado, e MCP de usuário nunca. A API, mesmo com chave de administração, não amplia a rede alcançável.
- Q: Como um MCP de usuário que exige autenticação recebe a credencial, se o registry não guarda segredos e o usuário não tem acesso ao secret store do servidor? → A: Não recebe, na Fase 3: MCP de usuário é só sem autenticação, com endpoint sem credencial embutida (sem usuário e senha na URL), e nunca referencia credencial. Autenticação por usuário (segredo cifrado ou OAuth) é decisão de uma fase futura.
- Q: Quais MCPs globais um usuário pode referenciar nos Assistants próprios? → A: Só os marcados, servidor a servidor, como liberados a usuários — marca no MCP global, desligada por padrão. A 003 continua consultando apenas a porta que já declarou (aliases do dono e globais liberados a usuários).
- Q: Como se evita que o alias de um MCP de usuário colida com o de um MCP global? → A: Alias de usuário leva o prefixo reservado `~` (ex.: `~drive`), único por dono; alias global nunca começa com `~` e é único entre os globais. Os dois espaços nunca se cruzam, nada sombreia nada — a regra dos Assistants de usuário da 003 (FR-017).
- Alinhamento com o princípio VI da constituição (achado C1 do `/speckit-analyze`, sem pergunta nova): além da exceção de hosts internos, o operador pode definir na configuração da imagem uma **allowlist de hosts de destino**, opcional. Definida, todo destino fora dos hosts internos — de MCP global ou de usuário — precisa casar com ela (nome exato ou `*.domínio`); ausente, vale qualquer host público. É a "allowlist de hosts" que o princípio VI exige do cliente MCP.

### Session 2026-10-22

- Q: O que acontece com a parte de imagem de um resultado MCP ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md))? → A: É preservada: o transporte a entrega como `RemotePart` com `mime` e os bytes (`data`), e o resultado a leva em `ToolResult.attachments` (contrato 001, 0.2.2). Ela não entra no texto — quem põe a marca no texto cercado é a 004.
- Q: Que imagem é recusada, e como? → A: Tipo fora da lista dos contratos (`ATTACHMENT_MIME_TYPES`; SVG incluído), bytes acima de `AXON_TOOL_MAX_ATTACHMENT_BYTES` (2 MiB por padrão) ou base64 inválido viram, no texto, a marca de omissão de hoje com o motivo: `[conteúdo image omitido: <motivo>]`. Partes de áudio e recurso seguem com a marca sem motivo.
- Q: O teto de bytes da política (`max_response_bytes`) conta as imagens? → A: Não: ele continua cortando só o texto. O teto do transporte, que protege a leitura da resposta inteira, soma à folga de hoje o tamanho em base64 de quatro anexos no teto — uma resposta acima disso falha como hoje ("resposta acima do teto").

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operador registra um MCP global sem código nem restart (Priority: P1)

O operador registra um servidor MCP com alias, transporte, endpoint, tipo de autenticação, referência de credencial e política. As tools são descobertas em runtime; Assistants passam a referenciar o alias.

**Why this priority**: Fase 3. MCP é protocolo: adicionar um MCP é dado puro.

**Independent Test**: Registrar um MCP de teste com a instalação em execução; uma execução nova de um Assistant que referencia o alias vê as tools, sem restart.

**Acceptance Scenarios**:

1. **Given** um MCP recém-registrado, **When** uma execução nova começa, **Then** as tools permitidas são descobertas e disponibilizadas.
2. **Given** um MCP desabilitado no registry, **When** a validação de Assistants roda, **Then** os Assistants que o referenciam são sinalizados com erro explícito.
3. **Given** uma chave do grupo de administração, **When** tenta registrar pela API um MCP com transporte `stdio`, **Then** o registro é recusado nomeando o campo; **Given** um MCP `stdio` no arquivo de configuração do operador, **When** a plataforma sobe, **Then** ele aparece no registry como global e somente leitura.

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
3. **Given** um usuário, **When** tenta registrar MCP com referência de credencial, tipo de autenticação diferente de nenhum ou endpoint com usuário e senha na URL, **Then** é rejeitado nomeando o campo — referenciar segredos do servidor permitiria enviá-los a um endpoint do próprio usuário.
4. **Given** um MCP global não liberado a usuários, **When** um usuário cria um Assistant que o referencia, **Then** a criação é rejeitada como referência inexistente; **Given** o mesmo MCP liberado a usuários, **When** cria, **Then** é aceita.
5. **Given** um MCP global `drive`, **When** um usuário registra um MCP próprio, **Then** o alias dele é `~drive` — os dois coexistem sem ambiguidade; **Given** um registro global com alias começando por `~`, ou de usuário sem o prefixo, **When** enviado, **Then** é recusado nomeando o alias.

---

### User Story 5 - Política por servidor (Priority: P2)

Cada servidor tem política: timeout, tamanho máximo de resposta, allowlist de tools expostas e lista de tools de escrita.

**Why this priority**: Um servidor pode expor 50 tools; o Assistant deve ver só as 3 que precisa.

**Independent Test**: Um servidor com allowlist de 3 tools de 50 expõe só 3 à descoberta.

**Acceptance Scenarios**:

1. **Given** allowlist de 3 tools, **When** a descoberta roda, **Then** retorna só as 3, com a marca de escrita das que estão em `write_tools`.

---

### User Story 6 - Proteções de rede (Priority: P2)

O cliente bloqueia `localhost` e faixas de IP privadas para todo MCP (inclusive quando alcançadas por DNS ou redirecionamento), com exceção apenas dos hosts internos que o operador libera na configuração da imagem, válida só para MCPs globais; e, quando o operador define uma allowlist de hosts de destino, só alcança os hosts que casam com ela.

**Why this priority**: Qualquer pessoa poderá instalar a plataforma; SSRF é o ataque óbvio contra MCPs de usuário.

**Independent Test**: Uma suíte de vetores de SSRF (IPs privados, localhost, DNS que resolve para IP privado, redirecionamento) é 100% bloqueada.

**Acceptance Scenarios**:

1. **Given** um MCP de usuário cujo host resolve para faixa privada, **When** o cliente conecta, **Then** a conexão é bloqueada.
2. **Given** um redirecionamento para `localhost`, **When** seguido, **Then** é bloqueado.
3. **Given** um host interno liberado na configuração do operador, **When** um MCP global aponta para ele, **Then** a conexão é feita; **When** um MCP de usuário aponta para o mesmo host, **Then** é bloqueada.
4. **Given** um MCP global registrado pela API apontando para faixa privada não liberada (ex.: o endpoint de metadados da nuvem), **When** o cliente conecta, **Then** a conexão é bloqueada.
5. **Given** uma allowlist de hosts de destino com `*.empresa.example`, **When** um MCP (de usuário ou global) aponta para um host público fora dela, **Then** a conexão é bloqueada; **When** aponta para `mcp.empresa.example`, **Then** passa às demais regras.

---

### Edge Cases

- Servidor fora do ar na descoberta: tools ausentes naquela execução, fato registrado e sinalizado (spec 004).
- Servidor muda a lista de tools: reflete após expirar o cache; tools fora da allowlist continuam ausentes.
- Referência de credencial inválida: erro explícito na chamada e no health check do registry.
- Operador declara MCP `stdio` global: permitido só no arquivo de configuração do operador (o operador é a fronteira de confiança), com o comando fixado ali. Tentativa de registrar `stdio` pela API, mesmo com chave do grupo de administração, é recusada nomeando o campo — seria execução remota de comando por construção (ADR-003).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O registry DEVE armazenar por servidor: alias, transporte (`stdio`, `http`, `sse`), endpoint, tipo de autenticação, referência de credencial, dono, escopo (`global`, `user`), habilitado, liberado a usuários (só globais; desligado por padrão) e política (timeout, tamanho máximo, allowlist de tools, tools de escrita).
- **FR-002**: Adicionar, alterar ou desabilitar um servidor `http` ou `sse` NÃO DEVE exigir código nem restart. Servidores `stdio` vêm só do arquivo de configuração do operador, lido no boot: mudá-los exige restart.
- **FR-003**: O registry NÃO DEVE armazenar segredos; apenas referências resolvidas no servidor.
- **FR-004**: Credenciais NÃO DEVEM trafegar em requisições de usuário nem aparecer em trace ou log.
- **FR-005**: O cliente DEVE aceitar apenas aliases autorizados pelo grant e resolver endpoint e credencial no servidor.
- **FR-006**: MCPs de escopo `user` DEVEM ser visíveis e utilizáveis apenas pelo dono. Um Assistant de usuário DEVE poder referenciar apenas os MCPs do próprio dono e os globais liberados a usuários; um Assistant de sistema, apenas globais.
- **FR-007**: A descoberta DEVE retornar apenas as tools da allowlist do servidor, marcando as de escrita.
- **FR-008**: O cliente DEVE aplicar timeout e tamanho máximo por chamada.
- **FR-009**: O cliente DEVE bloquear localhost, faixas privadas, link-local e de metadados para todo MCP, conferindo o IP resolvido a cada conexão e a cada redirecionamento. A única exceção é a allowlist de hosts internos do operador, definida na configuração da imagem (nunca pela API), e ela vale só para MCPs globais — MCP de usuário nunca alcança um host liberado. Além disso, o cliente DEVE aplicar a allowlist de hosts de destino do operador, quando definida na configuração da imagem: destino fora dos hosts internos que não casa com ela (nome exato ou `*.domínio`) é bloqueado, para MCPs globais e de usuário.
- **FR-010**: A descoberta DEVE usar cache com tempo de vida configurável.
- **FR-011**: O registry DEVE oferecer health check por servidor.
- **FR-012**: MCPs de escopo `user` NÃO DEVEM usar transporte `stdio` — corolário do ADR-003; o FR-013 o generaliza para todo registro pela API.
- **FR-013**: O registro pela API — em qualquer escopo — NÃO DEVE aceitar transporte `stdio`; servidores `stdio` existem só no arquivo de configuração do operador, e a API os mostra como somente leitura.
- **FR-014**: MCPs de escopo `user` NÃO DEVEM ter autenticação nem referência de credencial, e o endpoint NÃO DEVE conter credencial embutida (usuário e senha na URL); autenticação de MCP de usuário fica fora da Fase 3.
- **FR-015**: Alias de MCP de escopo `user` DEVE começar com o prefixo reservado `~` e ser único por dono; alias global NÃO DEVE começar com `~` e DEVE ser único entre os globais. Registro que viole a regra é recusado nomeando o campo.
- **FR-016**: O cliente DEVE preservar as partes de imagem do resultado como anexos (`ToolResult.attachments`, contrato 001), fora do texto, quando o tipo está em `ATTACHMENT_MIME_TYPES` e os bytes cabem no teto por anexo (`AXON_TOOL_MAX_ATTACHMENT_BYTES`); fora disso, a parte DEVE virar a marca de omissão com o motivo ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md), item 2).
- **FR-017**: O teto de texto da política (`max_response_bytes`) NÃO DEVE contar os anexos; o teto do transporte DEVE comportar, além do texto, quatro anexos no teto por anexo.

### Key Entities

- **MCP Server**: alias (`~` reservado aos de usuário, único por dono; global único entre globais), transporte, endpoint, autenticação, referência de credencial, dono, escopo, habilitado, liberado a usuários (globais), política.
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
- MCPs globais `http`/`sse` são registrados pela superfície privada (spec 008), e os `stdio`, pelo arquivo de configuração do operador; MCPs de usuário, pela superfície pública.
- O registry usa armazenamento persistente a partir da Fase 3 (adapter Postgres; em memória antes).
- Fora do escopo da Fase 3: autenticação de MCP de usuário (segredo por usuário cifrado ou OAuth). Até lá, MCP de usuário é sem autenticação (FR-014).


## Incremento: delegação MCP por execução (2026-10-29)

Regido por [ADR-055](../../docs/adr/ADR-055-autenticacao-mcp-delegada.md). Protocolo 1: um MCP delegado por grant, identidade confidencial por execução, sem cache compartilhado e sem alteração da ACL. Contrato: [delegação](../007-core-mcp-integration/contracts/delegation.md). Casos D01 isolamento concorrente; D02 falha fechada; D03 metadados e superfície privada; D04 segredo ausente de persistência/trace; D05 regressão estática.
