# Feature Specification: Assistants, identidade e autorização

**Feature Branch**: `003-core-assistants-access`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §12 (Assistants), §15 (autenticação e autorização), §16 (cadeia de enforcement — elos 1, 2 e 7), §25 (requisição só restringe), §28 (assistants de usuário persistidos), Parte IX (multi-tenancy); ADR-002, ADR-008.

## Module Boundary *(mandatory)*

- **Módulo**: Assistants & Access — autentica o Principal, mantém o registro de Assistants e resolve, para cada requisição, o que a execução pode usar.
- **Repositório / distribuição**: `ai-core` → `ai_core/assistants/` (inclui a autenticação; subcomandos `assistants validate` e `keys` em `adapters/cli.py`, registrados pela spec 011).
- **Consome (seams)**: Pack Registry — 002 (validar packs referenciados); MCP Registry — 007 (validar aliases); nomes de flow — 005 (validar flow); value objects da política de modelos — 006 (`ModelPolicy`, `ModelRef`, `ModelRole`: o grant carrega a política, [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)). Enquanto 007 e o índice de coleções não existem, a 003 declara a forma que exige desses catálogos e a composition root injeta catálogos vazios.
- **Expõe (seams)**: **Principal** e **Execution Grant** — consumidos por 004, 005, 006, 007, 008; **Assistant Directory** (listagem filtrada por ACL e CRUD de assistants de usuário) — consumido por 008; **API Key Admin** (emissão, listagem e revogação de chaves de API) — consumido por 008 (superfície privada) e pela linha de comando.
- **Depende de infraestrutura (via portas)**: armazenamento de Assistants de usuário, configuração de Assistants de sistema, verificação de identidade (provedor OIDC, chaves de API), contadores de taxa, relógio.
- **Não conhece**: como flows executam, como tools executam, providers, o protocolo HTTP (a 008 adapta a requisição e chama a autenticação daqui), qualquer domínio.
- **Substituição**: preservar a forma do Execution Grant e a semântica "404, nunca 403"; o formato de configuração e o armazenamento podem mudar (são adapters).
- **Insumo técnico**: [design.md](design.md); [ADR-002](../../docs/adr/ADR-002-assistant-fronteira-isolamento.md), [ADR-008](../../docs/adr/ADR-008-modelo-por-papel.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-015](../../docs/adr/ADR-015-persistencia-postgres-por-modulo.md), [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md).

## Clarifications

### Session 2026-09-30

- Q: O que limita um Assistant criado por usuário — quais packs, flows, modelos e limites ele pode declarar? → A: Políticas por grupo, declaradas pelo operador em configuração versionada: cada política tem um seletor (grupo ou `*`) e define packs e flows permitidos, allowlist de modelos e teto de limites. Vale a primeira política, na ordem declarada, que casa com o Principal; sem política aplicável, o Principal não cria Assistants. O Assistant de usuário é validado contra a política na criação e em cada resolução.
- Q: Onde ficam as chaves de API da superfície privada, e como uma chave é revogada? → A: Em armazenamento persistente (Postgres no perfil persistente, memória nos demais), só o hash, amarrado a subject e grupos; a chave em claro aparece uma única vez, na emissão. O operador emite, lista e revoga pela linha de comando e por um endpoint de administração na superfície privada, restrito a um grupo de administração que ele declara. A revogação vale a partir da requisição seguinte, sem restart.
- Q: Na Fase 2, sem registry MCP (007, Fase 3) nem coleções (Fase 5), como a 003 trata Assistants que declaram MCPs ou coleções? → A: Este módulo declara a forma dos catálogos que exige — aliases MCP visíveis a um Principal e nomes de coleção existentes — e a composition root (011) injeta catálogos vazios até os módulos donos existirem. Referência a MCP ou coleção deixa o Assistant indisponível com erro explícito (falha fechada). Os testes usam catálogos em memória com entradas; a 007 e o índice entram como troca de adapter, sem mudar a resolução.
- Q: Se `auth.allow` já decide quem resolve um Assistant, o que `visibility` muda? → A: Só defaults de segurança. A listagem é exatamente o conjunto que o Principal resolve. Um Assistant público nunca concede tools de escrita; um privado exige `allow` explícito, por subjects ou grupos, e `*` num privado é erro de validação. Assistants de usuário são sempre privados, com o dono como único permitido.
- Q: Como um Assistant de usuário é endereçado no id de modelo, e o que acontece se um deploy posterior traz um Assistant de sistema com o mesmo nome? → A: Assistants de usuário têm o prefixo reservado `~` (ex.: `~meu-rag/<modelo>`), que nome de sistema não pode usar; a unicidade é por (dono, nome). Colisão entre sistema e usuário é impossível por construção, nenhum deploy sombreia um Assistant de usuário, e a origem fica visível na listagem.

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
4. **Given** uma chave emitida pelo operador (linha de comando ou endpoint de administração), **When** ela é revogada, **Then** a requisição seguinte com essa chave é rejeitada como não autenticada, sem restart.
5. **Given** um Principal da superfície privada fora do grupo de administração, **When** chama a administração de chaves, **Then** recebe a mesma resposta que um recurso inexistente (404).

