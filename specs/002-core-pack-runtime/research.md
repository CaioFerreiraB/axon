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

## Passada de encaixe da Fase 5 na instalação — 2026-10-13

> Insumos: a nota R20 da 102 (o modelo no estágio `packs`, copiado para o `runtime`, e um Qdrant ao lado do core), o
> pack `scouting` 0.2.0 (101 US5: `config_schema`, `rag_first`, coleção `scouting`) e o core `v0.2.0` (005 US3–US4).
> Nenhum seam muda: só a instalação.

### R31 — Versões

- **Decision**: `CORE_REF` default `v0.2.0`; `PACKS` com o `ai-scouting` fixado no commit da Fase 5
  (`c60ffb460e082751e39705b539fbb82aa46eeccb`). O estágio `core` já clona o `agentic-app` raso e sem submódulos, e o
  `packs` instala com `--no-sources`, então os submódulos que o `agentic-app` ganhou não afetam o build.
- **Rationale**: o `scouting` 0.2.0 declara `rag_first`, que só existe no core `v0.2.0` (R29: versões fixadas).
- **Alternatives**: `main` em vez de tag (build não reprodutível).

### R32 — O modelo de embedding na imagem

- **Decision**: no estágio `packs`, depois de instalar os packs e **antes** do `packs check`,
  `ai-scouting-corpus model fetch /opt/ai-scouting/e5-small` (revisão e sha256 fixados pela 102; o download é verificado
  e nunca acontece em runtime); o `runtime` copia `/opt/ai-scouting`. O `config/packs.yaml` aponta `embedding_dir` para
  esse diretório, e o `packs check` confere que o pack carrega com ele.
- **Rationale**: a 102 proíbe baixar o modelo em runtime; o `read_config` do pack exige os arquivos na carga, então o
  `packs check` do build só passa com o modelo presente — a imagem fica autossuficiente e o build valida o que roda.
- **Alternatives**: montar o modelo por volume em runtime (o `packs check` do build falharia, e a instalação passaria a
  depender de um passo manual por máquina).

### R33 — O Qdrant ao lado do core

- **Decision**: serviço `qdrant` (`qdrant/qdrant:v1.19.2`, a versão da CI da 102) no `docker-compose.yml`, com volume
  nomeado para o armazenamento e sem porta publicada (só a rede do compose); o `ai-core` depende dele. O
  `config/packs.yaml` dá ao `scouting` `qdrant_url: http://qdrant:6333`. Chave do Qdrant opcional, documentada no
  `.env.example`: o mesmo valor em `QDRANT__SERVICE__API_KEY` (servidor) e `AI_SCOUTING_QDRANT_API_KEY` (pack, FR-012
  da 101).
- **Rationale**: o índice é da 102 e o core não o conhece; a instalação só o põe na mesma rede.
- **Alternatives**: Qdrant embutido (`qdrant_path`) no volume do core (trava o diretório por processo e mistura índice
  com runtime somente leitura).

### R34 — A ingestão do corpus

- **Decision**: o operador ingere com a CLI da própria imagem, montando o `corpus/` de um clone do `ai-scouting`:
  `docker compose run --rm -v <ai-scouting>/corpus:/corpus:ro ai-core ai-scouting-corpus ingest /corpus/corpus.yaml`.
  O serviço `ai-core` recebe `AI_SCOUTING_QDRANT_URL` e `AI_SCOUTING_EMBEDDING_DIR` (os da CLI da 102), apontando para o
  mesmo Qdrant e o mesmo modelo da configuração do pack.
- **Rationale**: o corpus mora no git do `ai-scouting` (102), não no pacote; a CLI já está instalada com o pack, e usar
  a mesma imagem garante a mesma codificação no índice e na busca (a 102 recusa índice de outro modelo).
- **Alternatives**: copiar o corpus para a imagem (rebuild a cada documento novo).

### R35 — Assistants e o teste da instalação

- **Decision**: o Assistant `scouting` do `config/assistants.yaml` deixa de declarar `flow` (roda no preferido,
  `rag_first`) e concede `collections: [scouting]`. O `check-build.sh` ganha um passo: o modelo está em
  `/opt/ai-scouting/e5-small` e `ai-scouting-corpus --help` roda na imagem. A conversa com o índice ingerido é
  verificação manual (quickstart), não do `check-build.sh` — exige Qdrant e a ingestão.
- **Rationale**: o `assistants validate` do passo 3 já confere a coleção (PackCollectionCatalog, 011 R35) e o flow.
- **Alternatives**: subir o Qdrant e ingerir no teste (minutos e 1,3 GB de memória a cada push).

## Passada de encaixe da Fase 7 na instalação — 2026-10-13

> Insumos: a Fase 7 da 008 (core `v0.4.0`: fila, progresso como raciocínio, pedido efêmero; research R39 e R40 da 008,
> com as notas para a 002), o pack `scouting` 0.3.0 (105: métricas de domínio) e o Open WebUI v0.12.0. Nenhum seam
> muda: só a instalação.

### R36 — Versões

- **Decision**: `CORE_REF` default `v0.4.1`; `PACKS` com o `ai-scouting` em `24cb157590dbc81c9b6778de0b868fcc8064c36b`
  (pack 0.3.0, contratos `>=0.1.2` da mesma tag). Com isso, `ai-core eval run` existe na imagem (premissa da 105).
  *Acrescido na implementação*: a `v0.4.1` é a `v0.4.0` com a correção do verificador OIDC da 003 (research R24 da 003)
  — sem ela, nenhum access token do Keycloak verificava, porque a chave de cifragem do JWKS descartava todas.
- **Rationale**: R29 (versões fixadas); o pack 0.3.0 precisa dos contratos 0.1.2, que vêm com o core `v0.3.0`+.
- **Alternatives**: manter `v0.2.0` (sem fila nem raciocínio no stream, e sem o harness).

### R37 — Provedor OIDC de desenvolvimento

