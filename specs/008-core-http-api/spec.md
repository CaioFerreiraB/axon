# Feature Specification: API HTTP, compatibilidade OpenAI e streaming

**Feature Branch**: `008-core-http-api`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §25 (API, duas superfícies, compat OpenAI e Open WebUI, streaming, requisição nativa), §28 (histórico de conversa), §31 Fase 7; ADR-002. Fase 9 (2026-10-13): superfície de administração para a console — ADR-029, ADR-031, ADR-032, ADR-033, ADR-034.

## Module Boundary *(mandatory)*

- **Módulo**: HTTP API — superfícies pública, privada e de administração, compatibilidade com o formato OpenAI, tradução de eventos do motor para SSE e histórico de conversa.
- **Repositório / distribuição**: `axon-ai` → `axon_ai/http/` (antes `axon_ai/api/`; renomeado para não colidir com a convenção `api.py` do ADR-012).
- **Consome (seams)**: autenticação, Principal, Execution Grant, Assistant Directory, API Key Admin e, na Fase 9, System Assistant Admin — 003, pelo `api.py` dela a partir da Fase 2 (na Fase 1, pelas formas que este módulo publicava como `Protocol`); Execution Engine (eventos) — 005; Pack Registry (introspecção) — 002; MCP Registry (CRUD e saúde) — 007, a partir da Fase 3; Model Router (verificação de saúde de modelo, "testar modelo") — 006, na Fase 9; Trace (identificador de requisição) e, na Fase 9, Usage Report, Price Book e Trace Destinations — 009; Account Admin e Login Settings — 012, na Fase 9.
- **Expõe (seams)**: **API HTTP** — `/v1` (OIDC), `/private/v1` (chave de API) e `/admin/v1` (token da console ou chave de API, grupo de administração — Fase 9) — consumida por clientes externos (Open WebUI, console 013, scripts). É o adapter primário da plataforma; não expõe seam Python.
- **Depende de infraestrutura (via portas)**: armazenamento das conversas; relógio (expiração de conversas); saúde agregada da plataforma (porta própria, implementada pela composition root, 011). O framework HTTP é o próprio adapter.
- **Não conhece**: flows e seu estado, packs individuais, providers, políticas de tool.
- **Substituição**: preservar os endpoints e o formato compatível com OpenAI; a camada HTTP pode ser reescrita sem afetar outros módulos.
- **Insumo técnico**: [design.md](design.md); [ADR-002](../../docs/adr/ADR-002-assistant-fronteira-isolamento.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md), [ADR-029](../../docs/adr/ADR-029-console-de-administracao-propria.md), [ADR-031](../../docs/adr/ADR-031-superficie-de-administracao.md), [ADR-032](../../docs/adr/ADR-032-assistants-de-sistema-sobrepostos-em-runtime.md).

## Clarifications

### Session 2026-09-14

- Q: Como uma execução de avaliação deve fixar a data de referência? → A: Só em processo — o harness (009), montado pela composition root (011), passa a data direto ao motor; a API HTTP não aceita data de referência em nenhuma superfície e rejeita o campo com erro que o nomeia.
- Q: Quando um cliente continua uma conversa, de onde vem o histórico que a execução usa? → A: Do servidor, nas duas superfícies — a API armazena o estado e as mensagens de cada conversa e os recupera do armazenamento; na compat OpenAI, o id de conversa vai num campo extra opcional.
- Q: O que a API deve fazer quando chegam mais execuções simultâneas do que a máquina consegue atender? → A: Limite global de execuções simultâneas com fila curta e limitada (ambos configuráveis); quem espera recebe em até 2 s um evento de progresso "na fila"; com a fila cheia, 503 com indicação de quando tentar de novo.
- Q: O usuário pode apagar as próprias conversas, e por quanto tempo o servidor as guarda? → A: O usuário apaga as próprias conversas pela API, com exclusão definitiva; conversas sem atividade expiram após um prazo configurável pelo operador, com padrão de 180 dias.

### Session 2026-09-21

- Q: A autenticação é da 003, que é Fase 2. Como a API da Fase 1 trata Principal e as duas superfícies? → A: As duas superfícies são montadas como a US1 pede, e o Principal chega por uma porta que este módulo declara. Na Fase 1 a composition root (011) injeta um adapter anônimo de desenvolvimento; na Fase 2 a 003 fornece o verificador real, e nenhuma rota muda — a autenticação entra como troca de adapter, não como reescrita da API.
- Q: O id de modelo `<assistant>/<modelo>` precisa virar um Execution Grant, mas quem resolve Assistant é a 003. Como a API obtém o grant na Fase 1? → A: Este módulo publica a forma do resolvedor que exige (id de modelo + Principal → grant); a 011 injeta um resolvedor montado da configuração na Fase 1 e a 003 passa a fornecê-lo na Fase 2, satisfazendo a forma estruturalmente. Mantém a direção `008 → 003` do grafo e impede que resolução de Assistant — que é a fronteira de isolamento — caia dentro da camada HTTP.
- Q: Os eventos de progresso do motor entram no SSE já na Fase 1, mesmo a US6 sendo Fase 7? → A: Sim, como chunk com um campo extra que clientes padrão ignoram e `delta` vazio. O motor já os emite, o custo é quase zero, e é o que entrega a SC-003 (primeiro sinal em até 2 s) na fase em que o streaming nasce. O restante da US6 — progresso de tool e aviso de fila — continua nas fases deles.
- Q: Quando a execução falha depois que o SSE já abriu, o status 200 já foi enviado. O que o cliente recebe? → A: O stream fecha normalmente: um chunk final com `finish_reason` de erro e os motivos num campo extra, seguido do marcador de fim. O cliente padrão vê a resposta parcial e um encerramento limpo; quem entende o campo extra vê a causa. Nem conexão pendurada, nem evento que clientes padrão não sabem ler.

