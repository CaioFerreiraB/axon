# Research — 003 Assistants & Access (Fase 2: US1–US7)

Insumos: [spec.md](spec.md) (com as cinco clarificações de 2026-09-30), [design.md](design.md), ADR-002, ADR-008,
ADR-012, ADR-013; os seams já publicados pelos consumidores — `ExecutionGrant` da 005 (research R3 dela), portas
`Authenticator` e `GrantResolver` da 008 (research R1, R2 dela) — e o `assistants.yaml` da 011 (research R4 dela).
As decisões do `design.md` e dos ADRs aparecem como pré-aprovadas; as clarificações de 2026-09-30 aparecem em R3, R7,
R10, R11 e R12. Dois itens pedem ADR novo, ambos aceitos em 2026-09-30: R8 (persistência), por fixar uma convenção que
004, 005, 007 e 008 vão herdar — [ADR-015](../../docs/adr/ADR-015-persistencia-postgres-por-modulo.md) —, e R1, porque o grant carregar a `ModelPolicy` da 006 revê a direção
006 → 003 registrada no grafo e na 006 — [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md), achado C1 do `/speckit-analyze`.

## R1 — Os seams seguem a forma que os consumidores já publicaram

**Decision**: `api.py` publica `Authenticator`, `GrantResolver`, `AssistantDirectory` e `ApiKeyAdmin` como `Protocol`
e `Principal`, `ExecutionGrant`, `Limits` e os demais value objects como dataclasses congeladas. As assinaturas de
`authenticate` e `resolve` são as das portas da 008 — argumentos só por nome, `credential: str | None`, credencial
recusada devolve `None` em vez de levantar —, e o grant carrega `composition` (o `Composition` da 002) e `models` (a
`ModelPolicy` da 006), que é o que o `Protocol` da 005 exige. Importar os value objects da 006 faz a seta ser 003 → 006,
o inverso do que o grafo e a R1 da 006 registravam — decisão do [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md). `packs` vira propriedade derivada de `composition.packs`.

**Rationale** (ADR-012, decisão 6; 005 R3; 008 R1, R2): o seam pertence a quem o implementa — a 003 —, mas 005 e 008
já declararam *a forma que exigem* e foram construídas contra ela. O esboço do `design.md` (`NotAuthenticated`,
`packs: tuple[str, ...]`) é anterior a essas decisões. Adotar a forma já acordada custa nada e mantém a promessa das
duas specs: a 003 entra como troca de adapter, sem mudar o motor nem as rotas. `Principal` mantém o campo `subject` do
`design.md`; a 008, que hoje lê `id` de um `Protocol` próprio, passa a ler `subject` quando consumir este seam (R2).

**Alternatives considered**: seguir o esboço literal do `design.md` (levantar em credencial recusada e grant sem
`composition` obrigariam a 005 e a 008 a mudar código já aceito); acrescentar `id` como apelido de `subject` (dois
nomes para o mesmo dado num value object de segurança; a 008 muda de qualquer jeito para importar o seam).

## R2 — Esta passada entrega o módulo; o encaixe na API e no boot é das passadas de 008 e 011

**Decision**: as mudanças de código ficam em `ai_core/assistants/**` e `tests/assistants/**` (mais `pyproject.toml`,
import-linter e CI). A troca na plataforma em execução acontece nas passadas da Fase 2 dos módulos donos, na ordem do
roadmap: a **008** passa a importar `Principal`, `Authenticator`, `GrantResolver` e os erros de `ai_core.assistants.api`
(e aposenta as cópias das portas), extrai o token do cabeçalho, traduz os erros em status e expõe listagem, CRUD e
administração de chaves; a **011** constrói os serviços e adapters desta spec nos perfis, acrescenta a etapa de
validação de Assistants, registra os subcomandos e aposenta `bootstrap/grants.py`.

