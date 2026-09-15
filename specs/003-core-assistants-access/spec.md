# Feature Specification: Assistants, identidade e autorização

**Feature Branch**: `003-core-assistants-access`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §12 (Assistants), §15 (autenticação e autorização), §16 (cadeia de enforcement — elos 1, 2 e 7), §25 (requisição só restringe), §28 (assistants de usuário persistidos), Parte IX (multi-tenancy); ADR-002, ADR-008.

## Module Boundary *(mandatory)*

- **Módulo**: Assistants & Access — autentica o Principal, mantém o registro de Assistants e resolve, para cada requisição, o que a execução pode usar.
- **Repositório / distribuição**: `ai-core` → `ai_core/assistants/` (inclui a autenticação; subcomando `assistants validate` em `adapters/cli.py`, registrado pela spec 011).
- **Consome (seams)**: Pack Registry — 002 (validar packs referenciados); MCP Registry — 007 (validar aliases); nomes de flow — 005 (validar flow).
- **Expõe (seams)**: **Principal** e **Execution Grant** — consumidos por 004, 005, 006, 007, 008; **Assistant Directory** (listagem filtrada por ACL e CRUD de assistants de usuário) — consumido por 008.
- **Depende de infraestrutura (via portas)**: armazenamento de Assistants de usuário, configuração de Assistants de sistema, verificação de identidade (provedor OIDC, chaves de API), contadores de taxa, relógio.
- **Não conhece**: como flows executam, como tools executam, providers, o protocolo HTTP (a 008 adapta a requisição e chama a autenticação daqui), qualquer domínio.
- **Substituição**: preservar a forma do Execution Grant e a semântica "404, nunca 403"; o formato de configuração e o armazenamento podem mudar (são adapters).
- **Insumo técnico**: [design.md](design.md); [ADR-002](../../docs/adr/ADR-002-assistant-fronteira-isolamento.md), [ADR-008](../../docs/adr/ADR-008-modelo-por-papel.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operador define Assistants de sistema (Priority: P1)

O operador declara, em configuração versionada, Assistants nomeados. Cada Assistant amarra: flow, packs (em ordem), MCPs permitidos, coleções acessíveis, modelos por papel com allowlist, limites (requisições por minuto, iterações, tokens de contexto), visibilidade (pública ou privada) e regras de acesso (esquemas aceitos e principals/grupos permitidos).

**Why this priority**: O Assistant é a fronteira de isolamento (ADR-002). Tudo que vem depois — catálogo, MCP, modelos — é resolvido a partir dele.

**Independent Test**: Declarar dois Assistants (um público só com um pack, outro privado com pack + MCP) e verificar que cada um resolve para configurações efetivas diferentes e completas.

**Acceptance Scenarios**:

1. **Given** um Assistant que declara `mcp: []`, **When** resolvido, **Then** o Execution Grant não contém nenhum alias de MCP — não há caminho pelo qual um MCP de outro Assistant entre.
2. **Given** um Assistant de composição que declara dois packs, **When** resolvido, **Then** o grant contém ambos, na ordem declarada.
3. **Given** um Assistant com um único pack e sem flow declarado, **When** resolvido, **Then** o flow é o preferido pelo pack (ou `chat`, se o pack não preferir nenhum).
4. **Given** um Assistant com dois ou mais packs e sem flow declarado, **When** validado, **Then** é rejeitado — em composição o flow é escolhido pelo Assistant, não derivado (arch-v1 §11).

---

### User Story 2 - Principal autenticado por uma de duas superfícies (Priority: P1)

Quem chama a plataforma se autentica por uma de duas superfícies: pública (OIDC) ou privada (chave de API). Cada esquema produz um Principal com identificador, esquema usado e grupos.

**Why this priority**: Autenticação é propriedade do sistema e pré-requisito da autorização. Superfícies são poucas e estáveis; Assistants crescem.

**Independent Test**: Chamar com token OIDC válido, chave de API válida e credencial inválida; os dois primeiros produzem Principals distintos e o terceiro é rejeitado antes de qualquer resolução.

**Acceptance Scenarios**:

1. **Given** um token OIDC válido, **When** a requisição chega na superfície pública, **Then** o Principal é `user:<sub>` com esquema `oidc` e os grupos do token.
2. **Given** uma chave de API válida, **When** a requisição chega na superfície privada, **Then** o Principal é o dono da chave com esquema `api_key`.
3. **Given** credencial ausente ou inválida, **When** a requisição chega, **Then** é rejeitada como não autenticada.

---

### User Story 3 - Autorização por Assistant sem vazar existência (Priority: P1)

A resolução compara o Principal com as regras do Assistant. Não autorizado recebe exatamente a mesma resposta que um Assistant inexistente (404). Autorizado recebe um Execution Grant.

**Why this priority**: 403 revelaria a existência de Assistants privados a qualquer usuário público (elo 2 da cadeia de enforcement).

**Independent Test**: Um usuário público pede um Assistant privado existente e um Assistant inexistente; as duas respostas são indistinguíveis (status, corpo e tempo de resposta na mesma ordem de grandeza).

**Acceptance Scenarios**:

1. **Given** um Assistant privado que aceita só `api_key` e `user:caio`, **When** um Principal OIDC o solicita, **Then** recebe 404.
2. **Given** o mesmo Assistant, **When** `user:caio` o solicita via chave de API, **Then** recebe um Execution Grant.
3. **Given** um Assistant com `allow: ["*"]`, **When** qualquer Principal autenticado por esquema aceito o solicita, **Then** recebe um grant.

---

### User Story 4 - A requisição só restringe, nunca amplia (Priority: P1)

Uma requisição nomeia um Assistant e pode, no máximo, restringir dentro do permitido (ex.: escolher um modelo de geração dentro da allowlist). Campos que ampliariam capacidades — packs, servidores MCP, provider fora da allowlist, tools do cliente — são rejeitados com erro explícito.

**Why this priority**: Princípio IV. Sem isso, o cliente decide o que o agente enxerga, e isolamento vira convenção.

**Independent Test**: Enviar requisições com `packs`, `mcp_servers`, provider fora da allowlist e `tools` do cliente; todas são rejeitadas antes de qualquer custo.

**Acceptance Scenarios**:

1. **Given** um Assistant com allowlist `ollama/*`, **When** a requisição pede um modelo `openai/...`, **Then** é rejeitada como "modelo não permitido".
2. **Given** qualquer Assistant, **When** a requisição inclui lista de packs ou de servidores MCP, **Then** é rejeitada com erro que nomeia o campo.
3. **Given** um Assistant com allowlist `ollama/*`, **When** a requisição escolhe outro modelo Ollama, **Then** o grant usa esse modelo para geração.

---

### User Story 5 - Descoberta filtrada (Priority: P2)

A listagem de Assistants disponíveis mostra ao Principal apenas os que ele pode usar (elo 1). Assistants privados de terceiros não aparecem.

**Why this priority**: É o que permite expor cada Assistant como "modelo" num dropdown (spec 008) sem vazar nada.

**Independent Test**: Listar com um Principal público e com o dono de um Assistant privado; as listas diferem exatamente pelos Assistants privados.

**Acceptance Scenarios**:

1. **Given** Assistants públicos e privados, **When** um Principal público lista, **Then** vê apenas os públicos que aceitam seu esquema.

---

### User Story 6 - Usuário cria Assistants próprios (Priority: P2)

Um usuário autenticado cria, edita e remove Assistants próprios, que ficam persistidos e visíveis só para ele. Um Assistant de usuário pode referenciar apenas packs permitidos ao usuário e MCPs do próprio usuário (ou globais permitidos).

**Why this priority**: Nível 1 de extensão (ADR-003): o usuário compõe capacidades sem código e sem restart.

**Independent Test**: Criar um Assistant de usuário com um MCP próprio; outro usuário não o vê nem o resolve.

**Acceptance Scenarios**:

1. **Given** um usuário com um MCP próprio, **When** cria um Assistant que o referencia, **Then** o Assistant é salvo e resolvível só por ele.
2. **Given** um usuário, **When** tenta criar um Assistant que referencia MCP de outro usuário, **Then** a criação é rejeitada — e a mensagem não confirma a existência do MCP alheio.
3. **Given** um Assistant de usuário, **When** o operador faz novo deploy, **Then** o Assistant permanece (vive no banco, não no arquivo de configuração).

---

### User Story 7 - Orçamento por Principal e Assistant (Priority: P2)

Cada Assistant define limites: requisições por minuto por (Principal, Assistant), máximo de iterações e teto de tokens de contexto. Excesso de taxa é recusado (429); limites de iteração e tokens chegam ao motor pelo grant e produzem truncamento, não loop.

**Why this priority**: Orçamento é controle de segurança (elo 7), não só custo: impede que um prompt malicioso transforme uma requisição num loop caro.

**Independent Test**: Exceder o limite de requisições por minuto de um Assistant e verificar 429 só para aquele par (Principal, Assistant).

**Acceptance Scenarios**:

1. **Given** `rpm: 20`, **When** um Principal faz a 21ª requisição no minuto, **Then** recebe 429; outro Principal não é afetado.

---

### User Story 8 - Validação de Assistants antes de servir (Priority: P3)

O operador valida por linha de comando (e o sistema valida no boot) que todo Assistant referencia pack habilitado, MCP existente, coleção existente e flow existente. Assistant inválido fica indisponível com erro explícito; os demais funcionam.

**Why this priority**: Falha cedo (princípio VII). Também é o que torna seguro renomear flows numa reescrita do grafo: referências pendentes aparecem aqui.

**Independent Test**: Declarar um Assistant que referencia flow inexistente; a validação falha nomeando Assistant e referência.

**Acceptance Scenarios**:

1. **Given** um Assistant que referencia um pack em erro, **When** a validação roda, **Then** ele é marcado indisponível com o motivo, e os demais Assistants seguem disponíveis.

---

### Edge Cases

- Assistant de usuário com o mesmo nome de um Assistant de sistema: nomes de sistema são reservados; Assistants de usuário vivem no escopo do dono.
- Chave de API revogada durante uma execução em andamento: a execução termina; novas requisições são rejeitadas.
- Grupos do Principal mudam entre requisições: a autorização é avaliada a cada requisição.
- Assistant privado cujo nome é adivinhado: 404 idêntico ao de inexistente.
- Allowlist de modelos vazia: Assistant inválido na validação.
- Execução de avaliação com data de referência fixa: só existe em processo, pelo harness (009); a API HTTP rejeita o campo (008 FR-012, ADR-013). Fixar a data não amplia capacidade.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE oferecer duas superfícies de autenticação — pública (OIDC) e privada (chave de API) — num único serviço.
- **FR-002**: Cada esquema de autenticação DEVE produzir um Principal com identificador, esquema e grupos.
- **FR-003**: O sistema DEVE carregar Assistants de sistema de configuração versionada do operador e Assistants de usuário do armazenamento persistente.
- **FR-004**: Um Assistant DEVE declarar: visibilidade, esquemas aceitos, principals/grupos permitidos, flow, packs em ordem, MCPs, coleções, allowed tools opcional, write tools opcional, modelos por papel, allowlist de modelos e limites.
- **FR-005**: A resolução DEVE produzir um Execution Grant contendo apenas o que o Assistant permite, já interseccionado com as restrições válidas da requisição.
- **FR-006**: Principal não autorizado DEVE receber resposta indistinguível da de Assistant inexistente (404).
- **FR-007**: Campos de requisição que ampliariam capacidades DEVEM ser rejeitados com erro explícito antes de qualquer execução.
- **FR-008**: A listagem de Assistants DEVE conter apenas os que o Principal pode resolver.
- **FR-009**: Usuários DEVEM poder criar, ler, atualizar e remover Assistants próprios, restritos a packs permitidos e MCPs próprios ou globais permitidos.
- **FR-010**: O sistema DEVE aplicar limite de taxa por (Principal, Assistant) e repassar ao motor os limites de iteração e de tokens via grant.
- **FR-011**: O sistema DEVE validar, no boot e por linha de comando, as referências de todo Assistant (pack, MCP, coleção, flow, modelos), marcando inválidos como indisponíveis com erro explícito.
- **FR-012**: Um Assistant público NÃO DEVE conceder tools de escrita por default; um privado só as concede se declaradas.
- **FR-013**: Assistants de sistema DEVEM ser sobrescritos apenas por novo deploy; Assistants de usuário, apenas pelo dono.

### Key Entities

- **Principal**: identificador (`user:…`, `svc:…`), esquema, grupos.
- **Assistant**: configuração nomeada (ver FR-004); origem sistema ou usuário; dono (quando de usuário).
- **Execution Grant**: configuração efetiva de uma execução — Assistant, Principal, flow, packs ordenados, aliases MCP, coleções, tools permitidas, tools de escrita, política de modelo por papel, limites.
- **Rate Budget**: contador por (Principal, Assistant).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Em teste automatizado, um Principal não autorizado não consegue distinguir Assistant privado existente de inexistente por nenhum campo da resposta.
- **SC-002**: 100% das execuções partem de um Execution Grant; teste adversarial confirma que nenhuma capacidade fora do grant é alcançável.
- **SC-003**: Adicionar ou alterar um Assistant exige zero mudanças de código; Assistants de usuário ficam disponíveis sem restart.
- **SC-004**: 100% das referências pendentes em Assistants são detectadas antes de servir tráfego.
- **SC-005**: 100% das requisições com campos de ampliação são rejeitadas antes de qualquer chamada de modelo.

## Assumptions

- Um operador por instalação, com múltiplos usuários. Isolamento entre organizações (multi-tenancy) está fora de escopo; instalação separada é o default (arch-v1 Parte IX).
- Provedor OIDC externo; a plataforma não gerencia senhas.
- Chaves de API são emitidas pelo operador.
- A verificação de que o modelo solicitado existe no provider é feita pela spec 006; esta spec aplica a allowlist.