### Session 2026-09-30

- Alinhamento com a clarificação de 2026-09-30 da 003 (sem pergunta nova): a listagem de modelos contém exatamente os Assistants que o Principal resolve — `visibility` não filtra (003 FR-008) —, e a superfície privada oferece a administração de chaves de API da 003 (emissão, listagem, revogação), restrita ao grupo de administração, com 404 para os demais (003 FR-015).
- Q: Sem o registry de MCP (007, Fase 3), o que a Fase 2 da 008 entrega do CRUD de servidores MCP, do usuário e globais? → A: Nada: os endpoints de MCP entram na Fase 3, junto com a 007. A Fase 2 entrega CRUD de Assistants de usuário, listagem de modelos, requisição nativa, introspecção de packs, administração de chaves, saúde e conversas.
- Q: Que entradas o `/v1/models` devolve para cada Assistant que o Principal resolve? → A: Uma por Assistant, com id curto `<assistant>` (ex.: `geral`, `~meu-rag`), que significa "o modelo de geração declarado"; o modelo de geração e a descrição vão em campos extras que clientes padrão ignoram. O id não muda quando o operador troca o modelo. Os outros modelos da allowlist continuam aceitos no pedido (`<assistant>/<modelo>` ou `<assistant>/<provider>/<modelo>`, 003 research R5), só não são listados.
- Q: Uma conversa pertence ao subject — visível nas duas superfícies para o mesmo subject — ou ao par (subject, esquema)? → A: Ao subject (`user:caio`, `svc:…`), como os Assistants de usuário da 003: o mesmo subject lista, lê, continua e apaga as próprias conversas por qualquer das duas superfícies; qualquer outro subject recebe 404.
- Q: Que status a API devolve quando o Principal pode usar o Assistant, mas ele está indisponível (pack em erro, flow inexistente, MCP ou coleção fora do catálogo, política de usuário não atendida)? → A: 424, no formato de erro da OpenAI, com código `assistant_unavailable` e os motivos. Os SDKs não repetem 424, e ele não se confunde com sobrecarga (503) nem com cota (429). Quem não pode usar o Assistant continua recebendo 404.
- Q: Na superfície privada, quem acessa a introspecção de packs e a saúde? → A: A saúde responde a qualquer chave de API válida — o monitoramento não precisa ser administrador. A introspecção de packs, como a administração de chaves, é só do grupo de administração, com 404 para os demais. *(Status refinado pela clarificação de 2026-09-30 da 011: só item crítico leva a 503; pack, Assistant ou modelo com problema dão 200 com `degraded`.)*

### Session 2026-10-01

- Q: Quando a autenticação não consegue consultar o armazenamento de credenciais (o banco do perfil persistente fora do ar), o que a API responde? → A: 503, no formato de erro da OpenAI, com código `storage_unavailable` e mensagem fixa que nomeia o armazenamento, sem detalhe de infraestrutura. Nunca 401 — culparia a credencial — nem o 500 genérico do framework. Vale para as duas superfícies, e é o que faz a saúde de uma instância persistente com o banco fora responder 503 (011 US5 cen. 3), já que a chave do monitor mora no mesmo banco.

### Session 2026-10-02

- Q: Quando uma execução sem streaming termina com registro `error` (MCP fora do ar, falha do controller) e a resposta foi gerada, que status a API devolve? → A: Continua 502, com a resposta e os motivos no corpo — falha explícita (princípio VII) —, e **toda** resposta de falha de execução leva o cabeçalho `x-should-retry: false`: o SDK oficial da OpenAI repete 5xx automaticamente, e cada repetição rodaria o loop `agentic` de novo, inclusive tools de escrita. Execução só com registros `notice` (limite de iterações, ação inválida, corte de contexto, apontamento de validator) é sucesso: 200 com `finish_reason: "stop"`, pela gravidade do ADR-018 — em streaming e sem streaming.

### Session 2026-10-13

