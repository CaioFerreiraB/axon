# Research — 101 Scouting Pack, Fase 4 (US1, US2, US3)

Insumos pré-aprovados: [design.md](design.md), [spec.md](spec.md) §Clarifications (sessão de 2026-10-07),
[ADR-004](../../docs/adr/ADR-004-contratos-no-repo-do-core.md), [ADR-006](../../docs/adr/ADR-006-rag-first-default-scouting.md),
[ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md),
[ADR-014](../../docs/adr/ADR-014-politica-versoes-0x-contratos.md), [ADR-021](../../docs/adr/ADR-021-workspace-ai-core-permanece-no-repositorio-da-plataforma.md);
constituição (princípios I, II, V, VI, VII, IX, XII, XIII). Código de referência: `ai-core-contracts` 0.1.0 na tag
`contracts-v0.1.0` (contrato de pack, `TurnView`, kit `ai_core_contracts.testing`), o Pack Runtime (002) e o
`ai-generic` (010), o exemplo a copiar. Escopo: **US1, US2 e US3**; a US4 (prioridade de fontes medida) e a US5
(`rag_first`, retriever, validators) são Fase 5.

## R1 — Onde o pack mora e como o repositório se liga

**Decision** (ADR-021): repositório privado `CaioFerreiraB/ai-scouting`, ligado no `agentic-app` como submódulo
`ai-scouting/` (criado em 2026-10-07). O código do pack é commitado lá; no `agentic-app` só muda o ponteiro do submódulo,
junto com o SDD da passada. Layout de distribuição na raiz do repositório (`pyproject.toml`, `src/ai_scouting/`,
`tests/`), como o design.md prevê.

**Rationale**: a Fase 4 existe para provar a arquitetura de packs com um pack real em repositório próprio (roadmap);
o submódulo mantém os caminhos que as specs `1xx` e as skills citam.

**Alternatives considered**: subpasta deste repositório (não prova a separação que a fase quer provar); clone ao lado
(specs passariam a citar outro repositório).

## R2 — Dependência de `ai-core-contracts`

**Decision** (ADR-014, ADR-021): `dependencies = ["ai-core-contracts>=0.1,<0.2"]` — a faixa derivada da
`contract_version = "0.1"` — e, em `[tool.uv.sources]`, `ai-core-contracts = { git =
"ssh://git@github.com/CaioFerreiraB/agentic-app.git", tag = "contracts-v0.1.0", subdirectory =
"ai-core/packages/contracts" }`. Nenhuma outra dependência de runtime (FR-001). `uv.lock` versionado.

**Rationale**: é a forma que um pack externo declara (010 R2), agora apontando para a tag de verdade. Verificado em
2026-10-07 num projeto descartável: o `uv lock` resolve os contratos do commit da tag, por SSH, com o subdiretório. A
etapa de distribuição da conformidade confere a faixa declarada na instalação normal (SC-003).

**Alternatives considered**: URL `https://github.com/caio/ai-core` com `subdirectory = "packages/contracts"` do
design.md (superada pelo ADR-021 — o repositório é o `agentic-app`); índice de pacotes privado (sem consumidor que
exija, ADR-021).

## R3 — Piso de Python e matriz

**Decision**: `requires-python = ">=3.12"` (o piso dos contratos, como o `ai-generic`). A suíte padrão roda em 3.12
(piso) e 3.14 (o Python do core); o grupo `platform` (R9) só em 3.14.

**Rationale**: um pack depende só dos contratos; o 3.14 é exigência do core, não do pack.

**Alternatives considered**: `>=3.14` (prenderia o pack ao Python do core sem motivo do pack).

## R4 — Manifest e identidade na Fase 4

**Decision** (clarificação 1): `name = "scouting"`, `contract_version = "0.1"` como atributos de classe;
`manifest()` devolve `PackManifest(name="scouting", version="0.1.0")` — sem `preferred_flow`, `requires_collections` e
`config_schema`, que chegam na Fase 5 com a US5. Distribuição `ai-scouting` 0.1.0; entry point
`scouting = "ai_scouting.pack:ScoutingPack"` no grupo `ai_core.packs`. Um teste compara `manifest().version` com a
versão da distribuição (010 R12).

**Rationale**: o `rag_first` não existe na Fase 4; declará-lo deixaria indisponível todo Assistant com `packs:
[scouting]` sem `flow` (003 `effective_flow`). O ADR-006 continua valendo: `rag_first` é o default do scouting quando
existir — o pack o declara na Fase 5. A versão `0.1.4` do design.md é ilustrativa (arch-v1), não decisão.

**Alternatives considered**: declarar tudo já e exigir `flow: chat` no Assistant (clarificação 1, opção B).

## R5 — A pergunta e a data de referência

**Decision**: a derivação lê só `view.question` e `view.reference_time`. O dia de referência é a data local de Brasília
— `view.reference_time.astimezone(timezone(timedelta(hours=-3))).date()` —, com o deslocamento fixo como constante do
pack (`BRASILIA = timezone(timedelta(hours=-3), "UTC-03:00")`).

**Rationale** (ADR-013, FR-005): o core entrega `reference_time` em UTC (relógio do motor); às 22h em Brasília o dia
UTC já é o seguinte, e a vigência de documento brasileiro é por dia local. O Brasil não tem horário de verão desde
2019, então o deslocamento fixo é exato no presente e dispensa `tzdata` (que seria dependência além dos contratos —
FR-001). Só a pergunta corrente: a derivação não interpreta o histórico da conversa ("e em 2023?" depois de outra
pergunta não herda o tema) — determinismo simples, e a US2 fala da pergunta.

