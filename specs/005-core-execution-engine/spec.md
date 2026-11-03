# Feature Specification: Motor de execução (flows)

**Feature Branch**: `005-core-execution-engine`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §6 (estado e contexto), §7 (topologias fixas), §8 (nós do core), §9 (custo do controller), §25 (streaming), §28 (checkpoint); ADR-001, ADR-005, ADR-006, ADR-007, ADR-010, ADR-011, ADR-012, ADR-013.

## Module Boundary *(mandatory)*

- **Módulo**: Execution Engine — orquestra uma execução: ordena as chamadas aos serviços do core e aos hooks de pack segundo um flow nomeado, e emite um fluxo de eventos. **Esta spec é desenhada para ser reescrita.**
- **Repositório / distribuição**: `axon-ai` → `axon_ai/graph/` (seam em `api.py`, políticas em `domain/`, framework de grafo e estado interno em `adapters/`).
- **Consome (seams)**: Turn View e PackRoutine — 001; Pack Hooks — 002; Execution Grant — 003 (nas Fases 1 e 2, pela forma que este módulo publicava como `Protocol`; a partir da Fase 3, o value object da 003, que o motor entrega à 004); Capability Catalog e Tool Gateway — 004; Model Router — 006; Trace Sink — 009.
- **Expõe (seams)**: **Execution Engine** — `run(grant, requisição) → fluxo de eventos` — consumido por 008 e 009; **nomes de flow** (`chat`, `agentic`, `rag_first`) — consumidos como dado por 003 (validação) e por manifests de pack.
- **Depende de infraestrutura (via portas)**: relógio (data de referência) e, quando houver retomada de execução, armazenamento de checkpoint (FR-014). O framework de grafo é adapter interno.
- **Não conhece**: HTTP, autenticação, quais packs existem ou seu domínio, como tools são executadas ou protegidas, quais providers existem.
- **Substituição**: qualquer implementação que honre os dois seams expostos e consuma apenas os seams listados é válida. **Nomes de nós, forma do estado interno e o framework de grafo não são contrato** (ADR-011). Reescrever o grafo troca o adapter de fluxo e preserva as políticas de `domain/` com seus testes (ADR-012). Renomear ou remover um flow é permitido; `assistants validate` (003) aponta as referências pendentes.
- **Insumo técnico**: [design.md](design.md); [ADR-001](../../docs/adr/ADR-001-topologia-fixa.md), [ADR-005](../../docs/adr/ADR-005-execute-tool-unificado.md), [ADR-006](../../docs/adr/ADR-006-rag-first-default-scouting.md), [ADR-007](../../docs/adr/ADR-007-citacao-mecanica.md), [ADR-010](../../docs/adr/ADR-010-temporal-fora.md), [ADR-011](../../docs/adr/ADR-011-contratos-independentes-do-motor.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

## Clarifications

### Session 2026-09-21

- Q: O flow `chat` da Fase 1 é linear. O framework de grafo entra já nesta fase ou só quando houver loop? → A: Já nesta fase, como o `design.md` e a tabela de stack da constituição determinam. A parte mais delicada do desenho é traduzir o streaming do framework nos eventos do seam, e é isso que a Fase 1 — cuja razão de ser é a conversa ponta a ponta em streaming (princípio XI) — precisa pôr à prova. A Fase 3 acrescenta o loop ao grafo existente, sem reescrever o adapter nem escrevê-lo duas vezes.
- Q: O seam é `run(grant, requisição)`, mas o Execution Grant pertence à 003, que é Fase 2. Como o motor recebe o grant na Fase 1? → A: O `api.py` deste módulo publica um `Protocol` que descreve apenas o que o motor lê do grant (assistant, flow, packs, política de modelos, limites). Na Fase 2 o Execution Grant concreto da 003 o satisfaz estruturalmente, sem import e sem inverter a direção `005 → 003` do grafo de dependências; o seam é o mesmo nas duas fases. Na Fase 1, quem constrói um objeto que cumpre o Protocol é a composition root (011).
- Q: Uma falha chega ao consumidor como evento ou como exceção? → A: Depende de quando acontece. A validação da requisição — parâmetros, flow inexistente, orçamento — levanta exceção tipada **antes** do primeiro evento, para que a 008 responda 4xx sem abrir o stream e sem custo (princípio VII: 4xx antes de qualquer custo). Depois que o fluxo começou, toda falha vira evento final com erros, porque o consumidor já está lendo um stream e os tokens já emitidos não podem ser perdidos.
- Q: A porta de checkpoint (FR-014) entra na Fase 1? → A: Não. Nesta fase nada retoma execução: o `chat` roda do começo ao fim dentro de uma requisição. Declarar a porta agora seria porta sem consumidor, contra o princípio XIII. Ela entra na Fase 3, junto com o loop, que é quando reter estado entre passos passa a significar alguma coisa.

### Session 2026-10-01

- Q: A porta de checkpoint do estado de execução entra nesta passada da Fase 3, mesmo sem nenhum fluxo que retome uma execução interrompida? → A: Não; adiada de novo. Na Fase 3 o loop roda inteiro dentro de uma requisição, o estado entre iterações vive na própria execução e o trace registra cada passo (FR-016). Nada lê o estado de volta — não há aprovação humana nem retomada após queda —, então a porta seria porta sem consumidor (princípio XIII). Ela entra junto com o primeiro consumidor de retomada, e o roadmap deixa de prever "memória → Postgres na Fase 3".
- Q: Quando a chamada ao modelo do papel `controller` falha no meio do loop (provider fora do ar, limite de taxa, stream travado), a execução segue para a geração ou encerra com erro? → A: Segue para a geração com o que já acumulou, registra o erro em erros (estágio do controller, nomeando provider e modelo) e não tenta de novo — a mesma regra do limite de iterações, sem fallback automático (006 FR-007). Erros de configuração do papel (não declarado, fora da allowlist) não chegam aqui: são pegos antes do primeiro evento (FR-013).
- Q: Qual limite de iterações o motor aplica quando o Assistant não declara `limits.max_iterations`, e o operador pode mudar esse padrão? → A: 3, constante na política do motor (`domain/`), sem configuração global. Quem precisa de mais declara no Assistant (`assistants.yaml` ou o rascunho do Assistant de usuário, sob o teto da política do grupo — 003). Com 3, o acumulado de resultados de tool fica em no máximo ~48 KB pelo limite de 16 KB por resultado da 004.
- Q: Como cada decisão do controller (chamar tool, responder, ação inválida, limite atingido) aparece no trace da 009? → A: Como evento novo e aditivo da 009 — decisão do controller com iteração, ação, nome da tool pedida e motivo quando inválida, **sem argumentos** (a mesma regra de privacidade do `ToolCall` da 004) —, acompanhado de um ADR que regulariza o crescimento do Trace Sink por eventos aditivos e cobre também o `ToolCall` já entregue. A chamada de modelo continua sendo o `ModelCall` da 006 e a execução de tool, o `ToolCall` da 004; falha do controller e truncamento também vão a erros.
- Q: O teto de tokens de contexto do grant (`limits.max_context_tokens`) vale já no loop `agentic` desta fase ou fica para a Fase 5? → A: Já na Fase 3, quando o grant declara teto. Tokens são estimados por caracteres (sem tokenizador). Se o próximo passo do loop passaria do teto, o loop para e segue para a geração, registrando o truncamento; se a geração ainda passar, os resultados de tool mais antigos saem do contexto com marca de omissão e a redução é registrada. Grant sem teto não sofre corte — o limite de iterações é a proteção. O corte de chunks por rank do `rag_first` continua na Fase 5, pela mesma política.

### Session 2026-10-07

- Q: Com streaming, como a resposta corrigida pelos validators chega ao cliente? → A: A geração passa cada pedaço pelo filtro do Pack Hooks e emite só o que ele libera, com a cauda no fim; depois dos validators restantes, o que eles só acrescentam sai como token, e reescrita no meio fica registrada como `notice` (`AnswerRewritten`). Os dois modos da API entregam o mesmo texto (ADR-024).

### Session 2026-10-09

- Q: Onde ficam os números do `rag_first` (limiar do portão, candidatos, trechos levados à geração) e qual o default do limiar antes da calibração da 105? → A: Configuração do operador, por variáveis `AXON_RAG_*` — limiar, candidatos e trechos —, com defaults 20 candidatos, 5 trechos e **sem limiar**: até a 105 calibrar, o portão só escala quando não há resultado depois dos filtros. Um limiar provisório pode ser configurado pelo operador; nenhum é fixado no código (princípio X).
- Q: Quando o portão escala, o que o motor faz se o Assistant não declara o papel `controller`? → A: Escala para o loop agêntico só se o Assistant declara `controller`; sem ele, gera **sem trechos** — o caminho em que o prompt do pack diz que nenhum documento foi encontrado — e registra um `notice` de cobertura insuficiente. O `rag_first` exige só o papel `generation` (ADR-019).

### Session 2026-10-22

- Q: Testando o `agentic` com um MCP de finanças (GLM 5.3 Flash), o controller chutou o ano (pediu outubro de 2023), repetiu a mesma tool com os mesmos argumentos até o limite, a geração escreveu `<tool_call>…` como texto e uma resposta saiu em branco. O que o motor faz? → A: Dá ao controller e à geração do loop a data de referência no fuso da instalação (`AXON_TIMEZONE`, 011); ação de tool repetida com os mesmos argumentos encerra o loop e vai à geração; marcação de chamada de tool no texto da geração é retirada; resposta vazia depois dos validators vira um aviso padrão ao usuário. Todos registram `notice` (R50).
- Q: O que o motor faz com a imagem que uma tool devolve ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md), item 4)? → A: Publica-a ao usuário e não a manda ao modelo no turno em que ela nasce: um `AttachmentEvent(attachment, tool)` sai logo depois do `StepFinished` da tool, uma vez por `id` na execução, e o `FinalEvent.attachments` traz as mesmas, na ordem e sem repetição. Controller e geração veem só a marca que a 004 pôs no resultado cercado; a geração recebe ainda um texto de sistema fixo, junto da cerca, dizendo que o usuário vê as imagens marcadas.
- Q: E a imagem que o usuário envia (item 5)? → A: A da última mensagem do usuário (`Message.attachments`, contrato 001) é a pergunta: vai à geração, como partes `image_url`, sem decisão; ao controller, só se o papel `controller` também declara `vision` — senão ele vê `[imagem <id> enviada pelo usuário]`. Só imagem vale como pergunta (a pergunta dos packs é a marca). Imagem com o papel `generation` sem `vision` é `ExecutionRequestInvalid` antes de qualquer custo (a 008 responde 400 antes). Tools não recebem a imagem do usuário.
- Q: Quando uma imagem da resposta anterior vai à geração (item 8)? → A: Só se a pergunta for sobre ela, e só se a geração declara `vision`. As candidatas são as imagens da última mensagem do assistente. No `agentic` (e no loop do `rag_first` que escalou), o formato da ação ganha `{"action": "view_image", "id": "<id>"}`, o sistema do controller lista só os ids, a escolha conta como iteração e a mesma imagem pedida de novo segue a regra da ação repetida (FR-006b). No `chat` e no `rag_first` que vai à geração (coberto ou sem trechos), com `controller` declarado, uma etapa nova, `image_gate`, chama o controller uma vez com saída `{"view": [...]}`; falha ou saída fora do formato segue sem imagem, com `notice`. Sem `controller`, todas as candidatas vão. Sem candidata, os dois flows são os de antes — nem o `controller` é resolvido no `chat`.
- Q: Como a imagem escolhida chega à geração, e quanto custa no teto? → A: Na última mensagem do usuário enviada à geração, como parte `image_url`, precedida da marca `[imagem <id> mostrada ao usuário]`. No teto de contexto (FR-011), cada imagem enviada conta um custo fixo de 1.000 tokens (provisório, a calibrar com o provider) e não é tirada pela regra de omissão.