- **Decision**: serviço `keycloak` (`quay.io/keycloak/keycloak:26.7.5`, `start-dev --import-realm`) no perfil `webui`
  do compose, com o realm `agentic` importado de `config/keycloak/agentic-realm.json`: cliente confidencial
  `open-webui` (redirect `http://localhost:3000/oauth/oidc/callback`), mapper de audiência `ai-core` e de grupos (claim
  `groups`, sem caminho) no access token, grupo `equipe` e dois usuários — `ana` (sem grupo) e `bia` (`equipe`). O
  segredo do cliente e a senha dos usuários vêm do `.env` por placeholders do import (`${OPEN_WEBUI_OIDC_SECRET}`,
  `${KEYCLOAK_DEV_PASSWORD}`); o administrador do Keycloak, de `KC_BOOTSTRAP_ADMIN_*`. Endereços: o navegador usa
  `http://localhost:8180` (`KC_HOSTNAME`, o emissor dos tokens) e os contêineres `http://keycloak:8080`
  (`KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true`). *Acrescido na implementação*: os dados do Keycloak ficam no volume
  `keycloak-data` — sem ele, cada recriação reimporta o realm com IDs novos, e o Open WebUI recusa o mesmo e-mail
  chegando com outro `sub`. A sessão do realm dura 10 h (`ssoSessionIdleTimeout` e `ssoSessionMaxLifespan`): com os 30
  minutos de inatividade do padrão do Keycloak, a sessão do provedor caía enquanto a do Open WebUI (4 semanas) seguia, e
  o token que ele repassa deixava de ser renovado.
- **Rationale**: 008 R39 — access token JWT por padrão, audiência e grupos por mapper, realm reproduzível. Só para
  desenvolvimento e para a prova; em produção, o operador usa o provedor dele.
- **Alternatives**: Authelia (access token opaco por padrão), Dex (sem grupos para usuários estáticos).

### R38 — O Open WebUI na instalação

- **Decision**: serviço `open-webui` (`ghcr.io/open-webui/open-webui:v0.12.0`) no perfil `webui`, porta
  `${OPEN_WEBUI_HOST_PORT:-3000}`, volume `open-webui-data`, configurado só por ambiente (008 R40):
  `ENABLE_PERSISTENT_CONFIG=false`, `ENABLE_OLLAMA_API=false`, `OPENAI_API_BASE_URLS=http://ai-core:8000/v1`,
  `OPENAI_API_CONFIGS` com `auth_type: system_oauth` e `headers: {"x-ai-core-store": "false"}`,
  `BYPASS_MODEL_ACCESS_CONTROL=true`, as seis tarefas auxiliares em `false`, OIDC (`OPENID_PROVIDER_URL` pela rede
  interna, `OAUTH_CLIENT_ID`/`SECRET`, `ENABLE_OAUTH_SIGNUP=true`, `ENABLE_LOGIN_FORM=false`,
  `OPENID_REDIRECT_URI`, `WEBUI_URL`), `DEFAULT_USER_ROLE=user`, `DEFAULT_MODEL_PARAMS` com `function_calling: legacy`, `DEFAULT_MODEL_METADATA` com
  `builtin_tools: false`, `JWT_EXPIRES_IN` de 8 h (`OPEN_WEBUI_SESSION_EXPIRES_IN`; menor que a sessão do provedor) e
  `WEBUI_SECRET_KEY` do `.env`. *Acrescido na
  implementação*: sem `DEFAULT_USER_ROLE=user`, quem entra depois do primeiro fica `pending` (a API do Open WebUI
  responde 401) — e quem pode o quê é decisão da plataforma (ACL da 003), não de aprovação na interface.
- **Rationale**: SC-001 da 008 (zero código de interface); o perfil `webui` deixa o `docker compose up` de sempre igual.
- **Alternatives**: configurar pela tela de administração (não reproduzível).

### R39 — O core com o Keycloak e um Assistant por grupo

- **Decision**: o `.env.example` ganha a seção do perfil `webui` com os valores de desenvolvimento da 003 —
  `AI_CORE_OIDC_ISSUER=http://localhost:8180/realms/agentic`, `AI_CORE_OIDC_AUDIENCE=ai-core`,
  `AI_CORE_OIDC_JWKS_URL=http://keycloak:8080/realms/agentic/protocol/openid-connect/certs`,
  `AI_CORE_OIDC_SUBJECT_CLAIM=preferred_username` — e as variáveis da fila comentadas. O `config/assistants.yaml`
  ganha `interno` (privado, `group:equipe`, só OIDC, flow `chat` com o `generic`), o que só a `bia` vê.
- **Rationale**: a prova da lista por usuário (008 US8 cen. 2) precisa de um Assistant que um usuário veja e o outro
  não; o subject legível (`user:ana`) facilita ler o trace.
- **Alternatives**: subject pelo `sub` (UUID do Keycloak; funciona, mas o trace fica ilegível).

### R40 — A prova da interface

- **Decision**: `scripts/check-webui.py` (só biblioteca padrão), local e manual (precisa do `.env` com a chave do
  OpenRouter): com o perfil `webui` de pé, entra no Open WebUI como `ana` e como `bia` pelo fluxo OIDC de verdade (o
  formulário do Keycloak), lê `/api/models` de cada um — a `bia` vê `interno`, a `ana` não — e manda uma mensagem pelo
  `/api/chat/completions` do Open WebUI, que chega à plataforma pela conexão `system_oauth`; confere a resposta e,
  pelo log de acesso do `ai-core`, que houve exatamente um `POST /v1/chat/completions` (nenhuma tarefa auxiliar) e que
  o subject não ganhou conversa (`x-ai-core-store`). A conversa no navegador fica no quickstart, como verificação manual.
- **Rationale**: a 008 US8 cen. 2–5 com a interface real, sem escrever interface; o CI do `agentic-deploy` continua só
  com o build (subir Keycloak e Open WebUI a cada push custaria minutos e memória).
- **Alternatives**: Playwright num navegador (código de teste de interface, pesado para o CI e para o mantenedor).

### R41 — A timeline de status na instalação (008 R42; ADR-028)

- **Decision**: a conexão do Open WebUI manda também `x-ai-core-progress: status`, junto do `x-ai-core-store: false`,
  e o `CORE_REF` vai para `v0.5.0`. O `check-webui.py` lê a timeline que o Open WebUI gravou na mensagem
  (`statusHistory`, `models/chats.py` do v0.12) e confere começo, modelo e conclusão.