**Alternatives considered**: `reference_time.date()` em UTC (dia errado à noite); `ZoneInfo("America/Sao_Paulo")`
(exige base de fusos no sistema ou `tzdata`); interpretar o histórico (regra frágil sem caso de uso).

## R6 — Normalização de texto e casamento de termos

**Decision**: função pura `normalize(text)`: `casefold`, remoção de diacríticos (`unicodedata` NFKD sem marcas
combinantes), toda sequência de não-alfanuméricos vira um espaço, e espaços nas pontas saem. Um termo do léxico (também
normalizado) casa quando aparece cercado por limites de palavra no texto normalizado — termos de várias palavras
inclusive ("ramo senior", "programa educativo"). Plural e feminino entram como termos explícitos no léxico, sem
stemmer.

**Rationale** (princípio V, XII): previsível, testável por tabela e sem dependência; o léxico é curado (FR-007), então
listar as formas é mais claro que um stemmer que casa demais.

**Alternatives considered**: stemmer ou biblioteca de NLP (dependência e falsos positivos); expressões regulares por
termo escritas à mão (o léxico deixaria de ser dado).

## R7 — Léxico: forma e semente

**Decision** (FR-007, clarificação 5): o léxico é **dado em código** — `context/lexicon.py` com estruturas imutáveis:
ramos (id canônico ASCII → termos), temas (id → termos e tipos de documento sugeridos), tipos de documento (id →
termos), sinais de tipo de documento (termo → tipos, ex.: "competências" → `programa_educativo`, `manual`), termos
ambíguos (casam e **não** aplicam filtro, ex.: "escoteiro" sozinho, que nomeia o movimento e o ramo) e marcas
históricas sem data ("manual anterior", "versão anterior", "antigamente"). Ids canônicos em ASCII com `_`
(`pioneiro`, `lideranca`, `programa_educativo`), na ordem do léxico. A semente — ramos Lobinho, Escoteiro, Sênior e
Pioneiro com sinônimos; tipos `manual`, `programa_educativo`, `por`, `resolucao`, `estatuto`, `guia`; cerca de 15 temas
— é proposta na primeira tarefa de implementação e revisada pelo mantenedor antes dos testes de aceite.

**Rationale**: constante Python, como o prompt do `ai-generic` (010 R7): nada a declarar no empacotamento, tipado,
verificado pelo mypy, e carregar não é I/O (princípio XIII sem porta). Ids ASCII casam com os valores de metadado que a
102 vai gravar e já são a forma da spec (`programa_educativo`).

**Alternatives considered**: arquivo YAML/TOML de dados no pacote (leitura de recurso na carga, parser e validação
próprios, sem ganho para um curador que edita o repositório); léxico só com os termos dos exemplos (clarificação 5,
opção C).

## R8 — Regras de derivação

**Decision**: `derive_context(question, reference_day, lexicon) -> ScoutingContext`, pura, em `context/derivation.py`:

1. **Ramo**: os ramos cujos termos casam; exatamente um → esse ramo; nenhum, mais de um, ou só termo ambíguo → sem
   filtro de ramo (caso de borda "na dúvida, não aplica filtro").
2. **Temas**: todos os que casam, na ordem do léxico.
3. **Tipos de documento**: os citados explicitamente; se nenhum, a união dos sugeridos pelos sinais e pelos temas; na
   ordem do léxico. Sem nada → vazio (sem filtro de tipo).
4. **Vigência** (clarificação 4, `context/periods.py`): data exata ("em 15/03/2023", "em 15 de março de 2023") →
   intervalo de um dia; mês com ano ("em março de 2023") → o mês inteiro; ano precedido de marca temporal ("em 2023",
   "no ano de 2023", "durante 2023") → o ano inteiro; "ano passado" → o ano anterior ao dia de referência. Ano solto
   (como em "resolução 3/2023") **não** é período. Com período → `include_superseded = True`. Sem período → o dia de
   referência, `include_superseded = False`. Mais de um período → o primeiro na ordem do texto.
5. **Versão anterior**: marca histórica sem data → `previous_version = True` e `include_superseded = True`, com a
   vigência no dia de referência (a recuperação busca a versão imediatamente substituída em relação a ele — 103,
   Fase 5).

**Rationale** (US2, US3, casos de borda): cada regra é uma linha da tabela de testes; a ambiguidade resolve para
"sem filtro", nunca para palpite (princípio VII). "Ano solto não é período" evita que números de documento virem
consulta histórica.

**Alternatives considered**: o modelo extrair os filtros (proibido pelo princípio V e pela FR-004); escolher o ramo
mais frequente quando há dois (palpite).

## R9 — Onde a US1 é provada

**Decision** (clarificação 3): a suíte padrão (`tests/`) usa só os contratos: conformidade da 001 com todas as etapas
(imports e distribuição), identidade e manifest, prompt, léxico e derivação — é a que o SC-003 mede. A integração com
a plataforma fica em `tests/integration/test_platform.py`, sob o grupo opcional `platform`
(`ai-core ; python_version >= '3.14'`, resolvido pela mesma tag do `agentic-app`), com `pytest.importorskip("ai_core")`.
Ela usa só a superfície que a 011 publica para suítes de packs externos: a configuração vai pelas variáveis do
operador (`AI_CORE_PACKS_FILE`, `AI_CORE_ASSISTANTS_FILE`, com as demais `AI_CORE_*` limpas) e a montagem por
`platform(profile="test")`, sem trocar porta — o provider simulado do perfil responde sozinho. Prova: o pack aparece
`enabled` com versão e versão de contrato, pelo seam da 002 (`PackRegistry.entry`) (US1 cen. 1); a plataforma compõe o
prompt do pack para o Assistant `scouting` (`PackHooks.system_prompts(compose(["scouting"]))` igual ao do pack) e a
conversa responde 200 (US1 cen. 2). Que a geração recebe os prompts compostos é garantia da 005, testada no core (a
010 T019 o mostra com o `ai-generic`); o pack não importa adapter nem módulo interno do core (princípio II).

