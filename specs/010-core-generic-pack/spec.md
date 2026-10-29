# Feature Specification: Pack genérico de referência (`axon-generic`)

**Feature Branch**: `010-core-generic-pack`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §1 (escopo), §30 (`ai-generic`), Parte IX ("O papel do ai-generic"); ADR-004. Fase 9, incremento 9.5 (2026-10-20): identidade Axon — ADR-037.

## Module Boundary *(mandatory)*

- **Módulo**: `axon-generic` — pack de uso geral e pack de referência: primeiro consumidor real dos contratos e fixture dos testes de carregamento de pack.
- **Repositório / distribuição**: workspace `axon-ai/` → `packages/generic`, distribuição própria `axon-generic` (import `axon_generic`), descoberta por entry point como um pack externo.
- **Consome (seams)**: Contrato de pack — 001. Nada mais.
- **Expõe (seams)**: o pack `generic` (via entry point) — consumido por 002 (testes de carga) e por Assistants.
- **Depende de infraestrutura (via portas)**: nenhuma na v1. Se uma tool nativa fizer I/O, o cliente fica num adapter interno do pack, instanciado pelo `pack.py`.
- **Não conhece**: nada do core além dos contratos.
- **Substituição**: só sai do workspace se deixar de agregar algo além de prompts (FR-005); nesse caso vira um Assistant e a fixture de carga passa a ser um pack mínimo de teste. Na Fase 3 (clarificação de 2026-10-07), continua pack.
- **Insumo técnico**: [design.md](design.md); [ADR-004](../../docs/adr/ADR-004-contratos-no-repo-do-core.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md) (nomes).

## Clarifications

### Session 2026-09-17

- Q: Quais capacidades o pack oferece na v1 (Fase 1)? → A: `system_prompt` de uso geral, uma tool nativa determinística (sem I/O) e um validator determinístico — três hooks de catálogo mais o `manifest()`, exercitados pela suíte de conformidade e pela carga real da 002. Sem `prepare_context`, sem retriever e sem reranker na v1; como não há I/O, o pack não declara porta secundária.
- Q: Como o pack declara a dependência de `axon-ai-contracts`? → A: Pela faixa derivada da `contract_version` (`>=0.1,<0.2`, ADR-014), com `[tool.uv.sources] axon-ai-contracts = { workspace = true }` para resolver no commit local enquanto o pack mora no workspace — o mesmo que um pack externo declara. Supera a redação "sem faixa semver" da FR-004 e a linha correspondente do `design.md`, que precedem o ADR-014 e a etapa 9 da suíte de conformidade.
- Q: O que o manifest declara na v1, além de nome e versão? → A: Nada — sem flow preferido, sem schema de configuração, sem dependências de pack e sem coleções exigidas. O Assistant escolhe o flow; a preferência por flow agêntico só faz sentido na Fase 3, quando esse flow existir (US2).
- Q: Onde vive o teste que prova a descoberta e a carga do pack real por entry point? → A: Nos testes de integração do core (o pack entra como dependência de desenvolvimento do workspace e é carregado pelo mecanismo de entry point, sem caso especial), enquanto a suíte de conformidade roda nos testes do próprio pack, sem tocar no core. O pack continua sem conhecer o core: a verificação de fronteiras cobre o código, não as dependências de teste.
- Q: Em que pasta do workspace mora a distribuição do pack? → A: Ao lado das outras distribuições do workspace, no mesmo padrão de pasta já usado por contratos e core — sem mudança na declaração de membros do workspace. Supera a linha de localização do `design.md`, escrita antes de o workspace existir. A fronteira com o core continua a ser provada pela verificação de imports, não pela posição da pasta.

### Session 2026-10-07

- Q: Na Fase 3, o pack genérico continua sendo pack ou vira apenas um Assistant com `packs: []` e sai do workspace (FR-005)? → A: Continua pack. A FR-005 vira regra permanente: o pack existe enquanto agregar algum hook além de prompt — hoje, a tool nativa `calculate` e o validator `non_empty_answer` —, e segue como referência dos contratos e fixture de carga por entry point.
- Q: O manifest do pack genérico declara `agentic` como flow preferido na Fase 3 (FR-007)? → A: Não. A FR-007 vale também na Fase 3: o manifest não declara flow preferido, e o Assistant genérico com MCP declara `flow: agentic` e o papel `controller` explicitamente (princípio VIII). Assistants com `packs: [generic]` sem `flow` continuam no `chat`.
- Q: O prompt de sistema do pack é reescrito para orientar o uso de resultados de qualquer ferramenta, sem mandar o modelo "usar a ferramenta de cálculo"? → A: Sim. O parágrafo de ferramentas fica neutro quanto ao flow e vale para qualquer tool (do pack ou de MCP): a resposta se baseia nos resultados de ferramentas presentes na conversa e os apresenta; se uma ferramenta falhou ou não trouxe o dado, diz isso em vez de estimar. O prompt não manda chamar ferramentas — no `agentic` ele só chega à geração, e quem chama é o controller. A regra "dado, nunca instrução" continua; o contrato 001 não muda.