- **Rationale**: é a configuração da instalação que liga a timeline (o padrão da API continua o raciocínio), e o
  `statusHistory` gravado é o que o usuário vê ao reabrir a conversa.
- **Alternatives**: ler o stream direto da plataforma no script (não provaria que o Open WebUI a recebeu e gravou).

## Fase 9 (2026-10-14): instalação com ou sem console, sem Keycloak (US7)

Insumos: ADR-029, ADR-030, ADR-033; a clarificação de 2026-10-13 (Postgres em toda instalação); os planos da Fase 9 da
012 (clientes, variáveis), 011 (configuração), 013 (nginx) e 008 (superfície de administração).

### R42 — Três modos pelo compose

**Decision**: modo padrão (sem perfil) = `ai-core` + `postgres` + `qdrant`, identidade desligada, só chaves de API;
`--profile webui` acrescenta o Open WebUI; `--profile console` acrescenta a console; os dois combinam. Com qualquer
interface, o `.env` liga `AI_CORE_IDENTITY_ENABLED=true`. O operador escolhe o modo com `COMPOSE_PROFILES` no `.env`
(ex.: `COMPOSE_PROFILES=webui,console`), sem editar o compose (SC-006).

**Rationale**: o compose já usa perfis (Fase 7); `COMPOSE_PROFILES` é o parâmetro de instalação mais simples.

**Alternatives considered**: build-arg para a console (a console é outra imagem, não parte da do core).

### R43 — Postgres sempre

**Decision**: serviço `postgres` (`postgres:17.6`, volume `postgres-data`, `healthcheck` com `pg_isready`, sem porta
publicada), `ai-core` com `AI_CORE_PROFILE=persistent`, `AI_CORE_DATABASE_URL` e `depends_on: {postgres:
{condition: service_healthy}}`. Senha do banco por `POSTGRES_PASSWORD` no `.env`.

**Rationale**: clarificação de 2026-10-13 da 002; contas, sobreposições, uso e chaves sobrevivem a restart.

**Alternatives considered**: manter o `memory` no modo padrão (rejeitado pelo mantenedor).

### R44 — Keycloak fora; Open WebUI na plataforma

**Decision**: saem o serviço `keycloak`, o volume `keycloak-data`, `config/keycloak/` e as variáveis `KEYCLOAK_*`. O
Open WebUI passa a: `OPENID_PROVIDER_URL=http://ai-core:8000/.well-known/openid-configuration` (a descoberta responde
o `issuer` público e os endpoints de servidor pelo endereço interno — 012 R8), `OAUTH_CLIENT_ID=open-webui`,
`OAUTH_CLIENT_SECRET=${AI_CORE_IDENTITY_SECRET_OPEN_WEBUI}`, `OAUTH_PROVIDER_NAME=${AI_CORE_DISPLAY_NAME}`,
`OAUTH_SCOPES=openid email profile groups offline_access`, `OAUTH_CODE_CHALLENGE_METHOD=S256` (se o v0.12 o aceitar;
senão, sem PKCE — o cliente é confidencial), `ENABLE_OAUTH_SIGNUP=true`, `ENABLE_LOGIN_FORM=false`,
`OAUTH_MERGE_ACCOUNTS_BY_EMAIL=true` (religa as contas criadas com o Keycloak, R48) e `JWT_EXPIRES_IN=29d` (abaixo dos 30
dias da sessão da 012). A conexão com a plataforma continua `system_oauth` com os cabeçalhos da Fase 7. **A conferir**
contra o Open WebUI v0.12 na prova (T083): nomes exatos das variáveis de PKCE e de junção por e-mail. **Conferido em
2026-10-14** (incremento 9.1, `CORE_REF=v0.6.0-rc2`): com `OAUTH_CODE_CHALLENGE_METHOD=S256`, o v0.12 manda
`code_challenge` e `code_challenge_method=S256` no `authorize`; com `OAUTH_MERGE_ACCOUNTS_BY_EMAIL=true`, as contas
`ana` e `bia` da Fase 7 foram religadas pelo e-mail (uma conta por pessoa); token, `userinfo` e JWKS saíram pelo
endereço interno (`ai-core:8000`), e o `check-webui.py` passou inteiro.

**Rationale**: ADR-030; o Open WebUI continua repassando o token de cada pessoa, agora emitido pela plataforma.

**Alternatives considered**: —

### R45 — `identity.yaml` e endereços

**Decision**: `config/identity.yaml` com os clientes `open-webui` (confidencial, `secret: open_webui`, audiência
`ai-core`, retorno `http://localhost:${OPEN_WEBUI_HOST_PORT}/oauth/oidc/callback`) e `console` (público, audiência
`ai-core-admin`, retorno `http://localhost:${CONSOLE_HOST_PORT}/callback`), escritos para `localhost` e montados
somente leitura; o README explica como trocar pelos domínios de produção. `AI_CORE_PUBLIC_URL` = a origem da console com
o perfil `console`, ou `http://localhost:${AI_CORE_HOST_PORT}` sem ela.

**Rationale**: o arquivo de clientes é do operador (012); endereços exatos são controle de segurança.

**Alternatives considered**: gerar o `identity.yaml` por script na subida (mais uma peça para entender).

### R46 — Imagem da console no mesmo Dockerfile

**Decision**: estágios novos `console-build` (`node:24.11-bookworm-slim`, copia `ai-core/console` do clone do estágio
`core` pela mesma `CORE_REF`, `npm ci && npm run build`) e `console` (`nginxinc/nginx-unprivileged:1.29-alpine`,
`dist/` em `/usr/share/nginx/html`, `nginx.conf.template` em `/etc/nginx/templates/`, `AI_CORE_UPSTREAM` por ambiente).
Serviço `console` no compose com `build.target: console`, `read_only: true`, `tmpfs` para `/tmp` e `/var/cache/nginx`,
porta `${CONSOLE_HOST_PORT:-8080}:8080`, perfil `console`. `AI_CORE_TRUSTED_PROXIES` inclui a rede do compose.