### Session 2026-10-28

- Q: Como o gráfico que uma tool devolve chega ao usuário ([ADR-052](../../docs/adr/ADR-052-graficos-na-conversa.md))? → A: Como a imagem: um `ChartEvent(chart, tool)` logo depois do `StepFinished` da tool (depois das imagens dela), uma vez por `id` na execução, e os mesmos em `FinalEvent.charts`. O modelo não recebe os dados, só a marca que a 004 põe no resultado cercado.
- Q: O modelo sabe que o gráfico foi mostrado? → A: Sim, por duas frases fixas do core, sem domínio: o `CONTROLLER_INSTRUCTION` passa a falar de "imagens e gráficos" que as ferramentas devolvem, e a geração do turno em que uma tool devolveu gráfico recebe `CHARTS_INSTRUCTION` — o gráfico aparece para o usuário, interativo e com a tabela; não refazê-lo em texto, tabela, código ou imagem; comentar o que mostra.
- Q: O que a geração sabe quando o loop termina, e em especial quando ele é cortado pelo limite (produção, 2026-10-29)? → A: Toda geração depois do loop (`agentic`, ou `rag_first` que escalou) recebe a frase fixa `NO_TOOLS_INSTRUCTION`: as ferramentas acabaram, escreva só texto, nunca chamadas nem `<tool_call>`. No corte pelo limite (`IterationLimit`), recebe também `LIMIT_INSTRUCTION`: responda com o que os resultados trazem e diga o que ficou faltando, como um gráfico que não chegou a ser feito. Sem elas, o glm-5.3-flash escrevia a chamada como texto; o filtro de marcação a cortava, e a resposta ficava vazia.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversa direta com resposta em streaming (Priority: P1)