### Session 2026-10-20

- Q: Quais são o nome da distribuição, o import e a versão do pack de referência depois do renome da plataforma? → A: Distribuição `axon-generic`, import `axon_generic`, versão `0.2.0` (ADR-037, itens 2 e 4: no código, o prefixo `ai-` vira `axon-`). A versão do manifest acompanha a da distribuição, como antes. A pasta `packages/generic` não muda. A faixa `axon-ai-contracts>=0.2,<0.3` e a `contract_version` "0.2" já vieram da passada da 001; esta passada não as muda. O pack sai na tag `v0.7.0-rc1`, com o core, depois da passada da 013 (ADR-004: core e pack de referência lançados juntos).
- Q: Por que a minor sobe, se nenhum comportamento muda? → A: O nome da distribuição e o do import são a interface de quem depende do pack ou o copia; renomeá-los quebra quem o instala ou o importa pelo nome. Pela política 0.x (ADR-014), quebra sobe a minor: `0.1.0` → `0.2.0`.
- Q: Há alias, reexportação ou janela para o nome antigo? → A: Não. Corte seco (ADR-037, item 3): não existe módulo `ai_generic` nem distribuição `ai-generic` no workspace, e nada a preserva — o pack não tem consumidor que o importe (o core o descobre por entry point).
- Q: O que **não** muda com o renome? → A: O nome do pack, `generic` — o nome do entry point, `GenericPack.name`, o namespace das tools (`generic.calculate`) e o `packs: [generic]` dos Assistants —, o manifest além da versão, o prompt, a tool `calculate`, o validator `non_empty_answer` e o flow `agentic` (ADR-037, item 5). O grupo de entry point (`ai_core.packs`) passa a `axon.packs` na passada da 002, não nesta.
- Q: Quem acompanha o renome nesta passada? → A: Os consumidores no workspace, de forma mecânica (ADR-037, item 7): a fonte e o grupo de desenvolvimento do workspace, a verificação de fronteiras (raiz e as três regras do pack), a ordenação de imports, a suíte do core que carrega o pack real por entry point (distribuição `axon-generic`, versão `0.2.0`), a CI (o ambiente limpo passa a esperar `axon-ai-contracts`, `axon-generic` e `typing-extensions`) e os documentos vivos das specs do core que citam o pack. Ficam para as passadas donas: as specs `1xx` (101), o contrato e os arquivos da instalação (002, instalação), o `CLAUDE.md` (fechamento) e o histórico (ADR-037, item 6).

### Session 2026-10-28

- Q: Onde fica a tool que desenha gráficos ([ADR-052](../../docs/adr/ADR-052-graficos-na-conversa.md))? → A: No `axon-generic`, como `generic.chart`: tool nativa, sem escrita, que recebe dados num esquema fechado (tipo, título, subtítulo, eixos, unidade e séries de pontos `{x, y}`), monta o `Chart` do contrato 001 e o devolve em `ToolResult.charts`. Nenhum HTML sai do pack; quem desenha é a plataforma. Erro de validação volta em `error`, legível, sem levantar.
- Q: Que versão sai? → A: `0.3.0`, com `contract_version = "0.2.4"` e a dependência `axon-ai-contracts>=0.2.4,<0.3`. O prompt não muda (FR-008): quem decide chamar a tool é o controller, pela descrição dela.

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

### User Story 3 - Identidade Axon: o pack de referência com o nome da plataforma (Priority: P2)

A plataforma passa a se chamar Axon (ADR-037). Quem copia o pack de referência para começar um pack novo encontra a distribuição `axon-generic` e o pacote `axon_generic`, ao lado de `axon-ai-contracts`; o operador e os Assistants continuam a usá-lo pelo nome `generic`, sem perceber diferença; a fronteira com o core continua verificada nas duas direções, com os nomes novos.

**Why this priority**: O pack de referência é o exemplo que todo pack copia (inclusive o de domínio, na passada da 101) e a fixture de carga do core; um exemplo com o nome antigo ensinaria o vocabulário errado. P2 porque nenhum comportamento muda, só o nome pelo qual o pack é instalado e importado.

**Independent Test**: Num ambiente limpo só com os contratos, instalar o pack: a resolução tem exatamente `axon-ai-contracts`, `axon-generic` e `typing-extensions`, e a suíte de conformidade passa sem nenhum item; no workspace, o core o carrega por entry point como `generic` da distribuição `axon-generic` 0.2.0.

**Acceptance Scenarios**:

