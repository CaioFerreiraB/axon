# Contrato — seams Pack Registry e Pack Hooks (`ai_core/packs/api.py`)

Único ponto pelo qual outros módulos (003, 004, 005, 008, 011) usam a 002. `api.py` só importa stdlib e a API pública de
`ai_core_contracts`. Campos e regras: [data-model.md](../data-model.md).

```python
# ai_core/packs/api.py
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
    # Fase 5 / 001 US5 (assinaturas do design.md): reranker(composition) e routine(composition, pack)
```

## Comportamento

| Operação | Regra | Origem |
|---|---|---|
| `entries()` | uma entrada por pack instalado ou citado na configuração; imutável após a carga | FR-003, FR-006 |
| `compose(names)` | recusa nome desconhecido, pack `disabled`/`error` (mensagem inclui o erro do pack), nome repetido, dependência ausente ou depois do dependente | FR-008, US2 cenário 3, R10 |
| `system_prompts` | fragmentos não vazios, na ordem da composição; vêm do catálogo coletado na carga | US3 cenário 2, 001 FR-019 |
| `prepare` | um pack por vez, na ordem; Turn View recortada (própria fatia + `depends_on`); retorno precisa ser mapeamento JSON; merge raso na fatia do pack; devolve as fatias novas | FR-008, FR-009, R7 |
| `validate` | validators na ordem da composição e do pack; `answer`/`citations` encadeados; exceção interrompe | R8, edge case |
| exceção ou retorno inválido em hook | `PackHookError` com `pack` e `hook`; nenhuma resposta parcial | FR-011, US3 cenário 4 |
| composição recebida | revalidada pelo Pack Hooks antes de executar | R10 |

## Suítes de conformidade do seam

`ai-core/packages/core/tests/packs/contract/`: `test_packs_registry_seam.py` e `test_packs_hooks_seam.py`, contra o
`service` montado com adapters em memória. Toda linha da tabela acima tem um teste.
