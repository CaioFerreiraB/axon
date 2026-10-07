# Research — 002 Pack Runtime

**Data**: 2026-09-15 · **Plano**: [plan.md](plan.md) · **Spec**: [spec.md](spec.md)

Decisões do [design.md](design.md) e dos ADRs 003, 009, 011 e 012 entram como pré-aprovadas (R-A*). As demais (R*) refinam o
que o design deixou em aberto, à luz das clarificações de 2026-09-15 e do contrato 001 já implementado
(`ai-core-contracts` 0.1.0).

## Decisões herdadas (pré-aprovadas)

### R-A1 — Code pack é extensão do operador, por entry point

- **Decision**: packs de código são distribuições Python descobertas pelo grupo de entry points `ai_core.packs`; não existe
  instalação de pack em runtime (FR-001, FR-014).
- **Rationale (ADR-003)**: usuário final nunca executa código no processo do core; quem precisa de código próprio sem ser
  operador escreve um MCP server.
- **Alternatives**: endpoint de admin que instala pack de git em runtime — rejeitado no ADR-003.

### R-A2 — Instalação por imagem com build-arg e `packs check` no build

- **Decision**: o repositório de instalação recebe a lista de packs por build-arg e roda `ai-core packs check` no build
  (US5, Fase 4).
- **Rationale (ADR-009)**: instalação imutável; incompatibilidade falha o build, não a produção.
- **Alternatives**: venv gravável em runtime — rejeitado no ADR-009.

### R-A3 — Turn View recortada por pack; o hook devolve a própria fatia

- **Decision**: o motor produz a projeção da execução; o Pack Hooks entrega a cada pack uma Turn View só com a própria
  fatia e as de `depends_on`, e mescla o retorno de `prepare_context` apenas na fatia do pack (FR-009).
- **Rationale (ADR-011)**: packs não enxergam o estado interno do motor; reescrever o grafo não quebra packs.
- **Alternatives**: estado bruto nos hooks — rejeitado no ADR-011.

### R-A4 — Módulo hexagonal com duas portas secundárias

- **Decision**: `ai_core/packs/` com `api.py` (seams Pack Registry e Pack Hooks), `domain/` (regras puras), `ports.py`
  (`PackSource`, `PackConfigSource`), `service.py` e `adapters/`; cada porta com adapter em memória e suíte de
  conformidade.
- **Rationale (ADR-012, design.md "Portas e adapters")**: descoberta e configuração são I/O e têm troca prevista
  (entry points → + declarativo; YAML → outras fontes).
- **Alternatives**: n/a.

## Decisões deste plano

### R1 — Escopo por fase

- **Decision** (clarificação 2026-09-15): **Fase 1** = US1 (descoberta e carga), US2 (falha fechada) e US3 cenários 2–4
  (Pack Hooks de execução: prompts, `prepare`, `validate`, erro de hook). **Fase 2** = US4 (CLI `packs list | check`).
  **Fase 3** = US3 cenário 1 (catálogo com namespace, para a 004). **Fase 4** = US5 (template de instalação). **P3** =
  US6 (pack declarativo). No seam Pack Hooks, `reranker` e `routine` entram com seus consumidores (Fase 5 e US5 da 001),
  com as assinaturas do design.md.
- **Rationale**: cada parte do seam chega junto do consumidor (princípio XII); a 005 US1 precisa só de prompts,
  preparação de contexto e validators.
- **Alternatives**: US3 inteira na Fase 1; Pack Hooks provisório na 005 — rejeitadas na clarificação.

### R2 — A distribuição `ai-core` nasce com esta spec

- **Decision**: a 002 é o primeiro módulo do core e cria `ai-core/packages/core/` (distribuição `ai-core`, versão
  `0.1.0`, `requires-python = ">=3.14"`, backend `uv_build`), com `ai_core/__init__.py` e o módulo `ai_core/packs/`.
  Dependências de runtime: `ai-core-contracts` (fonte do workspace), `pyyaml` (só no adapter de configuração) e
  `jsonschema` (validação de configuração). O script `ai-core` e a raiz do CLI ficam para a 011.