**Rationale**: ADR-022 (o core e o que vem dele saem da mesma tag); a console só é construída quando o perfil a usa.

**Alternatives considered**: imagem publicada da console (não há registro de imagens, ADR-022).

### R47 — `.env.example` em seções

**Decision**: seções "Sempre" (perfil, Postgres, chave mestra — `openssl rand -base64 32` —, nome da instalação,
OpenRouter, Qdrant, RAG, fila), "Com interface" (identidade, URL pública, segredo do Open WebUI, admin inicial por
arquivo `secrets/bootstrap-admin-password`, Google opcional e `AI_CORE_GOOGLE_LOGIN` comentado) e "Sem console"
(`AI_CORE_LANGFUSE_*`, comentado; com a console, as chaves do Langfuse vão pela tela — ADR-033). Nenhum valor real.

**Rationale**: FR-021 da 002; a decisão do mantenedor sobre onde ficam as chaves do Langfuse.

**Alternatives considered**: dois arquivos de exemplo (mais fácil de desalinhar).

### R48 — Migração da Fase 7

**Decision**: README com o passo a passo: parar o compose, remover o volume `keycloak-data`, cadastrar as pessoas com
`docker compose run --rm ai-core ai-core users create …` (mesmos nomes de usuário da Fase 7, para que ACL e donos
continuem), subir com `webui`; contas do Open WebUI religadas pelo e-mail (`OAUTH_MERGE_ACCOUNTS_BY_EMAIL`) ou volume
`open-webui-data` novo.

**Rationale**: o subject `user:<nome>` não muda (012 R10); só o `sub` do Open WebUI muda.

**Alternatives considered**: —

### R49 — Provas da instalação

**Decision**: `scripts/check-webui.py` reescrito (só biblioteca padrão): entra pelo formulário da plataforma
(`/oauth2/authorize` → página de login, campos `request` e `csrf`, `POST /oauth2/login`) como `ana` e `bia`, compara as
listas de modelos e manda uma mensagem, como antes. `scripts/check-console.py` (só biblioteca padrão): fluxo de código
com PKCE do cliente `console` contra a 012, `GET /admin/v1/me`, sobreposição de `generation` num Assistant com
`overrides: [models]`, uma conversa pela API e o uso dela em `GET /admin/v1/usage`. `scripts/check-build.sh` constrói
também o alvo `console`.

**Rationale**: FR-022 da 002; o padrão das provas manuais da Fase 7.

**Alternatives considered**: Playwright contra o compose (a suíte e2e da 013 já cobre a interface).

### R50 — Versões

**Decision**: `CORE_REF=v0.6.0` (depois da release da 011 R44); o `ai-scouting` no mesmo ponteiro.

**Rationale**: ADR-022.

**Alternatives considered**: —

## Passada de 2026-10-20: identidade Axon ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md); US8)

Decisões pré-aprovadas pelo ADR-037 (nomes, corte seco, ordem das passadas); o que segue é como elas chegam ao Pack
Runtime e aos packs do workspace, sem re-pesquisa. Os R anteriores ficam como foram executados (ADR-037, item 6); os
nomes antigos neles se leem pela tabela do ADR-037. A instalação (US7) tem passada própria, depois da 101.

### R51 — O grupo `axon.packs`

- **Decision**: `PACKS_GROUP = "axon.packs"` em `axon_ai/packs/adapters/entry_points.py` (a docstring de
  `EntryPointPackSource` cita o grupo novo). Nada mais muda no Pack Runtime: o nome do entry point continua igual ao
  `name` do pack (FR-017), o logger já é `axon_ai.packs` (passada da 011) e os subcomandos já são `axon packs list|check`.
- **Rationale** (ADR-037, item 2): o grupo é o que o autor de pack digita no `pyproject.toml`; na operação, o nome fica
  curto, `axon`. É identificador com comportamento da 002, por isso ficou fora da substituição mecânica da 011 (011 R47).
- **Alternatives**: `axon_ai.packs` (o nome do import do core; o ADR fixa `axon.packs`, e o grupo não é módulo
  importável); manter `ai_core.packs` (dois vocabulários para sempre, o que o ADR-037 rejeita).

### R52 — Corte seco, sem diagnóstico do grupo antigo

- **Decision**: o `EntryPointPackSource` lê só `axon.packs`. Um pack anunciado só em `ai_core.packs` não entra na
  descoberta; habilitado em `packs.yaml`, cai na regra que já existe em `PackRuntime.load()` (`error: não instalado`), e
  `axon packs check` sai com 1 (`check_command` conta os packs em `error`). Nenhuma consulta ao grupo antigo, nenhuma
  mensagem própria.
- **Rationale** (ADR-037, item 3): corte seco; a única concessão de diagnóstico é a recusa das variáveis antigas no boot
  (011) e no pack (101). A falha já é fechada e visível — o pack habilitado aparece em erro na introspecção, e o build
  da instalação para no `packs check` (FR-013) —, então um aviso a mais seria código de compatibilidade sem usuário.
- **Alternatives**: procurar o nome do pack ausente no grupo antigo e dizer "anunciado em `ai_core.packs`; use
  `axon.packs`" (útil só para quem tem pack antigo, e não há); descobrir nos dois grupos por uma janela (contraria o
  corte seco).

### R53 — Quem se anuncia no grupo (mecânico)

- **Decision**: troca de `ai_core.packs` por `axon.packs`, à mão, em: `axon-ai/packages/generic/pyproject.toml`
  (`[project.entry-points."axon.packs"]`), a docstring de `axon_generic/__init__.py` e o `README.md` do pack;
  `axon-ai/packages/contracts/tests/fixtures/contract_test_pack/pyproject.toml` e o exemplo de
  `axon-ai/packages/contracts/README.md`; o `entry_points.txt` sintético de `FakeDistributions.add` em
  `axon-ai/packages/core/tests/packs/packs_testkit.py`, que ganha o parâmetro `group: str = PACKS_GROUP` (o teste do
  R54 escreve uma distribuição no grupo antigo). O `axon-generic` continua `0.2.0`: a versão ainda não saiu em tag, e
  nenhum consumidor externo o instala. O `uv.lock` não muda (entry points não entram no lock). O job `frozen-pack` da CI
  dos contratos usa o pack de teste da tag antiga, que não é carregado pelo core; nada a fazer.
