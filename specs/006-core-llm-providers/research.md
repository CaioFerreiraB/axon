# Research — 006 LLM Providers (Fase 1, US1)

> Decisões pré-aprovadas vêm do [design.md](design.md) e dos ADRs citados na *Module Boundary*; não são re-pesquisadas.
> As cinco clarificações de 2026-09-18 estão na spec e aparecem aqui como R1, R4, R5, R7 e R8.

## R1 — De onde vem a política de modelos na Fase 1

**Decision**: o roteador é construído com um value object **Model Policy** (`ModelPolicy`: modelo por papel + allowlist)
publicado no `api.py` deste módulo. Na Fase 1 a composition root (011) o monta a partir da configuração do operador; a
partir da Fase 2 ~~é a própria 006 que o deriva do Execution Grant (003)~~ — superado pelo [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md): é a 003 que o monta,
dentro do grant, e a seta passa a 003 → 006. O seam não muda.

**Rationale** (clarificação de 2026-09-18; ADR-008; princípio XIII): o grafo de `specs/README.md` tem a seta `006 → 003`,
não a inversa — se a 003 construísse o value object, ela passaria a importar o `api.py` da 006 e a direção do seam
mudaria, o que exigiria ADR. Com a política como entrada do roteador, a 006 continua sem conhecer a 003 na Fase 1, o
`domain/` fica puro e testável, e o seam não muda quando o grant chegar: só muda quem monta a política.

**Alternatives considered**: porta de configuração dentro da 006 (o roteador leria a política sozinho — criaria um
segundo caminho quando o grant chegasse e colocaria configuração de operador dentro de um módulo de runtime);
antecipar o tipo Execution Grant da 003 (acopla a Fase 1 a uma spec ainda não planejada).

## R2 — Forma do seam: dois passos, `for_execution` e depois `for_role`

**Decision**: o seam **Model Router** tem dois Protocols em `api.py`:

```python
class ModelRouting(Protocol):        # montado uma vez, no boot (011)
    def for_execution(self, *, policy: ModelPolicy, request_id: str) -> ModelRouter: ...
    async def check(self, policy: ModelPolicy) -> tuple[ModelHealth, ...]: ...

class ModelRouter(Protocol):         # um por execução
    def for_role(self, role: ModelRole) -> BoundModel: ...
```

**Rationale**: `design.md` fixa `for_role(papel) → cliente de modelo` — assinatura preservada literalmente. O que o
design não diz é onde entram a política e o identificador de requisição, que são **por execução**, enquanto os
providers e o Trace Sink são **por processo**. Amarrar os dois numa única chamada (`for_role(role, policy, request_id)`)
obrigaria a 005 a repetir os mesmos dois argumentos em cada papel de cada iteração, com risco de passar o
`request_id` errado. Com `for_execution`, a ligação acontece uma vez por execução e o `ModelRouter` fica com exatamente
a assinatura pré-aprovada. Não é seam novo: é a fábrica do seam, no mesmo `api.py`.

**Alternatives considered**: `for_role` com tudo por argumento (repetição e risco de erro na 005); roteador por execução
instanciado pela 011 a cada requisição (obrigaria a composition root a participar do caminho quente, contra 011 FR
"nenhum adapter é instanciado durante a execução").

## R3 — `BoundModel` publica `complete()` e `stream()`, não os overloads do contrato

**Decision**: `BoundModel` é um `Protocol` em `api.py` com `role`, `ref`, `async complete(...) -> ChatResponse` e
`stream(...) -> AsyncIterator[ChatChunk]`. O modelo já está ligado — quem chama não passa `model`.

**Rationale**: o contrato `LLMProvider` (001) usa `stream: Literal[True|False]` com `@overload` porque é a forma que os
adapters implementam; para quem consome (a 005), dois métodos nomeados eliminam o `await` que devolve um iterador — a
parte mais fácil de errar do contrato. O `BoundModel` também é onde a instrumentação mora (R7), e separar os métodos
deixa medição de streaming e de resposta única independentes. O contrato 001 continua intacto: é ele que os adapters
implementam.

**Alternatives considered**: devolver o `LLMProvider` cru mais o nome do modelo (deixaria a allowlist e o trace por
conta de quem chama — SC-002 e o elo 6 dependeriam de disciplina).

## R4 — Adapter do Ollama pelo SDK oficial da OpenAI

**Decision**: `openai>=3.15,<4` como dependência da distribuição `ai-core`; `AsyncOpenAI(base_url=".../v1",
api_key=<sentinela>)` contra a camada compatível do Ollama. O SDK só aparece em `ai_core/llm/adapters/`.