---

### User Story 3 - Autorização por Assistant sem vazar existência (Priority: P1)

A resolução compara o Principal com as regras do Assistant. Não autorizado recebe exatamente a mesma resposta que um Assistant inexistente (404). Autorizado recebe um Execution Grant.

**Why this priority**: 403 revelaria a existência de Assistants privados a qualquer usuário público (elo 2 da cadeia de enforcement).

**Independent Test**: Um usuário público pede um Assistant privado existente e um Assistant inexistente; as duas respostas são indistinguíveis (status, corpo e tempo de resposta na mesma ordem de grandeza).

**Acceptance Scenarios**:

1. **Given** um Assistant privado que aceita só `api_key` e `user:caio`, **When** um Principal OIDC o solicita, **Then** recebe 404.
2. **Given** o mesmo Assistant, **When** `user:caio` o solicita via chave de API, **Then** recebe um Execution Grant.
3. **Given** um Assistant público com `allow: ["*"]`, **When** qualquer Principal autenticado por esquema aceito o solicita, **Then** recebe um grant.
4. **Given** um Assistant privado com `allow: ["*"]`, **When** validado, **Then** é rejeitado — privado exige principals ou grupos explícitos.

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

A listagem de Assistants disponíveis mostra ao Principal exatamente os que ele pode resolver (elo 1): Assistants privados aparecem só para quem o `allow` deles nomeia, por subject ou grupo. `visibility` não é filtro de listagem.

**Why this priority**: É o que permite expor cada Assistant como "modelo" num dropdown (spec 008) sem vazar nada.

**Independent Test**: Listar com um Principal público e com o dono de um Assistant privado; as listas diferem exatamente pelos Assistants privados.

**Acceptance Scenarios**:

1. **Given** Assistants públicos e privados, **When** um Principal público lista, **Then** vê apenas os públicos que aceitam seu esquema.
2. **Given** um Assistant privado que permite `group:chefia`, **When** um Principal desse grupo lista, **Then** o Assistant aparece — e o mesmo Principal o resolve.

---

### User Story 6 - Usuário cria Assistants próprios (Priority: P2)

Um usuário autenticado cria, edita e remove Assistants próprios, que ficam persistidos e visíveis só para ele. Um Assistant de usuário pode referenciar apenas o que a política de Assistants de usuário aplicável a ele permite — packs, flows, modelos e limites até o teto — e MCPs do próprio usuário (ou globais permitidos). A política aplicável é a primeira, na ordem declarada pelo operador, cujo seletor (grupo ou `*`) casa com o Principal.

**Why this priority**: Nível 1 de extensão (ADR-003): o usuário compõe capacidades sem código e sem restart.

**Independent Test**: Criar um Assistant de usuário com um MCP próprio; outro usuário não o vê nem o resolve.

**Acceptance Scenarios**:

1. **Given** um usuário com um MCP próprio, **When** cria um Assistant que o referencia, **Then** o Assistant é salvo e resolvível só por ele.
2. **Given** um usuário, **When** tenta criar um Assistant que referencia MCP de outro usuário, **Then** a criação é rejeitada — e a mensagem não confirma a existência do MCP alheio.
3. **Given** um Assistant de usuário, **When** o operador faz novo deploy, **Then** o Assistant permanece (vive no banco, não no arquivo de configuração).
4. **Given** um usuário que cria o Assistant `meu-rag`, **When** lista ou o usa, **Then** o endereça como `~meu-rag`; outro usuário com um `~meu-rag` próprio resolve o dele, e nenhum dos dois descobre que o outro existe.
5. **Given** uma política que permite só modelos `ollama/*` e `rpm` até 10 ao grupo do usuário, **When** ele cria um Assistant com modelo `openai/...` ou `rpm: 50`, **Then** a criação é rejeitada com erro que nomeia o campo fora da política.
6. **Given** um Principal que não casa com nenhuma política de Assistants de usuário, **When** tenta criar um Assistant, **Then** a criação é rejeitada.

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

