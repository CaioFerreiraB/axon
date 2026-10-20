# Research — 001 Contratos públicos (`ai-core-contracts`)

**Data**: 2026-09-15 · **Plano**: [plan.md](plan.md) · **Spec**: [spec.md](spec.md)

As decisões do [design.md](design.md) e dos ADRs 004, 005, 011, 012 e 013 são pré-aprovadas e aparecem aqui só como
registro (R-A*). As demais (R*) resolvem o que o design deixou em aberto ou o que a spec exigiu depois das clarificações de
2026-09-15. Nenhuma diverge do design; onde há refinamento de tipo, está marcado.

## Decisões herdadas (pré-aprovadas)

### R-A1 — Distribuição própria no workspace do core

- **Decision**: `ai-core-contracts` é uma distribuição do uv workspace `ai-core`, em `packages/contracts`, com versão e tags
  próprias (`contracts-vX.Y.Z`).
- **Rationale (ADR-004)**: packs externos dependem só dos contratos, sem arrastar FastAPI, LangGraph ou Qdrant; mudança de
  contrato é um PR atômico no core.
- **Alternatives**: contratos como módulo de `ai-core`; repositório separado; monorepo com packs — rejeitadas no ADR-004.

### R-A2 — Turn View no lugar do estado bruto; sem `AgentState` nos contratos

- **Decision**: hooks recebem `TurnView` (somente-leitura, campos enumerados); `prepare_context` devolve a atualização da
  própria fatia; nomes de nó, estado interno e framework de grafo não são contrato.
- **Rationale (ADR-011)**: permite reescrever o motor (005), inclusive trocar o LangGraph, sem major nos contratos.
- **Alternatives**: `AgentState` sem reducers nos contratos; subgraph LangGraph como escape hatch — rejeitadas no ADR-011.

### R-A3 — `reference_time` na Turn View

- **Decision**: campo `reference_time` (datetime), fixado pelo motor no início da execução e repetido em toda Turn View dela.
- **Rationale (ADR-013)**: mesma data para todos os hooks; conjunto dourado reproduzível; hooks testáveis com data fixa.
- **Alternatives**: relógio próprio em cada pack — rejeitada no ADR-013.

### R-A4 — Despacho único por `ToolSpec.kind`

- **Decision**: `kind ∈ {retrieval, mcp, native}`; `handler` só em `native`; `mutates` marca escrita.
- **Rationale (ADR-005)**: um ponto de execução de tools (004); capacidade nova nunca vira nó novo.
- **Alternatives**: nós separados por tipo de capacidade — rejeitada no ADR-005.

### R-A5 — Contratos como portas do microkernel

- **Decision**: os contratos não fazem I/O e não têm adapters próprios; packs e módulos do core os implementam.
- **Rationale (ADR-012)**: tabela "Portas e adapters" do design.md.
- **Alternatives**: n/a.

## Decisões deste plano

### R1 — Onde o código mora

- **Decision**: workspace `ai-core/` como **subpasta deste repositório** durante as Fases 0–3, com `git init` na raiz
  (feito em 2026-09-15) e CI em `.github/workflows/` da raiz. A separação em repositório `ai-core` próprio acontece antes
  da Fase 4; a tag `contracts-v0.1.0` é criada já no repositório separado.
- **Rationale**: decisão do mantenedor (2026-09-15), permitida pelo CLAUDE.md; resolve o item 2 de "Antes de começar" do
  roadmap. Os caminhos do design.md (`ai-core/packages/contracts/...`) valem sem mudança.
- **Alternatives**: repositório `ai-core` separado já na Fase 0 — adia pouco e dobra a coordenação justamente quando os
  contratos mais mudam.

### R2 — Versão de Python

- **Decision**: workspace e imagem em **Python 3.14** (`ai-core/.python-version`); `ai-core-contracts` declara
  `requires-python = ">=3.12"`; o CI dos contratos roda em 3.12, 3.13 e 3.14.
- **Rationale**: decisão do mantenedor (2026-09-15); a constituição delega a versão a este plano. 3.14.7 é a série estável
  mais recente (EOL 2030). O piso 3.12 custa nada numa biblioteca só-stdlib e cobre Python de distribuição (a máquina de
  desenvolvimento tem 3.12.3). Recursos usados: `type` aliases (PEP 695, 3.12), dataclasses `slots`/`kw_only`;
  `ReadOnly` e `deprecated` vêm de `typing_extensions` em 3.12.
- **Alternatives**: 3.13 no workspace (mais conservador quanto a wheels ARM64 das dependências da Fase 1 — reconferido no
  plano da 011); piso 3.14 (obrigaria autores de pack a usar 3.14 fora da imagem).

### R3 — Empacotamento e versão

- **Decision**: build backend `uv_build`, versão **estática** em `packages/contracts/pyproject.toml`, espelhada em
  `ai_core_contracts/_version.py` (`__version__`) e verificada por teste contra `importlib.metadata`. Dependência de
  runtime única: `typing_extensions>=4.12`. `py.typed` distribuído.
- **Rationale**: o workspace já é uv (constituição); `__version__` constante deixa a regra de compatibilidade pura, sem
  ler metadados em runtime (princípio XIII); versão estática evita que tags de duas linhas de versão (contratos e core) no
  mesmo repositório confundam versionamento dinâmico.