- Q: Como o Open WebUI deve se identificar na plataforma, para que cada usuário veja só os Assistants permitidos a ele? → A: Por SSO OIDC: Open WebUI e plataforma usam o mesmo provedor de identidade; a conexão do Open WebUI aponta para `/v1` com a autenticação `system_oauth`, que repassa o access token OAuth de cada usuário logado, e a 003 o verifica como qualquer token OIDC. O Open WebUI não filtra modelos por conta própria — a ACL da 003 é a fonte da verdade, e a lista de modelos é a do `/v1/models` com o token daquele usuário. Nenhum mecanismo de autenticação novo na API; a instalação de referência traz um provedor OIDC de desenvolvimento para a prova.
- Q: O progresso da execução (fila, recuperação, tool chamada) deve aparecer para quem usa o Open WebUI, ou só para clientes que leem o campo extra da API? → A: Também como raciocínio: cada evento de progresso sai, além do campo extra, como uma linha curta em português em `delta.reasoning_content` — que o Open WebUI mostra num bloco recolhível de "pensamento" e clientes OpenAI padrão ignoram —; o texto da resposta (`delta.content`) não muda. Refina a clarificação de 2026-09-21 (o chunk de progresso deixa de ter `delta` vazio).
- Q: O que fazer com as chamadas auxiliares que o Open WebUI dispara a cada conversa (gerar título, tags, sugestões de continuação, autocompletar)? → A: Desligá-las na instalação de referência, pela configuração do Open WebUI (sem código): a plataforma só recebe as mensagens da conversa, e o título passa a ser o começo da primeira mensagem. Cada tarefa auxiliar seria uma execução completa do Assistant, com recuperação, ocupando vaga da fila no hardware alvo.
- Q: As conversas que a plataforma criaria a cada mensagem do Open WebUI (que nunca envia id de conversa) devem ser gravadas mesmo assim? → A: Não, quando o cliente pede: o cabeçalho opcional `x-ai-core-store: false`, num pedido sem id de conversa, torna o pedido efêmero — a API executa e responde, mas não cria nem grava conversa e não devolve id. A conexão do Open WebUI na instalação de referência envia o cabeçalho; sem ele, tudo segue como antes (FR-013, FR-014). Evita dado pessoal duplicado e fragmentado que o usuário não vê nem apaga.
- Q: O bloco de raciocínio mostra só o nome de cada etapa. Como o usuário do Open WebUI acompanha o que a execução faz — chamadas, retornos, decisões e tempos? → A: Por uma timeline de status, no componente nativo do Open WebUI v0.12 (eventos `status` na chave `event` do chunk), ligada pelo cabeçalho opcional `x-ai-core-progress: status` que a conexão da instalação envia. Nesse modo, o progresso sai só como status, sem `reasoning_content`, e continua depois do primeiro texto (conferência da resposta, avisos e a linha final). Cada etapa ganha uma linha de início e uma de desfecho, com o desfecho que o motor publica (ADR-028) e o tempo que a API mede: tools chamadas e argumentos, trechos e documentos, decisões do controller e do portão, modelo e tokens. Nunca vai texto de trecho, conteúdo de resultado de tool nem texto de erro de tool. Sem o cabeçalho, vale a clarificação anterior.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cliente compatível com OpenAI conversa em streaming (Priority: P1)

Um cliente que fala o formato de chat completions da OpenAI envia mensagens e recebe a resposta em streaming SSE, no formato de chunk da OpenAI, nas duas superfícies. Sem streaming, recebe a resposta completa.

**Why this priority**: Fase 1. Streaming entra desde o início; retrofit é caro.

**Independent Test**: Usar um cliente OpenAI padrão apontado para a plataforma; o streaming funciona sem adaptação.

**Acceptance Scenarios**:

1. **Given** uma requisição com `stream: true`, **When** processada, **Then** o cliente recebe chunks SSE no formato OpenAI e o marcador de fim.
2. **Given** `stream: false`, **When** processada, **Then** o cliente recebe uma resposta completa no formato OpenAI.
3. **Given** uma geração longa, **When** em andamento, **Then** a conexão permanece viva até o fim.

---

### User Story 2 - Assistants aparecem como modelos (Priority: P1)

A listagem de modelos devolve cada Assistant que o Principal resolve como um "model" com id `<assistant>` — o Assistant com o seu modelo de geração declarado, que vai num campo extra, junto com a descrição. Escolher o id seleciona o Assistant; um cliente que conhece a allowlist pode pedir outro modelo dela com `<assistant>/<modelo>` ou `<assistant>/<provider>/<modelo>`, que é aceito mas não listado.

**Why this priority**: É o encaixe com Open WebUI sem interface custom: o usuário escolhe o ambiente isolado no dropdown de modelo.

**Independent Test**: Listar modelos com dois Principals diferentes; as listas refletem exatamente a ACL.

**Acceptance Scenarios**:

1. **Given** um Principal público, **When** lista modelos, **Then** vê exatamente os Assistants que resolve: os públicos que aceitam seu esquema e os privados cujo `allow` o nomeia, por subject ou grupo (003 FR-008).
2. **Given** um id de modelo de Assistant privado, **When** um Principal não autorizado o usa, **Then** recebe 404 idêntico ao de id inexistente.

---

### User Story 3 - Requisição nativa que só restringe (Priority: P2)

Além da compat OpenAI, a API aceita uma requisição nativa com Assistant, mensagens e streaming. Campos que ampliariam capacidades (packs, servidores MCP, provider, tools do cliente) são rejeitados.

**Why this priority**: Deixa explícito na interface o princípio IV.

**Independent Test**: Enviar requisições nativas com cada campo proibido; todas são rejeitadas com erro que nomeia o campo.

**Acceptance Scenarios**:

1. **Given** uma requisição nativa com `mcp_servers`, **When** recebida, **Then** é rejeitada antes de qualquer execução.

---

### User Story 4 - Usuário gerencia Assistants e MCPs próprios (Priority: P2)

Na superfície pública, o usuário lista e cria Assistants próprios e MCPs próprios. Os Assistants de usuário entram na Fase 2; os MCPs próprios, na Fase 3, com o registry da 007.

**Why this priority**: Níveis 1 e 2 de extensão (ADR-003).