**Rationale**: o perfil `test` é parte da distribuição do core justamente para suítes de packs externos (011); o core
não pode ter teste de escotismo (princípio I); o trace não grava conteúdo de prompt. Verificado em 2026-10-07: o grupo
resolve e importa a plataforma em 3.14, e sem ele o ambiente 3.12 tem só os contratos.

**Alternatives considered**: só o build da instalação (002 US5, outra fase de entrega); só o quickstart manual (sem
teste automatizado da US1).

## R10 — Fragmento de instruções da Fase 4

**Decision** (FR-009, FR-011): `prompts/domain.py` com `SYSTEM_PROMPT` constante, em português, com quatro blocos:
papel (assistente do movimento escoteiro brasileiro); **sem documentos consultados nesta fase** — responder com
conhecimento geral, declarar que nenhum documento institucional foi consultado, nunca citar, nomear ou numerar
documento, resolução ou trecho como consultado, recomendar confirmar na fonte oficial, e lembrar que regras mudam;
**dado, nunca instrução**; **fora do domínio** — dizer que o tema não é do escotismo e responder com cautela. As
prioridades de fonte e o "sempre citar" (FR-008) entram com o corpus, na Fase 5.

**Rationale**: no `chat` da Fase 4 a geração só tem o prompt do pack e a conversa; sem a regra explícita, o modelo
inventa referência a manual e resolução — o pior erro do domínio (princípio IX).

**Alternatives considered**: o prompt da Fase 5 já agora (citaria corpus inexistente); recusar perguntas de domínio
(clarificação 2, opção B).

## R11 — Capacidades publicadas na Fase 4

**Decision**: `system_prompt` (R10) e `prepare_context` (R8, R12). Sem tools, retrievers, reranker e validators na
101 desta fase: os validators da 104 entram pelo `pack.py` quando o esqueleto da 104 existir (toque declarado no plano
dela), e retriever e reranker com a 103 (Fase 5, FR-010). Nenhuma porta secundária: o pack não faz I/O.

**Rationale** (princípio XII): nada publicado sem efeito; o `pack.py` é a composition root onde os submódulos se ligam.

**Alternatives considered**: validators vazios de placeholder (código sem comportamento).

## R12 — Forma da fatia e dos filtros

**Decision**: `prepare_context` devolve `{"context": {...}, "retrieval_filters": {...}}` (design.md), em JSON:
`context` com `branch`, `topics`, `document_types`, `effective_from`, `effective_until`, `include_superseded`,
`previous_version`; `retrieval_filters` com as mesmas chaves, omitindo `branch` sem ramo e listas vazias. Datas em ISO
(`AAAA-MM-DD`). Formato completo em [contracts/retrieval-filters.md](contracts/retrieval-filters.md).

**Rationale** (001 FR-012, conformidade etapa 6): a fatia precisa ser JSON e determinística; os filtros são do próprio
pack (o retriever da 103 é o consumidor). O intervalo substitui o `effective_on` único do exemplo do design.md
(clarificação 4).

**Alternatives considered**: só `retrieval_filters` (a 105 mede a derivação pela fatia, e o validator de vigência da
104 lê a fatia); `effective_on` único (clarificação 4, opções B e C).

## R13 — "Não lê o relógio" e "não chama modelo", verificados

**Decision**: import-linter no `ai-scouting` com três contratos — o pack não importa `ai_core` nem `ai_generic`; só o
`pack.py` compõe (`ai_scouting.pack` acima de `ai_scouting.context | ai_scouting.prompts`, independentes entre si); e
`ai_scouting.context` não importa `ai_core_contracts.llm` nem `ai_core_contracts.mcp`. Um teste de unidade varre o
código de `context/` e falha com chamadas de relógio (`.now(`, `.today(`, `utcnow`, `time.time(`, `time.monotonic(`).
A conformidade já verifica determinismo de `prepare_context` (mesma entrada, mesma saída).

**Rationale** (SC-002, FR-005): sem acesso a modelo nem a relógio por construção — e verificado, não só prometido.

**Alternatives considered**: congelar o relógio nos testes (provaria que o resultado não muda, não que o relógio não é
lido).

## R14 — CI do `ai-scouting`

**Decision**: `.github/workflows/ci.yml` no `ai-scouting`, com quatro jobs: `lint` (ruff check e format, mypy strict,
lint-imports), `test` (matriz 3.12 e 3.14, `uv sync --locked`, `pytest` — a integração é pulada), `clean-env` (3.12,
instalação normal do pack só com os contratos e a suíte padrão — a etapa de distribuição confere a faixa) e `platform`
(3.14, `uv sync --locked --group platform`, `pytest tests/integration`). O acesso ao `agentic-app` (privado) é por uma
**deploy key só de leitura** do `agentic-app`, com a chave privada no segredo `AGENTIC_APP_DEPLOY_KEY` do
`ai-scouting`, carregada por `webfactory/ssh-agent`.

**Rationale** (ADR-021, consequência "acesso de leitura"): é o custo previsto de manter o core neste repositório; a
deploy key dá leitura a um repositório só, sem token pessoal.

**Alternatives considered**: token pessoal (acesso a todos os repositórios da conta); repositório público (decisão de
visibilidade de 2026-10-07: privados).

## R15 — Toques fora do `ai-scouting`

**Decision**: no `agentic-app`, só documentação — design.md (notas de origem: fonte dos contratos, manifest da Fase 4,
vigência como intervalo), `specs/README.md` (status da 101), CLAUDE.md, roadmap — e o ponteiro do submódulo. Nenhuma
linha do `ai-core/`.