- **Alternatives**: `hatchling` + `hatch-vcs` (versão a partir da tag — exige filtro de prefixo `contracts-v*` e não
  funciona bem com duas linhas de versão); `setuptools-scm` (mesmo problema); ler a versão via `importlib.metadata` em
  runtime (I/O no caminho da regra).

### R4 — Política de versões 0.x

- **Decision**: convenção 0.x deslocada, como clarificado em 2026-09-15 (FR-016, FR-018): enquanto o major for 0, aditiva
  = patch e breaking = minor; faixa dos packs `>=0.N,<0.(N+1)`; depreciado em 0.N.x sai a partir de 0.(N+1).0; a partir
  de 1.0, semver padrão.
- **Rationale**: o design.md ("Sugestão para o plano") delegou a escolha a este plano; a faixa `>=0.1,<0.2`, prevista na
  constituição e nos designs de 002 e 101, só funciona se campo novo não tirar o pack da faixa.
- **Formalização**: o `/speckit-analyze` apontou que a redação anterior da constituição ("breaking change = major")
  conflitava com esta política. Resolvido em 2026-09-15 pelo [ADR-014](../../docs/adr/ADR-014-politica-versoes-0x-contratos.md)
  e pela emenda da constituição para a 1.2.0; as linhas correspondentes do design.md estão marcadas como superadas.
- **Alternatives**: campo novo = minor com faixa `>=0.1,<1` (a faixa deixaria de proteger contra breaking); tratar 0.x
  como semver padrão (qualquer mudança tiraria os packs da faixa).

### R5 — Regra de versões sem `packaging`

- **Decision**: `compat.py` implementa um **subconjunto do PEP 440** só com stdlib:
  - versões `N(.N)*` com pré-release opcional (`aN`, `bN`, `rcN`) e `.devN`, ordenadas pelo PEP 440 (zeros à direita
    ignorados; `.dev` < `a` < `b` < `rc` < final); epoch, post-release e versão local → `InvalidVersion`;
  - especificadores `==`, `==X.Y.*`, `!=`, `!=X.Y.*`, `>=`, `<=`, `>`, `<`, `~=`, combinados por vírgula (E lógico);
  - regra de pré-release do PEP 440 para `<V` (não aceita pré-release de V final); a versão instalada é avaliada como
    fato (equivale a `prereleases=True`).
  Testes diferenciais com `hypothesis` usam `packaging` **como oráculo, só em dev**.
- **Rationale**: FR-001 proíbe dependências além de `typing_extensions`; FR-016/FR-018 exigem a regra dentro da
  distribuição. O subconjunto cobre as versões que o projeto emite e os especificadores que um `pyproject.toml` de pack
  plausivelmente declara; o que ficar fora é reportado, não aceito em silêncio.
- **Alternatives**: depender de `packaging` (viola FR-001); vendorizar `packaging` (~2 mil linhas e licença a manter
  para usar uma fração); comparar tuplas de inteiros (não trata pré-release nem especificadores).

### R6 — Faixa derivada, compatibilidade e mensagens

- **Decision**: `derive_range("0.1") → >=0.1,<0.2`, `"0.1.3" → >=0.1.3,<0.2`, `"1.2" → >=1.2,<2`. `check_compatibility`
  aceita a `contract_version` (derivando a faixa) ou uma faixa explícita, compara com a versão instalada e, se falhar,
  nomeia **a cláusula violada**: `requer ai-core-contracts>=0.2, instalado 0.1.4` (US3, 002 US2).
  `contract_version` aceita só `X.Y` ou `X.Y.Z`.
- **Rationale**: FR-018 e as mensagens já usadas nos cenários da 001 e da 002.
- **Alternatives**: mensagem com a faixa inteira (menos direta quando só um lado é violado).

### R7 — Hooks opcionais em Python

- **Decision**: `AgentPack` é um `Protocol` (`runtime_checkable`) com a **forma completa** do design.md (identidade,
  `manifest` e hooks). `PackBase` é uma classe concreta com implementação vazia de todo hook opcional (`None`, `()` ou
  `{}`). Packs herdam de `PackBase` e sobrescrevem o que usam; a conformidade exige a forma completa. Hook novo entra como
  membro do `AgentPack` **com** default em `PackBase` — aditivo (patch em 0.x).
- **Rationale**: FR-003 e US2 cenário 2 ("retornam vazio sem erro"); preserva a assinatura única do design.md; mantém
  hook novo como mudança aditiva para packs que herdam de `PackBase` (incluindo o pack de teste congelado do FR-020).
- **Alternatives**: um `Protocol` por hook com detecção por presença (multiplica tipos e a regra de opcionalidade vira
  `isinstance` espalhado); `getattr` com default no core (a opcionalidade vira contrato implícito da 002).

### R8 — Pack Context, Validator Context e ciclo de vida dos hooks

- **Decision** (clarificação 2026-09-15, FR-019): `PackContext(pack_name, config)` e `ValidatorContext(pack_name, config)`
  são tipos distintos, só com dados de carga; nenhum serviço na 0.1. Hooks de catálogo (`system_prompt`, `tools`,
  `retrievers`, `reranker`, `validators`) são chamados **uma vez, na carga**; dados por execução chegam só pela Turn View.