**Independent Test**: Criar um Assistant e um MCP de usuário pela API e usá-los numa conversa.

**Acceptance Scenarios**:

1. **Given** um usuário autenticado, **When** cria um MCP próprio e um Assistant que o usa, **Then** o Assistant aparece na sua listagem de modelos (Fase 3).
2. **Given** um usuário autenticado, **When** cria, lê, atualiza ou remove um Assistant próprio pela API, **Then** a operação segue as regras da 003 (política por grupo, prefixo `~`, 404 para nome alheio) e o Assistant criado aparece na sua listagem de modelos (Fase 2).

---

### User Story 5 - Operação pela superfície privada (Priority: P2)

Na superfície privada, o operador consulta packs (introspecção), administra chaves de API, gerencia MCPs globais e consulta a saúde do sistema. MCPs globais entram na Fase 3, com a 007; o resto, na Fase 2.

**Why this priority**: Diagnóstico e administração sem acesso ao host.

**Independent Test**: Consultar packs com um pack em erro; a resposta mostra o erro.

**Acceptance Scenarios**:

1. **Given** um pack em erro, **When** o operador consulta packs com uma chave do grupo de administração, **Then** vê status e mensagem de erro; **Given** uma chave fora do grupo, **When** consulta packs, **Then** recebe 404.
2. **Given** uma chave do grupo de administração, **When** o operador emite, lista ou revoga chaves pela API, **Then** a operação segue a 003 — a chave em claro aparece só na emissão, e a revogada é recusada na requisição seguinte; uma chave fora do grupo recebe 404.
3. **Given** qualquer chave de API válida, **When** consulta a saúde, **Then** recebe o estado agregado da plataforma (011): 200 quando `ok` ou `degraded`, 503 quando `down` (011 FR-012).
4. **Given** o armazenamento de credenciais inacessível, **When** qualquer requisição chega — inclusive a de saúde —, **Then** recebe 503 com código `storage_unavailable`, e não 401 (FR-021).
5. **Given** uma chave do grupo de administração, **When** o operador cria, lista, altera e remove MCPs globais pela API, **Then** a operação segue a 007 e os servidores do arquivo do operador aparecem como somente leitura (409 ao alterar); **Given** uma chave fora do grupo, **When** usa qualquer rota de MCP global, **Then** recebe 404 (Fase 3).

---

### User Story 6 - Progresso visível durante a execução (Priority: P2)

Eventos intermediários do motor (tool chamada, recuperação em curso) e a espera na fila são emitidos no stream como metadados, que clientes compatíveis podem ignorar, e como uma linha curta de raciocínio (`delta.reasoning_content`), que o Open WebUI mostra num bloco recolhível sem misturar com a resposta.

**Why this priority**: No hardware alvo, gerar pode levar dezenas de segundos; sem feedback, parece travado.

**Independent Test**: Numa execução agêntica, o stream contém eventos de progresso antes dos tokens de resposta; um cliente OpenAI padrão continua funcionando.

**Acceptance Scenarios**:

1. **Given** uma execução que chama uma tool, **When** em streaming, **Then** o stream contém um evento de progresso nomeando a tool.
2. **Given** todas as vagas de execução ocupadas, **When** uma requisição em streaming entra na fila, **Then** recebe em até 2 segundos um evento de progresso "na fila" e, ao ganhar a vaga, segue normalmente.
3. **Given** vagas e fila cheias, **When** chega uma requisição nova, **Then** ela é recusada com 503 e indicação de quando tentar de novo, antes de qualquer chamada de modelo.
4. **Given** uma execução em streaming pelo Open WebUI, **When** o motor emite progresso, **Then** cada evento anterior ao texto da resposta aparece como uma linha de raciocínio em português (`delta.reasoning_content`), nenhuma linha de raciocínio vem depois do primeiro texto, o texto da resposta não contém nenhuma delas, e um cliente OpenAI padrão recebe a mesma resposta que receberia sem o progresso.
5. **Given** uma execução em streaming com o cabeçalho `x-ai-core-progress: status`, **When** o motor emite progresso e desfechos de etapa, **Then** cada um sai como evento `status` do Open WebUI (`event`), com o início de etapa `done: false` e o desfecho `done: true`. A timeline nomeia tools e argumentos, trechos e documentos, as decisões e o modelo, com tempos, e segue depois do primeiro texto até uma linha final `done: true`. Nenhum `reasoning_content` sai, o texto da resposta não muda, e um valor de cabeçalho fora de `reasoning`/`status` é recusado com 400 antes de qualquer execução.

---

### User Story 7 - Conversa armazenada e retomada no servidor (Priority: P2)

Cada conversa — estado e mensagens — fica armazenada pelo subject do Principal e pelo Assistant, separada do estado de execução; o mesmo subject a alcança pelas duas superfícies. Nas duas superfícies, o cliente continua uma conversa enviando o id dela e a mensagem nova; o servidor carrega o histórico do armazenamento. Cada Principal lista e lê as próprias conversas.

**Why this priority**: Fase 2; histórico é domínio da aplicação, não do motor. Com o histórico no servidor, a conversa sobrevive a reinícios e o cliente não consegue forjar respostas anteriores do assistente.

**Independent Test**: Iniciar uma conversa, reiniciar o serviço, continuá-la enviando só o id e a mensagem nova, e ler a conversa completa pela API.