**Rationale** (princípio I, II): o core não sabe que o scouting existe; o pack o enxerga pelo contrato 001.

**Alternatives considered**: nenhuma.

# Fase 5 (2026-10-09): US4 e US5 — `rag_first`, retriever e reranker da 103, validators da 104, prompt com citação

Insumos: as cinco clarificações de 2026-10-08/09; a 103 (`ScoutingRetriever`, `MetadataReranker`, `search_docs`,
`RetrievalConfig`) e a 102 (`QdrantIndex`, `E5Embedder`, `Bm25Encoder`, `HashingEmbedder`) já implementadas; os
validators da 104 (`CitationIntegrityValidator` com `open_stream`, `ValidityNoticeValidator`), prontos desde a Fase 4;
o core conferido no código — o `packs.yaml` aceita `config`, validado contra o `config_schema` (002, `jsonschema`, sem
aplicar defaults); o `requires_collections` só aparece na introspecção, e o que o grant confere são as coleções que o
retriever declara (003, 004); a renderização de tool da 004 não mostra o `chunk_id` (resolvido pelo
[ADR-026](../../docs/adr/ADR-026-o-modelo-ve-o-identificador-de-cada-trecho.md)). Escopo: **US4, US5** e a publicação
dos validators da 104 (104 FR-008).

## R16 — Escopo e ordem da passada

**Decision** (clarificação 4): a passada é planejada agora e implementada **depois** da 005 US3–US4 (`rag_first`) —
que inclui o formato do ADR-026 na 004 e na 005 — e da tag do core que as traz (R22). Toques no `ai-scouting`:
`pack.py` (manifest, `system_prompt`, `retrievers`, `reranker`, `validators`), `prompts/domain.py` (prompt da Fase 5),
`pyproject.toml` (versão e fontes), testes. Na 104 nada muda no código: ela só passa a ser publicada; o status dela é
atualizado no fechamento.

**Rationale**: declarar `rag_first` antes de o motor tê-lo deixaria o Assistant do scouting indisponível; e o teste
ponta a ponta da US5 (uma chamada de modelo, citação válida) só faz sentido contra o flow real.

**Alternatives considered**: `agentic` como preferido até a 005 (clarificação 4, opção C); declarar já e aceitar o
424 (opção B).

## R17 — Coleção lógica fixa, índice configurável

**Decision**: a coleção que o grant concede é fixa no pack — `COLLECTION = "scouting"` — e vai no
`requires_collections` do manifest e no `NamedRetriever` da tool. O que a configuração escolhe é o **índice** (o alias
no Qdrant, `index`, default `scouting`). A premissa da spec que citava `scouting_docs` passa a `scouting`.

**Rationale**: `manifest()` não recebe configuração, então o nome exigido não pode depender dela; e o core confere o
Assistant contra as coleções que o retriever declara. Separar o nome lógico do alias deixa o operador trocar o índice
físico sem mexer em Assistant. O default igual ao alias que a ingestão já usa (`scouting`) mantém o caminho simples.

**Alternatives considered**: coleção configurável (o manifest ficaria dessincronizado do retriever); manter
`scouting_docs` (divergiria do índice já ingerido e da 102/103).

## R18 — `config_schema` (clarificação 1, FR-003, FR-012)

**Decision**: JSON Schema com `additionalProperties: false`:

| Campo | Tipo | Default (aplicado pelo pack) | Regra |
|---|---|---|---|
| `qdrant_url` | string `^https?://` | `http://localhost:6333` | exclusivo com `qdrant_path` |
| `qdrant_path` | string | — | Qdrant embutido num diretório (testes e desenvolvimento) |
| `index` | string `^[a-z0-9][a-z0-9_-]*$` | `scouting` | o alias no Qdrant |
| `embedder` | `e5` \| `hashing` | `e5` | `hashing` é o embedder de teste da 102, sem semântica — só para suítes |
| `embedding_dir` | string | — | obrigatório com `e5`; precisa ter `model.onnx` e `tokenizer.json` |
| `default_limit`, `max_limit` | inteiro ≥ 1 | 5, 30 | os da 103 (`RetrievalConfig`) |

A chave do Qdrant vem só de `AI_SCOUTING_QDRANT_API_KEY` (FR-012): fora do esquema, do `packs.yaml` e de qualquer
mensagem. O `jsonschema` do core não aplica defaults — o pack os aplica ao ler `ctx.config`. Combinação inválida
(`qdrant_url` com `qdrant_path`, `e5` sem diretório ou sem os arquivos, limites incoerentes) levanta `ValueError`
nomeando o campo na carga: o pack não carrega e o erro aparece na introspecção e no `ai-core packs check` (princípio
VII).

**Rationale**: o boot valida cedo o que dá para validar (esquema, combinação, arquivos do modelo); o que depende de
rede (Qdrant fora, índice ausente, modelo divergente) aparece na primeira busca como `IndexUnavailable`/`IndexMismatch`,
erro explícito (103 FR-007). O embedder `hashing` é o equivalente, para o pack, ao perfil `test` da 011: escolhido por
configuração, documentado como de teste.

**Alternatives considered**: tudo por ambiente (clarificação 1, B); tudo no arquivo, inclusive a chave (C); conferir o
sha256 do modelo na carga (470 MB lidos a cada boot; a FR-012 da 102 já recusa modelo divergente na busca).

## R19 — Composição no `pack.py`