**Rationale** (clarificação de 2026-09-18; `design.md`, seção "Ollama e o hardware alvo"): o design já escolheu a camada
compatível em `:11434/v1` justamente para que os três adapters fiquem quase idênticos; com o SDK, streaming (incluindo
`stream_options.include_usage`), tool calls e `response_format` vêm prontos e testados, e OpenAI e OpenRouter (Fase 3)
passam a ser diferença de `base_url`, credencial e cabeçalhos. Verificado na versão instalada: `AsyncOpenAI` aceita
`base_url`, `timeout`, `max_retries` e `http_client`, o que cobre R5 e R10.

**Alternatives considered**: `httpx` puro com parser de SSE próprio (reimplementaria streaming, tool calls e uso de
tokens três vezes, e o parser seria código nosso no caminho quente); API nativa do Ollama em `/api` (contraria o
`design.md` e afasta os adapters remotos).

## R5 — Timeouts: conexão curta e inatividade entre pedaços, sem teto total

**Decision**: cada provider recebe `connect_seconds` (default 5 s) e `idle_seconds` (default 120 s), traduzidos para o
timeout do cliente HTTP como `connect` e `read`; nenhum teto de tempo total; `max_retries=0`.

**Rationale** (clarificação de 2026-09-18; `design.md`: 5–15 tok/s em CPU ARM): no hardware alvo uma resposta legítima
leva minutos, então um teto total cortaria geração saudável. O `read` do cliente HTTP é, em streaming, exatamente o
tempo sem pedaço novo — é o sinal que distingue "modelo pensando devagar" de "stream travado". `max_retries=0` mantém a
falha explícita e a latência previsível (FR-007 proíbe fallback automático; repetição silenciosa da mesma chamada tem o
mesmo defeito de esconder o erro e dobrar o tempo).

**Alternatives considered**: teto único por chamada (corta geração longa legítima); nenhum timeout, delegando ao
orçamento do motor (a 005 só ganha orçamento na Fase 3 — a Fase 1 ficaria sem proteção nenhuma).

## R6 — Erros do módulo em `api.py`, mapeados no adapter

**Decision**: hierarquia publicada em `api.py` — `ModelRoutingError` (base), `RoleNotConfigured`, `ModelNotAllowed`,
`UnknownProvider` e `ModelCallFailed`. O adapter traduz os erros do SDK: `APIConnectionError`/`APITimeoutError` →
`ModelCallFailed` com o motivo, `APIStatusError` → `ModelCallFailed` com código e corpo truncado. Toda mensagem nomeia
provider e modelo.

**Rationale**: US1 cenário 2 e FR-010 exigem erro que nomeie provider e modelo; se o erro do SDK vazasse, a 005 e a 008
teriam de conhecer `openai` para tratá-lo — infraestrutura atravessando um seam (princípio XIII). Os erros ficam em
`api.py` porque são parte do que o seam promete.

**Alternatives considered**: deixar o erro do SDK subir (acopla consumidores ao SDK); erro único sem hierarquia
(impede a 008 distinguir erro de configuração — 4xx — de indisponibilidade do provider — 502/503 — na Fase 2).

## R7 — Quem emite o trace é o cliente devolvido pelo roteador

**Decision**: a implementação de `BoundModel` mede a chamada e emite `ModelCall` (009) com papel, provider, modelo,
duração, tokens e `finish_reason`, tanto no sucesso quanto na falha (`finish_reason="error"`). O tempo até o primeiro
token **não** entra na Fase 1.