**Acceptance Scenarios**:

1. **Given** uma requisição sem id de conversa, **When** processada, **Then** uma conversa nova é criada, a troca é armazenada e o id da conversa volta na resposta.
2. **Given** uma conversa existente, **When** o cliente envia o id e uma mensagem nova, em qualquer das duas superfícies, **Then** a execução usa o histórico armazenado mais a mensagem nova, e a nova troca é armazenada.
3. **Given** o serviço reiniciado, **When** o cliente continua a conversa pelo id, **Then** o histórico anterior está preservado.
4. **Given** um id de conversa de outro Principal ou inexistente, **When** usado, **Then** a resposta é 404.
5. **Given** um Principal, **When** lista ou lê conversas, **Then** vê só as próprias, com estado e mensagens.
6. **Given** uma conversa própria, **When** o Principal a apaga, **Then** estado e mensagens são removidos em definitivo, e listagem, leitura e continuação por aquele id passam a responder 404.
7. **Given** uma conversa sem atividade há mais tempo que o prazo de retenção (180 dias por padrão), **When** a expiração roda, **Then** a conversa é apagada como na exclusão pelo usuário.

---

### User Story 8 - Open WebUI conectado (Priority: P3)

Open WebUI se conecta pela compat OpenAI na superfície pública: o usuário entra no Open WebUI pelo mesmo provedor OIDC da plataforma, e a conexão repassa o token dele ao `/v1` (autenticação `system_oauth` do Open WebUI). Os Assistants permitidos àquele usuário aparecem como modelos e conversam em streaming.

**Why this priority**: Fase 7. A API não depende da interface (princípio XI).

**Independent Test**: Instalação com um provedor OIDC de desenvolvimento e o Open WebUI com SSO nele e a conexão `system_oauth` apontando para `/v1`; dois usuários de grupos diferentes entram e conversam com um Assistant público.

**Acceptance Scenarios**:

1. **Given** Open WebUI configurado, **When** o usuário abre o seletor de modelos, **Then** vê apenas os Assistants permitidos.
2. **Given** dois usuários com permissões diferentes logados no Open WebUI, **When** cada um abre o seletor de modelos, **Then** cada um vê exatamente os Assistants que o próprio token resolve no `/v1/models` — nenhum vê os do outro.
3. **Given** um Assistant público, **When** o usuário conversa pelo Open WebUI, **Then** a resposta chega em streaming, sem nenhum código de interface customizado.
4. **Given** a instalação de referência, **When** o usuário envia uma mensagem pelo Open WebUI, **Then** a plataforma recebe uma única execução — nenhuma chamada auxiliar de título, tags, sugestões ou autocompletar.
5. **Given** a conexão do Open WebUI com o cabeçalho `x-ai-core-store: false`, **When** o usuário conversa, **Then** nenhuma conversa é criada nem gravada na plataforma, e a listagem de conversas daquele subject não muda.

---

### User Story 9 - Administração pela superfície de administração (Priority: P2)

A superfície `/admin/v1` reúne o que a console (013) usa e o que a automação sem console usa com chave de API: quem sou
eu; Assistants de sistema com a configuração efetiva e as sobreposições (gravar, descartar, testar modelo); MCPs globais;
uso e custo; preços; Langfuse e captura de conteúdo; contas, grupos e ajustes de login. Só o grupo de administração
alcança essas rotas; os demais recebem 404, e credencial inválida recebe 401 ([ADR-031](../../docs/adr/ADR-031-superficie-de-administracao.md)).

**Why this priority**: A console não tem lógica própria (ADR-029); sem essas rotas ela não existe, e a instalação sem
console perde a administração por automação.

**Independent Test**: Com um token de admin da console e com uma chave de API de admin, percorrer as rotas de
administração; com um token de não admin, todas respondem 404; com um token do Open WebUI, 401.

**Acceptance Scenarios**:

1. **Given** um token da console de um admin, **When** pede `GET /admin/v1/me`, **Then** recebe o subject e os grupos;
   **Given** um não admin, **Then** recebe 404.
2. **Given** um Assistant com `overrides: [models]`, **When** um admin grava a sobreposição com a versão que leu,
   **Then** recebe a configuração efetiva nova; **Given** uma versão desatualizada, **Then** recebe 409 sem gravar.
3. **Given** uma sobreposição fora da allowlist, **When** gravada, **Then** recebe 422 que nomeia o campo, no envelope de
   erro da plataforma.
4. **Given** uso registrado, **When** um admin consulta o uso por período, fuso e agrupamento, **Then** recebe séries
   diárias, totais e as marcas de "sem preço" calculadas pela 009.
5. **Given** a chave secreta do Langfuse gravada, **When** um admin consulta os ajustes, **Then** a resposta diz que a
   chave existe e de onde vem, e não traz o valor.
6. **Given** um admin, **When** cadastra uma conta com senha temporária, **Then** a resposta traz a senha uma única vez;
   nenhuma outra resposta a repete.
7. **Given** um token emitido para o Open WebUI a um admin, **When** chega a `/admin/v1`, **Then** recebe 401.

---

### Edge Cases