- **Rationale**: nenhum pack da v1 precisa de serviço do core (princípios V e XII); catálogo validável no boot; serviço
  futuro entra como campo opcional (patch) sem alcançar validators, porque o tipo deles é separado.
- **Alternatives**: serviços por execução; dois contextos (carga e execução) — rejeitadas na clarificação.

### R9 — Retriever nomeado e tool de recuperação derivada

- **Decision** (clarificação 2026-09-15, FR-004, FR-006): `NamedRetriever(name, description, collections, retriever)`
  com `collections` não vazio. A distribuição publica `retrieval_tool_spec(named)` e `RETRIEVAL_TOOL_PARAMETERS` (esquema
  padrão: `query` obrigatória, `top_k` opcional), fonte única da tool `retrieval` para o core (004) e para a conformidade.
  `tools()` do pack só declara tools `native`.
- **Rationale**: princípio IV (fora do grant = fora do catálogo); ADR-005 (retrieval é tool); evita divergência entre o
  esquema que a 004 monta e o que a conformidade verifica.
- **Alternatives**: ligação por nome entre `ToolSpec` e retriever; coleção como argumento de `search` — rejeitadas na
  clarificação.

### R10 — Handler de tool nativa

- **Decision**: `NativeHandler = Callable[[ToolInvocation], Awaitable[object]]`, com
  `ToolInvocation(arguments, request_id, reference_time)`. O handler devolve o **conteúdo**; quem monta o `ToolResult`
  (sempre `untrusted=True`), aplica timeout e truncamento e converte exceção em erro é o gateway (004).
  *Refinamento* de `Callable[..., Awaitable[object]]` do design.md.
- **Rationale**: objeto-parâmetro único permite acrescentar campos opcionais como patch; `reference_time` evita que um
  handler leia o relógio (ADR-013 — uma tool nativa de data é o exemplo clássico); devolver conteúdo impede que um pack
  marque a própria saída como confiável (princípio VI).
- **Alternatives**: `handler(**arguments)` (sem dados da execução, colisão de nomes com argumentos); `handler(arguments,
  view)` (obriga o gateway a obter uma Turn View recortada por pack); handler devolvendo `ToolResult` (pack poderia
  declarar `untrusted=False`).
- **Impacto em consumidor**: a 004 constrói o `ToolInvocation` (precisa de `request_id` e `reference_time` da execução) —
  anotar no plano da 004.

### R11 — Imutabilidade e valores JSON

- **Decision**: value objects são `dataclass(frozen=True, slots=True, kw_only=True)`. Na construção (`__post_init__`),
  sequências viram `tuple`, conjuntos viram `frozenset` e mapeamentos viram `MappingProxyType` sobre cópia, **em
  profundidade** (`_freeze.py`). Fatias de pack e filtros são valores JSON (`JSONValue`: `str`, `int`, `float`, `bool`,
  `None`, sequências e mapeamentos com chave `str`) — exigido pela conformidade, porque a 005 persiste checkpoints na
  Fase 3. `reference_time` precisa ter fuso (datetime *aware*); datetime ingênuo é rejeitado.
- **Rationale**: US4 ("Turn View imutável"; "comportamento idêntico com dois produtores") vira garantia do tipo, não de
  cada produtor; `kw_only` torna seguro acrescentar campo com default em qualquer posição.
- **Alternatives**: congelar só no produtor (fixture e motor podem divergir); `MappingProxyType` raso (mutação aninhada
  vaza); pydantic congelado (dependência — viola FR-001).

### R12 — Forma de `messages` e `citations`

- **Decision**: `Message` e `Citation` são `TypedDict` com chaves `ReadOnly`: `Message{role, content}`;
  `Citation{chunk_id (obrigatória), document, version, status, section, page}`. Em runtime são mapeamentos congelados.
  *Refinamento* compatível de `Sequence[Mapping]` do design.md.
- **Rationale**: o ADR-011 quer campos enumerados — chave lida por pack sem declaração vira contrato implícito. Um
  `TypedDict` continua sendo `Mapping`, então a forma aprovada se mantém; a 104 (validators) e a 008 (evento final)
  passam a ter as chaves por escrito.
- **Alternatives**: dataclasses (mudaria a forma aprovada — pediria ADR); `Mapping` sem chaves documentadas (contrato
  implícito).

### R13 — Regras de declaração dentro da distribuição

- **Decision**: `declaration.py` publica `check_declaration(...) → tuple[ContractIssue, ...]`, função pura com as regras
  dos edge cases (nomes duplicados ou em colisão, tool não-nativa declarada pelo pack, retriever sem coleção, esquema de
  parâmetros implausível, manifest com nome diferente do pack, autodependência, nomes e versões inválidos). A 002 a chama
  na carga (fail-closed é dela) e a suíte de conformidade também. `ContractIssue(code, message, subject, severity)` tem
  códigos estáveis — ver [contracts/testing-kit.md](contracts/testing-kit.md).
- **Rationale**: uma só implementação das regras que decidem "manifest inválido"; a 002 não reimplementa semântica do
  contrato.
