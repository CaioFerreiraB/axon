# Contrato — seams Pack Registry e Pack Hooks (`axon_ai/packs/api.py`)

Único ponto pelo qual outros módulos (003, 004, 005, 008, 011) usam a 002. `api.py` só importa stdlib e a API pública de
`axon_ai_contracts`. Campos e regras: [data-model.md](../data-model.md).

```python
# axon_ai/packs/api.py
from __future__ import annotations

class PackStatus(StrEnum):
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"

@dataclass(frozen=True, slots=True, kw_only=True)
class RetrieverCapability:
    name: str
    collections: frozenset[str]

@dataclass(frozen=True, slots=True, kw_only=True)
class PackCapabilities:
    system_prompt: bool
    tools: tuple[str, ...]
    retrievers: tuple[RetrieverCapability, ...]
    reranker: bool
    validators: tuple[str, ...]
    preferred_flow: str | None
    depends_on: tuple[str, ...]
    requires_collections: tuple[str, ...]

@dataclass(frozen=True, slots=True, kw_only=True)
class PackEntry:
    name: str
    version: str | None
    contract_version: str | None
    origin: Literal["code", "declarative"]
    status: PackStatus
    error: str | None = None
    capabilities: PackCapabilities | None = None

@dataclass(frozen=True, slots=True, kw_only=True)
class Composition:
    packs: tuple[str, ...]

class CompositionError(ValueError):
    packs: tuple[str, ...]              # packs envolvidos (o recusado e, se for o caso, a dependência)

class PackHookError(RuntimeError):
    pack: str
    hook: str                           # "prepare_context", "validate:<validator>", ...

class PackConfigError(ValueError): ...

class PackRegistry(Protocol):
    def entries(self) -> Sequence[PackEntry]: ...          # ordenadas por nome
    def entry(self, name: str) -> PackEntry | None: ...
    def compose(self, pack_names: Sequence[str]) -> Composition: ...   # levanta CompositionError

@dataclass(frozen=True, slots=True, kw_only=True)
class ValidatorRun:
    pack: str
    validator: str
    result: ValidationResult

@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationOutcome:
    ok: bool
    answer: str | None
    citations: tuple[Citation, ...]
    flags: frozenset[str]
    runs: tuple[ValidatorRun, ...]

type Slices = Mapping[str, Mapping[str, JSONValue]]

class PackHooks(Protocol):
    def system_prompts(self, composition: Composition) -> tuple[str, ...]: ...
    async def prepare(self, composition: Composition, view: TurnView, slices: Slices) -> Slices: ...
    async def validate(self, composition: Composition, view: TurnView, slices: Slices) -> ValidationOutcome: ...
    def reranker(self, composition: Composition, pack: str) -> Reranker | None: ...   # Fase 5 (005 research R38)
    # 001 US5 (assinatura do design.md): routine(composition, pack)

# Fase 3 (US3 cen. 1; research R18, R19) — consumido pela 004
@dataclass(frozen=True, slots=True, kw_only=True)
class PackTool:
    name: str                          # "<pack>.<nome local>"
    pack: str
    spec: ToolSpec                     # nome local; o de recuperação via retrieval_tool_spec
    retriever: NamedRetriever | None = None

class PackToolset(Protocol):
    def toolset(self, composition: Composition) -> Sequence[PackTool]: ...

# Fase 6 (ADR-027) — consumido pelo harness da 009
@dataclass(frozen=True, slots=True, kw_only=True)
class PackEvalMetric:
    pack: str
    metric: EvalMetric                 # axon_ai_contracts.eval (contratos 0.1.2)

class PackEvalMetrics(Protocol):
    def eval_metrics(self, composition: Composition) -> Sequence[PackEvalMetric]: ...
```

`eval_metrics`: o hook opcional `eval_metrics(ctx)` do pack é chamado uma vez, na carga (pack sem o método não tem
métricas); exceção ou tipo errado deixa o pack em erro, como os outros hooks de catálogo. O seam devolve as métricas na
ordem da composição revalidada, sem chamar o pack.

## Comportamento