- Execução sem streaming com MCP do Assistant fora do ar: a resposta é gerada sem a tool, o registro `McpUnavailable` é `error`, e a API responde 502 com a resposta, os motivos e `x-should-retry: false` — o SDK oficial não repete.
- Cliente desconecta no meio do stream: a execução é cancelada (spec 005).
- Requisição OpenAI com `tools`/`functions`: rejeitada (ampliação de capacidade).
- Parâmetros de amostragem: aceitos dentro dos limites do Assistant.
- Id de modelo sem a parte `/<modelo>`: usa o modelo de geração default do Assistant.
- Requisição com campo de data de referência, em qualquer superfície: rejeitada com erro que nomeia o campo (FR-012).
- Cliente compatível com OpenAI que não devolve o id de conversa: cada requisição abre uma conversa nova — o comportamento padrão da OpenAI é preservado.
- Requisição com id de conversa que também traz as mensagens anteriores (cliente que sempre envia o histórico completo): só a última mensagem de usuário entra na execução; mensagens de assistente ou de tool enviadas pelo cliente são descartadas, porque o histórico armazenado é a fonte de verdade.
- Id de conversa usado com um Assistant diferente daquele da conversa: rejeitado com erro explícito, antes de qualquer execução.
- Edição de uma mensagem anterior pelo cliente (ramificação da conversa): não suportada na v1; o cliente abre uma conversa nova.
- Histórico armazenado maior que o teto de tokens do grant: o motor corta o contexto enviado ao modelo (005 FR-011); o armazenado não é alterado.
- Cliente desconecta enquanto espera na fila: a requisição sai da fila sem ocupar vaga.
- Requisição sem streaming que excede o tempo máximo de espera na fila: recusada com 503 e indicação de quando tentar de novo.
- Limite por minuto excedido (003), sobrecarga global e Assistant indisponível são respostas distintas: 429 para o par (Principal, Assistant), 503 para a plataforma, 424 para o Assistant autorizado que não pode executar — este último só para quem o resolveria; para os demais, 404.
- Conversa apagada enquanto uma execução dela está em andamento: a exclusão prevalece; a resposta chega ao cliente, mas a troca não é gravada.
- Pedido de exclusão de conversa de outro Principal ou inexistente: 404, sem revelar se ela existe.
- Open WebUI repassa um token expirado ou de outro emissor: a API responde 401 no formato de erro da OpenAI, como para qualquer cliente; a interface mostra o erro, e o usuário entra de novo — a API não renova tokens.
- Pedido com `x-ai-core-store: false` e id de conversa: recusado com 400 que nomeia o cabeçalho, antes de qualquer execução — continuar uma conversa armazenada sem gravá-la é contraditório. Valor do cabeçalho diferente de `true` ou `false`: 400 que nomeia o cabeçalho.
- Chave de API emitida com o subject de um usuário alcança as conversas e os Assistants dele: emitir chaves é poder do grupo de administração (003 FR-015), e a conversa pertence ao subject, não à superfície.
- Rota de administração pedida por um não admin: 404 idêntico ao de rota inexistente; a existência da administração não vaza.
- Dois admins gravam a mesma sobreposição ou o mesmo ajuste: o segundo recebe 409 com a versão atual; nada é sobrescrito.
- Gravar a chave secreta do Langfuse sem chave mestra na instalação: 409 que explica a falta, sem gravar.
- Campo de ajuste definido pela instalação: escrita recusada com 409 que nomeia o campo e a origem.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A API DEVE oferecer superfície pública (`/v1`, OIDC), privada (`/private/v1`, chave de API) e de administração (`/admin/v1`, token da console ou chave de API — Fase 9, [ADR-031](../../docs/adr/ADR-031-superficie-de-administracao.md)) num único serviço.
- **FR-002**: A API DEVE implementar chat completions compatível com OpenAI, com e sem streaming SSE.
- **FR-003**: A API DEVE listar como modelos exatamente os Assistants que o Principal resolve (003 FR-008), um por Assistant, com id `<assistant>` e o modelo de geração declarado e a descrição em campos extras. Pedidos com `<assistant>/<modelo>` ou `<assistant>/<provider>/<modelo>` continuam aceitos dentro da allowlist.
- **FR-004**: A API DEVE aceitar requisição nativa (Assistant, mensagens, streaming) e rejeitar campos de ampliação.
- **FR-005**: A API DEVE traduzir os eventos do motor em chunks SSE, emitindo progresso como metadados ignoráveis e, enquanto o texto da resposta não começou, também no mesmo chunk como uma linha curta em português em `delta.reasoning_content` (o raciocínio que o Open WebUI exibe à parte); depois do primeiro texto, só nos metadados. Progresso nunca vai em `delta.content`. Falha depois de o stream ter aberto DEVE encerrar o stream normalmente — chunk final com desfecho de erro, motivos em campo extra e marcador de fim —, nunca com conexão pendurada nem interrompida sem aviso.
- **FR-005a**: Nas duas superfícies, o cabeçalho opcional `x-ai-core-progress` DEVE escolher como o progresso aparece em streaming: `reasoning` (padrão, o FR-005) ou `status`; outro valor DEVE ser recusado com 400 que o nomeia, antes de qualquer execução. Em `status`, a fila, cada início e cada desfecho de etapa (005 FR-012a) e o fim da execução DEVEM sair como evento `status` na chave `event` do chunk, que o Open WebUI mostra como timeline, sem `reasoning_content` e também depois do primeiro texto. O desfecho DEVE trazer o tempo da etapa, medido pela API. Texto de trecho, conteúdo de resultado de tool e texto de erro de tool NÃO DEVEM aparecer. Sem streaming, o cabeçalho não muda nada.
- **FR-006**: A superfície pública DEVE oferecer CRUD de Assistants do próprio usuário (Fase 2) e de MCPs do próprio usuário (Fase 3, com a 007).
- **FR-007**: A superfície privada DEVE oferecer introspecção de packs e administração de chaves de API, ambas restritas ao grupo de administração (003 FR-015) com 404 para os demais; health para qualquer chave válida (Fase 2); e CRUD de MCPs globais (Fase 3, com a 007).
- **FR-008**: A API DEVE armazenar cada conversa — estado e mensagens — pelo subject do Principal e pelo Assistant, separada do estado de execução.
- **FR-009**: Erros de autorização DEVEM seguir a regra 404-não-403 da spec 003.
- **FR-010**: Toda resposta DEVE carregar o identificador da requisição usado no trace.
- **FR-011**: A API NÃO DEVE depender de nenhuma interface gráfica.
- **FR-012**: A API NÃO DEVE aceitar data de referência em nenhuma superfície: um campo de data de referência na requisição DEVE ser rejeitado, antes de qualquer execução, com erro que nomeia o campo. Execuções de avaliação fixam a data chamando o motor em processo, pelo harness (009) montado pela composition root (011) — ADR-013.
- **FR-013**: Nas duas superfícies, uma requisição com id de conversa DEVE continuar a conversa a partir do histórico armazenado, que é a fonte de verdade: da requisição, só a última mensagem de usuário entra na execução. Na compat OpenAI, o id vai num campo extra opcional; sem ele, a requisição segue o comportamento padrão da OpenAI (histórico enviado pelo cliente) e abre uma conversa nova.
- **FR-014**: Toda resposta de chat DEVE devolver o id da conversa, com e sem streaming — exceto a de pedido efêmero (FR-023), que não tem conversa.
- **FR-015**: Cada subject DEVE poder listar e ler as próprias conversas (estado e mensagens) por qualquer das duas superfícies; conversa de outro subject ou inexistente responde 404 (FR-009).
- **FR-016**: A API DEVE limitar o número de execuções simultâneas e manter uma fila limitada para o excedente, com limite, tamanho da fila e tempo máximo de espera configuráveis pelo operador. A vaga é ocupada do início da execução até o evento final.
- **FR-017**: Requisições em streaming que esperam na fila DEVEM receber um evento de progresso "na fila" em até 2 segundos. Com a fila cheia, a requisição DEVE ser recusada com 503 e indicação de quando tentar de novo, antes de qualquer chamada de modelo — com ou sem streaming. Com o tempo de espera esgotado, sem streaming DEVE ser 503 com a mesma indicação; em streaming, como o stream já abriu com o aviso de fila, DEVE terminar com o chunk final de erro (`finish_reason: "error"`, registro `QueueTimeout`) e o marcador de fim (clarificação de 2026-09-21) — em nenhum caso depois de uma chamada de modelo.
- **FR-018**: Cada Principal DEVE poder apagar as próprias conversas; a exclusão é definitiva e remove estado e mensagens.
- **FR-019**: Conversas sem atividade por mais tempo que o prazo de retenção DEVEM ser apagadas automaticamente; o prazo é configurável pelo operador, com padrão de 180 dias.
- **FR-020**: Assistant que o Principal resolve, mas que está indisponível, DEVE responder 424 no formato de erro da OpenAI, com código `assistant_unavailable` e os motivos, antes de qualquer execução; o 424 nunca é devolvido a quem não resolveria o Assistant (FR-009).
- **FR-021**: Falha do armazenamento de credenciais durante a autenticação DEVE responder 503 no formato de erro da OpenAI, com código `storage_unavailable`, antes de qualquer outra verificação; a mensagem nomeia o armazenamento e não expõe detalhe de infraestrutura (endereço, driver, mensagem do banco).
- **FR-022**: O desfecho de uma execução DEVE ser decidido pela gravidade dos registros do evento final (005, ADR-018), nunca pelo tipo: só registros `notice` → sucesso (`finish_reason: "stop"`, 200 sem streaming); algum registro `error` → falha (`finish_reason: "error"` no stream; 502 sem streaming, com a resposta e os motivos no corpo). Toda resposta de falha de execução DEVE levar o cabeçalho `x-should-retry: false`, para que clientes que repetem 5xx automaticamente não reexecutem o loop nem tools de escrita.
- **FR-023**: Nas duas superfícies, um pedido sem id de conversa e com o cabeçalho `x-ai-core-store: false` DEVE ser efêmero: executa e responde normalmente, mas não cria nem grava conversa e não devolve id de conversa. O cabeçalho com id de conversa, ou com valor diferente de `true`/`false`, DEVE ser recusado com 400 que o nomeia, antes de qualquer execução. Sem o cabeçalho (ou com `true`), vale o FR-013.
- **FR-024**: A superfície de administração DEVE aceitar só o grupo de administração (003), em qualquer esquema que ela aceite; credencial inválida → 401 no envelope de erro; Principal autenticado fora do grupo → 404 em toda rota, igual a rota inexistente.
- **FR-025**: A superfície de administração DEVE expor, sobre os seams dos módulos donos e sem regra própria: `me`; Assistants de sistema (lista e detalhe com YAML, sobreposições, efetivo, estado e seções permitidas; gravar e descartar sobreposição de `models` e de `mcp`; testar modelo pela verificação de saúde da 006); MCPs globais (o CRUD da superfície privada) com a lista de tools e a saúde de cada servidor; uso (período, fuso, agrupamento) e preços; ajustes do Langfuse e da captura de conteúdo, com teste de conexão; contas, grupos e ajustes de login (012). O formato fica no contrato `admin-api.md`.
- **FR-026**: Toda escrita na superfície de administração sobre um recurso versionado (sobreposição, ajustes) DEVE exigir a versão lida; versão desatualizada → 409 com a versão atual. Recusa de validação → 422 que nomeia o campo; escrita em campo definido pela instalação → 409 que nomeia o campo e a origem.
- **FR-027**: Nenhuma resposta da superfície de administração DEVE trazer valor de segredo (chaves do Langfuse, credenciais de MCP, hashes); a senha temporária de uma conta aparece só na resposta da operação que a definiu.
- **FR-028**: A API NÃO DEVE habilitar requisições entre origens: a console é servida na mesma origem da plataforma (013), e os prefixos da API são repassados sem reescrita.