**Decision**: `retrievers(ctx)` lê a configuração (R18), monta `AsyncQdrantClient` (URL com a chave do ambiente, ou
`path`), o embedder (`E5Embedder(dir)` ou `HashingEmbedder()`), `Bm25Encoder`, `QdrantIndex(client, index, …)`,
`ScoutingRetriever(index, RetrievalConfig(...))` e devolve `[search_docs(retriever, collection="scouting")]`.
`reranker(ctx)` → `MetadataReranker()`. `validators(ctx)` → `[CitationIntegrityValidator(), ValidityNoticeValidator()]`,
nessa ordem (o aviso de vigência lê as citações que a integridade validou). Os imports de infraestrutura ficam dentro
dos hooks, como no `corpus_cli`: ler a identidade do pack (002) continua barato. Os hooks são chamados uma vez, na
carga (001 FR-019).

**Rationale**: o `pack.py` é a composition root (princípio XIII); os hooks recebem a configuração já validada pelo
esquema.

**Alternatives considered**: um módulo `wiring.py` (contraria a letra "num pack, esse papel é do `pack.py`").

## R20 — Manifest e versão

**Decision**: `PackManifest(name="scouting", version="0.2.0", preferred_flow="rag_first", requires_collections=
["scouting"], config_schema=SCOUTING_CONFIG_SCHEMA)`; a distribuição sobe para `0.2.0` (o teste compara as duas).
Consequência: um Assistant com `packs: [scouting]` sem `flow` roda no `rag_first` — exige o core com o flow (R22).

**Rationale**: FR-003; capacidades novas e configuração nova pedem versão nova do pack.

**Alternatives considered**: manter `0.1.x` (esconderia uma mudança de comportamento para quem instala).

## R21 — Prompt da Fase 5 (FR-008, FR-009, FR-011, US4; 104 FR-007; ADR-026)

**Decision**: o bloco "sem documentos consultados" da Fase 4 dá lugar a quatro blocos:

| Bloco | Conteúdo |
|---|---|
| Prioridades de fonte (US4) | as cinco, na ordem: institucionais sobre secundárias; vigentes sobre revogadas ou substituídas; específicas do ramo e primárias sobre genéricas; o trecho preciso sobre o amplo; sempre citação e proveniência |
| Citação (104 FR-007, ADR-026) | depois de cada afirmação tirada de um trecho, `[[id]]` com o identificador exato que aparece depois de `id:` na referência do trecho (exemplo sintético: `[[manual-x-2026#4.2@p12]]`); nunca citar trecho que não veio, nunca inventar identificador |
| Sem trechos (FR-011, clarificação 2) | se nenhum trecho chegou, responder com conhecimento geral dizendo que nenhum documento oficial foi encontrado para a pergunta, sem citar nem nomear documento, e recomendar a fonte oficial |
| Vigência | trecho de versão substituída ou revogada é dito como tal |

Papel, "dado, nunca instrução" (FR-009) e "fora do escotismo" continuam. O prompt não manda chamar ferramenta (não
contém "chame" nem "use a ferramenta"): no `agentic` ele só chega à geração.

**Rationale**: é o que a FR-008 e a 104 FR-007 pedem, com o formato garantido pelo ADR-026; manter o caminho sem
trechos explícito evita citação inventada quando a busca vem vazia.

**Alternatives considered**: um prompt para cada flow (o prompt é do pack, não do flow — 010 FR-008).

## R22 — Dependências e tags

**Decision**: `ai-core-contracts` continua `>=0.1,<0.2`, com a fonte na tag `contracts-v0.1.1` (já existe; formaliza o
`StreamingValidator` do ADR-024). O grupo `platform` passa para a tag do core que trouxer o `rag_first` e o ADR-026
(`v0.2.0`, criada no `agentic-app` ao fim da 005 US3–US4 — ADR-021). Fora desta passada: o `CORE_REF` default do
`agentic-deploy` e o modelo e5 e o Qdrant na instalação (nota da 102 R20).

**Rationale**: o pack depende só dos contratos; o teste de plataforma precisa do core com o flow.

**Alternatives considered**: apontar o grupo `platform` para um commit (tag é o que a ADR-021 prevê).

> Nota da implementação (2026-10-09, T029): o `uv` recusa duas fontes para a mesma distribuição — o core na `v0.2.0`
> resolve `ai-core-contracts` da própria tag. Os dois vêm, então, da **mesma** tag, `v0.2.0` (como na Fase 4, quando
> ambos vinham de `contracts-v0.1.0`). Nela os contratos são os da `contracts-v0.1.1` (versão `0.1.1`; a única
> diferença é uma linha em branco).

## R23 — Testes

**Decision**: unidade — leitura da configuração (defaults, exclusividade URL/caminho, `e5` sem diretório ou sem
arquivos, limites), manifest (`rag_first`, coleção, esquema), capacidades (uma tool `search_docs` com a coleção
`scouting`, o reranker, os dois validators na ordem), prompt (os blocos e as frases fixas da R21; as cinco prioridades
na ordem — US4); conformidade da 001 com `config={"qdrant_path": tmp, "embedder": "hashing"}`; ponta a ponta no grupo
`platform` — corpus sintético ingerido num `qdrant_path` com o `HashingEmbedder`, perfil `test` com o `packs.yaml`
apontando para ele, Assistant `scouting` sem `flow` (logo `rag_first`), o provider de geração programado (troca de
porta `providers` da 011) para citar o primeiro `id:` que vir no contexto; espera-se 200, **uma** chamada de modelo no
trace da requisição (SC-004) e a citação `[1]` com a proveniência do trecho (US5 cen. 1).

**Rationale**: SC-003 segue valendo (a suíte padrão roda sem o core); a US5 é provada contra o flow e a renderização
reais. O limiar do portão no teste vem da configuração da 005 (o `HashingEmbedder` tem outra escala de similaridade).

**Alternatives considered**: provar a US5 só com unidades (não prova o "uma chamada de modelo").

## R24 — US4 nas instruções (clarificação 3)

