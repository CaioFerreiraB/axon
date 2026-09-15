# Design — 001 Contratos públicos

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §5, §6, §7.4, §30; ADR-004, ADR-005, ADR-011, ADR-012, ADR-013.
> Onde o ADR-011 altera a arch-v1, a mudança está marcada com **[ADR-011]**.

## Localização

```text
ai-core/packages/contracts/src/ai_core_contracts/
├── pack.py          # AgentPack, PackManifest, PackContext, PackRoutine
├── tools.py         # ToolSpec, ToolResult
├── view.py          # TurnView                                   [ADR-011 — substitui state.py]
├── llm.py           # LLMProvider
├── retrieval.py     # Retriever, Reranker, Chunk
├── mcp.py           # MCPClient
├── validation.py    # AnswerValidator, ValidationResult
└── compat.py        # regra semver de compatibilidade de contract_version
```

Sem dependências além da stdlib e de `typing_extensions`. É o que evita um pack externo arrastar FastAPI, LangGraph e Qdrant como dependência transitiva.

> **[ADR-011]** arch-v1 listava `state.py # AgentState` aqui. `AgentState` usa reducers do LangGraph e passa a existir só em `ai_core/graph/state.py` (spec 005).

## AgentPack

```python
class AgentPack(Protocol):
    name: str
    contract_version: str

    def manifest(self) -> PackManifest:
        """Metadados, flow preferido, dependências, config schema."""

    def system_prompt(self, ctx: PackContext) -> str | None:
        """Fragmento de instrução. O core concatena na ordem declarada pelo Assistant."""

    async def prepare_context(self, view: TurnView, ctx: PackContext) -> dict:   # [ADR-011]
        """Pré-processamento determinístico. RETORNA a atualização da própria fatia;
        o core faz o merge em packs[self.name]. Pode incluir 'retrieval_filters',
        repassados de forma opaca aos retrievers deste pack."""

    def tools(self, ctx: PackContext) -> list[ToolSpec]:
        """Catálogo. Nomes são locais; o core aplica namespace."""

    def retrievers(self, ctx: PackContext) -> list[NamedRetriever]: ...

    def reranker(self, ctx: PackContext) -> Reranker | None: ...

    def validators(self, ctx: PackContext) -> list[AnswerValidator]:
        """Checagens determinísticas da resposta."""

    def routine(self, ctx: PackContext) -> PackRoutine | None:                  # [ADR-011]
        """Escape hatch (nível 3). Raro."""
```

Não existe `build_graph()`. Packs não constroem grafos (ADR-001).

```python
@dataclass(frozen=True)
class PackManifest:
    name: str
    version: str
    preferred_flow: str | None          # nome; o Assistant pode sobrescrever
    depends_on: list[str] = ()          # fatias de outros packs que este pack lê
    requires_collections: list[str] = ()
    config_schema: dict | None = None   # JSON Schema
```

## ToolSpec e ToolResult

```python
@dataclass(frozen=True)
class ToolSpec:
    name: str                                    # local: "search_docs" → core expõe "scouting.search_docs"
    description: str
    parameters: dict                             # JSON Schema
    kind: Literal["retrieval", "mcp", "native"]
    mutates: bool = False                        # tool de escrita
    handler: Callable[..., Awaitable[object]] | None = None   # só para native


@dataclass(frozen=True)
class ToolResult:
    content: object
    untrusted: bool = True          # sempre verdadeiro para conteúdo externo
    truncated: bool = False
    error: str | None = None
```

`kind` permite um único ponto de execução despachar retrieval, MCP ou código nativo (ADR-005). `mutates` marca tools de escrita, que exigem autorização explícita (spec 004).

## Turn View **[ADR-011]**

```python
@dataclass(frozen=True)
class TurnView:
    request_id: str
    assistant: str
    reference_time: datetime               # data de referência da execução, a mesma para todos os hooks [ADR-013]
    question: str
    messages: Sequence[Mapping]            # somente leitura
    retrieved: Sequence[Chunk]
    reranked: Sequence[Chunk]
    generation_context: Sequence[Chunk]    # chunks efetivamente entregues à geração (base da verificação de citação)
    tool_results: Sequence[ToolResult]
    answer: str | None
    citations: Sequence[Mapping]
    own_slice: Mapping                     # packs[self.name]
    dependency_slices: Mapping[str, Mapping]   # só dos packs em manifest.depends_on
```

Regras de versionamento: ~~campo novo = minor; remoção, renomeação ou mudança de semântica = major~~ — superado pelo
**[ADR-014]**: enquanto 0.x, campo novo = patch e remoção, renomeação ou mudança de semântica = minor; a partir de 1.0,
minor e major.
O core produz a Turn View a partir do estado interno (spec 005); a forma do estado interno não é contrato.

`reference_time` **[ADR-013]**: o motor o fixa no início da execução (porta de relógio, ou valor fixado numa execução
de avaliação) e o repete em toda Turn View daquela execução. Packs usam esse valor em vez do relógio do sistema — é o
que torna itens datados do conjunto dourado reproduzíveis e hooks testáveis com data fixa. `datetime` é da stdlib.

## PackRoutine **[ADR-011 — substitui "subgraph LangGraph compilado" de arch-v1 §7.4]**

```python
class PackRoutine(Protocol):
    reads: frozenset[str]          # campos da Turn View que a rotina precisa
    writes: frozenset[str]         # saídas declaradas, além da própria fatia

    async def run(self, inputs: Mapping, own_slice: Mapping, limits: Limits) -> RoutineResult:
        """Recebe só o declarado. Não tem referência ao fluxo pai.
        Limites de iteração e orçamento herdados do Assistant."""
```

Propriedades mantidas da arch-v1: não reconecta o grafo pai; limites próprios herdados; injeção de nós/arestas não existe.

