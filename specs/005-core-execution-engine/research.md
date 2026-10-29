# Research — 005 Execution Engine (Fase 1, US1)

> Decisões pré-aprovadas vêm do [design.md](design.md) e dos ADRs da *Module Boundary*; não são re-pesquisadas.
> As quatro clarificações de 2026-09-21 estão na spec e aparecem aqui como R1, R3, R5 e R7.

## R1 — LangGraph entra já na Fase 1

**Decision**: `adapters/langgraph/` nasce agora, com o grafo do `chat`, o estado com reducers e a tradução do streaming
do framework em `ExecutionEvent`. Dependência `langgraph>=1.2,<2` na distribuição `ai-core`.

**Rationale** (clarificação de 2026-09-21; constituição, "Stack e restrições técnicas"; `design.md`): é a decisão
pré-aprovada, e a Fase 1 existe justamente para provar a conversa ponta a ponta **em streaming** (princípio XI, SC-004).
A parte delicada do desenho é traduzir o streaming do framework nos eventos do seam; adiá-la significaria escrever um
adapter sequencial para jogar fora e descobrir só na Fase 3 se a tradução funciona. Com o grafo montado agora, a Fase 3
acrescenta nós e arestas de loop a uma topologia que já roda.

**Alternatives considered**: adapter sequencial na Fase 1 e LangGraph na Fase 3 (exigiria ADR por divergir da
constituição, e o adapter seria escrito duas vezes); motor próprio em todas as fases (ADR que substituiria a escolha
original de orquestração).

## R2 — O streaming sai por `astream(stream_mode=["custom", "values"])`, não por `astream_events`

**Decision**: os nós escrevem tokens e progresso no canal `custom` (via o escritor de stream do próprio framework) e o
runtime do adapter consome `["custom", "values"]`: `custom` vira `TokenEvent`/`ProgressEvent` ao vivo e o último
`values` vira o `FinalEvent`.

**Rationale**: o `design.md` escreve "`astream_events` → filtrar tokens do `agent_generate`", que pressupõe que a
geração passe por um modelo do próprio framework. Não é o caso: pelo princípio XIII e pelo ADR-008, o modelo vem do
**Model Router** (006), que não é um modelo do LangChain — logo não há evento de LLM para filtrar. O canal `custom` é a
forma suportada de emitir de dentro de um nó, e dá o progresso de graça. Verificado na versão instalada: os pedaços
`custom` chegam intercalados, **antes** de o nó terminar (é o que sustenta SC-004), o último `values` traz o estado
completo, fechar o iterador no meio não levanta, e exceção dentro de nó propaga para quem consome. Isso é interior do
adapter, que o `design.md` declara livre ("tudo abaixo da seção Seams é interno"), então não há divergência a registrar
em ADR.

**Alternatives considered**: embrulhar o `BoundModel` (006) num modelo do LangChain só para `astream_events` enxergá-lo
(poria o framework no caminho do seam de outro módulo, contra o princípio XIII, e acrescentaria uma tradução a mais por
token); acumular tudo e emitir no fim (mata o streaming, que é requisito de fase).

## R3 — O grant chega como `Protocol` publicado por este módulo

**Decision**: `api.py` publica `ExecutionGrant` como `Protocol` com o que o motor lê: `assistant`, `flow`,
`composition` e `models`. A 003 produzirá, na Fase 2, um valor que o satisfaz **estruturalmente** — sem import, sem
registro e sem mudar o seam.

**Rationale** (clarificação de 2026-09-21): o grafo de dependências tem a seta `005 → 003`; definir o value object aqui
inverteria a posse do seam e exigiria ADR. Um `Protocol` expressa exatamente a relação certa: a 005 declara a *forma
exigida*, a 003 fornece o *valor*. Na Fase 1 quem monta o objeto é a composition root (011), e o seam `run(grant,
request)` fica idêntico nas duas fases. O `Protocol` cresce de forma aditiva: `limits` entra na Fase 3 (loop) e o teto
de contexto na Fase 5, quando houver o que limitar.

**Alternatives considered**: dataclass própria da 005 (inverte a posse do seam); antecipar `ai_core/assistants/` só com
o value object (código sem spec planejada, numa fase que não é a dele).

## R4 — O grant carrega a `Composition`, não a lista de nomes de pack

**Decision**: `ExecutionGrant.composition` é a `Composition` da 002, já validada. O motor **não** consome o Pack
Registry.

**Rationale**: a tabela de seams de `specs/README.md` dá o Pack Registry a 003, 004 e 008 — não a 005; a 005 só
consome Pack Hooks. Compor exige validar dependências e disponibilidade, que é resolução de Assistant (003). Receber a
composição pronta mantém a fronteira, evita que o motor conheça o estado de carga dos packs e deixa `run` sem nenhuma
chamada de registro. Na Fase 1, quem compõe é a 011, que consome todos os módulos por definição.

**Alternatives considered**: receber `Sequence[str]` e compor no motor (acrescentaria um seam não declarado à
*Module Boundary*, o que o princípio II proíbe sem ADR).

## R5 — A validação da requisição acontece fora do grafo, em `service.run()`

**Decision**: `run()` é função comum (não geradora): valida requisição, flow e grant de forma síncrona, levanta
`ExecutionRequestInvalid`/`UnknownFlow` se algo estiver errado e só então devolve o iterador de eventos.

**Rationale** (clarificação de 2026-09-21): para a 008 responder 4xx **antes** de abrir o SSE, o erro precisa aparecer
na chamada, não na primeira iteração — se `run` fosse geradora, o corpo só rodaria no primeiro `__anext__` e a 008
teria de espiar o iterador para decidir o código de resposta. Isso tira `validate_request` da lista de nós do
`design.md`, que é interior do adapter e declaradamente livre; a política em si continua pura, em `domain/request.py`,
e sobrevive a qualquer reescrita do grafo (é o que o SC-001 pede).

**Alternatives considered**: nó `validate_request` dentro do grafo (o erro chegaria depois do iterador começar);
validar em duas etapas (duplica a regra e cria o risco de as duas discordarem).

## R6 — Depois do primeiro evento, falha é evento; nunca exceção

**Decision**: o runtime do adapter envolve o consumo do grafo: qualquer exceção vira `FinalEvent` com a resposta
parcial e um erro que nomeia a etapa e a causa. `PackHookError` (002) nomeia o pack; `ModelCallFailed` (006) nomeia
provider e modelo.

**Rationale** (clarificação de 2026-09-21): quem consome já está lendo um stream e, em SSE, uma exceção não tem para
onde ir sem descartar o que já foi entregue. O princípio VII exige falha explícita, não falha silenciosa — e um evento
final com erro nomeado é explícito. Também é o que o edge case da spec já mandava para falha de provider no meio da
geração.

**Alternatives considered**: propagar a exceção (o consumidor perde tokens já emitidos e a 008 teria de fechar o SSE
sem explicação); engolir e devolver resposta vazia (falha silenciosa).

## R7 — Porta `Clock` com data e cronômetro; checkpoint só na Fase 3

**Decision**: `ports.py` declara `Clock` com `now()` (data de referência, ADR-013) e `monotonic()` (duração da
execução no trace). A porta `CheckpointStore` **não** nasce nesta fase.

**Rationale** (clarificação de 2026-09-21): a Fase 1 não retoma execução — o `chat` roda do começo ao fim dentro de uma
requisição —, então a porta de checkpoint não teria consumidor, o que o princípio XIII proíbe. As duas leituras de
tempo, ao contrário, têm uso imediato: `reference_time` vai em toda Turn View e a duração vai no trace. Os outros
módulos declaram portas de tempo próprias (009 com `now()`, 006 com `monotonic()`); um único adapter as satisfaz
estruturalmente, e é a 011 que injeta o mesmo objeto nos três (011 FR-008).

**Alternatives considered**: porta de checkpoint com adapter em memória agora (porta sem consumidor); reusar a porta de
outro módulo (um módulo não importa `ports.py` de outro — são internos).

## R8 — Eventos como dataclasses congeladas no `api.py`

**Decision**: `TokenEvent`, `ProgressEvent` e `FinalEvent`, união em `type ExecutionEvent`. Nenhum tipo do LangGraph,
do LangChain ou de HTTP aparece no `api.py`; `Citation` vem do contrato 001.