**Decision**: as prioridades vivem só no prompt; o teste da US4 confere as cinco, na ordem. A marca institucional /
secundária no catálogo e no índice entra quando chegar a primeira fonte secundária (102); o efeito nas respostas é
medido na 105.

**Rationale**: o corpus é todo institucional; uma marca sem valor diferente seria peso morto.

**Alternatives considered**: campo `institutional` já (clarificação 3, B).

---

# Passada de 2026-10-20: identidade Axon ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md); US6)

Decisões pré-aprovadas pelo ADR-037 (nomes, corte seco com a recusa de `AI_SCOUTING_*`, versão, tag); o que segue é como
elas chegam ao pack, sem re-pesquisa. Os R anteriores ficam como foram executados (ADR-037, item 6).

## R25 — Distribuição, pacote, CLI e versão

**Decision**: no repositório `axon-scouting`, `git mv src/ai_scouting src/axon_scouting`; `pyproject.toml` com `name =
"axon-scouting"`, `version = "0.4.0"`, `description = "Pack de domínio escoteiro da plataforma Axon (specs 1xx em
axon)."`, `dependencies` com `axon-ai-contracts>=0.2,<0.3`, o script `axon-scouting-corpus`, o entry point
`[project.entry-points."axon.packs"] scouting = "axon_scouting.pack:ScoutingPack"`, o grupo `platform` com `axon-ai`, e as
fontes `axon-ai-contracts` e `axon-ai` de `ssh://git@github.com/CaioFerreiraB/axon.git`, tag `v0.7.0-rc1`, subdiretórios
`axon-ai/packages/contracts` e `axon-ai/packages/core`. `pack.py`: `VERSION = "0.4.0"`, `contract_version = "0.2"`. O
`uv.lock` é regenerado (`uv lock`).

**Rationale** (ADR-037, itens 2 e 4): o pack segue a regra dos nomes (`ai-` → `axon-`) e sobe a minor por quebra (nome,
dependência e grupo novos). A série 0.2 dos contratos tem tudo o que a 0.1.2 tinha (métricas de domínio, `eval`), então
`contract_version` "0.2" basta. Contratos e core da mesma tag (R22): o `uv` não aceita duas fontes para os contratos.

**Alternatives considered**: `contract_version` "0.2.0" (mais estreito sem necessidade); manter a `v0.3.0` (contratos
0.1, grupo antigo: o core novo não acharia o pack).

## R26 — A recusa de `AI_SCOUTING_*`

**Decision**: em `pack.py`, `LEGACY_PREFIX: Final = "AI_SCOUTING_"`, `PREFIX: Final = "AXON_SCOUTING_"` e a função pura
`legacy_environment(environ: Mapping[str, str]) -> str | None`, que devolve `None` sem variáveis antigas ou a mensagem
"variáveis com o nome antigo (ADR-037): renomeie" seguida de uma linha `AI_SCOUTING_X → AXON_SCOUTING_X` por variável, em
ordem alfabética, sem valor. Uso: no início de `retrievers()` (a carga; `ValueError` com a mensagem, e o pack fica em erro
pelo Pack Runtime) e no início de `corpus_cli()` (imprime `erro: <mensagem>` na saída de erro e sai com `cli.FAILED`,
antes de compor qualquer coisa). A regra é o prefixo exato, vazia ou não, conhecida ou não, e vale com a nova definida.
As variáveis novas são `AXON_SCOUTING_QDRANT_URL`, `AXON_SCOUTING_QDRANT_API_KEY`, `AXON_SCOUTING_INDEX`,
`AXON_SCOUTING_EMBEDDING_DIR` e, nas suítes, `AXON_SCOUTING_TEST_QDRANT_URL`.

**Rationale** (ADR-037, item 3: "o pack recusa `AI_SCOUTING_*`, com uma mensagem que cita a variável nova"; a mesma
forma da recusa de `AI_CORE_*` no boot, 011 R48). O hook de recuperação é onde o pack lê o ambiente na carga.

**Alternatives considered**: recusar em `read_config` (é pura sobre o `config` do `packs.yaml`, não lê o ambiente);
ignorar as antigas (subiria com os defaults em silêncio).

## R27 — A substituição mecânica

**Decision**: um script no scratchpad aplica, no repositório `axon-scouting` (código, testes, configuração, CI, `README`,
`eval/`, `corpus/`, menos `uv.lock`) e nos documentos vivos das specs 101–106 (`spec.md`, `design.md`, `data-model.md`,
`quickstart.md`, `contracts/**`), do mais específico ao mais geral: `ai_core_contracts` → `axon_ai_contracts`,
`ai-core-contracts` → `axon-ai-contracts`, `ai_core.packs` → `axon.packs`, `ai-scouting-corpus` → `axon-scouting-corpus`,
`ai_scouting` → `axon_scouting`, `ai-scouting` → `axon-scouting`, `AI_SCOUTING_` → `AXON_SCOUTING_`, `ai_generic` →
`axon_generic`, `ai-generic` → `axon-generic`, o comando `ai-core <subcomando>` → `axon`, `ai_core` → `axon_ai`, `AI_CORE_`
→ `AXON_`, `ai-core` → `axon-ai`, `CaioFerreiraB/agentic-app` → `CaioFerreiraB/axon`, `agentic-app` → `axon` (repositório
da plataforma), "Plataforma Agentic AI"/"Agentic AI" → "Axon"; e os cabeçalhos `x-ai-core-*` → `x-axon-*` se aparecerem.
Protegidos: a palavra `agentic` sozinha (o flow), o nome do segredo `AGENTIC_APP_DEPLOY_KEY` da CI, os testes da recusa
(R26, R30) e as linhas de limpeza de ambiente das integrações, que passam a limpar os dois prefixos (R28). Fora: `research`,
`plan`, `tasks`, `checklists` (histórico), os submódulos do repositório da plataforma.