## LLMProvider

```python
class LLMProvider(Protocol):
    async def chat(
        self,
        messages: list[dict],
        model: str,
        *,
        tools: list[dict] | None = None,
        response_format: dict | None = None,   # saída estruturada
        stream: bool = False,
    ) -> AsyncIterator[dict] | dict: ...
```

`response_format` importa: o controller depende de saída estruturada confiável, e modelos pequenos só entregam isso sob constraint. `stream` está no contrato desde o início porque retrofit de streaming é caro.

## Retriever, Reranker, Chunk, MCPClient

```python
class Retriever(Protocol):
    async def search(self, query: str, *, top_k: int = 20, filters: dict | None = None) -> list[Chunk]: ...

class Reranker(Protocol):
    async def rerank(self, query: str, documents: list[Chunk], *, top_k: int = 5) -> list[Chunk]: ...

@dataclass(frozen=True)
class Chunk:
    chunk_id: str          # estável e determinístico, ex.: "man-pio-2026#4.2.1@p87"
    text: str
    score: float
    document: str
    version: str | None
    status: str | None     # semântica definida pelo pack (ex.: vigente/revogado)
    section: str | None
    page: int | None
    metadata: Mapping

class MCPClient(Protocol):
    async def discover_tools(self, aliases: list[str]) -> list[ToolSpec]: ...
    async def execute(self, alias: str, tool: str, arguments: dict) -> ToolResult: ...
```

`discover_tools` recebe **aliases já autorizados**, nunca URLs. A resolução alias → endpoint + credencial acontece server-side no MCP Registry (spec 007).

## AnswerValidator

```python
class AnswerValidator(Protocol):
    name: str
    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:   # [ADR-011]
        """Determinístico. ValidatorContext não expõe LLM."""

@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    issues: list[str]
    answer: str | None = None            # resposta modificada (ex.: aviso adicionado)
    citations: list[Mapping] | None = None   # citações após remoção das não resolvíveis
    flags: frozenset[str] = frozenset()  # ex.: {"ungrounded", "non_current_source"}
```

## Versionamento

| Distribuição | Repositório | Versão | Tag de exemplo |
|---|---|---|---|
| `ai-core-contracts` | `ai-core` | própria | `contracts-v0.1.0` |
| `ai-core` e `ai-generic` | `ai-core` | única, lançados juntos | `v0.3.1` |
| `ai-scouting` e demais packs | próprio | própria | `v0.1.4` |

| Regra | |
|---|---|
| Semver em `ai-core-contracts` **[ADR-014]** | enquanto 0.x: aditiva = patch, breaking = minor; a partir de 1.0: aditiva = minor, breaking = major |
| Janela de depreciação **[ADR-014]** | uma série compatível: depreciado em 0.N.x sai a partir de 0.(N+1).0 |
| `contract_version` no pack | verificada no boot (spec 002) |
| Faixa nos packs externos | `>=0.1,<0.2` |
| `ai-generic` | testado contra os contratos do mesmo commit, sem faixa |

## Fronteiras verificadas

```toml
# ai-core/pyproject.toml
[tool.importlinter]
root_packages = ["ai_core_contracts", "ai_core", "ai_generic"]

[[tool.importlinter.contracts]]
name = "contratos não importam o resto do projeto"
type = "forbidden"
source_modules = ["ai_core_contracts"]
forbidden_modules = ["ai_core", "ai_generic"]

[[tool.importlinter.contracts]]
name = "contratos não dependem de frameworks do runtime"    # [ADR-011]
type = "forbidden"
source_modules = ["ai_core_contracts"]
forbidden_modules = ["langgraph", "langchain", "fastapi", "qdrant_client", "sqlalchemy"]

[[tool.importlinter.contracts]]
name = "core e pack genérico não se importam"
type = "independence"
modules = ["ai_core", "ai_generic"]
```

Cada pack externo roda a mesma verificação no próprio CI, proibindo `ai_core`.

## Portas e adapters **[ADR-012]**

Os contratos são as **portas do microkernel**. Não fazem I/O e não têm adapters próprios; quem os implementa são os
packs e os módulos do core.

| Porta | Tipo | Adapters (quem implementa) | Quem consome | Teste |
|---|---|---|---|---|
| `AgentPack` e hooks | porta de plug-in | packs (010, 1xx) | 002 | suíte de conformidade de pack |
| `Retriever`, `Reranker` | porta secundária do core, implementada por plug-in | packs | 004 (via gateway), 002 (reranker via hooks) | idem |
| `AnswerValidator` | porta de plug-in | packs | 002 | idem |
| `PackRoutine` | porta de plug-in | packs | 005 (via 002) | idem |
| `LLMProvider` | porta secundária do core | 006 (Ollama, OpenAI, OpenRouter) + provider simulado de teste | 006 (Model Router) | suíte de conformidade de provider |
| `MCPClient` | porta secundária do core | 007 | 004 | suíte de conformidade de cliente MCP |
| `TurnView` | value object produzido pelo core | 005 (produz) | packs, via 002 | fixtures de Turn View |

## Sugestão para o plano

- Uma **suíte de conformidade de pack** publicada junto dos contratos (ex.: `ai_core_contracts.testing`): fixtures de Turn View e checagens que todo pack roda. É ela que prova o SC-002.
- Suítes de conformidade também para `LLMProvider` e `MCPClient`, rodadas contra cada implementação e contra os adapters simulados de teste (princípio XIII).
- Verificação de API pública no CI (diff de símbolos exportados) para detectar breaking change (SC-004).
- ~~Fixar a política de versões 0.x~~ — resolvido em 2026-09-15 pela clarificação da spec (FR-016) e pelo **[ADR-014]**.
