# Feature Specification: Pack scouting — composição, contexto determinístico e prompts

**Feature Branch**: `101-scouting-pack`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §19 (objetivo, prioridades, fluxo, `prepare_scouting_context`), §11 (code pack), §13 (declaração do pack), §30 (repositório `ai-scouting`), §31 Fase 4; ADR-006. Fase 9, incremento 9.5 (2026-10-20): identidade Axon — ADR-037.

## Module Boundary *(mandatory)*

- **Módulo**: Scouting Pack — o pack de domínio escoteiro: identidade, manifest, derivação determinística de contexto, prompts de domínio e a composição dos submódulos (retrieval 103, citações 104). O `pack.py` é a composition root do pack: instancia os adapters de 102 e 103 conforme a configuração (princípio XIII).
- **Repositório / distribuição**: `axon-scouting` (repositório próprio) → `src/axon_scouting/pack.py`, `context/`, `prompts/`.
- **Consome (seams)**: Contrato de pack e Turn View — 001. Internamente: Retriever/Reranker de 103 e validators de 104 (pelos contratos de 001).
- **Expõe (seams)**: o pack `scouting` via entry point `axon.packs`, com flow preferido `rag_first` e esquema de configuração — consumido pelo core (002) e por Assistants.
- **Depende de infraestrutura (via portas)**: nenhuma. A data de referência vem da Turn View (ADR-013); índice e busca são de 102 e 103.
- **Não conhece**: nada do core além dos contratos; outros packs; MCPs (o Assistant `scouting` declara `mcp: []`).
- **Acoplamento com o core**: apenas o contrato 001 e o **nome** do flow preferido (dado, sobrescrevível pelo Assistant).
- **Substituição**: o pack inteiro (101–106) pode ser reescrito sem tocar no core, desde que implemente o contrato 001. Submódulos são substituíveis entre si pelos contratos `Retriever`, `Reranker` e `AnswerValidator`.
- **Insumo técnico**: [design.md](design.md); [ADR-006](../../docs/adr/ADR-006-rag-first-default-scouting.md), [ADR-004](../../docs/adr/ADR-004-contratos-no-repo-do-core.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

## Clarifications

### Session 2026-10-07

- Q: Na Fase 4, sem RAG, o manifest já declara `rag_first` como flow preferido, a coleção exigida e o esquema de configuração (FR-003)? → A: Não. Na Fase 4 o manifest declara só nome e versão; `preferred_flow="rag_first"`, `requires_collections` e `config_schema` entram na Fase 5, com a US5 e o retriever (FR-010), quando passam a ter efeito. Na Fase 4, um Assistant com `packs: [scouting]` sem `flow` roda no `chat`.
- Q: Na Fase 4, sem documento indexado, como o Assistant `scouting` responde perguntas do domínio? → A: Com o conhecimento geral do modelo, declarando que nenhum documento institucional foi consultado, sem inventar citação, número de resolução, nome ou trecho de documento, e recomendando confirmar na fonte oficial. A regra é do fragmento de instruções do pack na Fase 4 e é substituída pela de citar o corpus quando o RAG chega (Fase 5).
- Q: Onde se prova que o pack carrega na plataforma real e que as instruções de domínio chegam ao modelo (US1 cen. 1–2), dado o SC-003 e o princípio I? → A: Num grupo opcional de integração do próprio `axon-scouting`, com o `axon-ai` (resolvido pela mesma tag do `axon`) como dependência de desenvolvimento separada, usando o perfil `test` da plataforma; ele prova a carga por entry point e que a plataforma compõe o prompt do pack para o Assistant (pelo seam `PackHooks` da 002 — a entrega à geração é garantia da 005), usando só a superfície que a 011 publica para suítes de packs externos, e é pulado sem o core instalado. A suíte padrão (unidade e conformidade da 001) roda só com os contratos — é ela que o SC-003 mede. O trace da plataforma não grava conteúdo de prompt, então a prova não passa por ele.
- Q: Quando a pergunta cita um período ("em 2023", "em março de 2023"), que vigência a derivação produz (FR-005)? → A: Um intervalo — início e fim do período citado (2023 → 2023-01-01 a 2023-12-31; março de 2023 → o mês inteiro) —, com revogados e substituídos incluídos; a recuperação considera os documentos vigentes em qualquer momento dele. Data exata é o intervalo de um dia; sem menção a período, o intervalo é o dia de referência da execução.
- Q: Quem produz o léxico inicial de ramos (com sinônimos), temas e tipos de documento (FR-007)? → A: Uma semente proposta na implementação, a partir da estrutura pública do escotismo brasileiro — ramos Lobinho, Escoteiro, Sênior e Pioneiro com sinônimos antigos e regionais; tipos de documento (manual, programa educativo, POR, resolução, estatuto, guia); cerca de 15 temas —, revisada pelo mantenedor antes de virar base dos testes de aceite. O mantenedor segue como curador; a semente não espera arquivo externo.

### Session 2026-10-08

- Q: De onde o pack tira, em produção, a configuração do índice (endereço do Qdrant, nome da coleção, diretório do modelo, chave de API)? → A: Do `config` do pack no `packs.yaml`, validado pelo `config_schema` do manifest no boot — URL do Qdrant, coleção, diretório do modelo de embedding e os limites da 103, com defaults —; a chave de API do Qdrant só pela variável de ambiente `AXON_SCOUTING_QDRANT_API_KEY`, nunca num arquivo.
- Q: Na Fase 5, o que o modelo faz quando nenhum trecho do corpus chega à geração (busca vazia ou pergunta que o corpus não cobre)? → A: Responde com conhecimento geral, dizendo que nenhum documento oficial foi encontrado para a pergunta, sem citar nem nomear documento, e recomenda confirmar na fonte oficial — a regra da Fase 4 (FR-011) vira o caminho sem trechos. O aviso "não fundamentada" da 104 continua valendo.
- Q: Como a v1 realiza a prioridade "institucionais sobre secundárias" (US4), se todo o corpus é institucional e o índice não marca fonte secundária? → A: Só nas instruções: elas expressam as cinco prioridades de fonte, na ordem; a marca institucional/secundária no catálogo e no índice entra quando chegar a primeira fonte secundária. A 105 mede se o modelo segue as prioridades.
- Q: Enquanto a 005 não tem o flow `rag_first`, em que ordem fechar a US5 (que declara `rag_first` como preferido)? → A: Planejar a 101 agora, mas implementar primeiro a 005 US3–US4 (`rag_first`, testada com retriever simulado) e só depois a US5 da 101, junto com a publicação dos validators da 104 — sem estado intermediário com o Assistant do scouting indisponível, e com o teste ponta a ponta da US5 contra o flow real.

### Session 2026-10-09

- Q: Como o modelo vê o identificador de cada trecho, para citar `[[chunk_id]]` como a 104 exige, se a renderização do core mostra só `[documento — seção, p. N]`? → A: O core passa a mostrar o `chunk_id` de cada trecho no que entrega ao modelo — a renderização da tool de recuperação (004) e a geração do `rag_first` (005) —, decisão registrada num ADR (o formato que o modelo vê passa a ser algo em que os prompts de pack se apoiam). O pack só ensina a sintaxe `[[id]]`; o texto dos trechos não muda. Implementado na passada da 005 US3, antes da US5 da 101.

### Session 2026-10-20

- Q: Quais são o nome da distribuição, o import, a CLI e a versão do pack depois do renome? → A: Distribuição `axon-scouting`, import `axon_scouting`, CLI `axon-scouting-corpus`, versão `0.4.0` (ADR-037, itens 2 e 4); o repositório é `axon-scouting`. O nome do pack (`scouting`), o da coleção (`scouting`) e o do índice padrão não mudam (ADR-037, item 5).
- Q: De que contratos e de que core o pack depende? → A: De `axon-ai-contracts>=0.2,<0.3`, com `contract_version` "0.2" (a série nova traz tudo o que a 0.1.2 trazia, inclusive as métricas de domínio), e, na integração com a plataforma, do `axon-ai`; os dois pela tag `v0.7.0-rc1` do repositório `axon`, a mesma para os dois, porque o gerenciador de dependências não aceita duas fontes para os contratos (research R22). O entry point passa ao grupo `axon.packs`, que é o que o Pack Runtime procura desde a passada da 002.
- Q: Que variáveis de ambiente o pack lê, e o que acontece com as antigas? → A: `AXON_SCOUTING_QDRANT_URL`, `AXON_SCOUTING_QDRANT_API_KEY`, `AXON_SCOUTING_INDEX`, `AXON_SCOUTING_EMBEDDING_DIR` e, nas suítes, `AXON_SCOUTING_TEST_QDRANT_URL` (eram `AI_SCOUTING_*`). Corte seco com diagnóstico (ADR-037, item 3): qualquer variável cujo nome comece com `AI_SCOUTING_`, conhecida ou não, vazia ou não, faz o pack recusar — na carga, ao montar a recuperação (o pack fica em erro, com a mensagem na introspecção), e na CLI do corpus (sai com erro de configuração). A mensagem tem uma linha por variável, com o nome antigo e o novo, nunca o valor.
- Q: O que acompanha na integração com a plataforma e na CI? → A: A integração (grupo `platform`) usa o import `axon_ai`, as variáveis `AXON_*` e o comando `axon`; a CI e o job de avaliação usam os nomes novos (`axon eval run`, `AXON_PROFILE`, `AXON_SCOUTING_*`). O nome do segredo da chave de leitura do repositório da plataforma na CI fica: renomeá-lo exige recadastrar a chave, e é configuração do GitHub, não código. As specs 102–106 mudam só nos nomes, nesta passada.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pack carregado e respondendo com instruções de domínio (Priority: P1)

O operador instala o `axon-scouting` na imagem e o habilita. Um membro do movimento escoteiro conversa com o Assistant `scouting` e recebe respostas orientadas pelas instruções de domínio do pack — ainda sem recuperação de documentos.

**Why this priority**: Fase 4 — prova a arquitetura de packs com um pack real, em repositório próprio, antes de somar a complexidade de RAG.

**Independent Test**: Instalar o pack a partir da tag do repositório, habilitá-lo e conversar com o Assistant; o pack aparece como habilitado e a plataforma compõe as instruções de domínio para o Assistant — provado pelo grupo opcional de integração do `axon-scouting`, sobre o perfil `test` da plataforma (o trace não grava conteúdo de prompt).

**Acceptance Scenarios**:

1. **Given** o pack instalado e habilitado, **When** o core inicia, **Then** o pack aparece `enabled` com sua versão e versão de contrato.
2. **Given** o Assistant `scouting`, **When** o usuário faz uma pergunta, **Then** a resposta segue as instruções de domínio do pack.
3. **Given** o CI do `axon-scouting`, **When** a checagem de fronteiras roda, **Then** confirma que nenhum módulo do core é importado.
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

**Independent Test**: As instruções do pack expressam as cinco prioridades de fonte, na ordem (institucionais sobre secundárias; vigentes sobre revogadas; específicas sobre genéricas; precisa sobre ampla; sempre citação e proveniência). Enquanto o corpus for só institucional, a prioridade entre institucional e secundária vive só nas instruções; o efeito sobre as respostas é medido na 105.

**Acceptance Scenarios**:

1. **Given** o pack carregado na Fase 5, **When** o fragmento de instruções é composto, **Then** ele traz as cinco prioridades de fonte na ordem da US4.
2. **Given** um manual institucional e um texto secundário sobre o mesmo tema (quando houver fonte secundária no corpus), **When** o usuário pergunta, **Then** a resposta se apoia no manual institucional — medido no conjunto dourado (105).

---

### User Story 5 - Resposta fundamentada no corpus pelo caminho determinístico (Priority: P2)

Com RAG disponível (Fase 5), o pack declara `rag_first` como flow preferido, expõe o retriever (103) e os validators de citação e vigência (104). O caminho comum responde com uma única chamada de modelo.

**Why this priority**: ADR-006; é o caso dominante do domínio: "responda a partir do corpus".

**Independent Test**: Uma pergunta coberta pelo corpus é respondida com citações válidas e uma única chamada de modelo (trace).

**Acceptance Scenarios**:

1. **Given** uma pergunta coberta pelo corpus, **When** respondida, **Then** a resposta tem citações resolvíveis e o trace mostra uma única chamada de modelo.

---

### User Story 6 - Identidade Axon: o pack de domínio com o nome da plataforma (Priority: P2)

A plataforma passa a se chamar Axon (ADR-037). O operador instala `axon-scouting`, configura o índice pelas variáveis `AXON_SCOUTING_*` e ingere o corpus com `axon-scouting-corpus`; o Assistant `scouting` responde como antes. Um `.env` com as variáveis antigas não faz o pack subir em silêncio com os defaults: ele recusa e diz o nome novo de cada variável.

**Why this priority**: O pack resolve contratos e core pela tag do repositório da plataforma; sem a passada, ele não acompanha a tag nova nem é encontrado pelo grupo de entry point novo. P2 porque nenhum comportamento de domínio muda.

**Independent Test**: Num ambiente só com os contratos 0.2, instalar o pack e rodar a suíte padrão; na integração com a plataforma da tag `v0.7.0-rc1`, a conversa do Assistant `scouting` cita o corpus; com `AXON_SCOUTING_INDEX` no ambiente, o pack fica em erro nomeando `AXON_SCOUTING_INDEX`, e a CLI do corpus sai com erro.

**Acceptance Scenarios**:

1. **Given** um ambiente com os contratos 0.2, **When** o pack é instalado, **Then** a distribuição é `axon-scouting` 0.4.0, o pacote importável é `axon_scouting`, o comando da ingestão é `axon-scouting-corpus`, e não existe `axon_scouting` nesse ambiente.
2. **Given** o pack instalado junto com a plataforma, **When** o core inicia, **Then** o pack `scouting` é descoberto pelo grupo `axon.packs`, com `contract_version` "0.2", e o Assistant `scouting` responde citando o corpus, como na US5.
3. **Given** `AXON_SCOUTING_QDRANT_URL`, `AXON_SCOUTING_INDEX` e `AXON_SCOUTING_EMBEDDING_DIR` definidas, **When** o operador ingere o corpus com `axon-scouting-corpus`, **Then** a ingestão usa esse servidor, esse índice e esse modelo.
4. **Given** uma variável `AI_SCOUTING_*` no ambiente, conhecida ou não, **When** o core carrega o pack, **Then** o pack fica em erro, e a mensagem tem uma linha `AI_SCOUTING_X → AXON_SCOUTING_X` por variável, sem o valor; **When** o operador roda a CLI do corpus, **Then** ela sai com erro de configuração e a mesma mensagem.
5. **Given** a suíte do pack, **When** a conformidade de pack roda, **Then** passa com os contratos 0.2, inclusive a etapa de distribuição (faixa `>=0.2,<0.3`) e a de imports (nenhum `axon_ai` nem `axon_generic`).

---

### Edge Cases

- Termos ambíguos de ramo (formas antigas ou regionais): o léxico mapeia sinônimos; na dúvida, não aplica filtro.
- Data histórica vaga ("antigamente"): usa a versão imediatamente substituída; se não houver, responde com vigentes e informa.
- Pergunta fora do domínio ou sem trecho recuperado: responde com conhecimento geral, dizendo que nenhum documento oficial foi encontrado, sem citar nem nomear documento, e recomenda a fonte oficial (FR-011); o validator da 104 marca a resposta como não fundamentada.
- Configuração do pack inválida (fora do `config_schema`): o pack não carrega, com o erro na introspecção — a partir da Fase 5; na Fase 4 o pack não tem esquema de configuração.
- Variável `AI_SCOUTING_*` vazia: recusada; a presença do nome antigo já indica um `.env` a migrar.
- Variáveis de prefixo parecido que não são do pack (`MY_AI_SCOUTING_X`, `AI_SCOUTINGX`): não são recusadas — a regra é o prefixo exato.
- `AI_SCOUTING_*` e `AXON_SCOUTING_*` juntas: recusado do mesmo jeito; o nome antigo nunca é ignorado.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O pack DEVE implementar o contrato de pack (001) e depender apenas da distribuição de contratos, por faixa semver.
- **FR-002**: O pack DEVE declarar-se por entry point `axon.packs` com o nome `scouting`.
- **FR-003**: A partir da Fase 5 (com a US5), o manifest DEVE declarar flow preferido `rag_first`, a coleção exigida e o esquema de configuração — URL do Qdrant, nome do índice (o alias no Qdrant; a coleção lógica `scouting` é fixa no pack — research R17), diretório do modelo de embedding e os limites da 103, com defaults (clarificação de 2026-10-08). Na Fase 4, o manifest declara só nome e versão (clarificação de 2026-10-07).
- **FR-012**: A chave de API do Qdrant DEVE vir só da variável de ambiente `AXON_SCOUTING_QDRANT_API_KEY`; ela NÃO DEVE aparecer no `config_schema`, no `packs.yaml` nem em mensagem de erro (clarificação de 2026-10-08).
- **FR-004**: A preparação de contexto DEVE derivar ramo, tema, tipos de documento e data de referência de vigência sem chamar modelos.
- **FR-005**: A vigência derivada DEVE ser um intervalo de datas (início e fim). O default DEVE ser o dia da data de referência da execução, recebida na Turn View (ADR-013); consultas históricas DEVEM trocar o intervalo pelo período citado — ano ou mês inteiros, ou o dia exato — e incluir revogados/substituídos (clarificação de 2026-10-07). O pack NÃO DEVE ler o relógio do sistema.
- **FR-006**: Os filtros derivados DEVEM ser publicados para os retrievers do próprio pack (contrato 001, FR-012).
- **FR-007**: O léxico de ramos, temas e tipos de documento DEVE ser mantido no pack, versionado junto com ele.
- **FR-008**: A partir da Fase 5 (com corpus), o fragmento de instruções DEVE expressar as prioridades de fonte da US4 e a regra de sempre citar os trechos recebidos, com a sintaxe `[[<id do trecho>]]` usando o identificador que o core mostra em cada trecho (104 FR-007; clarificação de 2026-10-09); quando nenhum trecho chega à geração, vale a regra da FR-011 — conhecimento geral, declarando que nenhum documento oficial foi encontrado, sem citar nem nomear documento, recomendando a fonte oficial (clarificação de 2026-10-08).
- **FR-009**: O fragmento de instruções DEVE afirmar que conteúdo recuperado é dado, nunca instrução.
- **FR-011**: Na Fase 4, sem corpus, o fragmento de instruções DEVE mandar responder com conhecimento geral declarando que nenhum documento institucional foi consultado, NÃO DEVE permitir citar ou nomear documento, resolução ou trecho como se tivesse sido consultado, e DEVE recomendar a confirmação na fonte oficial. Na Fase 5 a regra de citar o corpus (FR-008) vale quando há trechos, e esta continua valendo quando nenhum trecho chega à geração (clarificações de 2026-10-07 e 2026-10-08).
- **FR-010**: O pack DEVE expor o retriever e o reranker da spec 103 (a partir da Fase 5) e os validators da spec 104 (quando ela os entregar).

- **FR-013**: O pack DEVE ser a distribuição `axon-scouting`, com o pacote importável `axon_scouting` e a CLI de ingestão `axon-scouting-corpus`, na versão `0.4.0`, igual à do manifest; NÃO DEVE existir alias nem módulo com o nome antigo (ADR-037).
- **FR-014**: O pack DEVE declarar o entry point no grupo `axon.packs`, com o nome `scouting`, e depender de `axon-ai-contracts>=0.2,<0.3`, com `contract_version` "0.2".
- **FR-015**: As variáveis de ambiente do pack DEVEM usar o prefixo `AXON_SCOUTING_`. A presença de qualquer variável que comece com `AI_SCOUTING_` DEVE fazer o pack recusar a carga da recuperação e a CLI do corpus recusar a execução, com uma linha por variável que nomeia a antiga e a nova, sem o valor (ADR-037, item 3).
- **FR-016**: A integração com a plataforma, a CI e o job de avaliação DEVEM usar os nomes novos da plataforma (`axon_ai`, `AXON_*`, comando `axon`) e resolver contratos e core pela tag `v0.7.0-rc1` do repositório `axon`.
- **FR-017**: Os documentos vivos das specs 101–106 DEVEM usar os nomes novos (ADR-037, item 6); o histórico fica.


### Key Entities

- **Scouting Context**: ramo, tema, tipos de documento, vigência (intervalo: início e fim), inclusão de revogados — gravado na fatia do pack.
- **Domain Lexicon**: ramos, sinônimos, temas, tipos de documento.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A derivação de contexto acerta ramo, tema e data de referência em pelo menos 90% das perguntas do conjunto dourado (medido na 105).
- **SC-002**: 0 chamadas de modelo na derivação de contexto.
- **SC-003**: O pack instala e roda sua suíte padrão (unidade e conformidade) inteira sem o core instalado; o grupo opcional de integração com a plataforma é pulado nesse ambiente.
- **SC-004**: No caminho coberto, 100% das respostas usam uma única chamada de modelo.
- **SC-005**: Depois da passada da US6, zero ocorrências de `ai_scouting`, `ai-scouting`, `AI_SCOUTING_`, `ai_core`, `ai-core` e `AI_CORE_` no código, nos testes, na configuração e na CI do pack e nos documentos vivos das specs 101–106 (fora do histórico do ADR-037, item 6, e do código e dos testes da recusa), e as suítes do pack — padrão, ambiente limpo, plataforma e índice — passam com os contratos 0.2.

## Assumptions

- O Assistant `scouting` é público, sem MCPs, com a coleção `scouting` (definido pelo operador na spec 003; o nome lógico é fixo no pack, e o índice no Qdrant é configurável — research R17).
- O léxico inicial é uma semente proposta na implementação e revisada pelo mantenedor, que segue como curador (clarificação de 2026-10-07).
- Na Fase 4, os validators de 104 existem mas só têm efeito pleno quando há recuperação (Fase 5).
- A US5 é implementada depois da 005 US3–US4: declarar `rag_first` antes de o motor tê-lo deixaria o Assistant do scouting indisponível (clarificação de 2026-10-08).
- O core mostra o identificador de cada trecho ao modelo (004 na tool de recuperação, 005 na geração do `rag_first`), por ADR, na passada da 005 US3; sem isso nenhuma citação passaria no validator da 104 (clarificação de 2026-10-09).
- US6 (ADR-037): o caminho do submódulo no repositório da plataforma (`axon-scouting/`) e o da instalação mudam no fechamento do renome; até lá, os documentos citam o repositório pelo nome novo. A instalação passa ao pack 0.4.0 na passada dela.