**Rationale** (ADR-037, itens 6 e 7; a lição da 011: lista fechada de arquivos e conferência dos resíduos).

**Alternatives considered**: `sed` global (alcançaria o histórico e o nome do segredo).

## R28 — Integração, CI e avaliação

**Decision**: a integração (`tests/integration/`) importa `axon_ai.bootstrap.*`, define `AXON_PACKS_FILE` e
`AXON_ASSISTANTS_FILE` e, antes de montar a plataforma, limpa do ambiente tanto `AXON_` quanto `AI_CORE_` e `AI_SCOUTING_`
(a plataforma e o pack recusam os antigos, então um ambiente de desenvolvimento com eles quebraria a suíte por outro
motivo); `test_eval.py` chama o comando `axon`. A CI (`ci.yml`) e o `eval.yml` trocam os nomes (`AXON_SCOUTING_*`,
`AXON_PROFILE`, `axon eval run`, `axon-scouting-corpus`), e os comentários citam o repositório `axon`; o segredo
`AGENTIC_APP_DEPLOY_KEY` e os nomes dos submódulos (`ai-scouting`, `agentic-deploy`, que são nomes de submódulo do
`.gitmodules` da plataforma até o fechamento) ficam.

**Rationale** (ADR-037, item 7).

**Alternatives considered**: renomear o segredo (exige recadastrar a chave no GitHub, fora do código).

## R29 — Specs 102–106

**Decision**: só os nomes, pelo script do R27, nos documentos vivos; nenhum FR muda.

**Rationale** (ADR-037, item 7: "Specs 102–106 mudam só nos nomes, dentro da passada da 101").

**Alternatives considered**: nenhuma.

## R30 — Testes

**Decision**: `tests/test_legacy_environment.py`: `legacy_environment` com `{}` e com só `AXON_SCOUTING_*` → `None`; com
`AI_SCOUTING_INDEX`, `AI_SCOUTING_FOO` (desconhecida) e `AI_SCOUTING_QDRANT_URL=""` → uma linha por variável, em ordem,
sem valor; com `MY_AI_SCOUTING_X` e `AI_SCOUTINGX` → `None`; com a antiga e a nova juntas → recusa; `retrievers()` com
`AI_SCOUTING_INDEX` no ambiente levanta `ValueError` com `AXON_SCOUTING_INDEX`; a CLI (`corpus_cli` com `sys.argv` de
`status`) sai com 2 e a mesma mensagem; `importlib.util.find_spec("ai_scouting") is None`. `test_pack.py` confere a versão
`0.4.0` igual à de `axon-scouting` e `contract_version` "0.2". A conformidade (`test_conformance.py`) com os contratos 0.2.

**Rationale**: FR-013 a FR-015.

**Alternatives considered**: nenhuma.

## R31 — Verificação e entrega

**Decision**: no `axon-scouting`: `uv run pytest && uv run mypy && uv run ruff check && uv run ruff format --check && uv
run lint-imports`; a suíte em 3.12 no ambiente limpo; `uv run --python 3.14 --group platform pytest tests/integration`
(com a tag `v0.7.0-rc1`); a suíte do índice contra um Qdrant local (`AXON_SCOUTING_TEST_QDRANT_URL`); resíduos e a palavra
`agentic`. Commit no `axon-scouting`; o push dele e o do ponteiro do submódulo no `axon` só com o aval do mantenedor.

**Rationale**: SC-005; regra das ações externas.

**Alternatives considered**: nenhuma.

---

## Passada de 2026-10-21: o pack prepara o e5 e carrega o índice do pacote ([ADR-041](../../docs/adr/ADR-041-o-pack-prepara-os-proprios-dados-no-build.md), [ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md))

Decisões pré-aprovadas pelos ADRs (hook `prepare`, artefato do índice, embedder escolhido pela configuração); o que
segue é como elas chegam ao `pack.py`, sem re-pesquisa.

## R32 — O hook `prepare`

**Decision**: `ScoutingPack.prepare(ctx)` recusa `AI_SCOUTING_*` (como a carga), lê a configuração com
`read_config(ctx.config, ctx.data_dir, require_model=False)` e, só com o `e5`, chama o `fetch` do adapter (que já era
idempotente e conferia os sha256) no `embedding_dir` resolvido. `read_config` ganhou `data_dir` (default do
`embedding_dir`: `data_dir/e5-small`) e `require_model` (a carga exige `model.onnx` e `tokenizer.json`; o `prepare`, que
vai baixá-los, não). `contract_version = "0.2.1"`; dependência `axon-ai-contracts>=0.2.1,<0.3` pela tag `v0.7.0-rc4`.

**Rationale** (ADR-041, Consequências; ADR-043, item 6): o `model fetch` da instalação vira o hook do pack; o caminho
do modelo deixa de ser repetido no `packs.yaml` e no ambiente da CLI.

**Alternatives**: baixar também com `pplx` (a imagem carregaria 470 MB sem uso).

## R33 — `store`, `index_dir` e `embedder`

**Decision**: `SCOUTING_CONFIG_SCHEMA` ganha `store` (`memory`/`qdrant`) e `index_dir`, e o `embedder` ganha `pplx`.
`ScoutingConfig` traz `store` e `index_dir`; `qdrant_url`/`qdrant_path` ficam `None` com `memory`. A carga com
`memory` monta o `ArtifactIndex` da 102 sobre `PACKAGED_INDEX` (`axon_scouting/data/index`, dado do pacote) ou
`index_dir` e recusa um diretório sem `manifest.json`; com `qdrant`, o `QdrantIndex` de antes. O embedder sai de
`_embedder(config, environ)`: `E5Embedder`, `OpenRouterEmbedder(AXON_SCOUTING_EMBEDDING_API_KEY)` ou `HashingEmbedder`.
Pack `0.5.0`.