### Key Entities

- **Conversation**: id, subject do dono, Assistant, modelo de geração, datas de criação e de última atividade, número de mensagens.
- **Message**: conversa, papel (usuário ou assistente), conteúdo, momento, identificador da requisição (trace) e, nas respostas, as citações e marcações do evento final.
- **Model Listing Entry**: id `<assistant>` (estável quando o operador troca o modelo); campos extras com o modelo de geração declarado, a descrição e a origem (sistema ou usuário). Com sobreposição ativa (003), o modelo de geração listado é o efetivo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Open WebUI funciona com zero código de interface customizado.
- **SC-002**: A suíte ponta a ponta completa roda apenas via HTTP, sem interface gráfica.
- **SC-003**: O usuário vê o primeiro sinal de progresso em até 2 segundos após enviar a mensagem, no hardware alvo — inclusive quando a requisição espera na fila.
- **SC-004**: Clientes OpenAI padrão funcionam sem adaptação nas duas superfícies.
- **SC-005**: 100% das conversas continuadas depois de um reinício do serviço recuperam o histórico completo, e 0 mensagens de assistente enviadas pelo cliente entram numa execução com id de conversa (testes com o perfil persistente).
- **SC-006**: Em teste de carga acima do limite, 0 execuções além do limite configurado rodam ao mesmo tempo, e 100% das recusas por sobrecarga acontecem antes de qualquer chamada de modelo.
- **SC-007**: 100% das conversas apagadas pelo usuário deixam de ser recuperáveis pela API imediatamente, e nenhuma conversa permanece armazenada além do prazo de retenção mais um ciclo de expiração (teste com relógio fixo).
- **SC-008**: 100% das ações da console (013) têm rota na superfície de administração, e cada rota funciona também com chave de API de admin, sem console.
- **SC-009**: Em teste, nenhum Principal fora do grupo de administração distingue uma rota de administração de uma inexistente, e nenhuma resposta de administração traz valor de segredo.