- Assistant de usuário com o mesmo nome de um Assistant de sistema: impossível por construção — nomes de usuário levam o prefixo `~`, que nome de sistema não pode usar (erro de configuração no boot). Dois usuários podem ter `~meu-rag`; cada um resolve e lista só o próprio.
- Chave de API revogada durante uma execução em andamento: a execução termina; novas requisições são rejeitadas.
- Grupos do Principal mudam entre requisições: a autorização é avaliada a cada requisição.
- Política de Assistants de usuário mais restrita depois de um deploy, ou usuário que sai do grupo cuja política permitia o que o Assistant declara: o Assistant continua salvo, mas fica indisponível com erro explícito que nomeia o que saiu da política — nunca é resolvido com permissões que a política atual não concede.
- Assistant privado cujo nome é adivinhado: 404 idêntico ao de inexistente.
- Allowlist de modelos vazia: Assistant inválido na validação.
- Assistant que declara MCP ou coleção antes de os módulos donos existirem (Fases 2 a 4): o catálogo injetado está vazio, e o Assistant fica indisponível com erro que nomeia a referência — nunca é resolvido com a referência ignorada.
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
- **FR-008**: A listagem de Assistants DEVE conter exatamente os que o Principal pode resolver; `visibility` não filtra a listagem.
- **FR-009**: Usuários DEVEM poder criar, ler, atualizar e remover Assistants próprios, restritos à política de Assistants de usuário aplicável (FR-014) e a MCPs próprios ou globais permitidos.
- **FR-010**: O sistema DEVE aplicar limite de taxa por (Principal, Assistant) e repassar ao motor os limites de iteração e de tokens via grant.
- **FR-011**: O sistema DEVE validar, no boot e por linha de comando, as referências de todo Assistant (pack, MCP, coleção, flow, modelos), marcando inválidos como indisponíveis com erro explícito.
- **FR-012**: Um Assistant público NÃO DEVE conceder tools de escrita — declará-las num público é erro de validação; um privado só as concede se declaradas. Um Assistant privado DEVE declarar `allow` explícito (subjects ou grupos); `*` num privado é erro de validação. Assistants de usuário são sempre privados, com o dono como único permitido.
- **FR-013**: Assistants de sistema DEVEM ser sobrescritos apenas por novo deploy; Assistants de usuário, apenas pelo dono.
- **FR-014**: O operador DEVE declarar, em configuração versionada, políticas de Assistants de usuário ordenadas, cada uma com seletor (grupo ou `*`) e definindo packs, flows e coleções permitidos, allowlist de modelos, teto de limites e se tools de escrita são permitidas; vale a primeira que casa com o Principal, e sem política aplicável o Principal não cria Assistants. O Assistant de usuário DEVE ser validado contra a política aplicável na criação, na atualização e em cada resolução.
- **FR-015**: Chaves de API DEVEM ficar em armazenamento persistente apenas como hash, amarradas a subject e grupos, e a chave em claro DEVE ser exibida uma única vez, na emissão. Emissão, listagem e revogação DEVEM estar disponíveis por linha de comando e por administração na superfície privada, esta restrita a um grupo de administração declarado pelo operador; a revogação DEVE valer a partir da requisição seguinte, sem restart.
- **FR-016**: A validação de MCPs e coleções DEVE consultar catálogos por portas cuja forma este módulo declara (aliases MCP visíveis a um Principal; nomes de coleção existentes). Enquanto o módulo dono não existe, o catálogo injetado DEVE estar vazio, e toda referência DEVE tornar o Assistant indisponível com erro explícito.
- **FR-017**: Assistants de usuário DEVEM ser endereçados com o prefixo reservado `~` (`~<nome>`), únicos por (dono, nome) e resolvidos apenas no escopo do dono; nome de Assistant de sistema começando com `~` DEVE ser rejeitado como erro de configuração.

### Key Entities

- **Principal**: identificador (`user:…`, `svc:…`), esquema, grupos.
- **API Key**: hash, subject e grupos do dono, estado (ativa ou revogada), instante de emissão e de revogação; a chave em claro não é armazenada.
- **Assistant**: configuração nomeada (ver FR-004); origem sistema ou usuário; dono (quando de usuário). Nome de usuário leva o prefixo `~` e é único por dono; nome de sistema é único na instalação e não começa com `~`. `visibility` define defaults de segurança (FR-012), não a listagem.
- **Execution Grant**: configuração efetiva de uma execução — Assistant, Principal, flow, packs ordenados, aliases MCP, coleções, tools permitidas, tools de escrita, política de modelo por papel, limites.
- **Rate Budget**: contador por (Principal, Assistant).
- **User Assistant Policy**: seletor (grupo ou `*`), packs, flows e coleções permitidos, allowlist de modelos, teto de limites, permissão de tools de escrita (default: não); declarada pelo operador, avaliada em ordem (primeira que casa).

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
- Chaves de API são emitidas pelo operador; a primeira sai pela linha de comando, já que o endpoint de administração exige uma chave do grupo de administração.
- A verificação de que o modelo solicitado existe no provider é feita pela spec 006; esta spec aplica a allowlist.