| Operação | Regra | Origem |
|---|---|---|
| `entries()` | uma entrada por pack instalado ou citado na configuração; imutável após a carga | FR-003, FR-006 |
| `compose(names)` | recusa nome desconhecido, pack `disabled`/`error` (mensagem inclui o erro do pack), nome repetido, dependência ausente ou depois do dependente | FR-008, US2 cenário 3, R10 |
| `system_prompts` | fragmentos não vazios, na ordem da composição; vêm do catálogo coletado na carga | US3 cenário 2, 001 FR-019 |
| `prepare` | um pack por vez, na ordem; Turn View recortada (própria fatia + `depends_on`); retorno precisa ser mapeamento JSON; merge raso na fatia do pack; devolve as fatias novas | FR-008, FR-009, R7 |
| `reranker(composition, pack)` | o reranker que o pack declarou, coletado na carga (o hook não roda de novo), ou `None`; por pack porque o reranker pode depender do que o retriever do próprio pack grava — refina a `reranker(composition)` ilustrativa do design.md (005 research R38); pack fora da composição → `ValueError`; composição revalidada | 005 FR-002, US3 |
| `validate` | validators na ordem da composição e do pack; `answer`/`citations` encadeados; exceção interrompe | R8, edge case |
| exceção ou retorno inválido em hook | `PackHookError` com `pack` e `hook`; nenhuma resposta parcial | FR-011, US3 cenário 4 |
| composição recebida | revalidada pelo Pack Hooks antes de executar | R10 |
| `toolset` | por pack, na ordem da composição revalidada: tools nativas na ordem declarada, depois retrievers como tools de recuperação; nome `<pack>.<nome>`; sem I/O | US3 cenário 1, FR-007, R19 |

## Suítes de conformidade do seam

`axon-ai/packages/core/tests/packs/contract/`: `test_packs_registry_seam.py`, `test_packs_hooks_seam.py` e
`test_packs_toolset_seam.py` (Fase 3), contra o `service` montado com adapters em memória. Toda linha da tabela acima
tem um teste. A suíte da porta que a 004 declarou (`tests/capabilities/contract/test_pack_tool_source.py`) roda também
contra o `PackRuntime` (R20).

## Filtro da geração (2026-10-07, ADR-024)

```python
class AnswerFilter(Protocol):
    def feed(self, delta: str) -> str: ...
    def finish(self) -> StreamedValidation: ...     # tail, answer (= o que saiu + tail), runs

class PackHooks(Protocol):
    def open_answer_stream(self, composition, view, slices) -> AnswerFilter: ...
    async def validate(self, composition, view, slices, streamed: StreamedValidation | None = None) -> ValidationOutcome: ...
```

| Regra | Verificada por |
|---|---|
| O prefixo para no primeiro validator sem `open_stream` | `tests/packs/contract/test_packs_hooks_seam.py` |
| Sessões encadeadas na ordem; a cauda de uma entra na seguinte antes de ela fechar | idem |
| `validate(streamed=…)` reaproveita o prefixo e roda só o resto, sobre a resposta filtrada | idem |
| Sessão que não só acrescenta no fim → `PackHookError` (`hook="stream:<validator>"`) | idem |
| Sem validators de streaming, o filtro deixa tudo passar | idem |

## Preparo de dados (2026-10-21, ADR-041)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class PreparedPack:
    name: str
    data_dir: Path | None              # <raiz>/<nome>; None sem raiz de dados
    error: str | None = None           # causa, já na forma que o comando imprime
    @property
    def ok(self) -> bool: ...          # error is None

class PackDataPreparation(Protocol):
    def prepare_data(self) -> Sequence[PreparedPack]: ...    # levanta PackConfigError
```

`PackRuntime` implementa o seam; o nome `prepare` já é do Pack Hooks (preparação de contexto). `prepare_data` não depende
de `load()` nem o substitui: o registry não fica carregado, e o comando roda num processo próprio.

| Regra | Verificada por |
|---|---|
| Um `PreparedPack` por pack habilitado em `packs.yaml`, em ordem de nome; desabilitado e não citado ficam de fora | `tests/packs/contract/test_packs_prepare_seam.py` |
| Até a configuração validada (import, identidade, contrato, instanciação, manifest, `config_schema`), sem nenhum hook de catálogo; falha em qualquer passo vira `error` com a mesma mensagem da carga | idem |
| Pack habilitado e não instalado, ou com nome duplicado → `error`, como na carga | idem |
| O diretório é criado pela porta `PackDataDirs` antes do hook; o `PackContext` traz `data_dir` e a configuração validada | idem |
| Pack sem `prepare` (fora de `PackBase`): só o diretório; `prepare` assíncrono → `error` sem chamar; exceção → `error` com tipo e mensagem | idem |
| Falha de um pack não impede os demais; nenhuma dependência entre packs é considerada (arquivos, não fatias) | idem |
| `packs.yaml` malformado → `PackConfigError` | idem |
| A carga (`load()`) passa `data_dir = <raiz>/<nome>` (ou `None`) no `PackContext`, não cria o diretório e nunca chama `prepare` | `tests/packs/contract/test_packs_registry_seam.py` |
