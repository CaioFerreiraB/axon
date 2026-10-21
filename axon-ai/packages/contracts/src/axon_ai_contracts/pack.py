"""Contrato de pack: identidade, manifest, contexto de carga e hooks (FR-002, FR-003, FR-010, FR-012, FR-019).

Packs não constroem grafos (ADR-001). Os hooks de catálogo — `system_prompt`, `tools`, `retrievers`, `reranker` e
`validators` — são chamados uma vez, na carga; dados por execução chegam só pela Turn View. O hook `prepare` (ADR-041)
roda só no build da instalação, nunca na carga.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from axon_ai_contracts._freeze import JSONValue, empty_mapping, freeze_mapping, freeze_sequence, require_non_empty
from axon_ai_contracts.retrieval import NamedRetriever, Reranker
from axon_ai_contracts.tools import ToolSpec
from axon_ai_contracts.validation import AnswerValidator
from axon_ai_contracts.view import TurnView

if TYPE_CHECKING:  # o módulo de avaliação importa PackContext daqui; `Path` é só tipo (runtime sem I/O, R20)
    from pathlib import Path

    from axon_ai_contracts.eval import EvalMetric

RETRIEVAL_FILTERS_KEY: Final = "retrieval_filters"
"""Chave da fatia com os filtros que o core repassa, de forma opaca, aos retrievers do próprio pack (FR-012)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PackManifest:
    """Metadados do pack. As regras de validade estão em `check_declaration`."""

    name: str
    version: str
    preferred_flow: str | None = None
    depends_on: Sequence[str] = ()
    requires_collections: Sequence[str] = ()
    config_schema: Mapping[str, JSONValue] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "depends_on", freeze_sequence(self.depends_on))
        object.__setattr__(self, "requires_collections", freeze_sequence(self.requires_collections))
        if self.config_schema is not None:
            object.__setattr__(self, "config_schema", freeze_mapping(self.config_schema))


@dataclass(frozen=True, slots=True, kw_only=True)
class PackContext:
    """Dados de carga do pack: nome, configuração já validada contra `config_schema` e diretório de dados. Nenhum
    serviço.

    `data_dir` (0.2.1, ADR-041) é o diretório do pack que a plataforma entrega — o mesmo no build, onde `prepare` o
    preenche, e em runtime, onde é somente leitura. `None` quando a plataforma não tem raiz de dados: o pack recorre à
    própria configuração.
    """

    pack_name: str
    config: Mapping[str, JSONValue] = field(default_factory=empty_mapping)
    data_dir: Path | None = None

    def __post_init__(self) -> None:
        require_non_empty("pack_name", self.pack_name)
        object.__setattr__(self, "config", freeze_mapping(self.config))


@runtime_checkable
class AgentPack(Protocol):
    """Forma completa de um pack. Herde de `PackBase` para ganhar os hooks opcionais com default."""

    name: str
    contract_version: str

    def manifest(self) -> PackManifest: ...

    def system_prompt(self, ctx: PackContext) -> str | None: ...

    async def prepare_context(self, view: TurnView, ctx: PackContext) -> Mapping[str, JSONValue]:
        """Devolve a atualização rasa da própria fatia; pode incluir `retrieval_filters`."""
        ...

    def tools(self, ctx: PackContext) -> Sequence[ToolSpec]:
        """Só tools nativas; `retrieval` é derivada dos retrievers e `mcp` vem da descoberta do cliente MCP."""
        ...

    def retrievers(self, ctx: PackContext) -> Sequence[NamedRetriever]: ...

    def reranker(self, ctx: PackContext) -> Reranker | None: ...

    def validators(self, ctx: PackContext) -> Sequence[AnswerValidator]: ...


@runtime_checkable
class PreparesData(Protocol):
    """Hook opcional (0.2.1, ADR-041): produz em `ctx.data_dir` os arquivos de que o pack precisa em runtime.

    Chamado só no build da instalação (`axon packs prepare`), com a configuração já validada; nunca na carga. Síncrono e
    idempotente: o que já está presente e íntegro não é baixado de novo, e tudo o que baixa é fixado e conferido.
    """

    def prepare(self, ctx: PackContext) -> None: ...


class PackBase:
    """Defaults dos hooks opcionais. O pack define `name`, `contract_version` e `manifest()`."""

    def system_prompt(self, ctx: PackContext) -> str | None:
        return None

    async def prepare_context(self, view: TurnView, ctx: PackContext) -> Mapping[str, JSONValue]:
        return {}

    def tools(self, ctx: PackContext) -> Sequence[ToolSpec]:
        return ()

    def retrievers(self, ctx: PackContext) -> Sequence[NamedRetriever]:
        return ()

    def reranker(self, ctx: PackContext) -> Reranker | None:
        return None

    def validators(self, ctx: PackContext) -> Sequence[AnswerValidator]:
        return ()

    def eval_metrics(self, ctx: PackContext) -> Sequence[EvalMetric]:
        """Métricas de domínio para o harness de avaliação (ADR-027); opcional — nenhuma por default."""
        return ()

    def prepare(self, ctx: PackContext) -> None:
        """Dados de runtime produzidos no build (ADR-041); opcional — nada por default."""
        return None