- **Alternatives**: regras só na 002 (a conformidade do pack divergiria do boot); regras só na conformidade (a 002
  reimplementaria).

### R14 — Validação de JSON Schema

- **Decision**: os contratos fazem checagem **estrutural** de `parameters` e `config_schema`: mapeamento serializável em
  JSON; em `parameters`, `type: "object"` no topo, `properties` como mapeamento de mapeamentos e `required` contido em
  `properties`. Validação contra o metaesquema é do core (002/004), que pode usar biblioteca própria.
- **Rationale**: FR-001; o edge case "esquema de parâmetros inválido" é pego cedo na conformidade do pack e de novo, por
  completo, no boot.
- **Alternatives**: validador de metaesquema só-stdlib (grande); `jsonschema` como dependência (viola FR-001).

### R15 — Nomes

- **Decision**: nome de pack `^[a-z][a-z0-9_]{0,31}$` (vira namespace e chave de fatia); nomes locais de tool, retriever
  e validator `^[a-z][a-z0-9_]{0,47}$`. Tools `mcp` descobertas (007) não passam por essa regra.
- **Rationale**: namespace `<pack>.<local>` previsível e compatível com o mapeamento que a 004 fará para o formato de
  cada provider.
- **Alternatives**: nomes livres (colisões e caracteres que providers rejeitam aparecem só em runtime).

### R16 — Depreciação

- **Decision**: `contract_deprecated(since, *, use_instead=None)`, construído sobre `typing_extensions.deprecated`
  (PEP 702 — aviso estático e em runtime), com categoria `ContractDeprecationWarning(DeprecationWarning)`. A mensagem
  nomeia a versão da depreciação e a da remoção, calculada pela política (`removal_version("0.1.3") → "0.2.0"`). O
  decorador também grava `__contract_deprecated_since__ = since` no objeto, lido pelo snapshot de superfície (R18). A
  suíte de conformidade captura esses avisos e os reporta (`deprecation.used`, severidade *warning*). Campos depreciados
  ganham o mecanismo quando o primeiro caso aparecer.
- **Rationale**: US3 cenário 3; a 0.1 não tem nada depreciado, então o mecanismo é testado com símbolo definido só nos
  testes.
- **Alternatives**: `warnings.warn` manual (sem aviso estático); `FutureWarning` (voltado a usuário final, não a autor de
  pack).

### R17 — Kit de testes `ai_core_contracts.testing`

- **Decision**: parte **pública** da distribuição, só stdlib, independente de runner: construtores de fixture
  (`turn_view`, `chunk`, `pack_context`, `validator_context`, `tool_invocation`, `REFERENCE_TIME` fixo), suíte de
  conformidade (`acheck_pack` assíncrona; `check_pack` síncrona via `asyncio.run`; `assert_pack_conforms`) e checagens
  puras reutilizáveis. A conformidade inclui varredura AST dos imports do pacote do pack (proíbe `ai_core` e
  `ai_generic` — US1 cenário 3, SC-005 —, menos o próprio pacote varrido, para que o `ai_generic` possa importar a si
  mesmo; um módulo solto é varrido como arquivo único) e a checagem da dependência declarada (FR-018), que lê `Requires-Dist` por
  `importlib.metadata` numa função fina de borda. A checagem de distribuição pode ser desligada
  (`check_distribution=False`) só para packs do workspace, que usam os contratos do mesmo commit, sem faixa (010 FR-004).
  O kit entra na superfície pública versionada (FR-020).
- **Rationale**: FR-001 vale para o kit, então nada de pytest; qualquer runner chama `assert_pack_conforms`; a
  conformidade roda em todo pack (010, 101), o que torna SC-003 e SC-005 verificáveis sem ferramenta extra.
- **Alternatives**: plugin pytest como extra `[testing]` (dependência de runner); distribuição separada
  `ai-core-contracts-testing` (mais uma linha de release); só import-linter nos packs (depende de configuração correta em
  cada repositório; mantido como recomendação no quickstart).

### R18 — Detecção de breaking change (FR-020, SC-004)

- **Decision** (clarificação 2026-09-15): ferramenta própria `packages/contracts/tools/api_surface.py` (fora da
  distribuição):
  1. `dump` — por introspecção do pacote instalado, gera um snapshot JSON canônico de `ai_core_contracts.__all__` e
     `ai_core_contracts.testing.__all__`: tipo do símbolo, campos de dataclass (anotação, default, obrigatoriedade),
     membros de Protocol (assinaturas, `async`, se `PackBase` fornece default), chaves de TypedDict (obrigatória,
     `ReadOnly`), assinaturas de função. Anotações saem como texto, porque todo módulo usa
     `from __future__ import annotations` — o snapshot é o mesmo em 3.12, 3.13 e 3.14;
  2. `diff` — classifica cada mudança como aditiva ou breaking pela tabela de
     [contracts/compatibility.md](contracts/compatibility.md), calcula o bump exigido pela política (R4), compara com o
     bump declarado (versão no `pyproject.toml` × última tag `contracts-v*`) e falha se o declarado for menor.
  O CI gera os dois snapshots (`git worktree` na tag e HEAD) e executa o `diff`. O job só roda se houver tag
  `contracts-v*`; antes disso, registra "sem linha de base" e passa.

  Cuidados de implementação, apontados pelo `/speckit-analyze` e verificados em 3.12.3 e 3.14.7:
  - **Determinismo**: `repr(frozenset)` muda de ordem entre processos. Conjuntos entram no snapshot como listas
    ordenadas, e `ISSUE_CODES` é comparado como conjunto (código novo = aditivo; removido = breaking), não como
    "valor de constante";
  - **TypedDict**: com `from __future__ import annotations`, `__required_keys__` e `__readonly_keys__` saem errados
    em runtime (`Citation.__required_keys__ == set()`; `NotRequired` aparece como obrigatória). Obrigatoriedade e
    `ReadOnly` são lidas do **texto da anotação** (`Required[`, `NotRequired[`, `ReadOnly[`) mais `__total__`;
  - **Depreciação antes de remover** (FR-016): o snapshot registra `deprecated_since` de cada símbolo (lido de
    `__contract_deprecated_since__`, R16); remover um símbolo que não estava depreciado no snapshot anterior falha,
    qualquer que seja o bump.