Um usuário envia uma mensagem a um Assistant de flow `chat`. O motor valida a requisição, executa a preparação de contexto dos packs, gera a resposta com o modelo do papel `generation` emitindo tokens à medida que são produzidos, valida a resposta com os validators dos packs e encerra com um evento final.

**Why this priority**: É a Fase 1 — conversa ponta a ponta, em streaming. Streaming não é retrofit (princípio XI).

**Independent Test**: Executar um grant de flow `chat` com o pack de referência; o consumidor recebe eventos de token antes do fim da geração e um evento final com a resposta validada.

**Acceptance Scenarios**:

1. **Given** um grant de flow `chat`, **When** a execução roda com streaming, **Then** o consumidor recebe eventos de token incrementais e, ao final, um evento com resposta, citações e erros.
2. **Given** parâmetros inválidos ou orçamento esgotado, **When** a execução começa, **Then** falha na validação da requisição, antes de qualquer chamada de modelo.
3. **Given** um validator que remove uma citação, **When** a resposta é validada, **Then** o evento final reflete a resposta modificada e registra a remoção.

---

### User Story 2 - Loop agêntico com ação estruturada e limite (Priority: P1)

Num Assistant de flow `agentic`, o motor monta o catálogo e entra num loop: a cada iteração o modelo do papel `controller` emite **uma** ação estruturada — chamar uma tool (nome + argumentos) ou responder. Tools são executadas pelo gateway; resultados acumulam. Ao atingir o limite de iterações do grant, o motor segue para a geração com o que tem e registra o truncamento.