- **Rationale** (ADR-037, item 7): a passada que muda um seam atualiza quem o usa no workspace, para a CI ficar verde —
  sem a troca no pack de referência, a carga real por entry point (010 SC-002) quebra.
- **Alternatives**: bump do `axon-generic` para `0.2.1` (a `0.2.0` ainda não existe fora do workspace; a tag
  `v0.7.0-rc1` sai com o grupo novo); deixar o pack de teste dos contratos no grupo antigo (o core não o carrega, mas
  ele é o exemplo que a 001 mostra a um autor de pack).

### R54 — Testes

- **Decision**: `axon-ai/packages/core/tests/packs/integration/test_packs_entry_point_group.py`, com
  `FakeDistributions`: `PACKS_GROUP == "axon.packs"`; um pack bom anunciado em `axon.packs` e habilitado fica `enabled`
  (US8 cen. 1); o mesmo pack anunciado só em `ai_core.packs` e habilitado fica `error` com `"não instalado"`, e o boot
  carrega os demais (cen. 2); `check_command` sobre esse registry devolve 1 e a saída nomeia o pack (cen. 3); anunciado
  só no grupo antigo e não habilitado, ele não aparece em `entries()` (cen. 4). O cenário 5 é a carga real que já existe
  (`test_packs_generic_entry_point.py`), que só passa com o `axon-generic` no grupo novo.
- **Rationale**: FR-023 e FR-024 precisam de um verificador que não dependa do nome escrito no texto; o kit de
  distribuições falsas já é o meio da suíte para testar descoberta sem instalar nada.
- **Alternatives**: teste unitário só da constante (não prova que o grupo antigo fica de fora).

### R55 — Documentos vivos e verificação

- **Decision**: o grupo novo em `specs/002-core-pack-runtime/{design.md,data-model.md,contracts/ports.md}` (no
  `design.md`, só a parte do Pack Runtime: a árvore e o exemplo de `pyproject.toml`; o exemplo segue com
  `ai_scouting`, que é nome da 101) e um roteiro "Fase 9, incremento 9.5" no `quickstart.md`; na 010,
  `design.md`, `data-model.md`, `quickstart.md` (§3 e §15) e `contracts/{generic-pack.md,packaging.md}` (a nota do grupo
  passa a "desde a passada da 002"). Ficam: as specs `1xx`, `contracts/installation.md` e o resto do `design.md` sobre
  a instalação (passada da instalação), `CLAUDE.md` e o histórico. Verificação, a partir de `axon-ai/`: `uv run pytest
  && uv run mypy && uv run ruff check packages && uv run ruff format --check packages && uv run lint-imports`; na raiz,
  `git grep -nw "ai_core\.packs"` fora desses caminhos só mostra o teste do corte
  seco e os textos que nomeiam o grupo antigo de propósito; nenhuma palavra `agentic` sai (`--word-diff`).
- **Rationale** (ADR-037, item 6): documentos vivos passam ao nome novo; o histórico não se reescreve. Muitas
  ocorrências de `ai_core.packs` nos `plan.md`/`research.md`/`tasks.md` de outras specs são o **módulo** antigo
  (`ai_core.packs.api`), não o grupo, e são histórico.
- **Alternatives**: nenhuma.

## Passada de 2026-10-20: a instalação com os nomes da Axon ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md); US7 cen. 6)

> Os itens acima ficam como foram decididos (ADR-037, item 6). Estes são da passada da instalação, no submódulo
> `agentic-deploy/` (o repositório `axon-deploy`; a pasta muda no fechamento do renome).

### R56 — Os nomes da instalação

- **Decision**: no `docker-compose.yml`, `name: axon` no topo (o projeto deixa de vir da pasta), serviço `axon`, imagens
  `axon:local` e `axon-console:local`; no `Dockerfile`, `CORE_REPO=ssh://git@github.com/CaioFerreiraB/axon.git`,
  `CORE_REF=v0.7.0-rc1`, o clone em `/src/axon` com os pacotes de `axon-ai/packages/{contracts,core,generic}` e a console
  de `axon-ai/console`, o ambiente em `/opt/axon`, o modelo em `/opt/axon-scouting/e5-small`, a configuração em
  `/etc/axon`, o usuário do processo `axon` (uid 10001, igual), `CMD ["axon", "serve"]`, `PACKS` com
  `axon-scouting@git+ssh://git@github.com/CaioFerreiraB/axon-scouting.git@<commit da passada da 101>`, e no estágio da
  console `NGINX_ENVSUBST_FILTER=AXON_` e `AXON_UPSTREAM=http://axon:8000` (o template da 013 já usa `AXON_UPSTREAM`). O
  Postgres com usuário e banco `axon`; os segredos em `/run/secrets/axon`; todas as variáveis `AI_CORE_*` passam a
  `AXON_*` e as `AI_SCOUTING_*` a `AXON_SCOUTING_*`. Os volumes guardam os nomes (`postgres-data`, `qdrant-data`,
  `open-webui-data`), que o compose prefixa com o projeto (`axon_…`).
- **Rationale** (ADR-037, item 2, linha "compose"): o nome fixo no arquivo faz o projeto continuar `axon` quando a pasta
  passar a `axon-deploy/` no fechamento, sem trocar de volumes de novo.
- **Alternatives**: deixar o projeto derivar da pasta (os volumes mudariam outra vez no fechamento); `axon-ai` como
  serviço (o nome da operação é curto, `axon`).

### R57 — O Open WebUI e os clientes da identidade

- **Decision**: `OPENAI_API_CONFIGS` com os cabeçalhos `x-axon-store: false` e `x-axon-progress: status` (008 US10: os
  antigos recebem 400); `OPENAI_API_BASE_URLS` e `OPENID_PROVIDER_URL` em `http://axon:8000`; `WEBUI_NAME=Axon` (o nome
  da interface; o Open WebUI acrescenta "(Open WebUI)"); `OAUTH_PROVIDER_NAME=${AXON_DISPLAY_NAME:-Axon}` (o botão diz
  "Continuar com Axon"); `OAUTH_CLIENT_SECRET=${AXON_IDENTITY_SECRET_OPEN_WEBUI}`. No `config/identity.yaml`, as
  audiências `axon` (`open-webui`) e `axon-admin` (`console`), que são as que a 003 aceita desde a passada dela. As
  contas de desenvolvimento passam a `ana@axon.local` e `bia@axon.local`.