- **Rationale**: o workspace já prevê `packages/*`; `ai-core` e `ai-generic` compartilham a linha de versão (ADR-004).
- **Alternatives**: esperar a 011 criar o esqueleto (bloquearia a 002, que a 011 consome).

### R3 — Python 3.14 no core e consequência para os testes de piso dos contratos

- **Decision**: o core declara `requires-python = ">=3.14"` (imagem, research R2 da 001). Como o `requires-python` de um
  uv workspace é a interseção dos membros, o workspace passa a exigir 3.14; os testes dos contratos em 3.12 e 3.13 saem
  do workspace e rodam num ambiente isolado (`uv run --no-project --python 3.12 --with ./packages/contracts --with pytest
  ...`). O workflow `contracts.yml` e o quickstart da 001 são ajustados na mesma entrega.
- **Rationale**: o core só roda na imagem (3.14); declarar 3.12 prometeria suporte não testado. O piso 3.12 continua
  valendo — e testado — para `ai-core-contracts`, que é o que packs externos instalam.
- **Alternatives**: core com `>=3.12` (sem mexer no CI dos contratos, mas com suporte declarado e não verificado).

### R4 — Forma dos seams (`api.py`)

- **Decision**:
  - `PackRegistry`: `entries()`, `entry(name)` e `compose(pack_names) -> Composition`; `compose` valida a lista (pack
    conhecido, `enabled`, sem repetição, dependências presentes e antes do dependente) e levanta `CompositionError`
    nomeando os packs (FR-008, US2 cenário 3).
  - `PackHooks` (Fase 1): `system_prompts(composition)`, `async prepare(composition, view, slices)` e
    `async validate(composition, view, slices)`. O motor passa a Turn View base e o mapeamento `slices` (fatia de cada
    pack); o Pack Hooks recorta a view por pack. *Refinamento* de `state_projection` do design.md, que não tinha tipo.
  - Erros de execução levantam `PackHookError(pack, hook, message)` (FR-011).
  - Value objects: `PackEntry`, `PackStatus`, `PackCapabilities`, `RetrieverCapability`, `Composition`,
    `ValidationOutcome`, `ValidatorRun` — só stdlib e `ai_core_contracts`.
- **Rationale**: a 003 valida Assistants chamando `compose`; a 005 consome a composição sem conhecer packs individuais;
  a 008 lista entradas.
- **Alternatives**: `Composition` com os objetos de pack dentro (vazaria instâncias para a 005); validação de
  composição só na 003 (a regra de dependência é da 002).

### R5 — Algoritmo de carga e estados

- **Decision**: o carregamento (uma vez, no boot — FR-003) segue:
  1. `PackSource.discover()` lista entradas (nome do entry point, distribuição, versão, função que importa a classe);
  2. nomes repetidos → todas as entradas com o nome ficam `error`;
  3. para **todo** pack instalado: importar a classe (falha → `error`), ler `name` e `contract_version` da classe (FR-017),
     exigir `name` = nome do entry point e checar `check_compatibility(contract_version)` (FR-002). Isso vale também para
     packs desabilitados, porque o `packs check` do build (US4/US5) cobre tudo que está instalado;
  4. pack não habilitado → `disabled` (sem instanciar);
  5. pack habilitado → instanciar sem argumentos, `manifest()`, validar a configuração contra `config_schema` (R6),
     chamar os hooks de catálogo uma vez com o `PackContext` (001 FR-019) e aplicar `check_declaration`;
  6. regras de dependência (R9) até ponto fixo;
  7. pack citado na configuração mas não instalado → entrada `error: não instalado`.
  Qualquer exceção numa etapa vira `error` com a causa; o boot segue (FR-005, SC-002). Cada falha é registrada em log
  (R11).