- **Rationale**: as categorias do SC-004 são enumeradas e cada uma ganha teste; a classificação precisa conhecer a
  política 0.x e a regra `AgentPack`/`PackBase`; a introspecção vê exatamente o que o pack vê.
- **Alternatives**: `griffe check` (detecta quebras por análise estática contra um ref git, mas não reporta mudanças
  aditivas — que exigem patch —, não conhece a regra do `PackBase` e traz semântica própria); revisão manual (não
  verificável).

### R19 — Pack de teste congelado e ambiente limpo (FR-020 b, SC-001, US1)

- **Decision**: `packages/contracts/tests/fixtures/contract_test_pack/` é um pack mínimo e completo, com `pyproject.toml`
  próprio (`dependencies = ["ai-core-contracts>=0.1,<0.2"]`, entry point `ai_core.packs`), que herda de `PackBase`,
  exercita todos os hooks e value objects e tem testes próprios usando só o kit. Não é membro do workspace. O CI:
  (a) **ambiente limpo** — `uv venv` temporário, instala contratos + pack, `uv pip freeze` deve listar exatamente
  `ai-core-contracts`, `typing-extensions` e o pack; depois instala pytest e roda os testes do pack;
  (b) **pack congelado** — a partir da tag, roda os testes da cópia do pack que está na última tag contra os contratos do
  HEAD.
- **Rationale**: prova SC-001 pela resolução real; o pack congelado detecta quebra de uso que o diff de forma não vê.
- **Alternatives**: usar o `ai-generic` (010) como pack de teste (é Fase 1 e testado sem faixa, por definição);
  pack como membro do workspace (a resolução do workspace mistura dependências de dev).

### R20 — Fronteiras de import (FR-001, FR-017)

- **Decision**:
  1. **Allowlist** (teste AST): todo import em `src/ai_core_contracts/**` é da stdlib (`sys.stdlib_module_names`),
     `typing_extensions` ou do próprio pacote;
  2. **Sem I/O no runtime** (mesmo teste): módulos fora de `testing/` não importam `os`, `io`, `pathlib`, `socket`,
     `subprocess`, `shutil`, `urllib`, `http`, `time`, `random`, `secrets`, `asyncio` nem `importlib.metadata`;
  3. **import-linter** em `ai-core/pyproject.toml`: na Fase 0, `root_packages = ["ai_core_contracts"]` com
     `include_external_packages = true`, o contrato "contratos não dependem de frameworks do runtime" do design.md e
     "módulos de runtime não importam `ai_core_contracts.testing`". Os contratos entre `ai_core` e `ai_generic` do
     design.md entram quando esses pacotes existirem (Fase 1).
- **Rationale**: a allowlist é mais forte que a lista proibida do design.md e cobre o FR-001 de fato; a lista proibida
  continua, como o design pede e a constituição exige.
- **Alternatives**: só import-linter (não expressa "apenas stdlib").

### R21 — `LLMProvider` (FR-013)

- **Decision**: forma do design.md, tipada com `@overload` sobre `stream: Literal[False] | Literal[True]` (→
  `ChatResponse` ou `AsyncIterator[ChatChunk]`) e `TypedDict`s mínimos: `ChatMessage`, `ChatTool` (`name`,
  `description`, `parameters`), `ChatToolCall`, `ChatUsage`, `ChatResponse`, `ChatChunk`. `model: str` sempre
  explícito (princípio VIII). **Provisório até a tag**: o plano da 006 (Fase 1) pode refinar essas formas no workspace
  sem custo de versão. **Suíte mínima já na 0.1** (`testing.acheck_llm_provider`: sem stream, `message` com papel
  `assistant` e `finish_reason`; com stream, chunks com `delta` e `finish_reason` só no último), rodada contra um
  provider falso — exigência da constituição (Governance) e do ADR-012 ("todo seam ganha suíte de conformidade"),
  apontada pelo `/speckit-analyze`. A 006 a roda contra cada adapter e pode ampliá-la.
- **Rationale**: `list[dict]` e `dict` do design.md viram chaves por escrito sem mudar a forma (um `TypedDict` é um
  `dict`); streaming está no contrato desde o início (princípio XI).