**Why this priority**: Fase 3. É o que habilita MCP e capacidades compostas; o limite é o que impede loop infinito (princípio V).

**Independent Test**: Um controller simulado que sempre pede tool; com limite 3, a execução faz exatamente 3 chamadas, gera a resposta e registra o truncamento.

**Acceptance Scenarios**:

1. **Given** um controller que pede `x.tool` e depois responde, **When** a execução roda, **Then** a tool é executada uma vez, o resultado é acumulado e a resposta é gerada.
2. **Given** limite de 3 iterações e um controller que nunca responde, **When** a execução roda, **Then** há exatamente 3 iterações, a geração acontece e o truncamento é registrado em erros.
3. **Given** um controller que emite ação malformada, **When** isso ocorre, **Then** conta como iteração, é registrado como erro e não interrompe a execução.
4. **Given** um controller que pede tool fora do catálogo, **When** isso ocorre, **Then** o resultado "tool inexistente" volta ao controller e conta como iteração.

---

### User Story 3 - Recuperação determinística antes de qualquer decisão de modelo (Priority: P2)

Num Assistant de flow `rag_first`, o motor recupera e reordena documentos deterministicamente e aplica um **portão de cobertura** determinístico. Com cobertura suficiente, gera a resposta direto (uma única chamada de modelo). Sem cobertura, escala para o loop agêntico.

**Why this priority**: Fase 5. ADR-006: no hardware alvo, o caminho determinístico é mais barato e mais confiável que o loop.

**Independent Test**: Com um retriever de teste, uma consulta com score alto gera resposta com uma única chamada de modelo; uma consulta sem resultados escala para o loop.