**Rationale**: é o que torna o SC-001 verificável — trocar o framework não pode mudar o que a 008 e o harness leem. O
padrão é o mesmo do `api.py` da 009 (dataclasses congeladas que validam na construção), e um contrato de import-linter
impede o framework de vazar.

**Alternatives considered**: dicionários (perde validação e deixa o formato implícito em quem consome).

## R9 — A Turn View é projeção do estado interno

**Decision**: `adapters/langgraph/view.py` projeta `AgentState` → `TurnView` (001). `question` é o conteúdo da última
mensagem de papel `user` da requisição; `reference_time` é fixada uma vez, no início, e repetida em toda Turn View da
execução.

**Rationale**: ADR-011 — o estado interno é privado e o pack só enxerga a Turn View; manter a projeção num arquivo só
é o que permite reescrever o estado sem tocar em pack nenhum. A pergunta ser a última mensagem de usuário é a regra
mínima que serve a `chat`; se algum flow futuro precisar de outra, a regra muda aqui.

**Alternatives considered**: passar o estado ao pack (proibido pelo ADR-011); pedir a pergunta na requisição além das
mensagens (dado duplicado que pode divergir).

## R10 — Quem emite cada dado de trace

**Decision**: o `service.py` emite `ExecutionStarted` (com `reference_time`) antes do primeiro evento e
`ExecutionFinished` ao encerrar, com a duração; o nó de validação emite um `ValidationRun` por validator; falhas emitem
`ExecutionError`. As chamadas de modelo já são emitidas pela 006, e o motor não as duplica.

**Rationale**: FR-016 e o "Seam Notes for Consumers" do plano da 009 descrevem exatamente esta divisão. Emitir do
serviço garante que começo e fim existam mesmo quando o grafo falha no meio; emitir o validator do nó é o único lugar
que conhece o resultado de cada um.

**Alternatives considered**: emitir tudo do serviço (o serviço não vê o resultado de cada validator, só o agregado);
emitir tudo dos nós (execução que falha antes do grafo ficaria sem começo nem fim no trace).

## R11 — Escopo da fase

**Decision**: a Fase 1 entrega a **US1** inteira mais o registro de flows da US5, porque `flows()` faz parte do seam e
a 011 precisa dele no boot. `agentic` (US2), `rag_first` (US3), rotina de pack (US6), checkpoint e corte de contexto
por orçamento ficam para as fases deles. De `domain/`, nascem `request.py` (validação) e `outcome.py` (montagem do
evento final); `gate.py`, `limits.py`, `actions.py` e `budget.py` chegam com `rag_first` e `agentic`.

**Rationale**: `docs/roadmap.md` lista `005 · US1 (chat)` na Fase 1, `005 · US2` na Fase 3 e `005 · US3, US4` na Fase 5.
A US4 (validators com a Turn View correta) é exercida já aqui na sua parte que o `chat` alcança — validators rodam e
recebem `generation_context` —, mas o cenário de truncamento por orçamento é Fase 5, porque depende de chunks.

**Alternatives considered**: entregar também o `agentic` (antecipa 004 e 007, que não existem); entregar o `chat` sem
validators (deixaria a US1 cenário 3 sem cobertura).

## R12 — Contratos de import-linter novos

**Decision**: camadas do módulo (`api.py` não importa o resto; `domain/` não importa portas, service nem adapters;
`service.py` não importa adapters) e, sobretudo, `langgraph`/`langchain_core` proibidos em `api.py`, `domain/`,
`ports.py` e `service.py` — e proibidos em qualquer módulo que não seja `ai_core.graph.adapters`.

**Rationale**: é o que torna executável a promessa do ADR-011 e do SC-001: o framework de grafo não é contrato. Segue o
padrão já aplicado ao SDK de modelo na 006 (R13 daquela spec).

**Alternatives considered**: confiar em revisão (a regra mais importante do módulo seria a única não verificada).

## R13 — Os testes montam o caminho real

**Decision**: a suíte de conformidade do seam roda o grafo de verdade, com o Pack Runtime real (002) carregando o
`ai-generic` (010) e o provider simulado da 006. Só o modelo é simulado.

**Rationale**: é o "Independent Test" que a própria US1 descreve ("com o pack de referência"), e é o primeiro ponto do
projeto em que quatro módulos se encontram — o valor do teste está exatamente aí. Simular o modelo é o que mantém a
suíte sem rede e determinística; simular o resto esconderia justamente o que esta fase precisa provar.

**Alternatives considered**: duplos para packs e hooks (testaria o motor contra a ideia que ele faz dos outros módulos,
não contra eles).

## Decisões da Fase 3 (US2, flow `agentic`) — 2026-10-01

> Insumos: as cinco clarificações de 2026-10-01 (spec), o [design.md](design.md) ("`agentic` — loop de controller",
> "Controller", "Nós finos") e os ADRs 001, 005, 008, 011, 012, 013 e o novo
> [ADR-017](../../docs/adr/ADR-017-trace-sink-cresce-por-eventos-aditivos.md). Seams consumidos, já implementados:
> `Capabilities`/`ToolSession` (004), `ModelRouter` (006), `PackHooks` (002), `TraceSink` (009), `ExecutionGrant` (003).

### R14 — Escopo da passada

**Decision**: US2 inteira, mais o que ela puxa dos requisitos transversais: FR-005 (ação estruturada), FR-006 e
FR-006a (limite, truncamento, falha do controller), FR-009 (acúmulo sem perda), FR-010 (Turn View com resultados de
tool), FR-011 na parte do loop, FR-012 (progresso de tool), FR-013 (papéis exigidos pelo flow), FR-016 (decisão do
controller no trace) e SC-002/SC-005. Ficam fora: US3 e o portão do `rag_first` (Fase 5), US4 no cenário de chunks
cortados por rank (Fase 5), US6 (P3), a porta de checkpoint (clarificação 1, R30) e o corte de histórico de conversa.

**Rationale**: é a linha da 005 no roadmap da Fase 3 ("005 · US2 (`agentic`)"), com as decisões de 2026-10-01.

**Alternatives considered**: antecipar o `rag_first` (depende de retrievers com coleções, que a 003 só aceita na
Fase 5).

### R15 — O motor passa a receber o Execution Grant da 003

**Decision** ([ADR-018](../../docs/adr/ADR-018-seam-execution-engine-fase-3.md)): o `Protocol` `ExecutionGrant` do `api.py` sai; `run(grant, request)` recebe o `ExecutionGrant` publicado
pela 003 (`ai_core.assistants.api`), que o `api.py` da 005 importa e **reexporta com o mesmo nome**. A assinatura do
seam continua `run(grant, request)`.

**Rationale**: o R3 publicou o `Protocol` "até a 003 existir" — ponte declarada para a Fase 1. Agora o motor precisa
entregar o grant ao `Capabilities.open(grant, ...)` da 004, que exige o tipo concreto da 003 (principal, aliases de MCP,
coleções, `allowed_tools`, `write_tools`, limites). Manter o `Protocol` obrigaria a crescer até repetir todos os campos
da 003, ou a converter tipos na chamada. A seta 005 → 003 já está no grafo de `specs/README.md` e o seam Execution
Grant já lista a 005 como consumidora; o import-linter já permite `ai_core.graph` → `ai_core.assistants.api`. Todo
chamador de produção (a 008) já passa o grant da 003, que cumpria o `Protocol` estruturalmente — nada muda para ele. A
reexportação mantém `from ai_core.graph.api import ExecutionGrant` válido.

**Alternatives considered**: ampliar o `Protocol` com os campos que a 004 lê e mudar a 004 para aceitá-lo (edita outra
spec e duplica a forma do grant em dois `Protocol`s); `cast` na chamada à 004 (esconde do mypy exatamente a garantia
que o tipo dá).

### R16 — A sessão de tools abre dentro do flow, depois da preparação; sem `Capabilities`, não há `agentic`