**Rationale** (ADR-043, itens 3 a 5): o índice de produção é em memória; o Qdrant fica como opção; a chave lida na
construção, mas exigida só na codificação, deixa o `packs check` passar no build sem segredos.

**Alternatives**: inferir `store: qdrant` de `qdrant_url` presente (duas maneiras de dizer a mesma coisa); recusar a
carga sem a chave do `pplx` (reprovaria o build da instalação).

## R34 — Testes e verificação

**Decision**: `tests/test_config.py` (defaults sem Qdrant, exclusividades, `data_dir`), `tests/test_pack.py` (índice em
memória por um artefato no `tmp_path`, artefato ausente, `pplx` sem chave, `prepare` com o download trocado por um falso)
e a conformidade do kit 0.2.1 sobre o artefato do pacote (a etapa 3b chama o `prepare`, que com `hashing` não faz
nada). A integração do `rag_first` (`tests/integration/test_rag.py`) passa a publicar num artefato; as outras duas
seguem no Qdrant embutido com `store: qdrant`.

**Rationale**: cada FR novo com um teste; o caminho de produção (artefato) na prova ponta a ponta.

**Alternatives**: —

---

## Passada de 2026-10-27 (revisão do RAG; [ADR-045](../../docs/adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md))

## R35 — Filhotes e as facetas na derivação

- **Decision**: `filhotes` entra primeiro em `LEXICON.branches` (filhote, filhotes, ramo filhotes, ninhada, ninhadas) e
  o `Lexicon` ganha `all_branches` (cada ramo, todos os ramos, os ramos, dos ramos, nos ramos, aos ramos, pelos ramos,
  entre os ramos, 5 ramos, cinco ramos, por ramo). `ScoutingContext.branches`: com um marcador de totalidade, os cinco
  ramos; senão, os ramos casados, se forem dois ou mais; `branch` só com exatamente um e nenhum marcador. `to_slice`
  publica `branches` no contexto (lista, vazia quando não há) e nos filtros (só quando não vazia).
- **Rationale**: a pergunta do exemplo ("dos 5 ramos") e as variantes da revisão (E5, E6) não filtravam nada; a
  decomposição precisa saber quais ramos (103 R13). "Escoteiro" sozinho continua ambíguo; "os ramos Filhotes, Lobinho,
  …" casa o marcador ("os ramos") e dá os cinco.
- **Alternatives**: decompor por modelo (contra o princípio V: derivação sem modelo); só o número "5 ramos" como
  marcador (perde "cada ramo" e "os ramos").

## R36 — Cobertura parcial, conceito perguntado e resposta por ramo no prompt

- **Decision**: três parágrafos novos no `SYSTEM_PROMPT`, antes da vigência: cobertura parcial (o que não veio nos
  trechos não é o que não existe; sugerir a pergunta mais específica), o conceito perguntado (os vizinhos do domínio
  nomeados como exemplo, sem nenhum valor deles) e a resposta por ramo na ordem das idades. Testes de frase em
  `tests/test_prompt.py`, e um que proíbe fatos do conjunto de regressão no prompt.
- **Rationale**: a resposta de produção afirmou ausência a partir de cinco trechos e preencheu com ênfase educativa e
  símbolos (revisão, §3). O efeito é medido com modelo real pela `scouting:absence_claim_rate` da 105 (R17) e pelo juiz;
  o gerador simulado do perfil `test` não lê o prompt.
- **Alternatives**: um glossário dos conceitos no prompt (fatos do corpus no prompt, contra FR-022); validar a resposta
  depois (um validator não sabe o que os trechos deixaram de fora).

  **Medido em 2026-10-27** (105 R17): fidelidade 0,95 → 1,00 e cobertura 0,89 → 0,92 pelo juiz; a troca de conceito
  (caracterização do ramo dada como marco simbólico) e uma invenção no lema somem nas respostas lidas; o
  `fact_recall` não muda, e cada resposta usa uns 400 tokens a mais.

## R37 — Tipo citado filtra, sugerido ordena; a resposta sem "trechos"; ano relativo ([ADR-046](../../docs/adr/ADR-046-tipo-sugerido-ordena-no-scouting.md))

- **Decision**: `ScoutingContext.document_types` (citados, `_cited_types`) e `suggested_types` (temas e sinais, só sem
  citado, `_suggested_types`); `to_slice` publica os dois no contexto e, nos filtros, só os não vazios. Léxico:
  `programa_educativo` sai de `document_types` (as citações); os temas e os sinais sugerem tipos citáveis, com `guia`
  (especialidades → guia; insígnias → guia e POR; progressão, método, serviço, liderança e competências → manual e
  guia; uniforme → POR e resolução); "guia de" cita `guia`. Prompt: a cobertura parcial diz "não encontrei essa
  informação nos documentos que consultei", e um parágrafo proíbe as palavras do mecanismo na resposta. `periods.py`:
  `_LAST_YEAR` com "último ano" e "ano anterior"; `_THIS_YEAR` com "este ano", "neste ano", "deste ano", "ano atual" e
  "ano corrente".
- **Rationale**: no teste do mantenedor (17 perguntas), as 4 de especialidades voltaram sem trecho (o tipo sugerido
  `programa_educativo` não existe no catálogo), as de progressão perdiam os guias dos jovens, e as respostas falavam de
  "trechos recebidos", que o usuário não entende. Medido com o conjunto de regressão (105 R19): 0,7634 → 0,8705.
- **Alternatives**: no ADR-046.