**Acceptance Scenarios**:

1. **Given** resultados cujo melhor score está acima do limiar, **When** o portão avalia, **Then** a execução vai direto à geração, sem chamada de controller.
2. **Given** zero resultados após filtros ou melhor score abaixo do limiar, e um Assistant com o papel `controller`, **When** o portão avalia, **Then** a execução escala para o loop agêntico.
3. **Given** a mesma falta de cobertura num Assistant sem `controller`, **When** o portão avalia, **Then** a geração roda sem trechos (`generation_context` vazio) e a execução registra um `notice` de cobertura insuficiente.
4. **Given** um pack que publicou filtros de recuperação na preparação de contexto, **When** a recuperação roda, **Then** os filtros são repassados aos retrievers desse pack sem interpretação pelo motor.

---

### User Story 4 - Resposta validada deterministicamente (Priority: P2)

Antes de encerrar, o motor executa os validators dos packs ativos em sequência, entregando a eles a Turn View que inclui os chunks efetivamente entregues à geração. Validators não chamam modelos.

**Why this priority**: ADR-007 — a verificação de citação precisa saber exatamente o que esteve no contexto da geração.

**Independent Test**: Um validator de teste recebe a Turn View e confirma que `generation_context` contém exatamente os chunks enviados ao modelo.

**Acceptance Scenarios**:

1. **Given** dois packs com validators, **When** a resposta é validada, **Then** os validators rodam na ordem do Assistant e seus resultados se acumulam.
2. **Given** um contexto de geração truncado por limite de tokens, **When** os validators rodam, **Then** `generation_context` contém só os chunks que de fato couberam.

---

### User Story 5 - Seleção de flow por nome (Priority: P2)

O motor executa o flow nomeado no grant. Flows ficam num registro nomeado; um flow desconhecido é erro explícito (e a validação de Assistants o detecta antes).

**Why this priority**: É o que permite reescrever, renomear ou acrescentar flows sem tocar em outros módulos.

**Independent Test**: Registrar um flow de teste novo e executá-lo por nome sem alterar nenhum outro módulo.

**Acceptance Scenarios**:

1. **Given** o registro de flows, **When** consultado, **Then** lista os nomes disponíveis (usados pela validação de Assistants).
2. **Given** um grant com flow inexistente, **When** a execução começa, **Then** falha com erro explícito que nomeia o flow.

---

### User Story 6 - Rotina isolada de pack (Priority: P3)

Quando o catálogo inclui a rotina de um pack, o controller pode invocá-la como uma ação. O motor a executa como passo único, entregando apenas a fatia do pack e os campos declarados, sob limites herdados, e incorpora apenas as saídas declaradas.

**Why this priority**: Escape hatch excepcional (nível 3).

**Independent Test**: Uma rotina de teste que tenta devolver campo não declarado tem essa saída descartada e registrada como erro.

**Acceptance Scenarios**:

1. **Given** uma rotina que declara saída `resultado`, **When** devolve também `outro`, **Then** só `resultado` é incorporado e o excesso é registrado.

---

### Edge Cases

