# Research — 006 LLM Providers (Fase 1, US1)

> Decisões pré-aprovadas vêm do [design.md](design.md) e dos ADRs citados na *Module Boundary*; não são re-pesquisadas.
> As cinco clarificações de 2026-09-18 estão na spec e aparecem aqui como R1, R4, R5, R7 e R8.

## R1 — De onde vem a política de modelos na Fase 1

**Decision**: o roteador é construído com um value object **Model Policy** (`ModelPolicy`: modelo por papel + allowlist)
publicado no `api.py` deste módulo. Na Fase 1 a composition root (011) o monta a partir da configuração do operador; a
partir da Fase 2 é a própria 006 que o deriva do Execution Grant (003).

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