**Decision**: o `ExecutionService` ganha a dependência `capabilities: Capabilities | None = None` (seam da 004). O flow
`agentic` abre a sessão num passo próprio (`load_capabilities`), **depois** de `prepare_context`, com
`ToolContext(request_id, reference_time, retrieval_filters)`, em que `retrieval_filters` é, por pack, o valor da chave
`RETRIEVAL_FILTERS_KEY` (contrato 001) da fatia que o `prepare` devolveu — repassado sem leitura (FR-008). Motor
montado sem `capabilities` não oferece `agentic`: `flows()` o omite, e um grant com esse flow recebe `UnknownFlow` na
chamada. Os flows que exigem tools ficam numa constante de `domain/`.

**Rationale**: abrir a sessão faz descoberta de MCP — I/O que não pode acontecer em `run()` (que só valida, sem custo,
R5) e que precisa das fatias da preparação. É a ordem do `design.md` (`prepare_context → load_capabilities`). A
dependência opcional deixa a 011 ligar a 004 na passada de encaixe dela sem que esta passada quebre o boot de hoje, e
falha fechada: sem gateway, o flow simplesmente não existe, e a validação de Assistants (003) já aponta isso.

**Alternatives considered**: abrir a sessão em `run()` (I/O antes do primeiro evento, e sem as fatias); dependência
obrigatória (obrigaria a 011 a montar 004 e 007 nesta passada); flow `agentic` sempre listado, falhando no meio
(erro tardio para uma configuração que se conhece no boot).

### R17 — A ação sai por `response_format`, com um ramo por tool do catálogo

**Decision**: o controller é chamado com `for_role("controller").complete(messages, response_format=...)` e o formato é
`{"type": "json_schema", "json_schema": {"name": "controller_action", "schema": S}}`, sem `strict`. `S` é um `anyOf`
com um ramo `{"action": "answer"}` e um ramo por tool do catálogo, `{"action": "tool", "name": <const>, "arguments":
<parâmetros da tool>}`, todos com `required` e `additionalProperties: false`. Os parâmetros entram **saneados**:
`pattern` e `patternProperties` são removidos, e esquema com `$ref` em qualquer ponto vira `{"type": "object"}`. Tudo
em `domain/actions.py`, puro.

**Rationale**: `design.md` ("Saída estruturada via `response_format`") e 006 FR-005. No hardware alvo a restrição vira
gramática no provider local: com um ramo por tool, o modelo pequeno não consegue inventar nome nem errar a forma dos
argumentos — é o ganho que o `design.md` atribui à saída estruturada. Saneamento: o gateway (004) valida os argumentos
de verdade, então o esquema no formato serve só para guiar; regex de terceiro vira gramática no provider (o mesmo
risco que levou a 004 a desligar `pattern` em esquemas de MCP), e `$ref` aninhado dentro de outro esquema passa a
apontar para a raiz errada. `strict` e a recusa de provider sem suporte ficam com a 006 (US4).

**Alternatives considered**: esquema plano (`action`, `name`, `arguments` livre) — mais curto, mas não restringe os
argumentos; tool calling nativo do provider (`tools=`) — o `design.md` escolhe `response_format`, e o suporte a tool
calling nos modelos pequenos é justamente o "nominalmente suportado, não confiável" do arch-v1 §9.

### R18 — Ler a ação: forma no motor, argumentos no gateway

**Decision**: `parse_action(content)` (puro) devolve `ToolAction(name, arguments)`, `AnswerAction` ou
`InvalidAction(reason)`. Inválida: conteúdo vazio ou ausente, JSON malformado, raiz que não é objeto, `action` fora de
`tool`/`answer`, `name` vazio ou não texto, `arguments` que não é objeto. Nome fora do catálogo **não** é inválido: vai
ao gateway, que responde "tool inexistente" (004 FR-005), e o resultado volta ao controller (US2 cen. 4). Argumentos
não são conferidos contra o esquema aqui — é o gateway que valida e devolve `invalid_arguments`. O motivo da
invalidade é texto do motor (ex.: "JSON malformado"), nunca trecho do que o modelo escreveu.

**Rationale**: uma regra, um dono — a validação de argumentos é FR-006 da 004, e duplicá-la cria duas respostas
diferentes para o mesmo erro. Não copiar a saída do modelo para o motivo mantém o evento de trace sem conteúdo
(ADR-017).

