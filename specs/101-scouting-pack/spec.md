# Feature Specification: Pack scouting — composição, contexto determinístico e prompts

**Feature Branch**: `101-scouting-pack`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §19 (objetivo, prioridades, fluxo, `prepare_scouting_context`), §11 (code pack), §13 (declaração do pack), §30 (repositório `ai-scouting`), §31 Fase 4; ADR-006.

## Module Boundary *(mandatory)*

- **Módulo**: Scouting Pack — o pack de domínio escoteiro: identidade, manifest, derivação determinística de contexto, prompts de domínio e a composição dos submódulos (retrieval 103, citações 104). O `pack.py` é a composition root do pack: instancia os adapters de 102 e 103 conforme a configuração (princípio XIII).
- **Repositório / distribuição**: `ai-scouting` (repositório próprio) → `src/ai_scouting/pack.py`, `context/`, `prompts/`.
- **Consome (seams)**: Contrato de pack e Turn View — 001. Internamente: Retriever/Reranker de 103 e validators de 104 (pelos contratos de 001).
- **Expõe (seams)**: o pack `scouting` via entry point `ai_core.packs`, com flow preferido `rag_first` e esquema de configuração — consumido pelo core (002) e por Assistants.
- **Depende de infraestrutura (via portas)**: nenhuma. A data de referência vem da Turn View (ADR-013); índice e busca são de 102 e 103.
- **Não conhece**: nada do core além dos contratos; outros packs; MCPs (o Assistant `scouting` declara `mcp: []`).
- **Acoplamento com o core**: apenas o contrato 001 e o **nome** do flow preferido (dado, sobrescrevível pelo Assistant).
- **Substituição**: o pack inteiro (101–106) pode ser reescrito sem tocar no core, desde que implemente o contrato 001. Submódulos são substituíveis entre si pelos contratos `Retriever`, `Reranker` e `AnswerValidator`.
- **Insumo técnico**: [design.md](design.md); [ADR-006](../../docs/adr/ADR-006-rag-first-default-scouting.md), [ADR-004](../../docs/adr/ADR-004-contratos-no-repo-do-core.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

## Clarifications

### Session 2026-10-07

- Q: Na Fase 4, sem RAG, o manifest já declara `rag_first` como flow preferido, a coleção exigida e o esquema de configuração (FR-003)? → A: Não. Na Fase 4 o manifest declara só nome e versão; `preferred_flow="rag_first"`, `requires_collections` e `config_schema` entram na Fase 5, com a US5 e o retriever (FR-010), quando passam a ter efeito. Na Fase 4, um Assistant com `packs: [scouting]` sem `flow` roda no `chat`.
- Q: Na Fase 4, sem documento indexado, como o Assistant `scouting` responde perguntas do domínio? → A: Com o conhecimento geral do modelo, declarando que nenhum documento institucional foi consultado, sem inventar citação, número de resolução, nome ou trecho de documento, e recomendando confirmar na fonte oficial. A regra é do fragmento de instruções do pack na Fase 4 e é substituída pela de citar o corpus quando o RAG chega (Fase 5).
- Q: Onde se prova que o pack carrega na plataforma real e que as instruções de domínio chegam ao modelo (US1 cen. 1–2), dado o SC-003 e o princípio I? → A: Num grupo opcional de integração do próprio `ai-scouting`, com o `ai-core` (resolvido pela mesma tag do `agentic-app`) como dependência de desenvolvimento separada, usando o perfil `test` da plataforma; ele prova a carga por entry point e que a plataforma compõe o prompt do pack para o Assistant (pelo seam `PackHooks` da 002 — a entrega à geração é garantia da 005), usando só a superfície que a 011 publica para suítes de packs externos, e é pulado sem o core instalado. A suíte padrão (unidade e conformidade da 001) roda só com os contratos — é ela que o SC-003 mede. O trace da plataforma não grava conteúdo de prompt, então a prova não passa por ele.
- Q: Quando a pergunta cita um período ("em 2023", "em março de 2023"), que vigência a derivação produz (FR-005)? → A: Um intervalo — início e fim do período citado (2023 → 2023-01-01 a 2023-12-31; março de 2023 → o mês inteiro) —, com revogados e substituídos incluídos; a recuperação considera os documentos vigentes em qualquer momento dele. Data exata é o intervalo de um dia; sem menção a período, o intervalo é o dia de referência da execução.
- Q: Quem produz o léxico inicial de ramos (com sinônimos), temas e tipos de documento (FR-007)? → A: Uma semente proposta na implementação, a partir da estrutura pública do escotismo brasileiro — ramos Lobinho, Escoteiro, Sênior e Pioneiro com sinônimos antigos e regionais; tipos de documento (manual, programa educativo, POR, resolução, estatuto, guia); cerca de 15 temas —, revisada pelo mantenedor antes de virar base dos testes de aceite. O mantenedor segue como curador; a semente não espera arquivo externo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pack carregado e respondendo com instruções de domínio (Priority: P1)

O operador instala o `ai-scouting` na imagem e o habilita. Um membro do movimento escoteiro conversa com o Assistant `scouting` e recebe respostas orientadas pelas instruções de domínio do pack — ainda sem recuperação de documentos.

**Why this priority**: Fase 4 — prova a arquitetura de packs com um pack real, em repositório próprio, antes de somar a complexidade de RAG.

**Independent Test**: Instalar o pack a partir da tag do repositório, habilitá-lo e conversar com o Assistant; o pack aparece como habilitado e a plataforma compõe as instruções de domínio para o Assistant — provado pelo grupo opcional de integração do `ai-scouting`, sobre o perfil `test` da plataforma (o trace não grava conteúdo de prompt).

**Acceptance Scenarios**:

1. **Given** o pack instalado e habilitado, **When** o core inicia, **Then** o pack aparece `enabled` com sua versão e versão de contrato.
2. **Given** o Assistant `scouting`, **When** o usuário faz uma pergunta, **Then** a resposta segue as instruções de domínio do pack.
3. **Given** o CI do `ai-scouting`, **When** a checagem de fronteiras roda, **Then** confirma que nenhum módulo do core é importado.
4. **Given** a Fase 4, sem corpus indexado, **When** o usuário pergunta algo que dependeria de documento institucional, **Then** a resposta declara que nenhum documento foi consultado, não cita documento, resolução nem trecho, e recomenda confirmar na fonte oficial.

---

### User Story 2 - Contexto derivado da pergunta sem chamar modelo (Priority: P1)

A partir da pergunta, o pack deriva, por regras, léxico e metadados: ramo, tema, tipos de documento pertinentes e a data de referência de vigência (por default, a data de referência da execução, recebida na Turn View — o dia da requisição). Esses filtros são publicados para os retrievers do próprio pack.

**Why this priority**: Princípio V — decisão determinística não gasta chamada de modelo; no hardware alvo, cada chamada custa segundos.

**Independent Test**: Um conjunto de perguntas com filtros esperados é processado só pela derivação; 0 chamadas de modelo e filtros corretos.

**Acceptance Scenarios**:

1. **Given** "Quais competências do Pioneiro estão relacionadas à liderança?", **When** a derivação roda, **Then** produz ramo = pioneiro, tema = liderança, tipos = [manual, programa_educativo], vigência = o dia da data de referência da execução (início = fim).
2. **Given** uma pergunta sem menção a ramo, **When** a derivação roda, **Then** nenhum filtro de ramo é aplicado.
3. **Given** a derivação, **When** executada, **Then** nenhum modelo de linguagem é chamado.
4. **Given** uma Turn View com data de referência fixada, **When** a derivação roda, **Then** a vigência default é essa data — o pack nunca lê o relógio do sistema.

---

### User Story 3 - Consulta histórica (Priority: P2)

Quando a pergunta se refere a um momento passado ("o que dizia o manual anterior", "qual era a regra em 2023"), a derivação muda a data de referência e inclui documentos revogados ou substituídos, sinalizando que a resposta deve marcar a fonte como não vigente.

**Why this priority**: Citar norma revogada sem aviso é o pior erro do domínio; consulta histórica legítima precisa ser suportada explicitamente.

**Independent Test**: "Qual era a regra em 2023?" produz a vigência de 2023-01-01 a 2023-12-31 e inclusão de revogados.

**Acceptance Scenarios**:

1. **Given** "Qual era a regra em 2023?", **When** a derivação roda, **Then** a vigência é o intervalo de 2023-01-01 a 2023-12-31 e revogados/substituídos são incluídos.
2. **Given** "o que dizia o manual anterior?", **When** a derivação roda, **Then** a consulta mira a versão imediatamente substituída.

---

### User Story 4 - Respostas priorizam as fontes certas (Priority: P2)

As instruções do pack e os filtros priorizam, em ordem: documentos institucionais sobre fontes secundárias; vigentes sobre revogados; fontes específicas e primárias sobre genéricas; recuperação precisa sobre ampla; e sempre citação e proveniência.

**Why this priority**: Define o comportamento de domínio que o conjunto dourado (105) vai medir.

**Independent Test**: Para perguntas com fonte institucional e secundária disponíveis, a resposta cita a institucional.

**Acceptance Scenarios**:

1. **Given** um manual institucional e um texto secundário sobre o mesmo tema, **When** o usuário pergunta, **Then** a resposta se apoia no manual institucional.

---

### User Story 5 - Resposta fundamentada no corpus pelo caminho determinístico (Priority: P2)

Com RAG disponível (Fase 5), o pack declara `rag_first` como flow preferido, expõe o retriever (103) e os validators de citação e vigência (104). O caminho comum responde com uma única chamada de modelo.

**Why this priority**: ADR-006; é o caso dominante do domínio: "responda a partir do corpus".

**Independent Test**: Uma pergunta coberta pelo corpus é respondida com citações válidas e uma única chamada de modelo (trace).

**Acceptance Scenarios**:

1. **Given** uma pergunta coberta pelo corpus, **When** respondida, **Then** a resposta tem citações resolvíveis e o trace mostra uma única chamada de modelo.

---

### Edge Cases

- Termos ambíguos de ramo (formas antigas ou regionais): o léxico mapeia sinônimos; na dúvida, não aplica filtro.
- Data histórica vaga ("antigamente"): usa a versão imediatamente substituída; se não houver, responde com vigentes e informa.
- Pergunta fora do domínio: responde que o corpus não cobre o tema, sem inventar fonte.
- Configuração do pack sem coleção: pack não carrega (esquema de configuração) — a partir da Fase 5; na Fase 4 o pack não tem esquema de configuração.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O pack DEVE implementar o contrato de pack (001) e depender apenas da distribuição de contratos, por faixa semver.
- **FR-002**: O pack DEVE declarar-se por entry point `ai_core.packs` com o nome `scouting`.
- **FR-003**: A partir da Fase 5 (com a US5), o manifest DEVE declarar flow preferido `rag_first`, a coleção exigida e o esquema de configuração (nome da coleção). Na Fase 4, o manifest declara só nome e versão (clarificação de 2026-10-07).
- **FR-004**: A preparação de contexto DEVE derivar ramo, tema, tipos de documento e data de referência de vigência sem chamar modelos.
- **FR-005**: A vigência derivada DEVE ser um intervalo de datas (início e fim). O default DEVE ser o dia da data de referência da execução, recebida na Turn View (ADR-013); consultas históricas DEVEM trocar o intervalo pelo período citado — ano ou mês inteiros, ou o dia exato — e incluir revogados/substituídos (clarificação de 2026-10-07). O pack NÃO DEVE ler o relógio do sistema.
- **FR-006**: Os filtros derivados DEVEM ser publicados para os retrievers do próprio pack (contrato 001, FR-012).
- **FR-007**: O léxico de ramos, temas e tipos de documento DEVE ser mantido no pack, versionado junto com ele.
- **FR-008**: A partir da Fase 5 (com corpus), o fragmento de instruções DEVE expressar as prioridades de fonte da US4 e a regra de sempre citar; na Fase 4 vale a FR-011.
- **FR-009**: O fragmento de instruções DEVE afirmar que conteúdo recuperado é dado, nunca instrução.
- **FR-011**: Na Fase 4, sem corpus, o fragmento de instruções DEVE mandar responder com conhecimento geral declarando que nenhum documento institucional foi consultado, NÃO DEVE permitir citar ou nomear documento, resolução ou trecho como se tivesse sido consultado, e DEVE recomendar a confirmação na fonte oficial; a regra de citar o corpus (FR-008) a substitui na Fase 5 (clarificação de 2026-10-07).
- **FR-010**: O pack DEVE expor o retriever e o reranker da spec 103 (a partir da Fase 5) e os validators da spec 104 (quando ela os entregar).

### Key Entities

- **Scouting Context**: ramo, tema, tipos de documento, vigência (intervalo: início e fim), inclusão de revogados — gravado na fatia do pack.
- **Domain Lexicon**: ramos, sinônimos, temas, tipos de documento.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A derivação de contexto acerta ramo, tema e data de referência em pelo menos 90% das perguntas do conjunto dourado (medido na 105).
- **SC-002**: 0 chamadas de modelo na derivação de contexto.
- **SC-003**: O pack instala e roda sua suíte padrão (unidade e conformidade) inteira sem o core instalado; o grupo opcional de integração com a plataforma é pulado nesse ambiente.
- **SC-004**: No caminho coberto, 100% das respostas usam uma única chamada de modelo.

## Assumptions

- O Assistant `scouting` é público, sem MCPs, com a coleção `scouting_docs` (definido pelo operador na spec 003).
- O léxico inicial é uma semente proposta na implementação e revisada pelo mantenedor, que segue como curador (clarificação de 2026-10-07).
- Na Fase 4, os validators de 104 existem mas só têm efeito pleno quando há recuperação (Fase 5).