- **Rationale**: US1, US2 e os edge cases; importar para ler a classe é inevitável (FR-017, texto corrigido na
  spec).
- **Alternatives**: ler `contract_version` só de metadados da distribuição (não existe campo padrão); instanciar para ler
  (executaria o construtor de pack incompatível — rejeitada na clarificação).

### R6 — Configuração do operador (`packs.yaml`)

- **Decision**: a 002 é dona do **formato** (`packs: {<nome>: {enabled: bool, config: mapping}}`, chaves desconhecidas
  rejeitadas) e do adapter `YamlPackConfigSource(path)`; a 011 decide o caminho e liga o adapter pelo perfil. A validação
  da configuração de cada pack usa `jsonschema` com o dialeto indicado em `$schema` (padrão: Draft 2020-12), sem
  resolução de `$ref` remoto; a mensagem de erro nomeia o caminho do campo (US1 cenário 3). Pack sem `config_schema`
  recebe a configuração como está.
- **Rationale**: o design da 002 põe `config_yaml.py` no módulo e o da 011 põe os caminhos em `settings.py` — os dois se
  encaixam assim. `jsonschema` é validação pura (sem I/O com refs locais) e aponta o caminho do erro.
- **Alternatives**: a 011 ler o arquivo e repassar um mapeamento (a 002 perderia a validação do próprio formato);
  validação estrutural própria (não nomearia o campo com precisão).

### R7 — Fatias e preparação de contexto

- **Decision**: `prepare` roda os packs na ordem da composição; cada um recebe a Turn View recortada
  (`own_slice` = fatia atual do pack; `dependency_slices` = fatias atuais das dependências, já atualizadas nesta
  execução, porque dependências vêm antes — clarificação); o retorno precisa ser mapeamento JSON (senão
  `PackHookError`) e entra por **merge raso** na fatia do pack (001 data-model). `prepare` devolve o novo mapeamento de
  fatias da composição; o motor guarda.
- **Rationale**: FR-008, FR-009 e FR-011; fatia JSON é o que permite checkpoint (Fase 3).
- **Alternatives**: substituir a fatia inteira (perderia chaves de turnos anteriores sem o pack pedir); aceitar
  valores não-JSON em runtime (quebraria o checkpoint depois).

### R8 — Encadeamento de validators

- **Decision**: `validate` roda os validators de cada pack, na ordem da composição e na ordem declarada pelo pack; cada
  um recebe a Turn View recortada com `answer` e `citations` já atualizados pelos anteriores (quando um resultado traz
  `answer` ou `citations`). O `ValidationOutcome` final traz resposta, citações, união das `flags`, `ok` (todos
  aprovaram) e a lista de execuções. Exceção em validator → `PackHookError` (edge case: sem entrega sem validação).
- **Rationale**: 001 data-model ("citações correntes após validators anteriores") e 104 (o aviso de vigência considera
  só citações válidas).
- **Alternatives**: validators em paralelo sobre a mesma entrada (quebraria a dependência entre eles).

### R9 — Grafo de dependências

- **Decision**: depois da carga individual, função pura em `domain/` marca `error` todo pack cujo `depends_on` cite pack
  não instalado, desabilitado ou em erro, repetindo até ponto fixo (falha em cascata), e todo pack em ciclo (mensagem
  mostra o ciclo, ex.: `a → b → a`).
- **Rationale**: FR-010 como clarificado.
- **Alternatives**: checar só no `compose` (erro chegaria tarde, na hora de usar o Assistant).

### R10 — Composição

- **Decision**: `compose(pack_names)` recusa com `CompositionError`: nome desconhecido, pack `disabled` ou `error`
  (mensagem inclui o erro do pack — US2 cenário 3), nome repetido, dependência ausente da lista ou depois do dependente
  (nomeia os dois — FR-008). O Pack Hooks revalida a composição recebida (operação barata) para não confiar em
  `Composition` construída à mão.