**Rationale** (clarificação de 2026-09-18; ADR-013): com a medição dentro do objeto que faz a chamada, SC-002 ("100% das
chamadas rastreáveis") vale por construção — nenhum consumidor precisa lembrar de medir. O evento `ModelCall` da 009 já
carrega exatamente esses campos; acrescentar `ttft_ms` agora exigiria editar a spec 009 fora da fase dela, enquanto a
US6 (Fase 3) o acrescenta como campo aditivo, que é mudança sem custo de seam (009 R1). Em streaming, a emissão acontece
quando o iterador termina ou é interrompido, para que a duração seja a da geração inteira.

**Alternatives considered**: a 005 medir e emitir (espalha a instrumentação por quem chama e deixa tools de fora do
mesmo padrão); não emitir nada na Fase 1 (o trace da 009 nasceria cego para o único emissor que existe na fase).

## R8 — Saúde: porta `ModelProvider` = contrato 001 + sondagem

**Decision**: `ports.py` declara `ModelProvider(LLMProvider, Protocol)`, acrescentando `async probe(model) ->
ProbeResult`. `ModelRouting.check(policy)` sonda o provider de cada papel configurado e devolve um `ModelHealth` por
papel. O adapter do Ollama sonda listando os modelos da camada compatível e conferindo se o modelo declarado está lá.
A verificação é sob demanda e nunca participa do boot.

**Rationale** (clarificação de 2026-09-18; FR-009 e o edge case do modelo ausente): o contrato `LLMProvider` (001) tem
só `chat`, e acrescentar saúde a ele mudaria um seam de outra spec — logo, a exigência extra é deste módulo e vira porta
secundária dele. Sondar é mais barato e mais informativo que uma chamada de verdade: distingue "provider fora do ar" de
"provider no ar, modelo não baixado". Fora do boot porque a plataforma precisa subir em máquina sem Ollama (011 US3, e o
princípio VII manda falhar fechado onde a falha importa — na chamada e na consulta de saúde, não na inicialização).

**Alternatives considered**: acrescentar `health()` ao contrato 001 (muda seam de outra spec por conveniência desta);
saúde por chamada real de geração (custa tokens e segundos a cada checagem); etapa bloqueante de boot (impediria a
suíte ponta a ponta e o desenvolvimento sem Ollama).

## R9 — A allowlist é aplicada já na Fase 1

**Decision**: `ModelPolicy.allow` é conferida em toda resolução desde a Fase 1, mesmo a US5 sendo Fase 3. Allowlist
vazia significa "sem restrição declarada" e é registrada como tal.

**Rationale**: o value object nasce agora (R1) com o campo; um campo de segurança declarado e não aplicado é pior que
sua ausência — dá falsa garantia e viola o princípio VII (falha fechada) e o IV (a fronteira é o Assistant). O código é
uma função pura de casamento de padrão. O que fica para a Fase 3 é o resto da US5: modelo escolhido na requisição, que
depende de 003 e 008.

**Alternatives considered**: campo sem efeito até a Fase 3 (falsa garantia); omitir o campo do value object até lá
(mudaria a forma da política entre fases, justo o que R1 evita).

## R10 — Testes sem rede: transporte falso injetado no cliente do SDK

**Decision**: os testes do adapter constroem `AsyncOpenAI(http_client=...)` com um transporte de teste que responde com
respostas gravadas (inclusive um corpo SSE de streaming e uma resposta de erro), e um teste de inatividade com um
transporte que para de entregar pedaços. Nenhum teste da suíte padrão fala com rede.

**Rationale**: a biblioteca HTTP usada pelo SDK oferece transporte falso de primeira classe, e injetá-lo exercita o
adapter inteiro — tradução de mensagens, parsing de streaming, uso de tokens, mapeamento de erro — sem mock do SDK.
Testar contra um Ollama de verdade continua possível e fica marcado como integração opcional ([quickstart.md](quickstart.md)).

**Alternatives considered**: `monkeypatch` no método do SDK (testaria a nossa chamada, não a tradução); servidor HTTP
local em fixture (mais lento e mais frágil, sem ganho — o transporte falso já exercita o mesmo caminho).

## R11 — O provider simulado nasce na Fase 1

**Decision**: `adapters/fake.py` entrega um provider roteirizado (respostas e pedaços programados, erros programados),
publicado para uso da 011 no perfil de teste e do próprio módulo nos testes de serviço.

**Rationale**: `design.md` o lista entre os adapters, e a 011 US3 (Fase 1) exige a plataforma inteira em memória com
"um provider de modelo simulado". Ele também é o segundo adapter da suíte de conformidade da porta `ModelProvider`, que
o princípio XIII exige rodar contra o adapter em memória e contra o real.

**Alternatives considered**: cada suíte com o próprio duplo (a 011 e a 005 escreveriam o seu, sem conformidade comum).

## R12 — `ModelRef` divide no primeiro `/`

**Decision**: `ModelRef.parse("openrouter/qwen/qwen3-8b")` → provider `openrouter`, modelo `qwen/qwen3-8b`. Padrões da
allowlist são casados com `fnmatch` sobre o texto `provider/modelo`.

**Rationale**: nomes de modelo do OpenRouter contêm barra (o próprio `design.md` usa `openrouter/qwen/qwen3-8b`);
dividir em todas as barras quebraria a Fase 3 com dados que já estão escritos no design. `fnmatch` cobre `ollama/*` e
`openrouter/qwen/*` sem inventar linguagem de padrão.

**Alternatives considered**: separador próprio (`:`) — conflita com a tag do Ollama (`qwen3:1.7b`); casar por prefixo
simples (não expressa `*/qwen3*`).

## R13 — Contratos de import-linter novos

**Decision**: acrescentar ao `ai-core/pyproject.toml` os contratos de camada do módulo (`api.py` não importa o resto;
`domain/` não importa portas, service nem adapters; `service.py` não importa adapters), mais um contrato que proíbe
`openai` e `httpx2` em `api.py`, `domain/`, `ports.py` e `service.py`, e a atualização do contrato que impede o trace de
importar outros módulos do core (`ai_core.llm` entra na lista de proibidos para `ai_core.observability`).

**Rationale**: é o padrão já aplicado a `ai_core.packs` e `ai_core.observability`; o contrato sobre o SDK torna
executável a regra do princípio XIII que a clarificação R4 assume ("o SDK só aparece em `adapters/`").

**Alternatives considered**: confiar em revisão (o CI é o único lugar onde a regra não se esquece).

## R14 — Escopo da fase

**Decision**: a Fase 1 entrega a US1 inteira mais FR-003 (allowlist, R9), FR-009 (saúde sob demanda, R8) e FR-010
(timeouts, R5), que nascem com o seam. Ficam para a Fase 3, com os adapters remotos: US2 (papéis múltiplos com providers
diferentes), US3 (rejeição de roteamento automático na validação do Assistant), US4 (restrição de formato de saída
obrigatória no controller) e US6 (tempo até o primeiro token e métricas por papel).

**Rationale**: `docs/roadmap.md` lista `006 · US1` na Fase 1 e `006 · US2–US5` na Fase 3. As três exigências que
antecipamos são propriedades do objeto que está sendo criado agora, não histórias independentes: adiá-las significaria
publicar um seam com campo sem efeito (R9), sem como diagnosticar (R8) ou capaz de travar para sempre (R5).

**Alternatives considered**: entregar só o caminho feliz da US1 (deixaria o módulo sem diagnóstico e sem proteção de
travamento justamente na fase em que o modelo local é a única peça nova).

---

# Fase 3 (2026-10-02): US2–US5 — providers remotos, roteamento automático e saída estruturada

> As três clarificações de 2026-10-02 aparecem aqui como R16 (roteamento automático), R21 (credencial) e R17–R19
> (saída estruturada). Insumos: [design.md](design.md) (porta `SecretResolver`, `openai.py` e `openrouter.py`),
> ADR-008, ADR-012, ADR-013, ADR-016.

## R15 — Escopo da passada

**Decision**: US3 (OpenAI e OpenRouter; roteamento automático recusado), US4 (restrição de formato obrigatória no
`controller`, em três camadas) e FR-011 (credencial ausente), com código; US2 (papéis em providers diferentes) e US5
(allowlist no modelo default e no escolhido pela requisição) como **prova**: o código da Fase 1 e da 003 já as cumpre, e
o que falta são os testes com dois providers e o cenário literal. Toque declarado na 011: a porta de segredos e os
providers remotos nos perfis (R23). **Fora**: US6 (tempo até o primeiro token e métricas por papel, P3), outros
providers, URL base configurável dos remotos e cabeçalhos de atribuição do OpenRouter (R20).

**Rationale**: `docs/roadmap.md` lista `006 · US2–US5` na Fase 3; a US6 é P3 e não bloqueia o controller remoto, que é o
que a Fase 3 precisa.

**Alternatives considered**: incluir a US6 (o campo `ttft_ms` é aditivo na 009 e pode chegar sozinho depois, sem tocar
nada desta passada).

## R16 — Roteamento automático recusado na construção do `ModelRef` (FR-004)

**Decision**: invariante no próprio `ModelRef` (`api.py`): com `provider == "openrouter"`, o modelo cuja base — em
minúsculas, antes do primeiro `:` — é `auto` ou começa com `openrouter/` levanta `ValueError` com a mensagem
`"'<ref>' é roteamento automático, que escolhe o modelo sozinho: declare um modelo explícito (autor/modelo)"`. A forma
curta `auto` cobre o `openrouter/auto` como a US3 o escreve (que `ModelRef.parse` lê como provider `openrouter`, modelo
`auto`); o namespace `openrouter/…` cobre o `openrouter/openrouter/auto` e qualquer roteador futuro. Sufixos de variante
do próprio modelo (`:free`, `:nitro`, `:floor`) passam. A regra fica no `api.py` porque é invariante do value object, e o
`api.py` não importa `domain/` (Fase 1, R3).

**Rationale** (clarificação 1): toda referência a modelo passa pelo `ModelRef` — declaração do Assistant (003, YAML e
corpo da API), modelo escolhido na requisição (003, `select_models`) e saúde (011) —, então uma regra só cobre os três
caminhos, e a allowlist (`openrouter/*`) não consegue liberá-la. **Não é mudança de seam**: a assinatura não muda, e a
nota da Fase 1 para a 003 já anunciava que "a validação de Assistant (roteamento automático, FR-004) usa o mesmo value
object". Os consumidores já tratam o `ValueError`: o YAML da 003 relata `models.<papel>: <motivo>`, a requisição vira
`RequestRejected(field="model")` (400) e o corpo de Assistant da 008, `InvalidRequest(field="models.<papel>")` (400).
Consequência aceita: um Assistant de usuário gravado no Postgres antes da regra com um desses modelos deixaria de ser
lido. Não há dados de produção antes da Fase 3, então não há migração.

**Alternatives considered**: lista fechada de identificadores exatos (recusada na clarificação: não alcança roteador
novo); regra só na validação da 003 (a escolha por requisição passaria pela allowlist, e a 003 conheceria regra da 006);
exigir a forma `autor/modelo` de todo modelo do OpenRouter (mais estrito que o pedido; um id malformado já falha
explicitamente na primeira chamada).

## R17 — Guarda do papel `controller` no roteador (FR-005, camada 1)

**Decision**: regra pura em `domain/output.py` — `constraint_problem(role, response_format) -> str | None`: para o papel
`controller`, `response_format` precisa ser um mapeamento com `type == "json_schema"` e `json_schema.schema` mapeamento;
`None`, `json_object` ou esquema ausente devolvem o motivo. `TracedModel.complete` e `.stream` a aplicam **dentro** do
bloco instrumentado, antes do provider: a recusa levanta `ModelCallFailed(provider, model, reason)` e emite o `ModelCall`
com `finish_reason="error"` — toda invocação do cliente vira exatamente um registro (SC-002), inclusive a recusada.

**Rationale** (clarificação 3; SC-003 "0 chamadas de controller sem restrição", por construção e não por disciplina da
005): o nó do controller da 005 já captura `ModelCallFailed` (falha do controller segue para a geração) e a 008 já o
traduz; um tipo novo de erro seria mudança de seam (ADR) para um caso que só acontece por erro de programação.
`json_object` não é "esquema de ação" (US4): sem esquema, nada garante a forma.

**Alternatives considered**: erro novo `StructuredOutputRequired` (ADR, e a 005 teria de capturá-lo); guarda na 005
(SC-003 dependeria de quem chama); não registrar a recusa no trace (a chamada pedida sumiria do diagnóstico).

## R18 — A forma mais rígida de cada provider (FR-005, camada 2)

**Decision**: `OpenAICompatProvider._payload`, com `response_format` do tipo `json_schema`, envia uma cópia com
`json_schema.strict = True` — sempre, mesmo que quem chama tenha mandado `False`. Vale para os três providers: o
OpenAI só garante o esquema em modo estrito; o OpenRouter repassa `strict` ao upstream; o Ollama ignora o campo e
restringe por gramática. O `OpenRouterProvider` acrescenta `extra_body={"provider": {"require_parameters": True}}`
**quando há `response_format`**, para o OpenRouter só encaminhar a upstream que suporte a restrição.

**Rationale** (clarificação 3): "nunca degrada para texto livre" vale por provider; o adapter é o único lugar que
conhece a forma rígida de cada um. `require_parameters` só com `response_format` porque ele também exclui upstream que
não declara parâmetros acessórios que enviamos (como `stream_options`), sem ganho para o resto das chamadas.

**Alternatives considered**: `strict` só nos remotos (duas regras para a mesma garantia); `require_parameters` sempre
(reduz upstreams sem motivo); reescrever o esquema para caber no modo estrito da OpenAI (recusada na clarificação: muda
a forma dos argumentos).

## R19 — Recusa do provider vira erro explícito, sem reenvio (FR-005, camada 3)

**Decision**: nenhum código novo de mapeamento: `APIStatusError` já vira `ModelCallFailed` com o código e o corpo
truncado (Fase 1, R6), e `max_retries=0` já impede repetição. Os casos que a Fase 3 passa a exercitar são o 400 da OpenAI
para esquema fora do modo estrito (por exemplo, `anyOf` na raiz) e o 404 do OpenRouter "No endpoints found that can
handle the requested parameters". Nenhum caminho do módulo refaz a chamada sem a restrição.

**Rationale**: o corpo do provider explica o motivo melhor que qualquer pré-checagem; adivinhar as regras de esquema
de cada provider duplicaria regra externa que muda sem aviso. **Consequência registrada para a 005**: com o esquema
atual (`anyOf` na raiz), OpenAI como controller do `agentic` falha explicitamente até a 005 publicar um esquema de raiz
objeto; Ollama e OpenRouter funcionam (nota em Seam Notes).

**Alternatives considered**: pré-checar a compatibilidade do esquema no adapter da OpenAI (regra externa duplicada);
reenviar sem `strict` (é a degradação que a FR-005 proíbe).

## R20 — OpenAI e OpenRouter como arquivos finos sobre a camada compatível

**Decision**: `adapters/remote.py` — `RemoteProvider(OpenAICompatProvider)`, a parte comum dos remotos: recebe
`secrets: SecretResolver` e o nome da credencial, resolve na construção, guarda a falta (R21) e limpa o valor da chave
de qualquer motivo de erro. `adapters/openai.py` — `OpenAIProvider` (`name="openai"`, `https://api.openai.com/v1`,
credencial `AI_CORE_OPENAI_API_KEY`); `adapters/openrouter.py` — `OpenRouterProvider` (`name="openrouter"`,
`https://openrouter.ai/api/v1`, credencial `AI_CORE_OPENROUTER_API_KEY`, `require_parameters` do R18 e a sondagem por
variante do R22). Prazos com os defaults da Fase 1 (conexão 5 s, inatividade 120 s), por construtor (FR-010). URL base
fixa (o construtor aceita outra só para teste) e nenhum cabeçalho de atribuição.

**Rationale** (design.md; Fase 1, R4): a camada compatível já é a parte comum dos três; cada remoto muda endereço,
credencial e um detalhe de corpo. URL base configurável e cabeçalhos de atribuição não têm consumidor nesta fase
(princípio XII), e uma URL configurável receberia a credencial de qualquer destino.

**Alternatives considered**: um provider "compatível genérico" configurado pelo operador (URL e variável livres —
credencial enviável a qualquer endpoint, fora do design); `RemoteProvider` dentro do `openai_compat.py` (misturaria
credencial no adapter do Ollama, que não tem).

## R21 — Credencial pela porta `SecretResolver` (FR-011)

**Decision**: `ports.py` ganha `SecretResolver` (`resolve(name: str) -> str | None`), a porta do design.md. Adapters em
`adapters/secrets.py`: `EnvSecretResolver(environ=None)` lê exatamente a variável pedida (vazia ou só espaços = ausente)
e `InMemorySecretResolver(values)`. Os únicos nomes resolvidos são as duas constantes dos adapters remotos — nenhum nome
vem de entrada. A resolução acontece **uma vez, na construção** (boot); trocar a credencial é reiniciar. Sem
credencial, o provider é registrado assim mesmo: o cliente do SDK nasce com uma sentinela e nunca é usado; `chat`
levanta `ModelCallFailed(reason="sem credencial: defina AI_CORE_…")` antes de qualquer acesso à rede; `probe` devolve
`available=False` com o mesmo motivo. O valor da chave nunca entra em mensagem: o motivo de erro passa por uma troca do
valor por `***` (o 401 da OpenAI ecoa a chave mascarada; a troca é defesa adicional à 009). Como chave e URL base vão
sempre explícitas ao SDK, as leituras implícitas dele (`OPENAI_API_KEY`, `OPENAI_BASE_URL`) nunca acontecem.

**Rationale** (clarificação 2; FR-009 — saúde não bloqueia o boot): mesmo tratamento que a 011 dá à credencial MCP
ausente (degrada, nomeia a variável, não derruba). Resolver por chamada não ganha nada com o ambiente, que não muda
dentro do processo (princípio XII). A relação com a FR-009 e o caso de borda de segredo ausente da 011 está
decidida no [ADR-020](../../docs/adr/ADR-020-segredos-uma-fonte-por-perfil-uma-porta-por-modulo.md): uma fonte de
segredos por perfil (o ambiente), uma porta por módulo com a regra de nomes dele — o prefixo `AI_CORE_MCP_SECRET_` da
007 é controle de segurança (007 R7) e não serve aos nomes fixos da 006 — e credencial ausente degrada, sem derrubar o
boot.

**Alternatives considered**: a 011 ler as chaves no `Settings` e passar o valor (descarta a porta do design.md — exigiria
ADR); reaproveitar o adapter da 007 (a variável viraria `AI_CORE_MCP_SECRET_OPENAI_API_KEY`, contra a clarificação);
não registrar o provider sem credencial (recusada na clarificação: "provider desconhecido" esconde a causa).

## R22 — Sondagem dos remotos

**Decision**: a mesma `models.list()` da camada compatível, depois da checagem de credencial. No OpenRouter, o modelo
está disponível se o id está na lista **ou** se a base antes do último `:` está (variantes como `:nitro` e `:floor` não
aparecem como id; `:free` aparece). A lista de disponíveis no `detail` passa a ser truncada nos 20 primeiros ids, com
`(+N)` — o OpenRouter lista centenas; listas curtas, como a de um Ollama, não mudam. Chave inválida → `available=False`
com o 401 (já limpo, R21). Nada gera tokens.

**Rationale**: FR-009 (saúde sob demanda, sem custo de geração); o item `model:<provider/modelo>` da saúde agregada
precisa caber numa linha legível.

**Alternatives considered**: `models.retrieve(id)` (uma chamada por modelo, e o OpenRouter não a oferece para variantes);
uma geração de 1 token (custo e cota a cada consulta de saúde).

## R23 — Encaixe na 011 (toque declarado)

**Decision**: `REQUIRED_PORTS` ganha `llm_secrets`, **antes** de `providers` (a fábrica de providers a enxerga). `memory`
e `persistent`: `llm_secrets` = `EnvSecretResolver()` da 006, e `providers` = `ollama` + `openai` + `openrouter` (os
remotos com `parts["llm_secrets"]`). `test`: `llm_secrets` = `InMemorySecretResolver()` vazio, providers inalterados
(só o simulado `ollama`; as suítes trocam a porta `providers` quando precisam de outros nomes). A saúde agregada não
muda: os itens `model:<provider/modelo>` dos modelos declarados já mostram "sem credencial". O contrato
`profiles.md` da 011 ganha a linha da porta nova. `llm_secrets` pode ser trocada (não é de armazenamento).

**Rationale** (clarificação 2): a composition root escolhe o adapter; a ordem da lista de portas é o mecanismo que a
011 já usa para dependências entre fábricas.

**Alternatives considered**: registrar os remotos só com credencial (recusada na clarificação); o perfil `test`
registrar remotos simulados (as suítes já trocam `providers`, e o perfil continuaria sem efeito para quem não troca).

## R24 — US2 e US5: prova, não código

**Decision**: US2 — no seam, dois providers simulados (`openrouter` no `controller`, `ollama` no `generation`) e cada
`BoundModel` ligado ao seu, com um `ModelCall` por papel no provider certo; na 011, uma conversa `agentic` com
`controller: openrouter/qwen/qwen3-8b` e `generation: ollama/qwen3:1.7b` (providers trocados por simulados) deixa no trace
a chamada de controller no `openrouter` e a de geração no `ollama`. US5 — o cenário literal (`allow: ["ollama/*"]`, papel
em `openai/…` → `ModelNotAllowed`) na conformidade do seam, e o modelo escolhido na requisição fora da allowlist (400)
pela API — cada um só se a cobertura existente não o tiver (conferir antes de escrever).

**Rationale**: a resolução por papel e a allowlist existem desde a Fase 1 (R9) e a escolha por requisição desde a 003
(Fase 2); o que a Fase 3 precisa é a prova com providers diferentes.

**Alternatives considered**: reescrever a resolução (nada a mudar).

## R25 — Testes

**Decision**: `unit/` — regra do `ModelRef` (formas de roteamento automático, maiúsculas, variantes aceitas, outros
providers inalterados), `constraint_problem`, adapters de segredo. `contract/` — conformidade da porta `SecretResolver`
(ambiente × memória); a conformidade da porta `ModelProvider` passa a rodar também contra `OpenAIProvider` e
`OpenRouterProvider` com transporte HTTP falso (Fase 1, R10), mais os casos próprios: `strict` forçado,
`require_parameters` só com formato, credencial ausente (o transporte não recebe nada), recusa 400 → `ModelCallFailed`
com uma única requisição, sondagem por variante e chave limpa da mensagem; o seam ganha a guarda do controller (recusa
com `ModelCall` de erro, sem tocar o provider) e a prova da US2. `integration/` — opcional, pulada sem
`AI_CORE_OPENROUTER_API_KEY`/`AI_CORE_OPENAI_API_KEY`: o *Independent Test* da US4 (controller com esquema de ação →
resposta parseável) contra o provider real; custa chamada paga, então nunca roda por default. Marcas: `us2` a `us5`
existentes, com a descrição da 006 acrescentada.

**Rationale**: mesmo padrão da Fase 1 — rede só na integração opcional, transporte falso no resto.

**Alternatives considered**: gravar respostas reais (cassetes) para a suíte padrão (envelhecem com a API dos providers e
guardariam corpos com dados de conta).

## R26 — import-linter

**Decision**: nenhum contrato novo. Os arquivos novos de SDK (`remote.py`, `openai.py`, `openrouter.py`) ficam em
`adapters/`, onde o contrato existente já permite `openai` e `httpx2`; `domain/output.py` e a porta nova são puros e
caem nos contratos de camada que já existem. A 011 já importa `ai_core.llm.adapters`.

**Rationale**: o contrato da Fase 1 (R13) foi escrito por camada, não por arquivo.

**Alternatives considered**: contrato por arquivo de provider (sem ganho; a camada é a fronteira que importa).

---

# Passada de 2026-10-07: subconjunto estrito da OpenAI (ADR-023)

Insumos: [ADR-023](../../docs/adr/ADR-023-adapter-da-openai-converte-para-o-subconjunto-estrito.md); as regras do modo
estrito na documentação da OpenAI (Structured Outputs, "Supported schemas": raiz objeto, sem `anyOf` na raiz; todo campo
em `required`, opcional emulado com `null`; `additionalProperties: false` em todo objeto; sem `allOf`, `not`,
`dependentRequired`, `if/then/else`; até 10 níveis e 5000 propriedades); o esquema de ação da 005
(`graph/domain/actions.py`, que já tira `pattern` e troca `$ref` por objeto livre).

## R27 — Regra de conversão (pura)

**Decision**: `llm/domain/strict.py`, `to_strict(schema) -> StrictPlan` (o esquema de envio e um anotado, para a volta):
em todo nó, `oneOf` → `anyOf`; anotações `default`, `examples`, `title`, `$comment`, `deprecated`, `readOnly`,
`writeOnly` saem; objeto com `properties` ganha `additionalProperties: false` e todo nome em `required`, e cada
propriedade que não estava em `required` vira anulável — `type` ganha `"null"` (e `enum`, `null`), `const` e esquema sem
`type` com `anyOf` ganham o ramo `{"type": "null"}`. Raiz que não é objeto é embrulhada em `value` (com `$defs` na nova
raiz). Recusa (`StrictSchemaError`, com o caminho JSON do ponto): objeto sem `properties`, `additionalProperties`
diferente de `false`, `allOf`, `not`, `if`/`then`/`else`, `dependentRequired`, `dependentSchemas`, `patternProperties`,
`unevaluatedProperties`, `unevaluatedItems`, `propertyNames`, `minProperties`, `maxProperties`, e nó sem `type`, `enum`,
`const`, `anyOf` nem `$ref`.

**Rationale** (ADR-023): é a emulação de opcional que a própria OpenAI documenta; recusar cedo o que não tem equivalente
dá erro com caminho, em vez de um 400 genérico.

**Alternatives considered**: deixar o provider recusar (a R19 — sem conversão, a OpenAI nunca serve de controller).

## R28 — Conversão inversa

**Decision**: `from_strict(value, plan)`: desembrulha `value` quando houve embrulho; percorre o valor junto do esquema
anotado — em `anyOf`, escolhe o primeiro ramo cujo conjunto de chaves é exatamente o do valor e cujos `const`/`enum`
casam; em objeto, remove a chave com `null` que a conversão tornou anulável (o `null` que o original admitia fica); em
`array`, percorre os itens; `$ref` local (`#/$defs/…`) é resolvido. Conteúdo que não é JSON volta como veio (a 005 o lê
como ação inválida).

**Rationale**: o core recebe a forma do esquema original — a objeção da R19 deixa de valer.

## R29 — Onde se aplica

**Decision**: `RemoteProvider` ganha `_needs_strict_subset(model) -> bool` (default `False`); `OpenAIProvider` → sempre;
`OpenRouterProvider` → modelo começando por `openai/`. Com `response_format` de esquema e o subconjunto exigido, o
adapter converte antes de montar o corpo (erro → `ModelCallFailed` antes da rede) e desfaz no conteúdo da resposta; com
streaming, junta os pedaços, desfaz e entrega o conteúdo num pedaço só, antes do final (só o controller usa formato, e
ele não usa streaming). O `strict: true` (R18) e o `require_parameters` do OpenRouter continuam.

Na mesma condição, os nomes de função (tools e `tool_calls` da transcrição) que não casam com `^[a-zA-Z0-9_-]{1,64}$`
viram apelidos (`llm/domain/names.py`: prefixo legível e 8 hexadecimais do sha256) na ida e voltam ao nome original nas
`tool_calls` da resposta; nó com `const`/`enum` sem `type` ganha o `type` inferido do valor. O gancho do adapter é
`_follows_openai_rules(model)`. Ambas as regras apareceram no teste real com `openai/gpt-4.1-nano` via OpenRouter.

**Rationale** (ADR-023): só onde a regra é exigida — outros providers aceitam esquemas que o subconjunto recusaria.

## R30 — Testes

**Decision**: `tests/llm/unit/test_llm_strict.py` (tabela de conversão, recusas com caminho, inversa, e a propriedade
"o valor desfeito valida contra o esquema original" com `jsonschema`, inclusive para o esquema de ação da 005 com uma
tool de parâmetro opcional); em `tests/llm/contract/test_remote_providers.py`, o corpo enviado pela OpenAI e pelo
OpenRouter `openai/…` (raiz objeto, tudo em `required`), o conteúdo devolvido na forma original, a recusa antes da rede
e o OpenRouter com outro autor sem conversão; integração paga opcional com o `agentic` real (010) num modelo
`openai/…` hospedado pela OpenAI via OpenRouter.

## R31 — Nenhum toque fora da 006

**Decision**: a 005 não muda; a pendência "esquema de ação de raiz objeto" sai do roadmap e do CLAUDE.md.