- **Rationale**: os cabeçalhos e as audiências antigos são recusados pelo core da `v0.7.0-rc1`; sem a troca, o chat
  falha com 400 e os tokens não autenticam.
- **Alternatives**: manter `WEBUI_NAME` sem definir (mostraria "Open WebUI"; o ADR-037 pede o nome da plataforma).

### R58 — O pack incompatível da US5

- **Decision**: `packages/incompatible-pack` com `axon-ai-contracts>=0.2,<0.4`, grupo `axon.packs`, import
  `axon_ai_contracts` e `contract_version = "0.3"`.
- **Rationale** (FR-027): ele precisa instalar sobre os contratos da imagem (0.2.0) e ser reprovado pelo `axon packs
  check`; com "0.2" ele passaria a ser compatível.
- **Alternatives**: nenhuma.

### R59 — Migração de uma instalação local

- **Decision**: o README ganha "Vindo dos nomes antigos": `docker compose -p agentic-deploy down` (o projeto antigo vinha
  da pasta), renomear as variáveis do `.env` (`sed -i 's/^AI_SCOUTING_/AXON_SCOUTING_/; s/^AI_CORE_/AXON_/' .env`, nessa
  ordem), `docker compose up -d --build` (volumes `axon_*` novos), `scripts/dev-users.sh`, reingestão do corpus e, quando
  quiser, `docker volume rm` dos `agentic-deploy_*`. O `.env` antigo não sobe: o core recusa `AI_CORE_*` e o pack,
  `AI_SCOUTING_*`, nomeando a nova (011 US7, 101 US6). O `config/identity.local.yaml` do operador (fora do git) precisa
  das audiências novas.
- **Rationale** (ADR-037, item 3; FR-028): corte seco, ambientes recriados; o roteiro evita adivinhação.
- **Alternatives**: reaproveitar os volumes antigos com `external: true` (as chaves de API e a chave de assinatura
  seladas com os nomes antigos não valem mais; não há dado a preservar).

### R60 — CI e segredos

- **Decision**: `build.yml` mantém os segredos `AGENTIC_APP_DEPLOY_KEY` e `AI_SCOUTING_DEPLOY_KEY` (os comentários dizem
  que leem o `axon` e o `axon-scouting`); o `check-build.sh` usa `axon:check`, `axon packs list`, `axon assistants
  validate`, `axon-scouting-corpus --help`, `/opt/axon` e procura `axon packs check` na saída do build, e ganha um passo
  que roda a imagem com `AI_CORE_PROFILE=memory` e espera a recusa citando `AXON_PROFILE`.
- **Rationale**: o nome de segredo é configuração do GitHub (a mesma decisão da 101 R28); o passo novo prova o corte seco
  na imagem que vai para produção (US7 cen. 6).
- **Alternatives**: renomear os segredos (recadastrar as chaves sem ganho).

### R61 — Verificação

- **Decision**: `scripts/check-build.sh` verde (local, com o agente SSH) e a CI do `axon-deploy` verde; a instalação
  recriada no modo `webui,console` com o `.env` migrado: `scripts/dev-users.sh`, a ingestão do corpus, `python3
  scripts/check-webui.py` (listas de `ana` e `bia`, uma mensagem, 200, a timeline) e a console respondendo. Resíduos
  (SC-009): `git grep -nE 'ai-core|ai_core|AI_CORE_|ai-scouting|AI_SCOUTING_|agentic-app|agentic-deploy|x-ai-core'` no
  submódulo só no roteiro de migração, nos segredos da CI e no passo da recusa; nenhuma palavra `agentic` (o flow)
  removida. Documentos vivos da 002: `contracts/installation.md` e a parte da instalação do `design.md` nos nomes novos,
  com a seção "Fase 9, incremento 9.5"; `quickstart.md` com o roteiro.
- **Rationale**: SC-009; a prova do Open WebUI é a que pegou o defeito do JWKS na Fase 7.
- **Alternatives**: nenhuma.

## Passada de 2026-10-21: o pack prepara os próprios dados ([ADR-041](../../docs/adr/ADR-041-o-pack-prepara-os-proprios-dados-no-build.md); US4 cen. 3–5)

Decisões pré-aprovadas pelo ADR-041 (o comando, quem o chama, `data_dir`, códigos); o que segue é como elas chegam ao
Pack Runtime, sem re-pesquisa. A instalação (o `Dockerfile` chamando `axon packs prepare`, ADR-042) é outra passada, no
`axon-deploy`.

### R62 — A porta `PackDataDirs`

- **Decision**: porta secundária em `ports.py`, com `path(pack) -> Path | None` (`<raiz>/<pack>`, sem tocar o disco) e
  `create(pack) -> Path | None` (`mkdir(parents=True, exist_ok=True)`); `None` nos dois sem raiz. Um adapter,
  `LocalPackDataDirs(root: Path | None)` em `adapters/data_dirs.py`, que a 011 monta nos três perfis com
  `AXON_PACKS_DATA_DIR`. `PackRuntime(source, config_source, data_dirs=None)`: sem a porta, nenhuma raiz — a assinatura
  de antes continua valendo para as suítes. Um nome de pack é sempre um segmento seguro (001: `^[a-z][a-z0-9_]{0,31}$`,
  conferido antes de chegar à porta), então a porta não sanitiza.
- **Rationale** (princípio XIII, CLAUDE.md regra 7): criar diretório é I/O, e `service.py` não toca o sistema de
  arquivos. A porta só existe para isso; um adapter em memória fingiria um diretório que o pack vai de fato abrir, então a
  conformidade roda o adapter real contra `tmp_path`.