- Cliente desconecta no meio do streaming: a execução é cancelada e os recursos liberados.
- Falha do provider no meio da geração: o fluxo termina com evento de erro explícito.
- Falha do modelo do `controller` no meio do loop: a execução segue para a geração com o que acumulou, sem nova tentativa, e o erro — estágio do controller, provider e modelo — fica em erros do evento final.
- Contexto excede o teto de tokens do grant: é reduzido por prioridade — chunks de menor rank primeiro (`rag_first`, Fase 5), resultados de tool mais antigos primeiro (`agentic`) — e a redução é registrada.
- Todas as citações removidas pelos validators: a marcação "não fundamentada" do validator chega ao evento final.
- Execução concorrente de ramos (se um flow futuro paralelizar): dados acumulados não se perdem.
- Hook de pack lança exceção: a execução termina com erro explícito que nomeia o pack (spec 002, FR-011).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O motor DEVE expor uma única operação de execução: recebe Execution Grant e requisição e devolve um fluxo de eventos (token, progresso, final com resposta, citações e erros). Falha anterior ao primeiro evento DEVE ser exceção tipada; falha posterior DEVE ser evento final com erros, preservando o que já foi emitido.
- **FR-002**: O motor DEVE interagir com packs somente via Pack Hooks (002), com tools somente via Capability Catalog e Tool Gateway (004) e com modelos somente via Model Router (006).
- **FR-003**: O motor DEVE oferecer os flows `chat`, `agentic` e `rag_first` num registro nomeado; flows novos são decisão arquitetural registrada em ADR.
- **FR-004**: Packs NÃO DEVEM poder criar, alterar ou inspecionar flows.
- **FR-005**: No flow `agentic`, o controller DEVE emitir exatamente uma ação estruturada por iteração, sob restrição de formato de saída.
- **FR-006**: Toda execução DEVE ter contador de iterações e respeitar o limite do grant; ao atingi-lo, DEVE seguir para a geração e registrar o truncamento. Sem limite declarado no grant, o limite é **3** — constante do motor, não configurável pelo operador.
- **FR-006a**: No flow `agentic`, falha da chamada ao modelo do `controller` depois do primeiro evento NÃO DEVE encerrar a execução nem ser repetida: o motor DEVE seguir para a geração com o que acumulou e registrar o erro, nomeando provider e modelo.
- **FR-006b**: A geração depois do loop DEVE receber o aviso fixo de que não há mais ferramentas e de que não deve escrever chamadas; quando o loop foi cortado pelo limite de iterações, DEVE receber também o aviso de responder com o que há e dizer o que ficou faltando. O `chat` não recebe nenhum dos dois.
- **FR-006b**: No loop, uma ação de tool com o mesmo nome e os mesmos argumentos de uma tool já executada na execução NÃO DEVE ser executada de novo: o motor DEVE seguir para a geração e registrar `RepeatedAction` (`notice`).
- **FR-006c**: O controller e a geração do loop DEVEM receber, no texto de sistema, a data de referência da execução no fuso da instalação (011). O `chat` não a recebe.
- **FR-007**: No flow `rag_first`, o portão de cobertura DEVE ser determinístico: melhor score abaixo de limiar configurável ou nenhum resultado após filtros → escalar; caso contrário → gerar. Limiar, número de candidatos pedidos aos retrievers e número de trechos levados à geração DEVEM ser configuração do operador (`AXON_RAG_*`), com defaults 20 candidatos, 5 trechos e sem limiar — sem limiar, só a ausência de resultado escala (clarificação de 2026-10-09).
- **FR-007a**: Quando o portão escala, o motor DEVE ir para o loop agêntico só se o grant tem o papel `controller`; sem ele, DEVE gerar sem trechos e registrar um `notice` de cobertura insuficiente. Os papéis exigidos pelo `rag_first` são só `generation` (`flow_roles`, ADR-019).
- **FR-008**: O motor DEVE repassar de forma opaca aos retrievers de um pack os filtros de recuperação que esse pack publicou.
- **FR-009**: Mensagens, chamadas de tool, resultados de tool e erros DEVEM acumular sem perda entre iterações e ramos.
- **FR-010**: O motor DEVE produzir, para os hooks de pack, a Turn View definida em 001, incluindo o conjunto exato de chunks entregues à geração.
- **FR-011**: O contexto enviado a modelos DEVE respeitar o teto de tokens do grant, quando declarado, com tokens estimados de forma determinística (sem tokenizador). Na Fase 3 o teto vale no flow `agentic`; na Fase 5, também no `rag_first`, tirando primeiro os trechos de menor posição — se nem sem trechos couber, a geração segue e registra `ContextOverflow`, como no `agentic`. O `chat` não aplica o teto, e o histórico não é cortado em nenhum flow; os dois entram quando houver demanda (conversas longas). No loop `agentic`: passo que levaria o contexto acima do teto não acontece — a execução segue para a geração e registra o truncamento —, e, se a geração ainda passar do teto, os resultados de tool mais antigos saem do contexto com marca de omissão, com a redução registrada. Sem teto no grant, não há corte.
- **FR-012**: O motor DEVE emitir eventos de progresso (tool chamada, recuperação em curso) e de token durante a geração.
- **FR-012a**: Toda etapa que emitiu progresso DEVE terminar com um evento de desfecho, antes do progresso da etapa seguinte, com o que ela fez: chamadas de tool (nome, argumentos, status, corte e as fontes dos trechos que voltaram), trechos mantidos no rerank, a decisão do portão (cobertura, melhor score, limiar, rota, trechos entregues), a ação do controller (com o modelo, a tool e os argumentos), o modelo e os tokens da geração, e o tamanho do catálogo. O desfecho NÃO DEVE trazer texto de trecho, conteúdo de resultado de tool, texto de erro de tool, prompt ou resposta, e o motor não mede tempo nele ([ADR-028](../../docs/adr/ADR-028-o-motor-publica-o-desfecho-de-cada-etapa.md)). Sem streaming, nada disso é emitido.
- **FR-012b**: A geração DEVE retirar da resposta a marcação de chamada de tool que o modelo escreva como texto (`<tool_call>…</tool_call>`), também em streaming, e registrar `ToolMarkupRemoved` (`notice`). Resposta vazia depois dos validators DEVE ser trocada por um aviso padrão ao usuário, com `EmptyAnswer` (`notice`); os validators continuam vendo a resposta vazia.
- **FR-013**: A validação da requisição (parâmetros, modelo, orçamento) DEVE ocorrer antes de qualquer chamada de modelo e antes do primeiro evento, levantando exceção tipada que nomeia o que está errado.
- **FR-014**: O estado de execução DEVE poder ser registrado por checkpoint, separado do histórico de conversa, quando houver um consumidor de retomada (ex.: aprovação humana de tool de escrita, retomada após queda). A porta entra com esse consumidor, não com o loop: na Fase 3 nenhuma execução é retomada (clarificações de 2026-09-21 e 2026-10-01).
- **FR-015**: A rotina isolada de pack DEVE ser executada como passo único, com entradas e saídas restritas ao declarado e limites herdados.
- **FR-016**: Cada iteração, decisão do controller, chamada de tool e validação DEVE emitir dados de trace pelo Trace Sink (009). A decisão do controller é um evento próprio — iteração, ação (`tool`, `answer`, inválida, limite atingido), nome da tool pedida e motivo quando inválida —, NUNCA com os argumentos; a chamada de tool é o evento que o gateway (004) emite.
- **FR-017**: O motor DEVE fixar, no início de cada execução, a data de referência — pelo relógio ou, numa execução de avaliação, pelo valor fixado (ADR-013) — e entregá-la em toda Turn View daquela execução.
- **FR-018**: A geração DEVE passar pelo filtro de validators do Pack Hooks antes de emitir cada token, e emitir a cauda dele no fim; o que os validators em lote só acrescentam à resposta DEVE sair como token antes do evento final; reescrita no meio, depois da geração, DEVE gerar um registro `notice` (`AnswerRewritten`) (ADR-024).
- **FR-019**: O motor DEVE publicar cada imagem que uma tool devolver num `AttachmentEvent(attachment, tool)`, depois do `StepFinished` da tool e uma vez por `id`, e em `FinalEvent.attachments` (ordem de saída, sem repetição), sem enviá-la ao modelo no turno em que ela nasce; quando houver imagem de tool, a geração DEVE receber o texto de sistema fixo de que o usuário vê as imagens marcadas ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md), item 4).
- **FR-019a**: O `controller` DEVE ser instruído, em texto fixo do core, de que as imagens das tools são mostradas ao usuário e de que, havendo tool que produza a imagem pedida, ele a chama em vez de desenhá-la em texto; numa execução com tools em que nenhuma devolveu imagem, a geração DEVE receber a nota fixa de que a plataforma mostra as imagens das tools (research R52).
- **FR-020**: A imagem da última mensagem do usuário DEVE ir à geração sem decisão e ao controller só se ele declara `vision`; sem `vision` no papel `generation`, a requisição com imagem DEVE ser recusada antes de qualquer custo (item 5).
- **FR-021**: Uma imagem da última mensagem do assistente DEVE ir à geração só quando a pergunta for sobre ela e o papel `generation` declarar `vision`: pela ação `view_image` do controller no loop (conta como iteração; repetida, segue o FR-006b), pela etapa `image_gate` no `chat` e no `rag_first` que vai à geração quando o Assistant declara `controller` (falha segue sem imagem, com `notice`), e sem decisão — todas — quando não há `controller` (item 8).
- **FR-022**: O `controller` DEVE ser papel opcional também no `chat`, resolvido só quando a etapa `image_gate` vai rodar; a etapa DEVE publicar progresso e desfecho (`ImageGateOutcome`), e a decisão DEVE ir ao trace como `controller_decision` com a ação `view_image` (ADR-017, ADR-019, ADR-028).
- **FR-023**: O teto de contexto (FR-011) DEVE estimar cada imagem enviada ao modelo por um custo fixo.
- **FR-024**: Os gráficos que as tools devolvem (`FencedToolResult.charts`, 004) DEVEM ir ao consumidor como `ChartEvent`, depois do desfecho da tool e das imagens dela, uma vez por `id` na execução, e em `FinalEvent.charts`; NÃO DEVEM ir ao modelo. A geração do turno em que houve gráfico DEVE receber o aviso fixo de que ele aparece para o usuário ([ADR-052](../../docs/adr/ADR-052-graficos-na-conversa.md), item 2).
- **FR-024a**: Numa execução com tools, a geração DEVE receber o aviso fixo do bloco ` ```axon-chart ` e PODE declarar gráficos em JSON nesse bloco; o motor DEVE tirar o bloco do texto em streaming, validá-lo pelo `Chart` do contrato e entregá-lo como os gráficos de tool (`ChartEvent`, `FinalEvent.charts`), até 4 por resposta e sem repetir; bloco inválido DEVE sair do texto e virar registro `ChartBlockInvalid` (`notice`) ([ADR-054](../../docs/adr/ADR-054-a-geracao-declara-graficos-em-json.md)).

### Key Entities

- **Execution Request**: mensagens, streaming sim/não, restrições válidas e, só em execução de avaliação, data de referência fixa (ADR-013) — preenchida apenas pelo harness em processo, nunca pela API HTTP (008 FR-012).
- **Execution Event**: token, progresso ou final (resposta, citações, erros, marcações).
- **Execution Grant**: o value object da 003. O motor lê assistant, flow, composição, política de modelos e limites (iterações e teto de contexto), e o entrega inteiro à 004 ao abrir a sessão de tools. Nas Fases 1 e 2 chegava por um `Protocol` publicado aqui.
- **Flow**: topologia nomeada.
- **Controller Action**: `{action: tool, name, arguments}` ou `{action: answer}`.
- **Internal State**: privado do motor; não é seam.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma reescrita completa da orquestração (topologias novas ou troca do framework de grafo) é concluída alterando apenas esta spec e `axon_ai/graph/`; as suítes de conformidade de 002, 004, 006, 008 e dos packs passam sem modificação.
- **SC-002**: 0 execuções ultrapassam o limite de iterações do grant (teste de propriedade com controllers adversariais).
- **SC-003**: No caminho coberto do `rag_first`, 100% das respostas usam exatamente uma chamada de modelo.
- **SC-004**: Em requisições com streaming, o usuário recebe o primeiro sinal (progresso ou token) em até 2 segundos após o envio, no hardware alvo.
- **SC-005**: 0 perdas de dados acumulados em testes de loop com o número máximo de iterações.

## Assumptions

- ADR-011 aceito: o estado interno é privado e os packs recebem a Turn View.
- O contexto de cada execução é montado pelo próprio motor, a partir do grant, com os seams que a composition root (011) injeta no boot.
- Na composição de vários packs em `rag_first`, a recuperação consulta os retrievers de todos os packs do grant e une os resultados por score; se isso se mostrar inadequado, a regra muda aqui sem afetar packs.
- Defaults do hardware alvo: limite de iterações 3 quando o Assistant não declara outro (FR-006) e catálogo mínimo em contexto.
- O limiar do portão de cobertura é calibrado na Fase 6 (spec 105), não aqui; até lá o default é não ter limiar, e o operador pode configurar um provisório.


## Incremento: delegação MCP por execução (2026-10-29)

Regido por [ADR-055](../../docs/adr/ADR-055-autenticacao-mcp-delegada.md). Protocolo 1: um MCP delegado por grant, identidade confidencial por execução, sem cache compartilhado e sem alteração da ACL. Contrato: [delegação](../007-core-mcp-integration/contracts/delegation.md). Casos D01 isolamento concorrente; D02 falha fechada; D03 metadados e superfície privada; D04 segredo ausente de persistência/trace; D05 regressão estática.