- **Rationale**: a regra de ordem é da 002; a 003 a usa ao validar Assistants (Fase 2) sem reimplementar.
- **Alternatives**: token privado em `Composition` (acoplamento desnecessário).

### R11 — Log

- **Decision**: `logging` da stdlib com logger `ai_core.packs`; cada pack em `error` gera um registro com nome, etapa e
  causa. Handlers e formato são da composition root (011). Não é porta secundária.
- **Rationale**: não há troca prevista nem não-determinismo; dados de execução por requisição vão pelo Trace Sink (009),
  que a 002 não consome.
- **Alternatives**: porta `Logger` própria (indireção sem troca prevista — princípio XIII, "porta só onde se paga").

### R12 — Estratégia de testes

- **Decision**:
  - `domain/`: testes unitários puros (identidade, grafo de dependências, ordem de composição, recorte de view, merge,
    encadeamento de validators);
  - portas: suíte de conformidade de `PackSource` rodando contra o adapter em memória e contra `EntryPointPackSource`
    (distribuições falsas criadas em `tmp_path` com `*.dist-info/entry_points.txt` no `sys.path`); suíte de
    `PackConfigSource` contra o adapter em memória e o YAML;
  - seams: suítes de conformidade de `PackRegistry` e `PackHooks` contra o `service` com adapters em memória;
  - matriz de falhas injetadas (SC-002): incompatível, manifest inválido, exceção no construtor, exceção em hook de
    catálogo, config inválida, nome divergente, nome duplicado, dependência quebrada, ciclo;
  - packs de teste escritos com `PackBase` e validados antes pela conformidade da 001.
- **Rationale**: princípio XIII (porta = adapter em memória + conformidade contra o real) e governança da constituição.
- **Alternatives**: instalar distribuições reais num venv por teste (lento); depender da 010 (ainda não existe).

### R13 — Fronteiras de import

- **Decision**: novos contratos no import-linter: `ai_core_contracts` não importa `ai_core`; no módulo `ai_core.packs`,
  `api` não importa o resto do módulo, `domain` não importa `ports`/`service`/`adapters`, `service` não importa
  `adapters`, e `api`/`domain`/`ports`/`service` não importam `yaml`. A regra "outro módulo só importa `api.py`" entra
  quando existir o segundo módulo do core. O `ai_core.packs` importa só a API pública de `ai_core_contracts`.
- **Rationale**: princípios II e XIII; 001 R20 previa acrescentar os contratos do `ai_core` quando ele existisse.
- **Alternatives**: n/a.

### R14 — CI

- **Decision**: `.github/workflows/core.yml` (lint, tipos, testes 3.14, import-linter), disparado por mudanças em
  `ai-core/packages/core/**`, nos contratos, na raiz do workspace e no `uv.lock`; mypy estrito e ruff passam a cobrir
  `packages/core`.
- **Rationale**: mesmo padrão do `contracts.yml`.
- **Alternatives**: um workflow único para o workspace (misturaria as regras do FR-020, que valem só para os contratos).

## Decisões da Fase 2 (US4) — 2026-09-30

Clarificação da Fase 2 sem perguntas: o que `packs check` verifica já está em R5 (todo pack instalado, inclusive os
desabilitados) e na FR-003 (valida a configuração nova antes do restart). As decisões abaixo são de plano.

### R15 — Os comandos são funções sobre o Pack Registry já carregado

- **Decision**: `adapters/cli.py` oferece `list_command(registry, out)`, `check_command(registry, out)` e
  `config_error_command(error, err)`. Recebem o `PackRegistry` que a composition root montou e carregou com os mesmos
  adapters do servidor (entry points + `packs.yaml`), sem abrir a API. Quem os registra na raiz `ai-core` é a 011 (US4);
  a introspecção na superfície privada é a 008 (US5), a partir de `PackRegistry.entries()`.