- **Alternatives**: dois métodos (`chat` e `chat_stream`) — diverge da assinatura aprovada; `dict` sem chaves.

### R22 — `MCPClient` (FR-014)

- **Decision**: assinatura do design.md (`discover_tools(aliases)`, `execute(alias, tool, arguments)`), com
  `Sequence`/`Mapping` no lugar de `list`/`dict`. **Provisório até a tag**. Ponto a resolver no plano da 007: o retorno
  de `discover_tools` não diz de qual alias veio cada tool — quem precisa dessa associação chama por alias, ou a 007
  propõe um campo opcional (patch). **Suíte mínima já na 0.1** (`testing.acheck_mcp_client`: descoberta devolve
  `ToolSpec(kind="mcp")` sem handler; execução devolve `ToolResult` com `untrusted=True`), rodada contra um cliente
  falso; a 007 a roda contra o cliente restrito.
- **Rationale**: FR-014 (só aliases, nunca endereços) está preservado; a lacuna só aparece na Fase 3.
- **Alternatives**: retornar `Mapping[alias, Sequence[ToolSpec]]` agora — mudaria a assinatura que a 007 também
  transcreve; melhor decidir com a 007.

### R23 — Rotina isolada (US5) fora da 0.1

- **Decision**: `routine()`, `PackRoutine`, `RoutineLimits` e `RoutineResult` **não entram** na 0.1. A forma planejada
  (design.md) fica registrada no [data-model.md](data-model.md) e entra como hook opcional novo, com default em
  `PackBase` — aditivo, patch.
- **Rationale**: o roadmap põe US5 fora da Fase 0 e diz que P3 entra "quando houver caso de uso"; congelar agora uma
  forma que nenhum teste exercita contraria o princípio XII.
- **Alternatives**: incluir os tipos agora sem comportamento (forma não exercitada, candidata a breaking change depois).

### R24 — Ferramentas de desenvolvimento e CI

- **Decision**: grupo `dev` no `ai-core/pyproject.toml` com `pytest`, `pytest-asyncio`, `hypothesis`, `packaging`
  (oráculo), `import-linter`, `ruff` e `mypy` (strict nos contratos); versões travadas no `uv.lock`. CI em GitHub Actions
  (`.github/workflows/contracts.yml`, filtro de caminho `ai-core/packages/contracts/**`), com os jobs: lint e tipos;
  testes (matriz 3.12/3.13/3.14); fronteiras; ambiente limpo; superfície pública e pack congelado (condicionados à tag).
- **Rationale**: as ferramentas usuais do ecossistema, só em dev, sem tocar o FR-001; o design do core aponta GitHub/GHCR.
- **Alternatives**: `pyright` (equivalente; `mypy` é o mais comum em bibliotecas tipadas); `nox`/`tox` (desnecessário com
  `uv run`).

## Pendências para outros planos (não bloqueiam a 001)

| Pendência | Onde |
|---|---|
| Construir `ToolInvocation`; derivar tools de retriever com `retrieval_tool_spec`; excluir retriever cuja coleção não está no grant; redação da 004 US5 ("rejeitada" × "fora do catálogo") | plano da 004 |
| Chamar hooks de catálogo uma vez na carga; usar `check_compatibility` e `check_declaration`; merge raso do retorno de `prepare_context`; Turn View por pack | plano da 002 |
| Refinar `ChatMessage`/`ChatResponse`/`ChatChunk` antes da tag; rodar e, se preciso, ampliar `acheck_llm_provider` | plano da 006 |
| Associação tool → alias em `discover_tools`; rodar `acheck_mcp_client` contra o cliente restrito | plano da 007 |
| ~~Emenda da constituição (0.x em "Versionamento")~~ | feito: constituição 1.2.0 + ADR-014 (2026-09-15) |

---

## Passada de 2026-10-07: validators que filtram o streaming ([ADR-024](../../docs/adr/ADR-024-validators-filtram-o-streaming.md))

### R25 — Protocolo `StreamingValidator` (contratos 0.1.1)

- **Decision**: em `validation.py`, `AnswerStream` (`feed(delta) -> str`, `finish() -> ValidationResult`) e
  `StreamingValidator(AnswerValidator)` com `open_stream(view, ctx) -> AnswerStream`, ambos `runtime_checkable` e
  síncronos (o caminho quente da geração); a sessão vê a Turn View da abertura, sem `answer`. O kit ganha, na etapa de
  validators, a verificação em três partições (inteira, um caractere por vez, pedaços de 7), com os códigos
  `validator.stream.mismatch` e `validator.stream.not_append_only`. Versão `0.1.1`; o diff de superfície contra
  `contracts-v0.1.0` classifica as quatro mudanças como aditivas (patch).
- **Rationale** (ADR-014, ADR-024): aditivo — nenhum pack muda; quem não implementa `open_stream` continua em lote.
- **Alternatives**: método opcional no próprio `AnswerValidator` (mudaria o protocolo de todos os validators).

---

## Passada de 2026-10-20: identidade Axon ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md); US6)