**Rationale** (princípio II; gate de fronteira do módulo; 011 plan, "Seam Notes": "o bootstrap troca o adapter e a
etapa de validação de Assistants entra na lista"): a Fase 1 foi construída do mesmo jeito — cada módulo com suíte
própria antes de a composition root existir. Editar rotas e boot daqui misturaria três specs numa passada e deixaria a
008 e a 011 com código que o plano delas não descreve. A exceção que a 008 lança para 404 é exemplo do problema: não
existe forma de a 003 levantar a exceção declarada pela 008 sem importá-la (seta invertida e ciclo); a 008 consumindo o
seam resolve isso na raiz.

**Alternatives considered**: a 003 editar `http/` e `bootstrap/` na mesma passada (viola o gate e antecipa decisões dos
planos de 008 e 011); um adaptador de tradução de exceções na composition root (código de transição sem dono, que a
passada da 008 apagaria em seguida).

## R3 — `assistants.yaml` herdado da Fase 1 e completado com o `design.md`

**Decision**: o arquivo continua o mesmo (`AI_CORE_ASSISTANTS_FILE`), com referência de modelo em texto
`provider/modelo`. Cada Assistant ganha `visibility` e `auth` (obrigatórios), `description`, `mcp`, `collections`,
`allowed_tools`, `write_tools` e `limits` (opcionais). A allowlist de modelos sai da raiz do Assistant para
`models.allow`, como no `design.md`. Duas seções novas no topo: `user_assistants.policies` (clarificação 1) e
`api_keys.admin_group` (clarificação 2). Formato completo em [contracts/assistants-yaml.md](contracts/assistants-yaml.md).

**Rationale** (011 R4: "o formato nasce aqui e é herdado"; `design.md`, "Assistants"; princípios IV e VII): `allow` na
raiz, ao lado de `auth.allow`, é a leitura errada mais cara possível — confundir allowlist de modelos com lista de
quem pode entrar amplia acesso. Por isso a chave antiga é recusada com mensagem que diz para onde ela foi, em vez de
aceita como apelido. `auth` sem default: numa fronteira de isolamento, esquecer a ACL não pode virar "todo mundo".
Erro de arquivo (YAML inválido, chave de topo desconhecida, política malformada) impede o boot; erro de **um**
Assistant o deixa indisponível com o motivo, e os demais servem (011 FR-003, US8).

**Alternatives considered**: formato do `design.md` com modelo como mapeamento `{provider, model}` (a 011 já fixou o
texto e `ModelRef.parse` existe; dois formatos para o mesmo dado); aceitar `allow` na raiz como apelido de
`models.allow` (mantém a ambiguidade que a mudança existe para matar); arquivo separado para políticas e chaves (duas
fontes para a mesma decisão de acesso, validadas em momentos diferentes).

## R4 — Ordem da resolução: 404 antes de tudo, orçamento por último

**Decision**: `resolve` segue esta ordem, e cada passo só roda se o anterior passou:

1. separar `<assistant>` do resto do id de modelo;
2. achar o Assistant — de sistema pelo nome, de usuário por (dono = `principal.subject`, nome);
3. ACL: esquema aceito **e** (`*` ou subject listado ou `group:<g>` com `g` nos grupos) — falha em 2 ou 3 levanta
   `AssistantNotFound` com a mesma mensagem;
4. de usuário: política aplicável ao Principal e conformidade com ela;
5. disponibilidade: flow, composição de packs (002), MCPs e coleções (R11) — falha levanta `AssistantUnavailable`
   com os motivos;
6. restrição pedida (R5) — fora do permitido levanta `RequestRejected(field="model")`;
7. orçamento (R9) — excedido levanta `RateLimited(retry_after)`;
8. montar o grant.

**Rationale** (FR-006, SC-001, princípio VII, elo 7): ACL antes de disponibilidade é o que impede um Assistant privado
quebrado de se revelar por um erro diferente. Orçamento por último faz só requisições que de fato executariam
consumirem a cota — uma requisição recusada por 400 não gasta modelo, então não precisa gastar orçamento. Os passos 2
e 3 não fazem I/O para Assistants de sistema e fazem exatamente uma leitura para os de usuário, seja ele inexistente
ou alheio: o caminho é o mesmo, e é isso que torna os dois casos indistinguíveis também no tempo.

**Alternatives considered**: disponibilidade antes da ACL (vaza existência pela mensagem); orçamento antes da
validação (um cliente com erro de formato esgotaria a própria cota sem executar nada); orçamento antes da ACL (daria
429 a quem deveria receber 404).

## R5 — A requisição restringe pelo id de modelo, dentro da allowlist

**Decision**: gramática do id — `<assistant>` ou `<assistant>/<parte>`. Se a parte contém `/`, é uma referência
completa `provider/modelo` (`ModelRef.parse`); sem `/`, é um modelo do provider do papel `generation` declarado (a
forma da Fase 1). O modelo pedido substitui só o papel `generation` e precisa casar com a allowlist do Assistant
**na resolução**, com a mesma regra da 006 (`fnmatchcase` sobre `provider/modelo`); a 006 confere de novo na chamada.
Allowlist vazia é inválida (edge case), e os modelos declarados por papel também precisam casar com ela.

**Rationale** (US4 cenários 1 e 3; FR-005; `design.md`, "Requisição: só restringe"; 006 FR-003): o cenário 1 pede um
modelo de outro provider e espera "modelo não permitido" — o id precisa poder nomear o provider. Recusar na resolução
entrega a SC-005 (rejeição antes de qualquer chamada de modelo); a checagem da 006 continua como segunda linha, e as
duas não podem divergir: um teste da suíte compara as duas regras sobre o mesmo conjunto de casos. `ollama/qwen3:8b`
e `qwen3:8b` continuam valendo para quem já usava a forma curta.

**Alternatives considered**: só a forma curta (provider fixo; o cenário 1 perderia sentido); só a forma completa
(quebra ids que clientes da Fase 1 já usam); deixar a allowlist só para a 006 (a recusa viria depois de montar a
execução, contra a SC-005).

## R6 — OIDC: verificação local do JWT com JWKS do provedor

**Decision**: a porta `OidcVerifier.verify(token)` devolve as claims de um token cuja assinatura, `iss`, `aud` e
algoritmo foram conferidos, ou `None`. O adapter real (`adapters/oidc.py`) usa **PyJWT com `cryptography`** e busca o
JWKS por **httpx** — pelo documento de descoberta do emissor ou por URL configurada —, com cache, nova busca quando
aparece um `kid` desconhecido e intervalo mínimo entre buscas. Algoritmos aceitos: lista fechada de assimétricos
(`RS256`, `ES256`); `none` e HMAC são recusados. `exp`, `nbf` e `iat` são conferidos no `domain/` contra a porta
`Clock`, com tolerância configurável. Principal: `user:<claim de subject>` (default `sub`), grupos da claim configurada
(default `groups`), esquema `oidc`.

**Rationale** (`design.md`: "OidcVerifier — JWKS do provedor"; princípio XIII: tempo por porta, biblioteca de OIDC
fora de `api.py`/`domain/`/`service.py`): verificar localmente não põe rede no caminho de cada requisição. A lista
fechada de algoritmos fecha a confusão de algoritmo (token HMAC assinado com a chave pública). Conferir o tempo no
domínio faz expiração ser testável com relógio fixo, sem depender do relógio da biblioteca. O teste do adapter real
assina tokens com chaves geradas na própria suíte e serve o JWKS por um transporte em memória do httpx — sem provedor
externo.

**Alternatives considered**: introspecção no provedor a cada requisição (rede no caminho de toda chamada, e o
provedor vira ponto único de falha); Authlib/joserfc (mais superfície do que o necessário para verificar JWT); deixar
a biblioteca conferir `exp` (o relógio sairia da porta, e o teste de expiração dependeria de `sleep` ou de mock
global).

## R7 — Chaves de API: hash no armazenamento, emissão pela CLI e pela superfície privada

**Decision**: formato `aic_<key_id>_<segredo>` — `key_id` de 8 bytes em hexadecimal, público, usado para listar e
revogar; segredo de 32 bytes. Guarda-se o SHA-256 da chave inteira, nunca a chave. Verificação: extrair o `key_id`,
ler o registro, comparar o hash em tempo constante (`hmac.compare_digest`), recusar se revogada. Sem cache: a
revogação vale na requisição seguinte. A aleatoriedade vem da porta `TokenGenerator`. Administração: `ApiKeyAdmin`
exige que o ator pertença ao `api_keys.admin_group`, e quem não pertence recebe `NotFound` (404, US2 cenário 5); a CLI
fala com o serviço com a autoridade do operador — quem tem o host é o operador —, e é por ela que sai a primeira chave.

**Rationale** (clarificação 2; FR-015; princípio XIII: aleatoriedade por porta): a chave tem 256 bits de entropia, então
um hash rápido basta — KDF lenta (bcrypt, Argon2) existe para senha escolhida por gente e só custaria CPU a cada
requisição na VM de 2 OCPU. O `key_id` visível permite revogar sem ter a chave e mantém a busca num índice exato.
Consultar o armazenamento em toda requisição é o preço de "revogação sem restart"; numa tabela pequena e indexada, o
custo é uma leitura.

**Alternatives considered**: hash na configuração versionada (revogar exigiria deploy — descartado na clarificação);
cache de chaves válidas por alguns segundos (revogação deixaria de ser imediata); busca pelo hash da chave inteira sem
`key_id` (funciona, mas a listagem e a revogação precisariam de outro identificador de qualquer jeito).

## R8 — Postgres: psycopg 3, um schema por módulo, migrações do próprio adapter

**Decision**: os adapters `assistants_postgres.py` e `api_keys_postgres.py` usam **psycopg 3** (API assíncrona) e
recebem um `AsyncConnectionPool` (`psycopg-pool`) construído pela composition root. As tabelas ficam no schema
Postgres `assistants`, que só esta spec conhece; o DDL vive em arquivos SQL numerados em `adapters/sql/`, aplicados em
ordem por `migrate(pool)`, com trava consultiva e tabela de versão dentro do próprio schema. Timestamps vêm da porta
`Clock`, nunca de `now()` no SQL. Registrado como convenção de todos os módulos no
[ADR-015](../../docs/adr/ADR-015-persistencia-postgres-por-modulo.md).

**Rationale** (constituição, stack: "PostgreSQL — adapters das portas de armazenamento de cada módulo"; princípio II:
tabelas são internals do dono; princípio XII): esta é a primeira spec a tocar Postgres, e 008 (Fase 2), 004, 005 e 007
(Fase 3) vão seguir o que for decidido aqui — por isso o ADR. psycopg 3 é o driver de referência, tem API assíncrona e
wheels `cp314` para ARM64. Schema por módulo torna a fronteira física: nenhum módulo lê tabela de outro sem que isso
apareça no SQL. SQL versionado no próprio adapter mantém a migração junto do código que depende dela, sem ORM.

**Alternatives considered**: asyncpg (mais rápido, só assíncrono; a CLI e as migrações ganhariam pouco e a biblioteca
tem tipagem mais pobre); SQLAlchemy + Alembic (ORM e ferramenta de migração para quatro tabelas; contraria o princípio
XII); tabelas com prefixo no schema `public` (fronteira por convenção de nome, não por espaço de nomes).

## R9 — Orçamento: janela deslizante de 60 s por (Principal, Assistant)

**Decision**: `rpm` limita o número de execuções concedidas em qualquer janela de 60 s para o par (subject,
Assistant). A regra é pura (`domain/rate.py`): dada a lista de instantes do par, o instante atual e o limite, decide e
calcula `retry_after` — quanto falta para o instante mais antigo sair da janela. A porta `RateCounterStore` oferece uma
operação atômica, `acquire`, e o adapter em memória aplica a regra num processo único. Assistant sem `limits.rpm` usa
60. `max_iterations` e `max_context_tokens` viajam no grant; quem os aplica é o motor (Fases 3 e 5).

**Rationale** (US7 cenário 1: "a 21ª requisição no minuto recebe 429"; `design.md`: memória, processo único; ADR-013:
tempo por porta): a janela deslizante é a leitura literal do cenário e não permite o pico duplo da janela fixa na
virada do minuto. Com o limite na casa das dezenas, guardar os instantes custa pouco. Operação atômica na porta evita a
corrida "ler, decidir, gravar" quando houver outro adapter.

**Alternatives considered**: janela fixa por minuto do relógio (até 2×`rpm` em 60 s na virada); balde de fichas/GCRA
(guarda um número só, mas o comportamento sob rajada é menos óbvio de explicar ao operador); sem limite quando `rpm`
não é declarado (orçamento é controle de segurança, elo 7 — ausência não pode virar ilimitado).

## R10 — Assistants de usuário: política por grupo, prefixo `~`, dono único

**Decision**: políticas em `user_assistants.policies`, avaliadas em ordem; vale a primeira cujo `match` (`*` ou
`group:<g>`) casa com o Principal. A política fixa packs, flows e coleções permitidos, a allowlist de modelos, o teto
de cada limite e se tools de escrita são permitidas. O Assistant de usuário é sempre privado, aceita os dois esquemas
e tem o dono como único permitido; sua allowlist de modelos **é** a da política; limite ausente assume o teto.
Endereço `~<nome>`, único por (dono, nome); atualização é "a última escrita vence". Conformidade conferida na criação,
na atualização e em cada resolução — na resolução, contra a política aplicável *naquele momento*.

**Rationale** (clarificações 1, 4 e 5; FR-009, FR-014, FR-017; edge case "política mais restrita depois de um
deploy"): primeira que casa é a regra que o operador consegue prever lendo o arquivo; unir políticas daria a quem está
em dois grupos o que nenhuma política concede. Fixar a allowlist do Assistant de usuário na da política evita comparar
padrões `fnmatch` entre si, que não tem resposta exata. Um dono só, editando os próprios Assistants, não justifica
controle de versão otimista.

**Alternatives considered**: allowlist própria no Assistant de usuário, "contida" na da política (subsunção de padrões
não é decidível de forma simples); conformidade só na criação (um usuário que sai do grupo manteria o que perdeu);
nomes de usuário únicos na instalação (a mensagem "nome em uso" revelaria Assistants de outros usuários).

## R11 — MCPs e coleções por portas que esta spec declara, vazias até os donos chegarem

**Decision**: `ports.py` declara `McpDirectory.aliases(owner=...)` — aliases que um Assistant pode referenciar:
globais para Assistants de sistema (`owner=None`); do dono e globais permitidos para Assistants de usuário — e
`CollectionCatalog.names()`. Os adapters desta fase (`adapters/catalogs.py`) devolvem conjuntos vazios; a suíte usa
catálogos em memória com entradas. Referência fora do catálogo deixa o Assistant indisponível, com a mesma mensagem
para "não existe" e "é de outro usuário".

**Rationale** (clarificação 3; FR-016; US6 cenário 2): é o padrão que 005, 006 e 008 usaram na Fase 1 — quem consome
declara a forma, o dono entrega o valor, e a 007 (Fase 3) e o índice (Fase 5) entram como troca de adapter. As duas
portas são assíncronas porque os donos vão ler de armazenamento.

**Alternatives considered**: aceitar referências sem validar até a Fase 3 (aliases fantasmas entrariam no grant);
recusar `mcp` e `collections` não vazios como erro de configuração (a US6 não seria testável nesta fase).

> Nota de 2026-10-09 (passada de encaixe da Fase 5, 011 research R35): as coleções vêm do Pack Registry
> (`PackCollectionCatalog`) — as que os retrievers dos packs habilitados declaram —, porque o índice mora no pack. A
> porta não mudou.

## R12 — `visibility` muda defaults de segurança, não a listagem

**Decision**: descoberta = exatamente o conjunto que o Principal resolveria, excluídos os indisponíveis. Validação: um
Assistant público com `write_tools` é inválido; um privado com `*` em `auth.allow` é inválido. A gestão dos próprios
Assistants (`mine`) mostra também os indisponíveis, com o motivo, para que o dono possa corrigi-los.

**Rationale** (clarificação 4; FR-008, FR-012): uma regra só para listagem e resolução impede que as duas divirjam — o
que você vê é o que você usa. Esconder da descoberta o que não resolve evita um "modelo" no menu que só responde erro;
mostrá-lo na gestão evita que o dono perca de vista o que deixou de funcionar.

**Alternatives considered**: listar indisponíveis na descoberta com marcação (o formato de modelos da OpenAI não tem
onde pôr a marca, e clientes padrão mostrariam uma opção quebrada).

## R13 — Campos de ampliação: a lista é desta spec, a aplicação é da borda

**Decision**: `api.py` publica `WIDENING_FIELDS` — `packs`, `mcp`, `mcp_servers`, `collections`, `provider`, `flow`,
`limits`, `allowed_tools`, `write_tools`, `tools`, `functions`, `tool_choice`, `function_call`. A 008 recusa esses
campos no corpo da requisição, nomeando o campo, antes de pedir o grant; o único canal de restrição que chega aqui é o
id de modelo (R5).

**Rationale** (FR-007, SC-005; Module Boundary: "Não conhece o protocolo HTTP"): o que amplia capacidade é decisão da
fronteira de isolamento, então a lista mora aqui; ler o corpo da requisição é da borda. A 008 já recusa `tools` e
companhia desde a Fase 1 — ao consumir a lista, a regra passa a ter um dono só.

**Alternatives considered**: a 008 manter a própria lista (duas fontes para uma regra de segurança); `resolve` receber
o corpo inteiro (a 003 passaria a conhecer o formato da API).

## R14 — Validação de referências entregue agora, com relatório por Assistant

**Decision**: `service.validate()` devolve um `ValidationReport` com o estado de cada Assistant — disponível ou não, e
os motivos. Cobre os de sistema por inteiro e, dos de usuário, as referências; a conformidade com a política depende
dos grupos do Principal, conhecidos só na resolução. `adapters/cli.py` oferece os comandos `assistants validate` e
`keys create|list|revoke` como funções que recebem o serviço pronto e a saída; quem os registra na raiz `ai-core` é a
011 (US4).

**Rationale** (FR-011; 011 FR-002 — a etapa "validação de Assistants" — e 011 US4, ambas da Fase 2): a US8 é P3, mas a
etapa de boot e o `assistants validate` da 011 dependem desta função, e as regras são as mesmas que a resolução já
aplica — é a mesma verificação, rodada sobre todos de uma vez. Deixar a CLI em funções que recebem o serviço mantém a
decisão do framework de linha de comando com a 011.

**Alternatives considered**: validar só na resolução (a falha apareceria na primeira requisição, não no boot —
contra o princípio VII); a 003 montar o próprio `argparse` (anteciparia a decisão da US4 da 011).

## R15 — `AssistantStore` do `design.md` vira duas portas

**Decision**: `AssistantConfigSource.load()` — síncrona, lida uma vez no boot; adapters YAML e memória — e
`UserAssistantStore` — assíncrona, CRUD por (dono, nome); adapters memória e Postgres.

**Rationale** (princípio XIII: porta por I/O e por troca prevista): o `design.md` lista uma porta com dois tipos de
adapter, mas os dois lados não se parecem — um é configuração somente leitura, lida uma vez; o outro é armazenamento
com escrita por requisição. Uma porta só obrigaria o YAML a implementar escrita que recusa e o Postgres a implementar
carga de arquivo. Os adapters são os mesmos que o `design.md` nomeia.

**Alternatives considered**: uma porta com métodos opcionais (conformidade ambígua: o que o adapter YAML deve fazer num
`insert`?).

## R16 — Estratégia de teste

**Decision**: `tests/assistants/unit/` para `domain/` (regras puras: ACL, gramática do id, política, conformidade,
formato de chave, janela deslizante, tempo de token); `contract/` para os quatro seams — com uma suíte adversarial
para SC-001, SC-002 e SC-005 que usa hypothesis para gerar Assistants e pedidos e confere que o grant nunca excede o
declarado — e para cada porta secundária, parametrizada entre o adapter em memória e o real; `integration/` para o
Postgres real (pulada sem `AI_CORE_TEST_POSTGRES_DSN`, como o Ollama da 006) e para os comandos da CLI. A CI do core
ganha um serviço Postgres, e a suíte das portas roda contra ele em todo PR.

**Rationale** (princípio XIII: toda porta secundária tem adapter em memória e suíte de conformidade contra os dois;
governança: todo PR passa nas suítes das portas): sem Postgres na CI, a conformidade contra o adapter real vira
opcional na prática. OIDC real não precisa de serviço: o JWKS sai de um transporte em memória.

**Alternatives considered**: Postgres só local (a regra da governança deixaria de ser verificada em PR);
testcontainers (mais uma dependência para o que um serviço da CI já oferece).

## R17 — Dependências novas

**Decision**: na distribuição `ai-core` — `pyjwt[crypto]>=2.10,<3`, `httpx>=0.28,<1` (hoje só transitiva, pelo SDK da
006), `psycopg[binary]>=3.2,<4` e `psycopg-pool>=3.2,<4`. O import-linter confina `jwt`, `httpx`, `psycopg`,
`psycopg_pool`, `cryptography` e `yaml` a `ai_core/assistants/adapters/`.

**Rationale** (princípio XIII; restrições de ambiente: ARM64): todas têm wheel `cp314` para `aarch64` (conferido em
2026-09-30: `psycopg-binary` 3.3.6, `cryptography` 50.0.1). `httpx` explícito porque passa a ser usado diretamente;
depender dele só por transitividade quebraria no dia em que o SDK trocar de cliente.

**Alternatives considered**: `urllib` da biblioteca padrão para o JWKS (síncrono, bloquearia o laço de eventos na
primeira requisição após a rotação de chaves).

---

# Fase 3 (2026-10-02): passada de encaixe

Insumos: as duas clarificações de 2026-10-02; as pendências para a 003 nos planos da 004 ("Seam Notes": exemplo com
namespace, colisão alias × pack), da 005 (R33: papel `controller`) e da 007 (nada de código: a 011 liga o registry);
[ADR-019](../../docs/adr/ADR-019-papeis-por-flow-no-seam-execution-engine.md). O registry real da 007 já está ligado
como `McpDirectory` (passada da 011).

## R18 — Escopo da passada

**Decision**: três regras novas de validação de referências — papéis exigidos pelo flow, entradas de `allowed_tools` e
`write_tools`, colisão de alias MCP com pack — aplicadas aos Assistants de sistema (boot, `assistants validate`,
resolução) e de usuário (criação, atualização, resolução); o exemplo de `allowed_tools` com namespace no contrato do
`assistants.yaml`. Toques declarados: 005 (o método `flow_roles()` no seam, ADR-019) e 011 (injetar o mapeamento).

**Rationale**: é o que as outras specs deixaram para a 003 na Fase 3, com as clarificações.

**Alternatives considered**: deixar para a Fase 5 (o `agentic` já está no ar pela 011; Assistant mal configurado
apareceria disponível agora).

## R19 — Papéis por flow chegam como dado, como os nomes de flow

**Decision**: `AssistantsService` ganha `flow_roles: Mapping[str, tuple[ModelRole, ...]] | None = None` (ausente =
nenhuma exigência — as suítes da Fase 2 continuam valendo). Uma função pura, `role_reasons(definition, flow,
flow_roles)`, devolve `"models: o flow '<flow>' exige o papel '<papel>', que o Assistant não declara"` para cada papel
exigido pelo **flow efetivo** (o declarado, ou o derivado do pack — `effective_flow`) e ausente de `definition.roles`.
A 011 passa `engine.flow_roles()`, que a 005 publica (ADR-019).

**Rationale**: ADR-019; a regra vive na 005, a 003 só compara. `ModelRole` é value object da 006, que a 003 já importa
(ADR-016).

**Alternatives considered**: ver ADR-019.

## R20 — Entradas de `allowed_tools` e `write_tools`

**Decision** (clarificação 2): `tool_reasons(definition, pack_tools)`, pura, para cada entrada das duas listas (o campo
nomeado no motivo):

| Entrada | Motivo |
|---|---|
| sem `.` | `"<campo>: '<entrada>' precisa de namespace: <pack>.<tool> ou <alias>.<tool>"` |
| namespace (antes do **primeiro** `.`) fora de `packs` e `mcp` do Assistant | `"<campo>: '<entrada>': '<ns>' não é pack nem MCP deste Assistant"` |
| namespace de pack, e o resto não está entre as tools e os retrievers que o pack oferece | `"<campo>: '<entrada>': o pack '<ns>' não oferece '<tool>'"` |
| namespace de alias MCP | nenhum — o nome da tool exigiria rede; a 004 responde "tool inexistente" |

`pack_tools`: por pack da composição, os nomes de `PackCapabilities.tools` e dos `retrievers` (o retriever vira a tool
`<pack>.<retriever>`, 002 seam Pack Toolset). Pack sem capacidades (em erro) é pulado: o erro de composição já está
nos motivos.

**Rationale**: a comparação da 004 é exata e com namespace (clarificação 1 da 004); entrada que nunca casa é
configuração que parece funcionar e não funciona. O catálogo do pack está carregado no Pack Registry, que a 003 já
consome — sem rede e sem o seam Pack Toolset.

**Alternatives considered**: ver a clarificação 2; consultar o Pack Toolset da 002 (a 003 não consome esse seam, e o
Pack Registry já dá os nomes).

## R21 — Colisão de alias MCP com pack do mesmo Assistant

**Decision**: `collision_reasons(definition)`: para cada alias de `mcp` que é também nome em `packs`, `"mcp: o alias
'<alias>' colide com o pack '<alias>': as tools '<alias>.<tool>' seriam ambíguas"`.

**Rationale**: nota da 004 ("Seam Notes", 003): o catálogo dela levanta `CatalogConflict` na execução; aqui a mesma
configuração é recusada antes de servir. Alias de usuário começa com `~` e pack não, então só alias global colide.

**Alternatives considered**: deixar para o `CatalogConflict` na execução (falha tardia).

## R22 — Onde as regras se aplicam

**Decision**: as três funções entram em `reference_reasons` — a mesma usada pela resolução, pelo boot e pelo `assistants
validate` (R14) —, e também em `_conform` (criação e atualização de Assistant de usuário): ali, o primeiro motivo vira
`RequestRejected` nomeando o campo (`models`, `allowed_tools`, `write_tools` ou `mcp`), como as violações de política
já fazem.

**Rationale**: FR-011 e FR-014 ("validado na criação, na atualização e em cada resolução"); uma função só, para que
validação e resolução nunca discordem.
Efeito visível: um Assistant `agentic` sem `controller` passa de 400 (o motor recusava na chamada, 005 R25) a 424
"Assistant indisponível" com o motivo do papel, porque a resolução já o barra — o mesmo tratamento de qualquer
referência pendente.

**Alternatives considered**: só na validação (o usuário criaria um Assistant que nunca resolve, sem saber por quê).

## R23 — Testes

**Decision**: unidade das três funções (`tests/assistants/unit/`); cenários US8 2–4 na suíte de validação; criação e
atualização de Assistant de usuário recusadas com o campo; e, nos toques, `flow_roles()` na conformidade do registro de
flows da 005 (com e sem `capabilities`) e a validação de um Assistant `agentic` sem `controller` pelo boot real
(`tests/bootstrap`). Marca `us8` na validação e `us6` nos de usuário.

**Rationale**: o padrão das suítes da Fase 2 (R16).

**Alternatives considered**: só unidade (a injeção pela 011 ficaria sem prova).

## R24 — JWKS com entradas que não são de assinatura (2026-10-13)

**Decision**: o `JwksOidcVerifier` guarda só as chaves de assinatura (`use` ausente ou `sig`) e ignora, uma a uma, as
entradas que o PyJWT não carrega; só erro de rede ou documento malformado descarta a atualização.

**Rationale**: provedores reais publicam chaves de cifragem no mesmo JWKS — o Keycloak sempre tem uma `RSA-OAEP` com
`use: enc`. Antes, essa entrada fazia o `PyJWK` levantar dentro do laço, a atualização inteira era abandonada e todo
token era recusado (achado na prova do Open WebUI, 002 research R40). Ignorar a chave de cifragem não abre nada: ela não
serve para verificar assinatura, e um token que a nomeie continua sem chave e é recusado.

**Alternatives considered**: filtrar só por `alg` conhecido (deixaria passar uma chave RS256 marcada `use: enc`).

# Fase 9 (2026-10-14): superfície de administração e sobreposições

## R25 — Três superfícies: `SCHEMES_OF_SURFACE`

**Decision**: `Surface = Literal["public", "private", "admin"]`, `ADMIN_SURFACE = "admin"`, e o seam
`SCHEME_OF_SURFACE` vira `SCHEMES_OF_SURFACE: Mapping[str, frozenset[Scheme]]` = `{public: {oidc}, private: {api_key},
admin: {oidc, api_key}}` (ADR-031). `SCHEME_OF_SURFACE` continua exportado por uma série, derivado do novo para as duas
superfícies antigas, marcado como depreciado no docstring. No `authenticate`, a superfície com dois esquemas decide pelo
formato: `parse_key(credencial)` reconhece o prefixo `aic_` → caminho de chave; senão, OIDC.

**Rationale**: a 008 só precisa saber os esquemas da superfície; o despacho pelo formato é determinístico e não exige
tentar os dois caminhos.

**Alternatives considered**: tentar OIDC e cair para chave (dois custos e mensagens de erro ambíguas); cabeçalho
diferente por esquema (cliente teria que saber, sem ganho).

## R26 — Audiência por superfície e chaves em processo

**Decision**: a porta `OidcVerifier.verify(token, *, audience: str)` passa a receber a audiência esperada; o
`AccessService` recebe `OidcAudiences(public="ai-core", admin="ai-core-admin")` (configurado pela 011 a partir dos
clientes da 012) e passa a da superfície. O `JwksOidcVerifier` mantém a lógica (algoritmos assimétricos, emissor,
`exp`, chaves só de assinatura — R24) e ganha uma fonte de chaves plugável: `JwksSource` = `HttpJwksSource` (descoberta
ou `AI_CORE_OIDC_JWKS_URL`, o caminho atual, com cache) ou `CallableJwksSource(fn)` (a função `jwks()` do seam
`PublicKeySet` da 012, injetada pela 011, sem rede). Token de outra audiência → `None` (401 na 008).

**Rationale**: ADR-030 (verificação local, emissor único) e ADR-031 (token do chat não alcança a administração); a 003
continua sem importar a 012 — só recebe uma função.

**Alternatives considered**: dois verificadores, um por audiência (duplicaria cache e configuração); aceitar as duas
audiências nas duas superfícies (anularia o ADR-031).

## R27 — Admin pelo grupo, em qualquer esquema

**Decision**: `is_admin(principal, admin_group)` = `admin_group is not None and admin_group in principal.groups`. O
`AdminGate` da 008 continua sendo o `AccessService.is_admin`.

**Rationale**: cada superfície já limita os esquemas que aceita (R25); o esquema deixou de ser critério (ADR-031).

**Alternatives considered**: manter `api_key` obrigatório (a console não existiria).

## R28 — Flag `overrides` e impressão digital da seção

**Decision**: `AssistantDefinition.overrides: frozenset[Literal["models", "mcp"]]` lido de `overrides` no YAML (ausente
= vazio; valor desconhecido = problema do Assistant). Funções puras em `domain/overrides.py`:
`section_fingerprint(definition, section)` = SHA-256 do JSON canônico da seção — `models`: os papéis declarados (a
allowlist fica de fora: ela é o teto, não a seção sobreposta); `mcp`: aliases ordenados e as entradas com namespace MCP de
`allowed_tools`/`write_tools`. `effective(definition, overrides) -> (definition, states)`: para cada seção com
sobreposição guardada, `active` se a seção está em `overrides` **e** a impressão digital guardada é igual à atual;
senão `inactive` com motivo `"o deploy não permite mais"` ou `"o deploy mudou a seção"` (clarificação de 2026-10-13).

**Rationale**: o deploy sempre vence (ADR-032); a impressão digital torna "mudou" uma comparação, sem guardar o YAML
antigo inteiro.

**Alternatives considered**: comparar o YAML inteiro do Assistant (qualquer mudança em outra seção inativaria a
sobreposição sem motivo).

## R29 — Conteúdo e validação das sobreposições

**Decision**: `models`: `Mapping[ModelRole, ModelRef]` dos papéis; cada `ModelRef` casa `models.allow` do YAML; a
validação de papéis por flow (R18) roda sobre a definição efetiva. `mcp`: `aliases`, `allowed: frozenset[str]` e
`write: frozenset[str]`, todas as entradas com namespace de um alias da própria sobreposição; a efetiva troca só as
entradas de MCP de `allowed_tools`/`write_tools` e mantém as de pack. Se o YAML não declara `allowed_tools` (tudo
permitido) e a sobreposição restringe MCP, a lista efetiva vira: todas as tools dos packs (como a validação já enumera)
mais as tools de MCP escolhidas. Gravar roda `static_reasons`/`reference_reasons`/`role_reasons`/`tool_reasons`/
`collision_reasons` e a FR-012 (escrita em público) sobre a efetiva: qualquer motivo → `RequestRejected(field=...)`.

**Rationale**: a mesma régua da criação de Assistant de usuário (FR-020); a sobreposição nunca amplia o YAML.

**Alternatives considered**: sobrepor a allowlist (rejeitado no ADR-032).

## R30 — Armazenamento, versão e histórico

**Decision**: porta `SystemOverrideStore` (`get(name)`, `all()`, `put(name, section, payload, fingerprint, actor,
expected_version)`, `delete(name, section, actor, expected_version)`, `history(name)`), memória e Postgres
(`sql/003_system_overrides.sql`: `system_overrides(assistant, section, payload jsonb, fingerprint, version, updated_by,
updated_at, PK(assistant, section))` e `system_override_history(id, assistant, section, payload, fingerprint, version,
actor, at, action)`). Versão desatualizada → `Conflict`. `put` e `delete` gravam o histórico na mesma transação.

**Rationale**: FR-021 (autor, instante, versão, histórico); ADR-015.

**Alternatives considered**: histórico só no log (não consultável pela aba "Histórico" da console).

## R31 — Seam `SystemAssistantAdmin` e configuração efetiva no serviço

**Decision**: seam novo no `api.py` (contrato em [contracts/assistants-api.md](contracts/assistants-api.md), seção
Fase 9), implementado pelo `AssistantsService`: `system_assistants(actor)`, `system_assistant(name, actor)`,
`override_models(...)`, `override_mcp(...)`, `discard_override(...)`, `history(...)`, todos exigindo `is_admin` (404
para os demais) e `declared_models()` para a saúde. O serviço passa a resolver a definição efetiva em `_find`,
`discover` e `validate` com um cache por processo invalidado a cada gravação (TTL de segurança de 5 s), e o `resolve`
nunca usa sobreposição inativa nem inválida (indisponível com motivo `override.<seção>`). Modelos candidatos para
"testar modelo" são da 008 com o Model Router (006): o seam devolve a allowlist e os papéis.

**Rationale**: a regra mora onde a configuração efetiva é usada; a 008 só traduz HTTP (ADR-029).

**Alternatives considered**: a 008 montar a efetiva (duplicaria a regra fora do dono).

## R32 — Testes da Fase 9

**Decision**: unidade de `domain/overrides.py` (impressão digital estável, estados, mesclagem de `allowed_tools`);
conformidade do `SystemOverrideStore` (memória × Postgres; versão; histórico); suíte adversarial do seam (fora da
allowlist → `RequestRejected`; seção não liberada; escrita em público; MCP apagado → indisponível com motivo; flag
removida → inativa; seção mudada → inativa; conflito de versão; não admin → `NotFound`); autenticação nas três
superfícies (token da console na pública e do chat na administração recusados; chave de admin na administração aceita).
Marcas `us9` e `us10`.

**Rationale**: SC-006 e SC-007 são adversariais.

**Alternatives considered**: —