- **Alternatives**: `Path.mkdir` no `service.py` (I/O fora de porta); criar o diretório no adapter de CLI e passar o
  caminho ao serviço (o serviço precisaria confiar que o chamador criou, e a carga calcula o mesmo caminho por outro
  lugar).

### R63 — `prepare_data`: até a configuração validada, sem catálogo

- **Decision**: seam `PackDataPreparation` em `api.py` (`prepare_data() -> Sequence[PreparedPack]`), implementado pelo
  `PackRuntime`. Lê a configuração (`PackConfigError` propaga), descobre, e para cada pack **habilitado**, em ordem de
  nome: duplicado ou não instalado → `error` com a mensagem da carga; senão import, identidade, compatibilidade,
  instanciação, manifest e `config_schema` pelos mesmos passos de `_load_one`/`_instantiate` (fatorados num
  `_configured` comum); depois `data_dirs.create(nome)`, e então `prepare(PackContext(pack_name, config, data_dir))` se o
  pack o tiver. `prepare` coroutine function → `error` "prepare precisa ser síncrono" sem chamar; exceção →
  `"prepare levantou <Tipo>: <mensagem>"`; o retorno não é conferido (o kit da 001 confere). Falha de criação do
  diretório (`OSError`) → `error` com a causa. Nenhuma ordem por `depends_on` e nenhuma cascata: o `prepare` produz
  arquivos, não fatias. `prepare_data` não marca o registry como carregado.
- **Rationale** (ADR-041, itens 3 e 4): os hooks de catálogo do scouting constroem o embedder, que abre o modelo que o
  `prepare` baixa — rodar o catálogo antes falharia exatamente o pack que precisa do comando. Os mesmos passos da carga
  garantem a mesma mensagem para o mesmo defeito no `prepare` e no `check`.
- **Alternatives**: `load()` e depois `prepare` dos `enabled` (o catálogo falha antes do preparo); chamar o `prepare`
  dentro de `load()` quando houver uma flag (o boot passaria a ter um caminho com rede, contra o item 4).

### R64 — `data_dir` na carga

- **Decision**: `_instantiate` monta `PackContext(pack_name, config, data_dir=data_dirs.path(nome))` — o mesmo contexto
  para catálogo e `prepare_context`; `ValidatorContext` sem mudança. A carga nunca chama `create` nem `prepare` (em
  runtime o diretório é somente leitura, ADR-041 item 4).
- **Rationale** (ADR-041, item 2): o caminho é o mesmo no build e em runtime porque as duas pontas o calculam pela mesma
  porta, com a mesma raiz.
- **Alternatives**: `data_dir` só quando o diretório existir (o pack não distinguiria "sem raiz" de "não preparado" — e
  a mensagem do pack sobre o segundo é a útil).

### R65 — O comando, os testes e a dependência dos contratos

- **Decision**: `prepare_command(preparation, out, err)` em `adapters/cli.py`: chama `prepare_data()`;
  `PackConfigError` → `config_error_command` (2); senão uma linha por pack (nome, `ok`/`error`, diretório ou causa, com
  `-` sem raiz) e o resumo `M packs preparados` (0) ou `F de M packs falharam no preparo` (1). A 011 o registra (011
  R54). O core passa a depender de `axon-ai-contracts>=0.2.1,<0.3` (usa `PackContext.data_dir`). Testes:
  `tests/packs/contract/test_packs_prepare_seam.py` (as linhas da tabela do contrato), a linha da carga em
  `test_packs_registry_seam.py`, `tests/packs/contract/test_packs_data_dirs.py` (porta) e os casos 7 e 8 de
  `tests/packs/integration/test_packs_cli.py`, com distribuições falsas. O `axon-generic` não muda (herda o default).
- **Rationale**: o padrão do `packs check` (R15, R16): o comando é função sobre o seam, e quem monta é a 011.
- **Alternatives**: —

## Passada de 2026-10-21: instalação por camadas ([ADR-042](../../docs/adr/ADR-042-instalacao-por-camadas.md); US5 cen. 4–5, FR-032–FR-034)

Decisões pré-aprovadas pelo ADR-042 (três camadas, imagens base, modelo de instalação, configuração na imagem,
segredos no ambiente, release pelo CI, Portainer CE); o que segue é como elas chegam ao `axon-deploy`, sem
re-pesquisa. Os R21–R61 sobre a instalação ficam como foram executados.

### R66 — As imagens base num `Dockerfile` de três alvos

- **Decision**: `images/Dockerfile` com os estágios internos `tools` (python slim + git + cliente SSH + `uv` 0.12.23 +
  chave de host do GitHub) e `source` (clone raso da `CORE_REF`, sem submódulos, pela identidade `core`; obrigatória,
  sem default), e os alvos `build`, `runtime` e `console`. `build` instala os três pacotes de `/src/packages` montado do
  `source` (o fonte não fica em camada), copia `images/packs.yaml` (só o `generic`) e roda `axon packs prepare && axon
  packs check`, para a `axon-runtime` subir sozinha e a raiz `/opt/axon-data` sempre existir. Label OCI `source`
  apontando o `axon-deploy` (o GHCR liga o pacote ao repositório). Sai o `ORT_DISABLE_TELEMETRY` (era do scouting: o pack
  passa a cuidar disso, na passada da 101/102 do ADR-043).
- **Rationale** (ADR-042, item 2): os três alvos saem do mesmo fonte e do mesmo `PYTHON_IMAGE` numa rodada; a
  instalação copia `/opt/axon` da `axon-build` para a `axon-runtime` da mesma versão, então o Python das duas é o mesmo.
- **Alternatives**: três `Dockerfile`s (repetiriam o clone e o Python); fixar o `PYTHON_IMAGE` por digest (bom, mas
  à parte: o par build/runtime já sai coerente de cada rodada).

### R67 — Tag e publicação

- **Decision**: a tag da imagem é a do `axon` sem o `v` (`0.7.0-rc4`), e o registry é `ghcr.io/caioferreirab/`.
  `.github/workflows/images.yml`, só manual (`core_ref`): confere o formato `v<versão>`, recusa se qualquer das três já
  existe no registry (`docker buildx imagetools inspect`), roda o `check-build.sh` com `REGISTRY`/`VERSION` do registry
  (o driver `docker` do buildx, para o modelo construir `FROM` as imagens locais) e só então faz o push.