## Assumptions

- O histórico de conversa usa armazenamento persistente a partir da Fase 2 (adapter Postgres; em memória na Fase 1).
- O Open WebUI não envia o id de conversa; o histórico da interface é o dela. Na instalação de referência a conexão envia `x-ai-core-store: false`, e esses pedidos são efêmeros (FR-023); sem o cabeçalho, cada requisição abriria uma conversa nova.
- A mesma conexão envia `x-ai-core-progress: status` (FR-005a): o progresso aparece na timeline de status do Open WebUI v0.12, que repassa a chave `event` de cada chunk ao emissor de eventos dele e grava os status na mensagem. Outro cliente que não conheça a chave a ignora como campo extra.
- A fila atende por ordem de chegada; justiça entre Principals fica fora da v1, porque o limite por minuto da 003 já contém o abuso individual. Processo único na v1: limite e fila valem por processo.
- Os valores iniciais de limite, fila e espera são medidos no hardware alvo na implementação (o plano fixa valores provisórios e o método), não aqui.
- O harness de avaliação (009) roda em processo próprio e não passa por esta fila; avaliação não roda no mesmo host da produção.
- Os traces (009) seguem a própria retenção, limitada e configurável; apagar uma conversa não apaga, na v1, os traces das requisições dela.
- A aplicação HTTP é montada pela composition root (011), que injeta os seams consumidos.
- As interfaces são o Open WebUI (chat) e, opcional, a console de administração (013, Fase 9); nenhuma lógica de agente nem regra de negócio vive nelas (princípio XI, ADR-029).
- O Open WebUI faz login no mesmo provedor OIDC que a 003 verifica e repassa o access token de cada usuário (`system_oauth`); o token precisa ter o emissor, a audiência e as claims de subject e grupos que a configuração da 003 lê. Desde a Fase 9, a instalação de referência (002) usa o provedor da própria plataforma (012, ADR-030) no lugar do Keycloak de desenvolvimento; um provedor externo continua possível.
- Na instalação de referência, as tarefas auxiliares do Open WebUI (título, tags, sugestões de continuação, autocompletar) ficam desligadas; o operador que as religar sabe que cada uma é uma execução completa do Assistant e ocupa vaga da fila (FR-016).