**Alternatives considered**: nome fora do catálogo como ação inválida (o cenário 4 da US2 pede o resultado "tool
inexistente" de volta ao controller, e o gateway já o produz igual para proibida e inexistente).

### R19 — A transcrição do loop usa o formato nativo de tool

**Decision**: cada iteração de tool acrescenta à conversa enviada aos modelos uma mensagem `assistant` com `tool_calls`
(id sintético `call-<iteração>`, nome e argumentos em JSON) e uma mensagem `tool` com o mesmo `tool_call_id` e o texto
**cercado** que o gateway devolveu. Ação inválida acrescenta só uma mensagem `user` do motor ("A ação anterior era
inválida: <motivo>. Responda com uma ação válida.") — sem repetir a saída do modelo. Mensagens enviadas:

- controller: sistema com a instrução do controller, a lista do catálogo (nome, descrição, parâmetros) e a
  `FENCE_INSTRUCTION`; depois as mensagens da requisição; depois a transcrição;
- geração: os fragmentos de `PackHooks.system_prompts` (como no `chat`) e, se houver ao menos um resultado na
  transcrição, a `FENCE_INSTRUCTION` numa mensagem de sistema a mais; depois as mensagens da requisição e a transcrição.

Os construtores são funções puras em `domain/transcript.py`; com transcrição vazia, a geração recebe exatamente as
mensagens do `chat` da Fase 1.

**Rationale**: o contrato 001 já tem `tool_calls`/`tool_call_id` e o papel `tool` em `ChatMessage` para isto. Todos os
providers-alvo (o template de chat do modelo local, OpenAI, OpenRouter) têm um lugar próprio, de menor autoridade, para
saída de tool — pôr conteúdo externo no papel `user` lhe daria a autoridade do usuário (princípio VI). A instrução da
cerca vai "no texto de sistema, sem alterar" (004, `contracts/fencing.md`). Pack prompts ficam fora do controller,
como na tabela "Nós finos" do `design.md`: o controller escolhe tool, a geração fala com a voz do pack.

**Alternatives considered**: resultados como mensagem `user` (autoridade errada para conteúdo externo); um bloco único
de resultados no sistema (o modelo perde a associação pedido → resultado); repetir a saída inválida do modelo (leva
para o contexto e para o trace o que ele próprio errou).

### R20 — Contagem, limite e para onde o loop vai

**Decision**: `domain/limits.py`, puro. `DEFAULT_MAX_ITERATIONS = 3` (clarificação 3); o limite efetivo é
`grant.limits.max_iterations or 3`. Uma **iteração** é uma chamada ao controller. Depois de cada decisão:

| Decisão na iteração `n` | `n < limite` | `n == limite` |
|---|---|---|
| `tool` | executa e volta ao controller | executa e vai à geração, registrando o truncamento |
| inválida | registra e volta ao controller | registra e vai à geração, registrando o truncamento |
| `answer` | vai à geração | vai à geração (sem truncamento) |
| falha do modelo | vai à geração, registrando o erro (R21) | idem |

Com limite 3 e um controller que só pede tool: exatamente 3 chamadas ao controller, 3 execuções, geração, truncamento
registrado — o Independent Test da US2. Catálogo vazio (nenhuma tool, ou todos os MCPs indisponíveis) vai direto à
geração, sem chamada ao controller e sem consumir iteração (R27).

**Rationale**: FR-006 e o `design.md` ("ao atingir o limite, o controller não falha: transiciona para `agent_generate`
com o que tem, e registra o truncamento"). A decisão de rota é função pura chamada pelas arestas condicionais — o
grafo só ordena (ADR-001, SC-001).

**Alternatives considered**: contar execuções de tool em vez de chamadas ao controller (uma ação inválida não
contaria, e um controller que só erra rodaria sem fim — o cenário 3 da US2 diz que conta).

### R21 — Falha do controller segue para a geração

**Decision** (clarificação 2): `ModelCallFailed` na chamada ao controller encerra o loop e vai à geração com o que há;
sem nova tentativa (006 FR-007). Registro: `ExecutionIssue(stage="controller", kind="ModelCallFailed",
severity="error")` com provider e modelo na mensagem, e `ExecutionError` no trace. Papel não configurado ou fora da
allowlist nunca chega aqui: é verificado em `run()` (R25). Qualquer outra exceção no controller segue a regra geral do
R6 (evento final com erro).

**Rationale**: a mesma regra do limite, explícita para o usuário (o erro está no evento final) e sem fallback.

**Alternatives considered**: ver a clarificação 2 na spec.

### R22 — Teto de contexto: estimativa por caracteres, parada do loop e omissão dos resultados mais antigos

**Decision** (clarificação 5), em `domain/budget.py`, puro:

- **Estimativa**: `ceil(caracteres / 3) + 4` por mensagem, somando conteúdo e, nas mensagens com `tool_calls`, nome e
  argumentos. Determinística, sem tokenizador, e conservadora (3 caracteres por token sobrestima português e JSON).
- **Antes de cada chamada ao controller**: se a estimativa das mensagens do controller passar de
  `grant.limits.max_context_tokens`, o loop para e vai à geração, com `ExecutionIssue(kind="ContextLimit",
  severity="notice")` e a decisão `limit` (motivo `context`) no trace.
- **Antes da geração**: se a estimativa passar do teto, o conteúdo dos resultados de tool mais antigos é trocado, um
  por vez, pela marca `[resultado omitido: teto de contexto]` até caber; a redução vira
  `ExecutionIssue(kind="ContextTrimmed", severity="notice")` com quantos saíram. Se nem sem resultados couber, a
  geração acontece assim mesmo e o excesso é registrado (`kind="ContextOverflow"`, `notice`) — cortar histórico de
  conversa não é desta passada.
- **Sem teto no grant**: nada é estimado nem cortado.
- **Omissão não é perda**: a troca pela marca vale só para as mensagens enviadas ao modelo; os passos acumulados no
  estado ficam intactos (FR-009, SC-005), e a Turn View de `validate` lista só o que a geração recebeu (R26).
- **No `chat`**: nada muda — o plano do `chat` não lê `limits` (teto e limite ficam `None`), e as mensagens enviadas
  são byte a byte as da Fase 1. O teto vale onde a clarificação 5 o pôs: no loop.

**Rationale**: cumpre a FR-011 onde o contexto passa a crescer sem controle do usuário. A regra "o que vale menos sai
primeiro" é a mesma do corte de chunks por rank da Fase 5, no mesmo arquivo. Omitir o mais antigo preserva a
transcrição (o par pedido/resultado continua lá, com a marca), e o controller nunca chega a receber um contexto que
o provider truncaria em silêncio.

**Alternatives considered**: tokenizador real (dependência por modelo e por provider; a estimativa conservadora basta
para um teto que é proteção, não cobrança); cortar o resultado mais longo primeiro (muda qual informação sai conforme
o tamanho, não conforme a idade — mais difícil de explicar no registro).

### R23 — Gravidade dos registros: `ExecutionIssue.severity`, aditivo

**Decision** ([ADR-018](../../docs/adr/ADR-018-seam-execution-engine-fase-3.md)): `ExecutionIssue` ganha
`severity: Literal["error", "notice"] = "error"`. São `notice` os **resultados de política**: apontamentos de
validator (já eram tratados à parte pelo `kind`), o truncamento por limite (`IterationLimit`), a ação inválida do
modelo (`InvalidAction`), a parada por teto (`ContextLimit`) e a omissão e o excesso de contexto (`ContextTrimmed`,
`ContextOverflow`). São `error` as **falhas de dependência**: a falha do controller, o MCP indisponível na montagem
do catálogo (`McpUnavailable` — princípio VII: degradação nunca silenciosa) e toda falha que já era erro. `succeeded()` passa a ser "nenhum registro `error`" — é o `ok` do
`ExecutionFinished`.

**Rationale**: até aqui só havia um tipo de registro que não era falha, identificado pelo `kind` — em `domain/outcome.py`
e, duplicado como texto, em `http/domain/openai_chunks.py` (008). Com o loop, aparecem seis: sem a gravidade, toda
execução que bate no limite de iterações viraria falha no trace e `finish_reason: "error"` na API, e a 008 teria de
conhecer cada `kind` da 005. O campo tem default, então nada que já constrói `ExecutionIssue` muda; a 008 continua
correta para o `chat` e adota `severity` na passada de encaixe dela (até lá, uma execução `agentic` truncada sai com
`finish_reason: "error"`, com a resposta inteira). Mudança de seam registrada no ADR-018, com as consumidoras
listadas: nenhum nome existente muda de forma, e o significado de `ExecutionFinished.ok` passa a ignorar `notice`.

**Alternatives considered**: registrar os avisos em `flags` (a US2 cen. 2 diz "registrado em erros"); publicar a lista
de `kind`s que não são falha (a 008 continuaria acoplada a nomes da 005); deixar como está (métrica de sucesso errada
na Fase 6).

### R24 — Trace: `ControllerDecision` na 009, sob o ADR-017

**Decision** (clarificação 4): evento novo, aditivo, no `api.py` da 009 — `ControllerDecision(request_id, iteration,
action, tool=None, reason=None)`, com `action ∈ {"tool", "answer", "invalid", "limit"}`, `iteration ≥ 0` (0 só em
`limit` antes da primeira chamada), `tool` só em `tool`, `reason` obrigatório em `invalid` e em `limit`
(`"iterations"` ou `"context"`). Sem argumentos, sem saída do modelo. Quem emite o quê numa execução `agentic`:

| Dado | Quem emite |
|---|---|
| `ExecutionStarted`, `ExecutionFinished` | `service.py` (como na Fase 1) |
| `ModelCall` do controller e da geração | a 006, pelo cliente que devolve |
| `ExecutionError(stage="catalog")` por MCP indisponível ou tool com esquema inválido | a 004, ao abrir a sessão |
| `ToolCall` por execução | a 004, no gateway |
| `ControllerDecision` por decisão e no limite | a 005, no passo do controller |
| `ExecutionError(stage="controller")` na falha do controller | a 005 |
| `ValidationRun` | a 005, como na Fase 1 |

Toque declarado na 009: dataclass, membro da união `TraceEvent`, `contracts/trace-api.md`, `contracts/record-format.md`,
`data-model.md` (que ainda não lista o `ToolCall`, e passa a listar os dois) e o teste de nomes públicos. O tipo no
registro sai do nome da classe: `controller_decision`.

**Rationale**: FR-016 e ADR-017; o motor não duplica o que 004 e 006 já emitem (como o R10 fez para `ModelCall`).

**Alternatives considered**: ver ADR-017.

### R25 — Papéis exigidos pelo flow são conferidos em `run()`

**Decision**: `domain/request.py` declara os papéis de cada flow (`chat` → `generation`; `agentic` → `controller` e
`generation`), e `run()` pede `for_role(...)` de cada um ao roteador da execução **antes** de devolver o iterador;
`RoleNotConfigured`, `ModelNotAllowed` e `UnknownProvider` (006) viram `ExecutionRequestInvalid` nomeando o papel.

**Rationale**: FR-013 ("parâmetros, modelo, orçamento" antes do primeiro evento). `for_role` resolve e confere a
allowlist sem I/O (contrato da 006), então a checagem não tem custo. Sem ela, um Assistant `agentic` sem `controller`
descobriria o problema depois de preparar contexto e abrir a sessão de tools. No `chat` muda só o momento do erro de
um papel `generation` ausente — que a 003 já impede de existir.

**Alternatives considered**: deixar o erro aparecer no passo do controller (custo antes do erro); validar só na 003
(é a regra dela também, mas a 003 não sabe quais papéis cada flow exige — R33).

### R26 — Turn View no `agentic`

**Decision**: `tool_results` traz, na ordem, um `ToolResult` (001) por resultado **entregue à geração** — conteúdo = o
texto cercado, `untrusted=True`, `truncated` e `error` do gateway; os omitidos pelo teto não entram. `retrieved` traz os
chunks de todos os resultados de recuperação; `generation_context`, os chunks dos resultados de recuperação que
ficaram no contexto da geração; `reranked` fica vazio (o `agentic` não reordena). `prepare` recebe a Turn View sem
resultados; `validate`, a completa.

**Rationale**: FR-010 e ADR-007 — o validator precisa ver exatamente o que esteve no contexto da geração; a regra é a
mesma do US4 cen. 2, aplicada a resultados de tool. Na Fase 3 nenhuma tool de recuperação chega ao catálogo (a 003 só
aceita coleções na Fase 5), mas a projeção já fica certa.

**Alternatives considered**: `tool_results` com todos os resultados, inclusive os omitidos (o validator veria o que a
geração não viu).

### R27 — Catálogo vazio vai direto à geração

**Decision**: se a sessão abre sem nenhuma tool, o `agentic` pula o controller e gera — como o `chat`, mais os avisos
de MCP indisponível, se houver. Nenhuma iteração é consumida e nenhuma decisão é emitida.

**Rationale**: um controller sem tools só pode responder; a chamada custaria um modelo (arch-v1 §9) para uma decisão
determinística.

**Alternatives considered**: chamar o controller assim mesmo (custo sem decisão).

### R28 — Progresso do loop

**Decision**: `ProgressEvent("load_capabilities")` ao abrir a sessão; `ProgressEvent("controller", detail="iteração
<n>")` antes de cada chamada ao controller; `ProgressEvent("execute_tool", detail=<nome pedido>)` antes de cada
execução. O nome é o que o controller pediu, inclusive quando não existe no catálogo.

**Rationale**: FR-012 ("tool chamada"). O nome de tool é do catálogo do próprio Assistant — nada que o usuário não
possa usar; e a 008 já traduz progresso num campo que cliente padrão ignora.

**Alternatives considered**: progresso sem nome (FR-012 pede a tool chamada).

### R29 — Testes: controller simulado no testkit, gateway falso no seam, real na integração

**Decision**:

- **Controller simulado**: `ScriptedController` no `graph_testkit.py`, que cumpre estruturalmente o `ModelProvider` da
  006 (`name`, `chat`, `probe`) e devolve um roteiro de conteúdos ou exceções, um por chamada, guardando mensagens e
  `response_format`. Entra no `ModelRoutingService` real como provider do papel `controller`. A 006 não muda.
- **Gateway**: na conformidade do seam e na suíte de propriedade, `FakeCapabilities`/`FakeSession` no testkit, que
  cumprem os `Protocol`s da 004 com os value objects dela (`CatalogTool`, `FencedToolResult`); na integração, o
  `CapabilityService` real com o `PackRuntime` real carregando o `ai-generic` (tool `generic.calculate`), MCP vazio e
  auditoria em memória.
- **SC-002 e SC-005**: hypothesis gera roteiros adversariais (tool válida, tool inexistente, ação inválida, resposta,
  falha) e limites de 1 a 6; propriedades: chamadas ao controller ≤ limite, execuções ≤ limite, um único `FinalEvent`,
  resultados acumulados = execuções feitas, decisões no trace = chamadas ao controller (+1 no `limit`).
- **SC-001**: `contract/` e `unit/` continuam sem importar o framework de grafo.
- O grant dos testes passa a ser o `ExecutionGrant` da 003 (R15), montado por uma fábrica do testkit.
- Marca `us2` nos testes novos.

**Rationale**: o R13 (caminho real) vale onde há o que provar entre módulos — a integração; a conformidade e a
propriedade precisam de centenas de execuções rápidas e de controle total do gateway. Simular o controller por um
provider de teste mantém o roteador da 006 real (inclusive o `ModelCall` do papel `controller` no trace).

**Alternatives considered**: estender o `ScriptedProvider` da 006 com roteiro (toca outro módulo por necessidade de
teste); gateway falso também na integração (esconderia o encontro 004 × 005).

### R30 — Checkpoint adiado; roadmap e `design.md` anotados

**Decision** (clarificação 1): nenhuma porta `CheckpointStore`. O roadmap ("Persistência por fase") passa de "memória →
Postgres, 1 → 3" para "quando houver retomada (FR-014)", e o `design.md` recebe uma nota datada nas duas tabelas que
citam a porta, no mesmo padrão das notas de 2026-09-21.

**Rationale**: princípio XIII — porta sem consumidor.

**Alternatives considered**: ver a clarificação 1.

### R31 — Estrutura do adapter: `nodes/` vira pacote; `flows.py` continua arquivo

**Decision**: `adapters/langgraph/nodes.py` vira `nodes/` com `common.py` (canais de stream, `prepare_context`,
`generate`, `validate_answer`) e `agentic.py` (`load_capabilities`, `controller`, `execute_tool`). `flows.py` ganha o
grafo do `agentic` e continua um arquivo; o `AgentState` ganha os campos do loop com reducers (`steps` — cada tool
executada com o pedido e o resultado, ou cada ação inválida com o motivo —, `decisions` e o `errors` que já existia) e o
`AgentContext`, a sessão de tools num compartimento preenchido pelo passo de abertura.

**Rationale**: o plano da Fase 1 previu "viram pastas quando `agentic` e `rag_first` chegarem"; os nós dobram, o
registro de flows ganha só uma função. Tudo isso é interior do adapter (ADR-011).

**Alternatives considered**: `flows/` como pacote já (uma função a mais não justifica; vira pacote com o `rag_first`).

### R32 — Fronteiras de import

**Decision**: contratos novos de import-linter: (1) `ai_core.graph` não importa `ai_core.mcp` (nem o `api.py`) — o
motor só alcança MCP pelo gateway (FR-002); (2) `ai_core.capabilities` e `ai_core.mcp` entram na lista de módulos que
não importam `langgraph`/`langchain_core`. Os contratos "só pelo `api.py`" de 003 e 004 já cobrem o motor.

**Rationale**: FR-002 verificável, como o R12 fez com o framework.

**Alternatives considered**: confiar em revisão.

### R33 — Pendências para outros planos

| Spec | O quê |
|---|---|
| 011 (passada de encaixe) | montar o `ExecutionService` com `capabilities=<CapabilityService>` nos três perfis — até lá, `agentic` não aparece em `flows()` |
| 008 (passada de encaixe) | `finish_reason` por `ExecutionIssue.severity` em vez do `kind` `ValidatorIssue` (R23) |
| 003 (passada de encaixe) | `assistants validate` acusar Assistant `agentic` sem papel `controller`; para isso a 005 pode publicar os papéis por flow como dado (seam aditivo, como os nomes de flow) — decidir na passada da 003 |
| 006 (US2–US5) | US4: `strict` e recusa explícita de provider sem saída estruturada para o papel `controller`; o motor já envia o `response_format` |
| 009 | nada além do toque desta passada (R24) |

---

## Passada de 2026-10-07: validators que filtram o streaming ([ADR-024](../../docs/adr/ADR-024-validators-filtram-o-streaming.md))

### R34 — A geração filtrada e o acréscimo final

- **Decision**: no nó `generate`, `hooks.open_answer_stream(composition, turn_view(state), slices)` antes do stream;
  cada pedaço passa por `feed`, só o liberado vira `TokenEvent`; `finish()` dá a cauda (emitida) e o resultado
  filtrado (`streamed` no estado; `answer` é a resposta filtrada). O nó `validate_answer` passa `streamed` ao
  `validate`; se a resposta final só acrescenta à entregue, o acréscimo sai como token; se não, `ExecutionIssue`
  `notice` `AnswerRewritten`. A resposta parcial de uma falha continua sendo o que saiu — agora já filtrado.
- **Rationale** (ADR-024, princípio XI): streaming desde o primeiro token, sem citação inventada no texto.
- **Alternatives**: desligar o streaming de tokens com validator que reescreve (20 a 60 s sem nada no hardware alvo).

## Fase 5 (US3, US4, flow `rag_first`; ADR-026) — 2026-10-09

> Insumos: as duas clarificações de 2026-10-09 (spec), o [design.md](design.md) ("`rag_first` — retrieval
> determinístico"), ADR-005, ADR-006, ADR-017, ADR-019 e o [ADR-026](../../docs/adr/ADR-026-o-modelo-ve-o-identificador-de-cada-trecho.md).
> Conferido no código: o motor (flows `chat`/`agentic`, nós finos, `validate_answer` com `generation_context`, teto por
> omissão de resultados), o gateway da 004 (exceção de retriever vira resultado `error`/`timeout`; o resultado traz os
> `chunks`; a renderização não mostra o `chunk_id`), o `PackHooks` da 002 (ainda sem o hook de rerank que o design dela
> prevê para a Fase 5) e o pack `scouting` (103: `score` = similaridade densa em `[0, 1]`, comprimida no e5).

### R35 — Escopo da passada e toques fora da 005

**Decision**: `rag_first` (US3) e a validação nele (US4), com o ADR-026. Toques declarados ("passada de encaixe"):
**002** — `PackHooks.reranker(composition, pack)`, o hook que o design.md da 002 prevê para a Fase 5; **004** — o
`· id: <chunk_id>` na renderização de recuperação e `ToolSession.fence_chunks(name, chunks)` (ADR-026, decisão 2);
**009** — o evento aditivo `CoverageGate` (ADR-017); **011** — `RagSettings` pelas variáveis `AI_CORE_RAG_*` e o
`rag_first` em `flows()` quando há gateway. Na 003 nada muda: ela lê os papéis por flow do motor (ADR-019). Ao fim,
a tag do core `v0.2.0` (R48).

**Rationale**: o `rag_first` é o primeiro flow que recupera sem o controller; o resto são as portas que ele usa.

**Alternatives considered**: implementar o rerank fora do Pack Hooks (o motor chamaria pack direto — viola FR-002).

### R36 — Topologia

**Decision** (design.md): `START → prepare_context → retrieve → rerank → gate`, e do portão:

| Rota | Quando |
|---|---|
| `generate` com os trechos | coberto |
| `controller` (loop do `agentic`, nós existentes) | sem cobertura e o grant tem `controller` |
| `generate` sem trechos | sem cobertura e sem `controller` (registra `notice`) |
| fim, sem geração | recuperação falhou (R37) |

`generate → validate_answer → END`, como nos outros flows. As arestas só leem a rota que o nó calculou por
`domain/gate.py`.

**Rationale**: reaproveita os nós do `agentic` e o caminho de geração e validação; a decisão é pura.

**Alternatives considered**: um sub-grafo para o loop escalado (os nós já existem; uma aresta basta).

### R37 — Recuperação pelo gateway (ADR-005)

**Decision**: o nó `retrieve` abre a sessão de tools (como o `load_capabilities`, com os filtros das fatias no
`ToolContext`) e executa **cada tool `retrieval` do catálogo** com `{"query": <pergunta>, "top_k": candidates}`. O
gateway emite o `ToolCall` (009) e repassa os filtros de forma opaca (US3 cen. 4). Resultado com `status` diferente de
`ok` (o retriever levantou, estourou o prazo) vira registro `error` `RetrievalFailed`, nomeando a tool e o motivo, e a
execução termina **sem gerar**: o Assistant depende do índice e fica indisponível com erro explícito, nunca degradado
para "sem resultado" (princípio VII; 103 FR-007). Catálogo sem tool de recuperação = nenhum resultado.

**Rationale**: "retrieval é tool, um único ponto de execução" — trace, prazo, tamanho e filtros vêm de graça.

**Alternatives considered**: chamar os retrievers pelo Pack Toolset direto (dois caminhos de execução); tratar falha como
"sem resultado" (o portão escalaria em silêncio, e a resposta diria que não há documento quando há).

### R38 — Rerank por pack (002 `PackHooks.reranker`)

**Decision**: os chunks agrupam por pack (o prefixo `<pack>.` da tool); com `reranker(composition, pack)`, cada grupo
vai a `rerank(pergunta, chunks, top_k=passages)`; sem reranker, os primeiros `passages` na ordem do retriever. Um pack
só: a lista dele. Vários: junção pelas cabeças dos grupos — a cada passo, a de maior `score` (empate: o pack que vem antes) —, cortada
em `passages` (a premissa da spec); a ordem dentro de cada pack é a do reranker dele, que no scouting vem da fusão e não
do score (anotado na implementação, T066). Reranker
que levanta → `notice` `RerankFailed` e a ordem do retriever: degradação explícita.

**Rationale**: o reranker do scouting depende das marcas que o retriever dele grava (103 R4); rerankear os chunks de
outro pack não faria sentido. A assinatura por pack refina a `reranker(composition)` ilustrativa do design da 002.

**Alternatives considered**: um reranker para a composição inteira (qual, com dois packs?).

### R39 — Portão de cobertura (FR-007; clarificação 1)

**Decision**: função pura `domain/gate.py`: `coberto = há chunks e (sem limiar ou maior score ≥ limiar)`. O score é o
`Chunk.score` (no scouting, a similaridade densa — 103). Sem limiar configurado (o default), só a ausência de resultado
escala. A decisão vira o evento `CoverageGate` (009, aditivo pelo ADR-017): `request_id`, candidatos, trechos, melhor
score, limiar, coberto e rota — sem texto.

**Rationale**: o princípio X proíbe fixar o número; a medida vem da 105.

**Alternatives considered**: limiar default "intuitivo" (o ensaio da 103 mostrou que 0,5 ou 0,7 deixariam passar tudo).

### R40 — Escalada (FR-007a; clarificação 2)

**Decision**: sem cobertura e com `controller` na política de modelos do grant → rota `controller`, com o limite de
iterações do grant (ou 3) e a sessão já aberta pelo `retrieve`; o loop começa com a transcrição vazia (os trechos
recusados pelo portão não entram). Sem `controller` → `generate` sem trechos e `notice` `CoverageInsufficient`.
`flow_roles()["rag_first"] = ("generation",)`. O `controller` declarado num Assistant `rag_first` é resolvido antes do
primeiro evento, como os papéis exigidos (FR-013): papel fora da allowlist é erro de requisição, não falha no meio da
escalada.

**Rationale**: o Assistant escolhe se paga o loop; sem ele, a pergunta sem cobertura cai no caminho "nenhum documento
encontrado" do prompt do pack, sem citar trecho irrelevante.

**Alternatives considered**: exigir `controller` sempre (clarificação 2, B); nunca escalar (C).

### R41 — Como os trechos chegam à geração (ADR-026; princípio VI)

**Decision**: no caminho coberto, o nó `gate` grava um passo de tool sintético por tool de recuperação com trecho
entregue (um por pack no caso comum) — chamada `<pack>.<tool>` com `{"query": <pergunta>}` e resultado
`session.fence_chunks(<tool>, trechos)` —, no mesmo formato nativo de tool do
`agentic` (`assistant` com `tool_calls` + `tool`), com a `FENCE_INSTRUCTION` no sistema. A renderização é a do
ADR-026: `[documento — seção, p. N · id: <chunk_id>]` + texto.

**Rationale**: o conteúdo recuperado é externo e entra cercado e no papel de menor autoridade, como no loop; a
geração e a projeção na Turn View funcionam sem caminho novo.

**Alternatives considered**: um bloco de sistema com os trechos (daria autoridade de sistema a conteúdo externo).

### R42 — Teto de contexto no `rag_first` (FR-011)

**Decision**: função pura `fit_chunks` (em `domain/budget.py`): com teto, tira os trechos de **menor posição** até o
contexto da geração caber; `notice` `ContextTrimmed` com a contagem. Sem teto, vão os `passages`.

**Rationale**: o que vale menos sai primeiro (a regra que o `budget.py` já anuncia para a Fase 5); a omissão por
mensagem inteira apagaria todos os trechos de uma vez.

**Alternatives considered**: cortar o texto de cada trecho (quebraria a citação).

### R43 — Turn View no `rag_first` (US4)

**Decision**: `retrieved` = todos os candidatos; `reranked` = a lista do R38; `generation_context` = os trechos que
couberam (R42) — o que os validators da 104 conferem (US4 cen. 2). No loop escalado, a projeção do `agentic`. O estado
ganha `retrieved` e `reranked`.

**Rationale**: é o que o contrato da Turn View promete e o que a citação mecânica precisa.

**Alternatives considered**: nenhum.

### R44 — Configuração (clarificação 1)

**Decision**: `RagSettings(candidates=20, passages=5, min_score=None)` em `api.py`, validado (`candidates ≥ 1`,
`passages ≥ 1`, `min_score` em `[0, 1]`); a 011 lê `AI_CORE_RAG_CANDIDATES`, `AI_CORE_RAG_PASSAGES` e
`AI_CORE_RAG_MIN_SCORE` (valor inválido impede o boot, nomeando a variável) e o passa ao `ExecutionService`.

**Rationale**: um Assistant `rag_first` hoje; por Assistant entra quando houver o segundo.

**Alternatives considered**: no grant (clarificação 1, B).

### R45 — Progresso (FR-012, SC-004)

**Decision**: eventos de progresso `retrieve`, `rerank` e `gate` (com contagem no detalhe), antes de qualquer espera
longa.

**Rationale**: o primeiro sinal chega antes da geração.

**Alternatives considered**: nenhum.

### R46 — Testes

**Decision**: domínio por tabela (portão, junção, `fit_chunks`); o flow com o gateway falso do testkit (tools de
recuperação programadas) e o Pack Hooks com reranker falso: US3 cen. 1–4, US4 cen. 1–2, SC-003 (uma chamada de modelo
no caminho coberto, contando os `ModelCall`), recuperação que falha (erro, sem geração), sem `controller` (`notice`,
`generation_context` vazio), com `controller` (vai ao loop); 004: a renderização com `· id:` e `fence_chunks`; 002: o
hook por pack, isolado; 011: as variáveis e o `rag_first` em `flows()`; integração no perfil `test` com um pack de
teste que tem retriever.

**Rationale**: os mesmos andaimes do `agentic`.

**Alternatives considered**: nenhum.

### R47 — Fronteiras de import

**Decision**: nada novo: a 005 importa da 002 e da 004 só os `api.py`; `domain/gate.py` e `fit_chunks` são puros.

**Rationale**: princípio XIII.

**Alternatives considered**: nenhum.

### R48 — Release

**Decision**: ao fim da passada, a tag do core `v0.2.0` (core e `ai-generic`) no `agentic-app` (ADR-021); os contratos
não mudam (`0.1.1`). O pack `scouting` (101 US5) e a instalação apontam para ela.

**Rationale**: a 101 precisa do `rag_first` e do ADR-026 numa referência estável.

**Alternatives considered**: apontar para um commit.

### R49 — Desfecho de etapa ([ADR-028](../../docs/adr/ADR-028-o-motor-publica-o-desfecho-de-cada-etapa.md), FR-012a; 2026-10-13)

**Decision**: evento novo `StepFinished(stage, outcome)` no `ExecutionEvent`, escrito pelos nós no canal de stream
(`{"kind": "step", ...}`, traduzido em `runtime.py`) ao fim de cada etapa, inclusive nos caminhos de falha
(`retrieve` que falha, controller que falha). Desfechos tipados em `api.py`, montados por funções puras de
`domain/steps.py`. O modelo vem de `BoundModel.ref` e os tokens do `usage` do último pedaço do stream (ou da resposta do
controller) — sem mudança na 006. O motor não mede tempo: quem consome mede entre o `ProgressEvent` e o `StepFinished`.

**Rationale**: o pedido do mantenedor de uma timeline com chamadas, retornos e decisões no Open WebUI (008 FR-005a); o
que faltava estava no estado do grafo ou só no trace.

**Alternatives considered**: texto mais rico no `detail` do `ProgressEvent`; mapeamento livre de fatos; ler o trace em
tempo real (todas no ADR-028).


### R50 — Robustez do loop com modelos pequenos (FR-006b, FR-006c, FR-012b; 2026-10-22)

**Decision**: quatro políticas puras em `domain/`, sem mudança de seam.
1. *Data de referência* (`transcript.date_instruction`): a `reference_time` da execução no fuso da instalação,
   com dia da semana, no sistema do controller e da geração quando o loop correu (`agentic` ou `rag_first` escalado).
   O fuso entra no `ExecutionService(timezone=…)`, vindo de `AXON_TIMEZONE` (011, default `UTC`).
2. *Ação repetida* (`transcript.repeats`): nome e argumentos canônicos iguais aos de um `ToolStep` não sintético →
   geração, com `RepeatedAction`. O desfecho e a decisão no trace seguem `tool` (foi o que o modelo pediu); o motivo
   está no `notice`, sem valor novo no `ControllerDecision` da 009.
3. *Marcação de tool no texto* (`markup.ToolMarkupFilter`): filtro de streaming antes do filtro dos validators;
   segura só o fim que ainda pode ser começo de `<tool_call>`. Bloco sem fechamento é descartado até o fim.
4. *Resposta vazia* (`outcome.EMPTY_ANSWER`): aplicada depois dos validators, para o `non_empty_answer` do
   `axon-generic` continuar reprovando; o aviso sai como token e vira a resposta final.

**Rationale**: traces de 2026-10-22 com o MCP do mango e `z-ai/glm-5.3-flash`: `inicio: 2023-10-01` por falta de data,
três `listar_transacoes` iguais até o limite, `<tool_call>mango.grafico…` entregue ao usuário (e reaproveitado no
histórico pelos turnos seguintes) e uma geração de 560 tokens de saída com conteúdo vazio (provável raciocínio sem
texto).

**Alternatives considered**: subir o limite de iterações (só adia a repetição); filtrar a marcação no adapter do
provider (é sintoma do modelo, mas aparece em mais de um provider e o filtro é puro); erro `error` para resposta
vazia (viraria 502 sem streaming por algo que o usuário pode simplesmente perguntar de novo).

### R51 — Imagens no motor (ADR-044, itens 4, 5 e 8; FR-019 a FR-023)

**Decision**: políticas puras em `domain/images.py` — `candidates` (imagens da última mensagem do assistente antes da
pergunta), `user_images`, `unique` (ordem da primeira ocorrência), `image_plan` (a tabela do item 8: candidatas só com
`vision` na geração; no `agentic`, decisão do controller; no `chat`/`rag_first` com `controller`, etapa `image_gate`;
sem `controller`, todas já escolhidas), `user_content` (a última mensagem do usuário ao modelo: texto e marcas, ou
partes com as imagens do usuário e cada candidata escolhida precedida de `[imagem <id> mostrada ao usuário]`),
`gate_format`/`parse_gate` e `IMAGE_TOKENS` = 1.000. `actions.py` ganha o ramo `view_image` (o `id` em `enum` das
candidatas) e `ViewImageAction`; id fora das candidatas é `InvalidAction` (`UNKNOWN_IMAGE`). `transcript.py` ganha
`ViewStep` (no controller, o aviso "A imagem <id> foi marcada para a resposta."; na geração, nada), `repeats_view`,
`gate_messages` e o `IMAGES_INSTRUCTION` na geração quando algum passo trouxe imagem. `budget.py` soma
`IMAGE_TOKENS` por parte `image_url`. `request.py`: só imagem vale como pergunta (a marca), `ensure_vision` recusa
imagem sem `vision` na geração, `OPTIONAL_ROLES["chat"] = ("controller",)` e `roles_to_resolve` só resolve o
`controller` do `chat` com a etapa de imagem. O serviço calcula o `ImagePlan` e o leva no `ExecutionPlan`. No adapter,
o estado ganha `gate_images` e os acumuladores `viewed` e `attachments`; o `execute_tool` emite os `AttachmentEvent`
novos depois do `finished`; o `controller` trata `view_image` (desfecho `ControllerOutcome(action="view_image",
image=…)`, decisão `view_image` com `images`); o `load_capabilities` chama o controller com catálogo vazio se há
candidata; a etapa `image_gate` (`nodes/images.py`) vem depois do `prepare_context` no `chat` e depois do `gate` no
`rag_first` (rotas `generate` e `fallback`), com `ControllerDecision(iteration=1, action="view_image")` e
`ImageGateOutcome`. Na API, `AttachmentEvent`, `ImageGateOutcome`, `FinalEvent.attachments` e a ação `view_image` no
`ControllerOutcome`. A timeline da 008 ganhou as linhas do desfecho novo e do estágio `image_gate`, para continuar
total (008 R60).

**Rationale** ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md)): o plano é decidido antes do primeiro evento, como os papéis (FR-013), e é o que deixa o `chat`
sem imagem idêntico ao da Fase 1 — sem etapa nova e sem resolver o `controller`. As candidatas vêm só da última
mensagem do assistente, mesmo que o cliente mande mais: a 008 já descarta os bytes das outras, e o motor não depende
disso. O custo fixo por imagem é o que o ADR pede; nenhuma regra de omissão tira uma imagem, porque quem a pôs ali foi
a pergunta.

**Alternatives considered**: `view_image` como tool do catálogo (o ADR a recusa: a imagem não é capacidade de nenhum
servidor); etapa `image_gate` também no loop (o controller já está decidindo ali, e uma chamada a mais por turno não
acrescenta); resolver o `controller` do `chat` sempre que declarado (mudaria o `chat` de quem nunca manda imagem e
falharia Assistants que declaram um controller não usado).

### R52 — O motor diz que a plataforma mostra as imagens das tools (FR-019, FR-019a; 2026-10-27)

**Decision**: duas frases fixas do core, sem domínio. (1) O `CONTROLLER_INSTRUCTION` diz que as imagens que as tools
devolvem são mostradas ao usuário junto da resposta e que, se ele pede gráfico, imagem ou figura — ou pergunta por uma
que uma tool devolveu — e há tool que a produza, o controller a chama em vez de descrevê-la ou desenhá-la em texto. (2)
Numa execução com tools (`agentic`, ou `rag_first` que escalou) em que nenhuma tool devolveu imagem neste turno, a
geração recebe `IMAGES_CAPABILITY` (`graph/domain/images.py`): a plataforma mostra as imagens que as tools devolvem, o
modelo não diz que só produz texto e, se o usuário quer uma imagem que não chegou, oferece buscá-la. Com imagem de tool
no turno, segue valendo só o `IMAGES_INSTRUCTION` (R51). `generation_messages` ganha `tools: bool`; o `generate` passa
`looped`.

**Rationale**: na trace de uma conversa real do Assistant `geral` (Mango por MCP), nenhum turno chamou a tool que gera
PNG, e a geração afirmou "minha saída é só texto": o aviso do R51 só existia depois de a imagem nascer, então nem o
controller nem o modelo sabiam da capacidade. Reproduzido com o `glm-5.3-flash` e um MCP no formato do Mango (histórico
da trace, 3 rodadas por cenário): "por que você não exibe imagens?" negou a capacidade em 3/3 antes e em 0/3 depois; "pode
gerar" chamou a tool em 1/3 antes e 3/3 depois. No Open WebUI v0.12 a imagem renderiza e a pergunta passou a ser
respondida corretamente. Texto de prompt, sem seam novo: sem ADR.

**Alternatives considered**: pôr a nota na geração de todo flow (o `chat` não tem tool; a frase seria falsa); listar o
catálogo na geração para ela decidir (mais tokens por turno, e quem decide chamar tool é o controller); frase no prompt
do pack `generic` (o prompt do pack é neutro quanto ao flow, 010 FR-008, e o `scouting` e outros packs ficariam sem ela).

### R53 — Gráficos no motor (ADR-052, item 2; FR-024)

**Decision**: `ChartEvent(chart, tool)` e `FinalEvent.charts: tuple[Chart, ...] = ()` no seam (`graph/api.py`; o
`ExecutionEvent` ganha o tipo). No `execute_tool` do loop, depois das imagens, cada gráfico de `result.charts` que a
execução ainda não emitiu vai ao stream (`{"kind": "chart"}`) e ao acumulador `charts` do estado; o runtime o traduz em
`ChartEvent`, e o `final_event` (e o evento final de uma execução que falhou) leva os gráficos na ordem, sem repetir
`id` (`domain/images.unique_charts`). O `rag_first` só executa tools pelo loop quando escala, então o mesmo nó cobre
os dois flows. Texto: o `CONTROLLER_INSTRUCTION` fala de "imagens e gráficos"; `CHARTS_INSTRUCTION`
(`graph/domain/images.py`) entra no sistema da geração quando algum passo de tool tem gráfico.

**Rationale** (ADR-052: "a 005 publica `ChartEvent` e `FinalEvent.charts`; o modelo não recebe os dados"): o mesmo
caminho das imagens (R51), sem nó novo. A frase da geração vem do aprendizado do R52 — sem ela, o modelo pequeno diz
que só produz texto ou redesenha os dados em tabela, o que repetiria a tabela que a 008 já põe na resposta.

**Alternatives considered**: o gráfico como `AttachmentEvent` de outro tipo (o anexo é imagem para o `view_image`, a
etapa `image_gate` e o teto de contexto); mandar os dados à geração para ela comentar (o resultado da tool de origem,
um MCP por exemplo, já está na transcrição; repetir custaria tokens); frase no prompt do pack `generic` (o prompt é
neutro quanto ao flow, 010 FR-008).

### R54 — A geração sabe que as ferramentas acabaram e que o limite foi atingido (FR-006b; produção, 2026-10-29)

**Decision**: duas frases fixas do core em `graph/domain/transcript.py`, ambas no sistema da geração:
- `NO_TOOLS_INSTRUCTION`, sempre que a geração vem do loop (`tools=True` em `generation_messages`);
- `LIMIT_INSTRUCTION`, quando o loop foi cortado pelo limite (`truncated=True`).

O `generate` passa `truncated` quando algum registro tem `kind == ITERATION_LIMIT`. Essa constante agora fica em
`graph/domain/limits.py`, usada também pelo nó que registra o corte.

**Rationale**: no Langfuse de produção, duas conversas do `geral` pediram um gráfico de rosca dos gastos do mês. O
controller gastou as 3 iterações padrão buscando dados num MCP paginado, e o loop foi para a geração sem chamar
`generic.chart`. A geração, sem ferramentas e sem saber disso, escreveu `<tool_call>renderizar_grafico…` (uma tool
inventada) e, na outra conversa, `<tool_call>mango.listar_transacoes…`. O `ToolMarkupFilter` (R50) cortou a marcação,
a resposta ficou vazia e saiu o `EMPTY_ANSWER`. As frases tratam a causa na geração. O limite do Assistant é
configuração da instalação: o `geral` do `axon-cfblabs` passou a declarar `max_iterations: 8`.

**Alternatives considered**:
- **Reservar uma iteração final do controller para "terminar".** Mudaria a tabela de rotas do FR-006 sem saber se
  falta algo.
- **Orientar o controller a preferir resumos a paginar.** Recusado pelo mantenedor: a escolha da fonte é do
  controller.
- **Subir o `DEFAULT_MAX_ITERATIONS`.** O padrão é decisão da clarificação 3 de 2026-10-01, e o Assistant declara o
  que precisa.

### R55 — A geração recebe os passos do loop em texto (FR-006b; produção, 2026-10-29)

**Decision**: na geração, cada passo de tool do loop vira uma mensagem `user` em texto (`_generation_transcript`):
`Resultado da ferramenta <nome>, chamada com <argumentos>:` e o resultado cercado. O passo sintético do `rag_first`
(os trechos do portão) segue no formato nativo, como antes. O controller não muda: ele continua recebendo o formato
nativo, porque é ele quem chama ferramentas. O corte por teto (`trim_results`) reconhece as duas formas
(`is_tool_result`); no texto, mantém a linha do cabeçalho e troca o resto pela marca de omissão.

**Rationale**: com a rc10, a geração já sabia que as ferramentas tinham acabado (R54), e ainda assim o glm-5.3-flash
escreveu `<tool_call>generic.chart…</tool_call>` como texto numa conversa longa. O controller tinha feito um gráfico de
barras quando o usuário pediu rosca, e a geração tentou consertar chamando a tool. A causa é o formato: no nativo
(`assistant` com `tool_calls` e a mensagem `tool`), a geração vê uma conversa de chamadas de ferramenta e continua o
padrão. Em texto, ela lê resultados. O `rag_first` coberto não muda: o passo dele é sintético, e o `fact_recall` do
scouting foi medido com o formato nativo.

**Alternatives considered**:
- **Repetir a geração quando o filtro esvazia a resposta.** Custa uma chamada a mais e trata o sintoma; o mantenedor
  escolheu só o texto.
- **Mandar as tools com `tool_choice: none`.** Nem todo provider da 006 aceita.
- **Texto também no passo sintético.** Mexeria nos números do eval do scouting sem medição.