- **Rationale** (ADR-042, item 2: "imutável; nunca `latest`"): a tag do git já é a versão que o operador lê; a forma
  sem `v` é a convenção de tag de imagem. Publicar sem provar seria a única forma de uma imagem base quebrada chegar a
  uma instalação.
- **Alternatives**: a versão PEP 440 (`0.7.0rc4`; diverge da tag do git que o operador vê); publicar por push de tag
  no `axon` (o `axon-deploy` não recebe eventos do `axon` sem um token entre repositórios).

### R68 — O `Dockerfile` do modelo

- **Decision**: `ARG AXON_VERSION` (fonte única da versão do modelo; o `check-build.sh` a lê) e `ARG AXON_REGISTRY`;
  estágio `packs` `FROM axon-build`: `COPY config/packs.yaml`, `PACKS` com montagem SSH `packs` (não obrigatória: sem
  pack privado, nenhuma identidade) e `packages/` montado, instalado só se não vazio; `axon packs prepare && axon packs
  check`. Estágio final `FROM axon-runtime`: copia `/opt/axon`, `/opt/axon-data` e `config/` para `/etc/axon`, e fixa
  `AXON_ASSISTANTS_FILE` e `AXON_IDENTITY_CLIENTS_FILE`. `packages/` vem com um README (o bind exige o diretório).
- **Rationale** (ADR-041, ADR-042 item 3): nenhuma linha conhece pack; o `prepare` antes do `check` é o que o ADR-041
  pede. A configuração inteira na imagem é o item 4.
- **Alternatives**: instalar os packs no estágio de runtime (traria o `uv` de volta).

### R69 — O compose do modelo

- **Decision**: `compose.yml` com `name: axon`, só `image:` (a da instalação como placeholder `ghcr.io/SEU-USUARIO/
  SUA-INSTALACAO:sha-0000000`, a `axon-console` na versão do `AXON_VERSION`), nenhum `ports`, `build` ou arquivo montado
  (só volumes nomeados), `restart: unless-stopped`. Rede externa `proxy` com o nome em `${AXON_PROXY_NETWORK}`; apelidos
  `axon-console`, `axon-chat` e também `axon-api` (o modo sem interface precisa de um caminho até a API). As variáveis
  da plataforma são citadas uma a uma no `environment` do `axon` (no Portainer CE, só o que o compose cita chega ao
  contêiner), com `${VAR:?}` nas obrigatórias e `${VAR:-}` nos segredos opcionais (vazio vale como ausente), e
  `AXON_DISPLAY_NAME` com default `Axon` (vazio derrubaria o boot). `AXON_CHAT_URL` é o endereço do chat (`WEBUI_URL` e
  o retorno do OIDC). `compose.local.yml` acrescenta o `build`, as portas do host e redefine a rede de proxy como
  local (`axon-local-proxy`).
- **Rationale** (ADR-042, itens 3, 5 e 7): a stack do Portainer CE resolve caminhos relativos dentro dele, então nada é
  montado; os apelidos próprios evitam colisão com outras aplicações na mesma rede do proxy.
- **Alternatives**: `env_file: stack.env` (só existe no Portainer; o local usaria outro nome); publicar a porta da API
  (contraria "sem porta publicada").

### R70 — O workflow de release do modelo

- **Decision**: push na branch principal, tag `v*` ou manual; login no GHCR com o `GITHUB_TOKEN` (`packages: write`),
  que também lê as imagens base quando o repositório da instalação recebe acesso aos pacotes ("Manage Actions access");
  `PACKS` de uma variável do repositório; a deploy key `PACKS_DEPLOY_KEY` vira a identidade `packs` só quando
  cadastrada; tags `sha-<7>` e, numa tag do git, a versão sem `v`.
- **Rationale** (ADR-042, item 6, e Consequências: "acesso do repositório da instalação ao pacote, ou um token só de
  leitura"): um segundo login no mesmo registry com um token só de leitura trocaria a credencial do push; o acesso pelo
  pacote dispensa o token.
- **Alternatives**: um PAT só de leitura num segundo login (quebraria o push, como acima).

### R71 — O que sai do `axon-deploy`, e a prova

- **Decision**: saem o `Dockerfile`, o `docker-compose.yml`, o `.env.example` e o `config/` da instalação do
  mantenedor (o Qdrant, o scouting, os Assistants `scouting`/`geral`/`interno`, os endereços `localhost`), o
  `secrets/.gitignore`, `scripts/check-webui.py` e `scripts/dev-users.sh` — estes dois voltam, do histórico, no
  repositório da instalação do mantenedor (passo 4 do plano), com a prova da interface (FR-022), que passa a ser de cada
  instalação. O `.gitignore` ignora `config/` e `secrets/`, para os restos locais (fora do git) não aparecerem.
  `scripts/check-build.sh` reescrito (passos 1 a 6 do contrato), `build.yml` com só a deploy key do `axon` e o driver
  `docker`. O `packages/incompatible-pack` fica (copiado para um contexto temporário do modelo no passo 5).
- **Rationale** (ADR-042, Consequências): a referência perde o `PACKS` default, o passo do modelo do scouting, o Qdrant,
  os Assistants e os endereços do mantenedor; a prova da US5 é com o `generic` e o incompatível.
- **Alternatives**: manter a instalação do mantenedor aqui até o passo 4 (a referência continuaria conhecendo pack).

### R72 — O `ARG PACKS` é a fonte única (correção do modelo, 2026-10-21)

- **Decision**: o `compose.local.yml` e o `release.yml` do modelo deixam de passar `PACKS` como build-arg; vale o `ARG
  PACKS` do `Dockerfile`, que cada instalação fixa. Corrige R69 e R70.
- **Rationale**: achado ao montar a primeira instalação com pack (`axon-cfblabs`): um build-arg vazio — variável não
  definida — vence o default do `ARG`, e o pack sumia do build sem aviso; e o build local e o do CI podiam divergir.
- **Alternatives**: manter a variável do repositório e não ter default no `Dockerfile` (dois lugares para a mesma
  informação, como antes).
