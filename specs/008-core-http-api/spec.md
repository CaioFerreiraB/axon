# Feature Specification: API HTTP, compatibilidade OpenAI e streaming

**Feature Branch**: `008-core-http-api`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §25 (API, duas superfícies, compat OpenAI e Open WebUI, streaming, requisição nativa), §28 (histórico de conversa), §31 Fase 7; ADR-002.

## Module Boundary *(mandatory)*

- **Módulo**: HTTP API — superfícies pública e privada, compatibilidade com o formato OpenAI, tradução de eventos do motor para SSE e histórico de conversa.
- **Repositório / distribuição**: `ai-core` → `ai_core/http/` (antes `ai_core/api/`; renomeado para não colidir com a convenção `api.py` do ADR-012).
- **Consome (seams)**: autenticação, Principal, Execution Grant, Assistant Directory e API Key Admin — 003, pelo `api.py` dela a partir da Fase 2 (na Fase 1, pelas formas que este módulo publicava como `Protocol`); Execution Engine (eventos) — 005; Pack Registry (introspecção) — 002; MCP Registry (CRUD) — 007, a partir da Fase 3; Trace (identificador de requisição) — 009.
- **Expõe (seams)**: **API HTTP** — `/v1` (OIDC) e `/private/v1` (chave de API) — consumida por clientes externos (Open WebUI, scripts). É o adapter primário da plataforma; não expõe seam Python.
- **Depende de infraestrutura (via portas)**: armazenamento das conversas; relógio (expiração de conversas); saúde agregada da plataforma (porta própria, implementada pela composition root, 011). O framework HTTP é o próprio adapter.
- **Não conhece**: flows e seu estado, packs individuais, providers, políticas de tool.
- **Substituição**: preservar os endpoints e o formato compatível com OpenAI; a camada HTTP pode ser reescrita sem afetar outros módulos.
- **Insumo técnico**: [design.md](design.md); [ADR-002](../../docs/adr/ADR-002-assistant-fronteira-isolamento.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

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
- Q: Na superfície privada, quem acessa a introspecção de packs e a saúde? → A: A saúde responde a qualquer chave de API válida — o monitoramento não precisa ser administrador. A introspecção de packs, como a administração de chaves, é só do grupo de administração, com 404 para os demais.

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
3. **Given** qualquer chave de API válida, **When** consulta a saúde, **Then** recebe o estado agregado da plataforma (011).

---

### User Story 6 - Progresso visível durante a execução (Priority: P2)

Eventos intermediários do motor (tool chamada, recuperação em curso) são emitidos no stream como metadados, que clientes compatíveis podem ignorar.

**Why this priority**: No hardware alvo, gerar pode levar dezenas de segundos; sem feedback, parece travado.

**Independent Test**: Numa execução agêntica, o stream contém eventos de progresso antes dos tokens de resposta; um cliente OpenAI padrão continua funcionando.

**Acceptance Scenarios**:

1. **Given** uma execução que chama uma tool, **When** em streaming, **Then** o stream contém um evento de progresso nomeando a tool.
2. **Given** todas as vagas de execução ocupadas, **When** uma requisição em streaming entra na fila, **Then** recebe em até 2 segundos um evento de progresso "na fila" e, ao ganhar a vaga, segue normalmente.
3. **Given** vagas e fila cheias, **When** chega uma requisição nova, **Then** ela é recusada com 503 e indicação de quando tentar de novo, antes de qualquer chamada de modelo.

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

Open WebUI se conecta pela compat OpenAI; os Assistants permitidos ao usuário aparecem como modelos e conversam em streaming.

**Why this priority**: Fase 7. A API não depende da interface (princípio XI).

**Independent Test**: Configurar Open WebUI apontando para `/v1`; conversar com um Assistant público.

**Acceptance Scenarios**:

1. **Given** Open WebUI configurado, **When** o usuário abre o seletor de modelos, **Then** vê apenas os Assistants permitidos.

---

### Edge Cases

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
- Chave de API emitida com o subject de um usuário alcança as conversas e os Assistants dele: emitir chaves é poder do grupo de administração (003 FR-015), e a conversa pertence ao subject, não à superfície.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A API DEVE oferecer superfície pública (`/v1`, OIDC) e privada (`/private/v1`, chave de API) num único serviço.
- **FR-002**: A API DEVE implementar chat completions compatível com OpenAI, com e sem streaming SSE.
- **FR-003**: A API DEVE listar como modelos exatamente os Assistants que o Principal resolve (003 FR-008), um por Assistant, com id `<assistant>` e o modelo de geração declarado e a descrição em campos extras. Pedidos com `<assistant>/<modelo>` ou `<assistant>/<provider>/<modelo>` continuam aceitos dentro da allowlist.
- **FR-004**: A API DEVE aceitar requisição nativa (Assistant, mensagens, streaming) e rejeitar campos de ampliação.
- **FR-005**: A API DEVE traduzir os eventos do motor em chunks SSE, emitindo progresso como metadados ignoráveis. Falha depois de o stream ter aberto DEVE encerrar o stream normalmente — chunk final com desfecho de erro, motivos em campo extra e marcador de fim —, nunca com conexão pendurada nem interrompida sem aviso.
- **FR-006**: A superfície pública DEVE oferecer CRUD de Assistants do próprio usuário (Fase 2) e de MCPs do próprio usuário (Fase 3, com a 007).
- **FR-007**: A superfície privada DEVE oferecer introspecção de packs e administração de chaves de API, ambas restritas ao grupo de administração (003 FR-015) com 404 para os demais; health para qualquer chave válida (Fase 2); e CRUD de MCPs globais (Fase 3, com a 007).
- **FR-008**: A API DEVE armazenar cada conversa — estado e mensagens — pelo subject do Principal e pelo Assistant, separada do estado de execução.
- **FR-009**: Erros de autorização DEVEM seguir a regra 404-não-403 da spec 003.
- **FR-010**: Toda resposta DEVE carregar o identificador da requisição usado no trace.
- **FR-011**: A API NÃO DEVE depender de nenhuma interface gráfica.
- **FR-012**: A API NÃO DEVE aceitar data de referência em nenhuma superfície: um campo de data de referência na requisição DEVE ser rejeitado, antes de qualquer execução, com erro que nomeia o campo. Execuções de avaliação fixam a data chamando o motor em processo, pelo harness (009) montado pela composition root (011) — ADR-013.
- **FR-013**: Nas duas superfícies, uma requisição com id de conversa DEVE continuar a conversa a partir do histórico armazenado, que é a fonte de verdade: da requisição, só a última mensagem de usuário entra na execução. Na compat OpenAI, o id vai num campo extra opcional; sem ele, a requisição segue o comportamento padrão da OpenAI (histórico enviado pelo cliente) e abre uma conversa nova.
- **FR-014**: Toda resposta de chat DEVE devolver o id da conversa, com e sem streaming.
- **FR-015**: Cada subject DEVE poder listar e ler as próprias conversas (estado e mensagens) por qualquer das duas superfícies; conversa de outro subject ou inexistente responde 404 (FR-009).
- **FR-016**: A API DEVE limitar o número de execuções simultâneas e manter uma fila limitada para o excedente, com limite, tamanho da fila e tempo máximo de espera configuráveis pelo operador. A vaga é ocupada do início da execução até o evento final.
- **FR-017**: Requisições em streaming que esperam na fila DEVEM receber um evento de progresso "na fila" em até 2 segundos; com a fila cheia ou o tempo de espera esgotado, a requisição DEVE ser recusada com 503 e indicação de quando tentar de novo, antes de qualquer chamada de modelo.
- **FR-018**: Cada Principal DEVE poder apagar as próprias conversas; a exclusão é definitiva e remove estado e mensagens.
- **FR-019**: Conversas sem atividade por mais tempo que o prazo de retenção DEVEM ser apagadas automaticamente; o prazo é configurável pelo operador, com padrão de 180 dias.
- **FR-020**: Assistant que o Principal resolve, mas que está indisponível, DEVE responder 424 no formato de erro da OpenAI, com código `assistant_unavailable` e os motivos, antes de qualquer execução; o 424 nunca é devolvido a quem não resolveria o Assistant (FR-009).

### Key Entities

- **Conversation**: id, subject do dono, Assistant, modelo de geração, datas de criação e de última atividade, número de mensagens.
- **Message**: conversa, papel (usuário ou assistente), conteúdo, momento, identificador da requisição (trace) e, nas respostas, as citações e marcações do evento final.
- **Model Listing Entry**: id `<assistant>` (estável quando o operador troca o modelo); campos extras com o modelo de geração declarado, a descrição e a origem (sistema ou usuário).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Open WebUI funciona com zero código de interface customizado.
- **SC-002**: A suíte ponta a ponta completa roda apenas via HTTP, sem interface gráfica.
- **SC-003**: O usuário vê o primeiro sinal de progresso em até 2 segundos após enviar a mensagem, no hardware alvo — inclusive quando a requisição espera na fila.
- **SC-004**: Clientes OpenAI padrão funcionam sem adaptação nas duas superfícies.
- **SC-005**: 100% das conversas continuadas depois de um reinício do serviço recuperam o histórico completo, e 0 mensagens de assistente enviadas pelo cliente entram numa execução com id de conversa (testes com o perfil persistente).
- **SC-006**: Em teste de carga acima do limite, 0 execuções além do limite configurado rodam ao mesmo tempo, e 100% das recusas por sobrecarga acontecem antes de qualquer chamada de modelo.
- **SC-007**: 100% das conversas apagadas pelo usuário deixam de ser recuperáveis pela API imediatamente, e nenhuma conversa permanece armazenada além do prazo de retenção mais um ciclo de expiração (teste com relógio fixo).

## Assumptions

- O histórico de conversa usa armazenamento persistente a partir da Fase 2 (adapter Postgres; em memória na Fase 1).
- O Open WebUI não envia o id de conversa sem configuração; nesse caso cada requisição abre uma conversa nova, e o histórico da interface continua sendo o dela.
- A fila atende por ordem de chegada; justiça entre Principals fica fora da v1, porque o limite por minuto da 003 já contém o abuso individual. Processo único na v1: limite e fila valem por processo.
- Os valores iniciais de limite, fila e espera são medidos no hardware alvo durante o plano, não fixados aqui.
- O harness de avaliação (009) roda em processo próprio e não passa por esta fila; avaliação não roda no mesmo host da produção.
- Os traces (009) seguem a própria retenção, limitada e configurável; apagar uma conversa não apaga, na v1, os traces das requisições dela.
- A aplicação HTTP é montada pela composition root (011), que injeta os seams consumidos.
- Não há interface própria além do Open WebUI; nenhuma lógica de agente vive na interface.
