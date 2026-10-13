# Contrato — kit de testes `ai_core_contracts.testing`

Parte pública e versionada da distribuição (R17): fixtures de Turn View, a suíte de conformidade de pack e as suítes
mínimas dos contratos de serviço. Só stdlib;
funciona com qualquer runner. É o que SC-002, SC-003 e SC-005 usam como prova, e o que 010 FR-003 e 101 exigem.

## API

```python
# ai_core_contracts/testing/__init__.py
REFERENCE_TIME: Final[datetime]           # 2026-01-01T12:00:00+00:00 — data fixa padrão das fixtures

# fixtures.py — construtores determinísticos; todo argumento é só-nome e opcional
def turn_view(*, request_id: str = "req-test", assistant: str = "test-assistant",
              reference_time: datetime = REFERENCE_TIME, question: str = "", messages=(), retrieved=(),
              reranked=(), generation_context=(), tool_results=(), answer=None, citations=(),
              own_slice=None, dependency_slices=None) -> TurnView: ...
def chunk(chunk_id: str = "doc#1", *, text: str = "", score: float = 1.0, document: str = "doc",
          version=None, status=None, section=None, page=None, metadata=None) -> Chunk: ...
def pack_context(pack_name: str, config: Mapping[str, JSONValue] | None = None) -> PackContext: ...
def validator_context(pack_name: str, config: Mapping[str, JSONValue] | None = None) -> ValidatorContext: ...
def tool_invocation(arguments: Mapping[str, JSONValue] | None = None, *, request_id: str = "req-test",
                    reference_time: datetime = REFERENCE_TIME) -> ToolInvocation: ...

# conformance.py
@dataclass(frozen=True, slots=True, kw_only=True)
class ConformanceReport:
    pack_name: str
    issues: tuple[ContractIssue, ...]
    @property
    def ok(self) -> bool: ...             # nenhuma issue "error"
    def render(self) -> str: ...          # texto legível, uma issue por linha

async def acheck_pack(pack: object, *, config: Mapping[str, JSONValue] | None = None,
                      views: Sequence[TurnView] | None = None,
                      check_distribution: bool = True) -> ConformanceReport: ...
def check_pack(pack: object, **kwargs) -> ConformanceReport: ...      # asyncio.run; RuntimeError se já houver loop
async def aassert_pack_conforms(pack: object, **kwargs) -> None: ...  # AssertionError com report.render()
def assert_pack_conforms(pack: object, **kwargs) -> None: ...

# checagens puras reutilizáveis
def check_contracts_requirement(requirements: Sequence[str], contract_version: str) -> tuple[ContractIssue, ...]: ...
def check_imports(package: str, *, forbidden: Sequence[str] = ("ai_core", "ai_generic")) -> tuple[ContractIssue, ...]: ...
#   o próprio pacote varrido nunca é proibido (ex.: ai_generic importando ai_generic.x); módulo solto = um arquivo

# services.py — suítes mínimas dos contratos de serviço (R21, R22); 006 e 007 rodam contra os adapters reais
async def acheck_llm_provider(provider: object, *, model: str = "test-model") -> tuple[ContractIssue, ...]: ...
async def acheck_mcp_client(client: object, *, alias: str, tool: str,
                            arguments: Mapping[str, JSONValue] | None = None) -> tuple[ContractIssue, ...]: ...

ISSUE_CODES: Final[frozenset[str]]        # todos os códigos abaixo; entra no snapshot de superfície
```

- `config`: configuração do pack para montar o `PackContext` (os hooks de catálogo são chamados uma vez, como na carga).
- `views`: Turn Views usadas em `prepare_context` e nos validators; default = `[turn_view()]` com `own_slice` vazio e
  `dependency_slices` só com os packs de `manifest.depends_on` (fatias vazias).
- `check_distribution=False`: só para packs do workspace do core, testados contra os contratos do mesmo commit (010 FR-004).

## O que `acheck_pack` verifica, em ordem

Uma etapa que falha com issue `error` e impede as seguintes (ex.: sem manifest não há catálogo) encerra a verificação.