- **Rationale** (design.md, "Linha de comando": "os subcomandos `packs` moram em `adapters/cli.py` deste módulo; a raiz
  `ai-core` que os registra é da spec 011"; 011 FR-010, FR-011): o comando e o servidor não podem divergir sobre o mesmo
  pack, então os dois leem o mesmo registry, carregado pela mesma rotina (R5). Sem parser aqui: o framework de linha de
  comando é decisão da 011 — o mesmo arranjo da 003 (research R14 dela).
- **Alternatives**: o comando montar o próprio `PackRuntime` (duplicaria a escolha de adapters, que é da composition
  root); ler os entry points direto, sem a carga (o `check` do build aprovaria o que o boot recusa).

### R16 — O que reprova o `packs check` e com que código

- **Decision**: qualquer entrada do registry com `status == error` — pack instalado incompatível (mesmo desabilitado),
  identidade divergente, falha de import ou de instanciação, configuração que não conforma ao schema, dependência
  indisponível ou circular, pack citado e não instalado — sai com **1**, nomeando pack e causa. `packs.yaml` malformado
  (`PackConfigError`, que para o boot) sai com **2**. Tudo certo, **0**. `packs list` sai com 0 mesmo com packs em erro —
  listar não é validar —, e com 2 para `packs.yaml` malformado.
- **Rationale** (US4 cen. 2, FR-012, R5, R-A2): o `check` roda no build da imagem (US5, Fase 4) e precisa reprovar
  exatamente o que o boot marcaria como erro. Os códigos são os do `assistants validate` da 003 — 0 disponível, 1
  indisponível, 2 configuração —, para que um script de build trate os dois comandos do mesmo jeito.
- **Alternatives**: reprovar só packs habilitados (um pack instalado e incompatível passaria no build e quebraria no dia
  em que alguém o habilitasse); um código só para qualquer falha (o build não distinguiria arquivo quebrado de pack
  quebrado).

### R17 — Saída em texto, uma linha por pack

- **Decision**: uma linha por entrada, na ordem de `entries()` (por nome): nome, versão, versão de contrato, status e,
  quando em erro, a mensagem. `check` termina com um resumo (`N de M packs em erro`, ou `M packs ok`). Campo ausente
  (pack não instalado não tem versão) aparece como `-`. Sem saída estruturada nesta fase.
- **Rationale** (US4 cen. 1; princípio XII): é o que o operador lê no terminal e no log do build. A interface
  estruturada é a introspecção HTTP da 008, que já devolve JSON; uma segunda, sem consumidor, seria complexidade sem
  caso de uso.
- **Alternatives**: `--json` (sem consumidor hoje; entra de forma aditiva se o build precisar).

## Decisões da Fase 3 (US3 cenário 1) — 2026-10-01

Insumos: a US3 cenário 1 e a FR-007 desta spec; o plano da 004 (research R2 dela), que declarou como porta a forma que
exige deste módulo (`PackToolSource.toolset(composition)`) e a conformidade dela (`test_pack_tool_source.py`).

### R18 — Um seam novo, `PackToolset`, com o tipo publicado aqui

**Decision**: `api.py` publica `PackTool` (`name` com namespace, `pack`, `spec: ToolSpec` com o nome local, `retriever:
NamedRetriever | None`) e o `Protocol` `PackToolset` com `toolset(composition) -> Sequence[PackTool]`, que o
`PackRuntime` implementa. Não entra no `PackRegistry`: os registries falsos das suítes de outros módulos (003) deixariam
de cumprir a forma, e catálogo de tools é outra pergunta que "quais packs existem".

**Rationale** (ADR-012: o seam pertence a quem o implementa; 004 R2): a 004 declarou a forma provisoriamente, como a 003
fez com a 007. Com o implementador existindo, o tipo passa a morar com ele, e a 004 o reexporta (R20).

**Alternatives considered**: método novo no `PackRegistry` (quebra a forma para quem já a cumpre); a 002 devolver um tipo
da 004 (seta invertida: a 004 consome a 002).

### R19 — O que o `toolset` devolve, e em que ordem

**Decision**: para cada pack da composição, na ordem dela (revalidada como no Pack Hooks, R10): primeiro as tools nativas
na ordem que o pack as declarou, depois os retrievers na ordem declarada, cada retriever como a tool de recuperação do
contrato (`retrieval_tool_spec`). O nome é `<pack>.<nome local>` (FR-007). Sem I/O: o catálogo de cada pack é coletado
uma vez, na carga (001 FR-019). Nome repetido dentro de um pack não chega aqui — a conformidade da 001 já recusa tool
repetida e retriever com nome de tool.

**Rationale** (FR-007; ADR-005: retrieval é tool): determinístico, e quem filtra por coleção, `allowed_tools` e escrita
é a 004 — este módulo não conhece Assistants.

**Alternatives considered**: devolver só as nativas e deixar a 004 derivar os retrievers (duas fontes para o mesmo
namespace).

### R20 — O toque na 004

**Decision**: `ai_core/capabilities/domain/records.py` passa a reexportar `PackTool` de `ai_core.packs.api`, e a suíte
de conformidade da porta (`tests/capabilities/contract/test_pack_tool_source.py`) roda também contra o `PackRuntime`.
Nada mais muda na 004.

**Rationale** (004 plan, "Seam Notes": "a 002 satisfaz `PackToolSource` estruturalmente"): é a troca prevista, e a
mesma suíte prova as duas implementações.

**Alternatives considered**: um adaptador na composition root convertendo um tipo no outro (dois tipos para o mesmo
dado, e a conformidade da 004 não rodaria contra o real).

## Decisões da Fase 4 (US5) — 2026-10-07

Insumos: ADR-009, [ADR-021](../../docs/adr/ADR-021-workspace-ai-core-permanece-no-repositorio-da-plataforma.md),
[ADR-022](../../docs/adr/ADR-022-instalacao-constroi-o-core-num-estagio-proprio.md) e as quatro clarificações de
2026-10-07. Verificado no código: `ai-core packs check` só precisa de `AI_CORE_PACKS_FILE`, sai com 1 para pack em erro
(inclusive instalado e desabilitado) e reprova `contract_version` incompatível com os contratos instalados (R16).

### R21 — O repositório de instalação

- **Decision**: `CaioFerreiraB/agentic-deploy`, privado, submódulo `agentic-deploy/` no `agentic-app`. Conteúdo:
  `Dockerfile`, `docker-compose.yml`, `config/` (`packs.yaml`, `assistants.yaml`), `.env.example` (segredos ficam em
  `.env`, fora do git), `packages/incompatible-pack/` (pack de teste da US5 cen. 2), `scripts/check-build.sh` (o
  *Independent Test*), `.github/workflows/build.yml` e `README.md`.
- **Rationale** (ADR-009, clarificação 1): instalação imutável e reproduzível, separada do core e dos packs; o
  submódulo mantém os caminhos que as specs citam.
- **Alternatives**: o template dentro do `agentic-app` (misturaria instalação do operador com o produto).

### R22 — Os estágios do Dockerfile

- **Decision** (ADR-022): `python:3.14-slim` em todos os estágios. `core`: instala `git` e `openssh-client`, copia o
  `uv` de `ghcr.io/astral-sh/uv:0.12.23`, clona a tag `CORE_REF` (build-arg, default `v0.1.0`) do `agentic-app` — raso
  e **sem submódulos**: o `agentic-app` liga os packs como submódulos, e a identidade `core` só lê ele (o `uv`, ao
  instalar por URL de git, clonaria os submódulos e falharia na CI) — e instala `ai-core-contracts`, `ai-core` e
  `ai-generic` das pastas locais em `/opt/ai-core`. `packs`: sobre o `core`, copia
  `config/packs.yaml` para `/etc/ai-core/packs.yaml`, instala `PACKS` (build-arg) e roda `ai-core packs check`.
  `runtime`: copia `/opt/ai-core` e `/etc/ai-core/packs.yaml`, remove `pip` e `ensurepip` da base, cria o usuário
  `ai-core` (uid 10001, sem home gravável), define `AI_CORE_HOST=0.0.0.0` e os caminhos de configuração, e roda
  `ai-core serve` como esse usuário.
- **Rationale**: o ambiente virtual vai inteiro de um estágio para o outro (mesma base, mesmo caminho do Python); o que
  só o build usa (`uv`, `git`, SSH) não chega ao runtime.
- **Alternatives**: `uv sync` de um projeto da instalação (um `pyproject.toml` e um lock a mais só para listar o que o
  build-arg já lista).

### R23 — Credenciais no build

- **Decision**: montagens SSH do BuildKit com duas identidades — `core` (lê o `agentic-app`) e `packs` (lê os
  repositórios dos packs). `known_hosts` com a chave ed25519 do GitHub fixada no Dockerfile (a publicada em
  `api.github.com/meta`), sem `ssh-keyscan`. Localmente: `docker buildx build --ssh core --ssh packs` (as duas usam o
  agente SSH do operador). Na CI: cada identidade aponta para o arquivo de uma deploy key só de leitura.
- **Rationale** (FR-013): nenhuma credencial em camada; uma deploy key do GitHub vale para um repositório só, e a
  identidade por origem resolve isso sem truque de alias de host.
- **Alternatives**: token num build-arg (fica no histórico da imagem); `--secret` com token pessoal (acesso a todos os
  repositórios da conta).

### R24 — Configuração: o que vai na imagem e o que é montado

- **Decision**: `packs.yaml` vai **na imagem** — o build valida exatamente o conjunto de packs e a configuração deles
  que vão rodar. `assistants.yaml` (e `mcp.yaml`, quando houver) é montado em runtime, somente leitura; segredos vêm do
  `.env`.
- **Rationale**: pack e configuração de pack mudam juntos, com rebuild; Assistants são decisão do operador em runtime,
  com restart (003).
- **Alternatives**: montar `packs.yaml` (o `packs check` do build validaria um arquivo e o boot leria outro).

### R25 — Nenhuma instalação em runtime (FR-014, US5 cen. 3)

- **Decision**: o runtime não tem `uv`, `pip` nem `ensurepip`; `/opt/ai-core` pertence a root e o processo roda como
  `ai-core`, sem escrita nele; o `docker-compose.yml` sobe o serviço com `read_only: true` e `tmpfs` em `/tmp`.
- **Rationale**: o core já não oferece instalação (o Pack Registry só descobre entry points do ambiente); a imagem tira
  também a ferramenta e a permissão.
- **Alternatives**: só confiar na ausência de API (a imagem continuaria capaz de `pip install` como root).

### R26 — O pack incompatível do teste

- **Decision**: `packages/incompatible-pack/` no `agentic-deploy`: distribuição `incompatible-pack` 0.1.0, entry
  point `incompatible`, `contract_version = "0.2"`, dependência `ai-core-contracts>=0.1,<0.3` (instala sobre os
  contratos 0.1.0 e falha só no `packs check`). Entra por `PACKS=/build/packages/incompatible-pack`, com o diretório
  montado no estágio `packs` (`--mount=type=bind`), nunca no default.
- **Rationale** (US5 cen. 2): o build tem de falhar **na etapa de validação de packs**, não na resolução de
  dependências.
- **Alternatives**: um pack com faixa incompatível (o `uv` recusaria antes do `packs check`).

### R27 — O *Independent Test* da US5

- **Decision**: `scripts/check-build.sh` builda o alvo `runtime` com o `PACKS` default e confere: `ai-core packs list`
  com `scouting` e `generic` habilitados; `ai-core assistants validate` com `config/assistants.yaml`; sem `uv`, `pip` e
  `ensurepip`; `/opt/ai-core` sem escrita para o usuário do processo. Depois builda o alvo `packs` com o pack
  incompatível e exige que o build falhe com a saída do `packs check` nomeando `incompatible`. Sai com 0 só se tudo
  isso vale. Variáveis `SSH_CORE` e `SSH_PACKS` escolhem a identidade de cada origem (default: o agente).
- **Rationale**: um comando para o operador e para a CI; os três cenários da US5 verificados.
- **Alternatives**: testes em Python no repositório de instalação (um ambiente a mais só para chamar o Docker).

### R28 — CI do `agentic-deploy`

- **Decision**: `.github/workflows/build.yml` em push e PR: grava as deploy keys dos segredos `AGENTIC_APP_DEPLOY_KEY`
  e `AI_SCOUTING_DEPLOY_KEY` em arquivos e roda `scripts/check-build.sh` com `SSH_CORE`/`SSH_PACKS` apontando para eles,
  em `linux/amd64`. ARM64 (o alvo de produção) fica para a primeira instalação real — `--platform linux/arm64` com
  emulação na CI dobra o tempo sem informação nova para a US5.
- **Rationale** (clarificação 4): o *Independent Test* a cada push.
- **Alternatives**: só local (clarificação 4, opção B).

### R29 — Versões fixadas

- **Decision**: core pela tag `v0.1.0` do `agentic-app` (criada nesta passada, anotada, no commit `f6dbf7e` — o core da
  Fase 4, o mesmo do build local); o
  `ai-scouting` pelo commit `329d592010a74eaaa0cc113ef2f717905455be8f` (o pack ainda não tem tag de release); `uv` pela
  imagem `0.12.23`; base `python:3.14-slim`.
- **Rationale**: reprodutível sem criar tag que o mantenedor não pediu no repositório do pack.
- **Alternatives**: `main` dos repositórios (build não reprodutível).

## Pendências para outros planos

| Pendência | Onde |
|---|---|
| `assistants validate` chama `PackRegistry.compose` com a lista de cada Assistant; Assistant com composição inválida fica indisponível | plano da 003 (Fase 2) |
| Motor guarda o mapeamento de fatias e passa Turn View base + `slices` ao Pack Hooks; transforma `PackHookError` em erro explícito | plano da 005 |
| Caminho do `packs.yaml` e escolha do adapter por perfil; handlers de log; raiz do CLI | plano da 011 |
| Registrar `packs list` e `packs check` (`adapters/cli.py`, R15) na raiz `ai-core`, carregando o registry sem abrir a API | plano da 011 (Fase 2, US4) |
| Introspecção HTTP a partir de `PackRegistry.entries()` | plano da 008 |
| Pacote genérico em `ai-core/packs/generic/` exige acrescentar `packs/*` aos membros do workspace | plano da 010 |
| Conformidade da 001 checar `name`/`contract_version` como atributos de classe (FR-017) — adição de patch | backlog da 001 |

## Passada de 2026-10-07: validators que filtram o streaming ([ADR-024](../../docs/adr/ADR-024-validators-filtram-o-streaming.md))

### R30 — `open_answer_stream` e o `validate` com `streamed`

- **Decision**: no `api.py`, `AnswerFilter` (`feed`, `finish`) e `StreamedValidation` (`tail`, `answer`, `runs`);
  `PackHooks.open_answer_stream(composition, view, slices)` e `validate(..., streamed=None)`. O prefixo é a sequência
  de validators da composição (pack a pack, na ordem de cada um) até o primeiro sem `open_stream`. O encadeamento é
  puro (`domain/stream.py`, `ChainedFilter`): cada pedaço passa pelas sessões em ordem; no fim, cada sessão recebe o
  que a anterior ainda tinha a entregar antes de fechar. Com `streamed`, o `validate` confere que as execuções
  correspondem ao prefixo, começa da resposta filtrada e roda o resto.
- **Rationale** (ADR-024): o motor só conhece o seam; a ordem dos validators continua a da composição.
- **Alternatives**: filtrar com qualquer validator de streaming, mesmo depois de um em lote (quebraria a ordem: o de
  lote precisa da resposta inteira antes).