1. **Given** o workspace sincronizado, **When** se consulta a distribuição instalada do pack, **Then** ela é `axon-generic` 0.2.0, o pacote importável é `axon_generic`, e não existem o módulo `ai_generic` nem a distribuição `ai-generic`.
2. **Given** um ambiente limpo com os contratos e o pack, **When** a resolução é listada e a suíte de conformidade roda, **Then** a resolução tem exatamente `axon-ai-contracts`, `axon-generic` e `typing-extensions`, e o relatório não tem nenhum item — a etapa de distribuição confere a faixa `>=0.2,<0.3` no pacote `axon-generic`.
3. **Given** o pack instalado no workspace, **When** o core o descobre pelo mecanismo de qualquer pack externo, **Then** o registry o mostra com o nome `generic`, a distribuição `axon-generic`, a versão `0.2.0`, a `contract_version` "0.2", a tool `calculate` e o validator `non_empty_answer`, e um Assistant com `packs: [generic]` resolve como antes.
4. **Given** o CI do repositório, **When** a verificação de fronteiras roda, **Then** ela confirma, com os nomes novos, que o pack não importa o core, que o core não importa o pack e que o pack não importa frameworks de infraestrutura.
5. **Given** o Assistant genérico da US2 (`flow: agentic`, `controller` e um MCP), **When** o usuário pede algo que exige a tool, **Then** a resposta usa o resultado dela, como na US2.

---

### Edge Cases

- Pack genérico desabilitado: testes de carga usam o pack mínimo de teste; nada no core depende dele.
- Ambiente reaproveitado com a distribuição antiga (`ai-generic`) ainda instalada ao lado de `axon-generic`: os dois anunciam o pack `generic`, e a regra de nome duplicado da 002 vale — nenhum dos dois carrega, e o erro nomeia o conflito; recriar o ambiente (sincronizar o workspace) remove a antiga.
- Código ou exemplo que ainda importa `ai_generic`: o import falha; não há módulo de compatibilidade (corte seco).

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

- **FR-009**: O pack DEVE ser a distribuição `axon-generic`, com o pacote importável `axon_generic`, na versão `0.2.0`, igual à versão do manifest. NÃO DEVE existir alias, reexportação nem módulo com o nome antigo (`ai-generic`, `ai_generic`): corte seco (ADR-037; clarificação de 2026-10-20).
- **FR-010**: O renome NÃO DEVE mudar o nome do pack (`generic`, também o do entry point e o namespace das tools), o manifest além da versão, o prompt, a tool, o validator nem a dependência de contratos (`axon-ai-contracts>=0.2,<0.3`, `contract_version` "0.2"). O grupo de entry point é o do Pack Runtime (002) e muda na passada dele.
- **FR-011**: A verificação de fronteiras do SC-001 DEVE nomear o pacote `axon_generic`: o pack não importa `axon_ai`, `axon_ai` não importa o pack e o pack não importa frameworks de infraestrutura.
- **FR-012**: Os consumidores do pack no workspace — a dependência de desenvolvimento, a suíte do core que o carrega por entry point, a CI e os documentos vivos das specs do core que o citam — DEVEM usar o nome novo na mesma passada (ADR-037, item 7), para a CI ficar verde.
- **FR-013**: O pack DEVE oferecer a tool nativa `chart` (`generic.chart`, sem escrita): parâmetros num esquema fechado do subconjunto estrito (objetos com `additionalProperties: false`, sem `$ref` nem regex, até 8 séries), resultado `ToolResult` com o `Chart` em `charts` e um resumo curto em `content`; argumento que o `Chart` recusa DEVE voltar como `error` legível, sem exceção ([ADR-052](../../docs/adr/ADR-052-graficos-na-conversa.md), item 7). Versão `0.3.0`, `contract_version` `0.2.4`.


### Key Entities

- **Generic Pack**: prompt de sistema de uso geral, uma tool nativa determinística e um validator determinístico (v1).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 imports do core no pack, verificado no CI.
- **SC-002**: Os testes de integração do core carregam o pack pelo mecanismo de entry point, sem nenhum caso especial no código do core.
- **SC-003**: Depois da passada da US3, zero ocorrências de `ai_generic` ou `ai-generic` no código, nos testes, na configuração e na CI do workspace e nos documentos vivos das specs do core (fora do histórico do ADR-037, item 6, das specs `1xx`, do contrato da instalação e do `CLAUDE.md`, que mudam nas passadas donas, e dos testes do corte seco e dos textos que nomeiam o antigo de propósito), e as suítes do workspace passam com o pack `axon-generic` 0.2.0.

## Assumptions

- O pack continua sendo a fixture de carga por entry point dos testes de integração do core enquanto a FR-005 o mantiver como pack.
- US3 (ADR-037): até a passada da 002, o pack continua anunciado no grupo de entry point de nome antigo, que é o que o Pack Runtime procura; os dois mudam juntos lá. A instalação continua presa a uma tag antiga (com `ai-generic`) até a passada dela, e o pack de domínio, até a da 101.