| # | Etapa | Códigos |
|---|---|---|
| 1 | Forma: `isinstance(pack, AgentPack)`; `prepare_context` e `validate`/`search`/`rerank` assíncronos | `hook.missing`, `hook.not_async` |
| 2 | Identidade: nome (`^[a-z][a-z0-9_]{0,31}$`), `contract_version` (`X.Y[.Z]`) e compatível com a versão instalada | `pack.name.invalid`, `pack.contract_version.invalid`, `pack.contract_version.incompatible` |
| 3 | Manifest: tipo, nome igual ao do pack, versão válida, `preferred_flow` não vazio, `depends_on` sem repetição e sem o próprio nome, `requires_collections` sem repetição, `config_schema` estruturalmente válido | `manifest.type`, `manifest.name_mismatch`, `manifest.version.invalid`, `manifest.preferred_flow.invalid`, `manifest.self_dependency`, `manifest.duplicate_dependency`, `manifest.duplicate_collection`, `manifest.config_schema.invalid` |
| 4 | Catálogo — hooks chamados **uma vez** com o `PackContext`; exceção ou tipo errado; `rerank` assíncrono e, chamado com três chunks de fixture e `top_k=2`, devolve no máximo 2, todos vindos da entrada (FR-007) | `hook.raised`, `hook.return_type`, `hook.not_async`, `reranker.contract` |
| 5 | Declaração — `check_declaration` (R13): tools só nativas, com handler assíncrono, nomes válidos e únicos, `parameters` com `type: "object"`; retrievers com nome válido e único, sem colisão com tools e com `search` assíncrono; validators com nome válido e único e `validate` assíncrono | `tool.not_native`, `tool.name.invalid`, `tool.duplicate_name`, `tool.parameters.invalid`, `tool.handler.not_async`, `retriever.name.invalid`, `retriever.duplicate_name`, `retriever.name_collision`, `validator.name.invalid`, `validator.duplicate_name`, `hook.not_async` |
| 6 | `prepare_context` para cada view: devolve `Mapping`; valores JSON; `retrieval_filters`, se presente, é mapeamento JSON; mesma entrada duas vezes → mesma saída | `prepare_context.not_mapping`, `prepare_context.not_json`, `prepare_context.retrieval_filters.invalid`, `prepare_context.non_deterministic` |
| 7 | Validators para cada view: devolvem `ValidationResult`; mesma entrada duas vezes → mesmo resultado | `validator.result_type`, `validator.non_deterministic` |
| 7b | Métricas de domínio (0.1.2, ADR-027), só se o pack tem `eval_metrics`: o hook devolve sequência de `EvalMetric`, nomes não vazios e únicos, `better` em `higher`/`lower`, `deterministic` bool e `measure` síncrono | `hook.raised`, `hook.return_type`, `eval_metric.name.invalid`, `eval_metric.duplicate_name`, `eval_metric.contract` |
| 8 | Imports do pacote do pack (AST): nenhum `ai_core`/`ai_generic` — a mensagem nomeia arquivo, linha e módulo | `imports.forbidden` |
| 9 | Distribuição (se `check_distribution`): regras de [compatibility.md §5](compatibility.md) | `distribution.*` |
| — | Durante todas as etapas: `ContractDeprecationWarning` capturado | `deprecation.used` (*warning*) |

`hook.raised` e `hook.return_type` também valem nas etapas 6 e 7. Toda issue carrega `subject` (ex.: `tool:search`,
`retriever:docs`, `validator:citation_integrity`, `reranker`, `hook:prepare_context`, `file:pack.py:12`).

## Suítes dos contratos de serviço

| Suíte | O que verifica | Código |
|---|---|---|
| `acheck_llm_provider` | `await chat([{"role": "user", "content": "ping"}], model)` devolve mapeamento com `message` (`role == "assistant"`, `content` `str` ou `None`) e `finish_reason` `str` | `llm.response.invalid` |
| `acheck_llm_provider` | `await chat(..., stream=True)` devolve iterador assíncrono de mapeamentos com `delta` `str`; `finish_reason` aparece só no último chunk e nele é obrigatório | `llm.stream.invalid` |
| `acheck_mcp_client` | `await discover_tools([alias])` devolve sequência de `ToolSpec` com `kind == "mcp"` e `handler is None` | `mcp.discovery.invalid` |
| `acheck_mcp_client` | `await execute(alias, tool, arguments or {})` devolve `ToolResult` com `untrusted is True` | `mcp.result.invalid` |

Exceção levantada durante a suíte vira a issue da linha correspondente, com a exceção na mensagem.

Invariantes de construção não viram código de issue: `ToolSpec` nativa sem handler (ou não-nativa com handler) e
`NamedRetriever` sem coleção levantam `ValueError` ao serem criados. Dentro de um hook de catálogo, isso aparece como
`hook.raised`, e o pack não carrega do mesmo jeito (edge case "retriever sem coleção").

## Uso esperado num pack

```python
# tests/test_conformance.py de um pack externo
from ai_core_contracts.testing import assert_pack_conforms, turn_view
from meu_pack.pack import MeuPack

def test_pack_conforms():
    assert_pack_conforms(MeuPack(), config={"collection": "docs"},
                         views=[turn_view(question="pergunta de exemplo")])
```

Hooks individuais são testados com as fixtures (`turn_view(...)`, `chunk(...)`, `pack_context(...)`), sem subir nenhum
serviço (SC-003).

## Etapa de validators — streaming (0.1.1, ADR-024)

Para cada validator que implementa `StreamingValidator` e cada Turn View com `answer`: a sessão é aberta sem `answer` e
alimentada em três partições (inteira, um caractere por vez, pedaços de 7). `validator.stream.not_append_only` quando
`finish().answer` não começa com o texto liberado; `validator.stream.mismatch` quando o resultado difere do `validate`.