Decisões pré-aprovadas pelo ADR-037 (nome, versão, corte seco, ordem das passadas); o que segue é como elas chegam aos
contratos, sem re-pesquisa. O [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md) (marca
visível) não toca os contratos.

### R26 — Nome da distribuição e do import

- **Decision**: distribuição `axon-ai-contracts`, pacote `axon_ai_contracts` (`git mv src/ai_core_contracts
  src/axon_ai_contracts`), kit em `axon_ai_contracts.testing`. A pasta `ai-core/packages/contracts` fica; a pasta do
  workspace muda na passada da 011. `description` do `pyproject.toml`: "Contratos públicos do núcleo da plataforma Axon".
  Superfície pública idêntica à de 0.1.3, símbolo a símbolo.
- **Rationale** (ADR-037, itens 1 e 2): no código, `ai-core` vira `axon-ai` e o prefixo `ai-` vira `axon-`; `axon`
  sozinho colide com um pacote do PyPI no import e no nome de distribuição. Mudar só o nome mantém o FR-020 legível:
  o diff relata o renome e nada mais (R30).
- **Alternatives**: `axon_contracts` (quebra a regra do ADR-037, que deriva os nomes de `axon-ai`); renomear também a
  pasta `packages/contracts` para `packages/axon-ai-contracts` (nenhum outro membro do workspace leva o nome da
  distribuição na pasta).

### R27 — Versão 0.2.0 e corte seco

- **Decision**: `version = "0.2.0"` (`pyproject.toml` e `_version.py`); CHANGELOG ganha a seção `0.2.0` com o renome
  como única mudança (breaking) e a nota de que todo pack escrito para `0.1.x` precisa de nova versão
  (`axon-ai-contracts>=0.2,<0.3`, `contract_version = "0.2"`). Nenhum módulo `ai_core_contracts`, alias, reexportação ou
  `contract_deprecated` para o nome antigo. Um teste de fronteira afirma que `ai_core_contracts` não é importável no
  ambiente do workspace (US6, cenário 1).
- **Rationale** (ADR-037, itens 3 e 4; ADR-014): renomear o import é quebra, e quebra em 0.x sobe a minor. Sem
  instalação nem pack de terceiro a preservar, um módulo de compatibilidade só carregaria código sem usuário. A janela de
  depreciação do FR-016 é para símbolos dentro da distribuição; o renome da distribuição inteira está decidido no ADR.
- **Alternatives**: pacote `ai_core_contracts` fino que reexporta `axon_ai_contracts` com aviso (rejeitado no ADR-037,
  "período de transição"); `1.0.0` (o ADR-014 reserva o 1.0 para a estabilidade dos contratos, não para um renome).

### R28 — Mensagens e etapa de distribuição

- **Decision**: o nome `axon-ai-contracts` nas três mensagens que nomeiam a distribuição — `Compatibility.message`
  (`requer axon-ai-contracts<cláusula>, instalado <versão>`), o aviso de depreciação (`desde axon-ai-contracts <since>`) e
  as cinco da etapa de distribuição — e `_DISTRIBUTION = "axon-ai-contracts"` em `testing/distribution.py`. A busca
  continua por nome normalizado (PEP 503); uma dependência de `ai-core-contracts` é uma dependência qualquer, e o pack
  que só tem ela recebe `distribution.missing_requirement` (US6, cenário 3). Os códigos de issue não mudam.
- **Rationale** (ADR-037, item 3): o pack que ainda aponta para o nome antigo precisa de uma mensagem que diga o nome
  novo, e `missing_requirement` já diz ("não declara dependência de axon-ai-contracts; declare >=0.2,<0.3"). Nenhum código novo de issue: a única
  concessão de diagnóstico do ADR-037 é a recusa das variáveis de ambiente antigas, no boot (011).
- **Alternatives**: código novo `distribution.renamed` para o nome antigo (diagnóstico além do que o ADR concede; o
  `missing_requirement` já nomeia a dependência certa).

### R29 — Módulos proibidos por padrão na varredura de imports

- **Decision**: `DEFAULT_FORBIDDEN = ("axon_ai", "axon_generic")` em `testing/imports.py`; a comparação continua por
  módulo (igual, ou prefixo seguido de ponto), então `axon_ai_contracts` nunca casa com `axon_ai`. Os packs de teste que
  provam `imports.forbidden` passam a importar `axon_ai` (a varredura é por AST; o módulo não precisa existir).
- **Rationale** (ADR-037, item 2): o kit sai na tag `contracts-v0.2.0`, que só é criada depois das passadas do core
  (011) e do pack de referência (010), quando os imports proibidos são esses. Entre a 001 e a 011, o core ainda é
  `ai_core`, e a fronteira de `ai_generic` contra `ai_core` continua guardada pelo import-linter do workspace
  ("o pack genérico não importa o core").
- **Alternatives**: proibir os dois pares (`ai_core`, `ai_generic`, `axon_ai`, `axon_generic`) e limpar na 011 (carrega
  nome antigo na superfície que o pack externo consome, só para cobrir semanas de desenvolvimento); manter
  `ai_core`/`ai_generic` e trocar na 011 (a passada da 011 teria de mudar a superfície dos contratos, que é da 001).

### R30 — Diff de superfície com renome da raiz

- **Decision**: em `tools/api_surface.py`:
  - `dump(package="axon_ai_contracts")` introspecta `package` e `package.testing`; o snapshot ganha `package` e tira o
    nome da distribuição dos metadados instalados: `importlib.metadata.packages_distributions()` e, como o workspace
    instala os membros em modo editável (sem `top_level` nos metadados), a distribuição de nome derivado do pacote
    (`_` → `-`, que vale para `axon_ai_contracts` e para `ai_core_contracts`); o próprio pacote é a última reserva. CLI: `dump [--package NOME] [--output ARQUIVO]`.
  - `classify` compara os módulos pelo nome relativo à raiz (`""`, `".testing"`) e mostra cada símbolo com o nome do
    HEAD. Se `distribution` ou `package` diferem entre os snapshots, acrescenta **uma** mudança breaking
    (`símbolo` = pacote novo, `detalhe` = "distribuição renomeada: ai-core-contracts (ai_core_contracts) →
    axon-ai-contracts (axon_ai_contracts)"), sem `removed_without_deprecation`.
  - No CI (`contracts.yml`, jobs `surface` e `frozen-pack`), o pacote da linha de base sai do próprio worktree da tag
    (`$base/src/*/__init__.py`) e vai em `--package`; o `same_series` importa `axon_ai_contracts`.
  - Quando a raiz muda, os textos da linha de base (anotações, `repr` de aliases e defaults) têm a raiz antiga trocada
    pela nova, por palavra inteira, antes da comparação: o `repr` de `NativeHandler` cita `ai_core_contracts.tools`, e
    sem isso o alias sairia como alterado.
  A última tag é `contracts-v0.1.2` (a 0.1.3, `ChatUsage.cost`, não foi marcada). Contra ela, verificado em
  2026-10-20: o renome (breaking), `ChatUsage['cost']` (aditiva) e `testing.check_imports` (breaking: default novo de
  `forbidden`, R29); bump exigido `minor`, declarado `minor` (0.1.2 → 0.2.0), sem falha; com 0.1.4 declarado, falha (US6,
  cenário 4). O pack congelado de 0.1.2 é pulado (série nova).
- **Rationale** (ADR-037, item 4; FR-020, FR-025): comparar pelo nome completo relataria cada símbolo como removido sem
  depreciação, e o CI falharia por uma mudança que o ADR decidiu. Comparar pelo relativo mantém a garantia em cada
  símbolo e registra o renome uma vez. O snapshot é gerado a cada rodada pela ferramenta do HEAD, então mudar o formato
  não exige migração.
- **Alternatives**: pular o job `surface` nesta versão (perde a verificação de que nenhum símbolo mudou junto com o
  nome); mapa fixo `ai_core_contracts → axon_ai_contracts` na ferramenta (nome antigo no código, contra o SC-006).

### R31 — Consumidores no workspace (atualização mecânica)

- **Decision**: um script de substituição no scratchpad (não versionado), do padrão mais longo ao mais curto
  (`ai_core_contracts` antes de `ai_core`; `ai-core-contracts` antes de `ai-core`), aplicado só a código, testes e
  configuração do workspace (`ai-core/packages/**`, `ai-core/pyproject.toml`) e aos workflows `contracts.yml` e
  `generic.yml`; documentos de histórico (ADR-037, item 6) ficam fora. Junto:
  - `packages/core/pyproject.toml`: dependência e fonte `axon-ai-contracts`;
  - `packages/generic/pyproject.toml`: `axon-ai-contracts>=0.2,<0.3` (fonte do workspace) e `contract_version = "0.2"`
    no `GenericPack`; o nome da distribuição (`axon-generic` 0.2.0) fica para a 010;
  - `contract_version = "0.1"` → `"0.2"` nos packs de teste do core e dos contratos e no pack de teste congelado
    (`contract_test_pack`: `axon-ai-contracts>=0.2,<0.3`), e as asserções que leem a coluna `contract_version`; os
    testes da regra de versões que passam `installed=` explícito ficam como estão, porque testam a regra, não a versão
    instalada;
  - raiz do workspace: `known-first-party`, `root_packages` e contratos do import-linter com `axon_ai_contracts`;
  - `check_clean_env.py`: `EXPECTED = {"axon-ai-contracts", "typing-extensions", "contract-test-pack"}`;
  - `generic.yml`: a lista instalada esperada passa a `["ai-generic", "axon-ai-contracts", "typing-extensions"]`;
  - `uv lock`.
  O `axon-scouting` (submódulo) e a instalação continuam na tag `v0.3.0` até as passadas da 101 e da 002.
- **Rationale** (ADR-037, item 7): a passada que renomeia uma distribuição atualiza, de forma mecânica, os imports de
  quem a consome, para a CI ficar verde. Com a minor nova, todo pack que declara `"0.1"` fica incompatível pela própria
  regra do FR-018; levar a faixa junto é consequência, não escolha. Os nomes do core, do pack de referência e do pack
  de domínio são das passadas deles.
- **Alternatives**: deixar a faixa do `ai-generic` para a 010 (o workspace não resolve: `>=0.1,<0.2` contra o membro
  0.2.0); aplicar a substituição ao repositório inteiro (reescreveria ADRs e research executados).
