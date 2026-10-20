"""Packs de teste e distribuições falsas para os testes do Pack Runtime (T007).

Importável pelos testes (`from packs_testkit import ...`); o `conftest.py` expõe as fixtures.
"""

from __future__ import annotations

import importlib
import textwrap
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from axon_ai_contracts import (
    JSONValue,
    PackBase,
    PackContext,
    PackManifest,
    ToolInvocation,
    ToolSpec,
    TurnView,
    ValidationResult,
    ValidatorContext,
)

GOOD_SCHEMA: Mapping[str, JSONValue] = {
    "type": "object",
    "properties": {
        "collection": {"type": "string"},
        "limits": {"type": "object", "properties": {"top_k": {"type": "integer"}}},
    },
    "required": ["collection"],
}


def make_pack_class(
    name: str | None = "good",
    contract_version: str | None = "0.2",
    *,
    manifest: PackManifest | Callable[[Any], PackManifest] | None = None,
    depends_on: Sequence[str] = (),
    init: Callable[[Any], None] | None = None,
    **hooks: Any,
) -> type[PackBase]:
    """Subclasse de PackBase com `name`/`contract_version` como atributos de classe e contador `created`.

    `name=None` ou `contract_version=None` omitem o atributo (para testar a identidade).
    """
    pack_name = name or "sem_nome"

    def __init__(self: Any) -> None:
        type(self).created += 1
        if init is not None:
            init(self)

    def _manifest(self: Any) -> PackManifest:
        if callable(manifest):
            return manifest(self)
        return manifest or PackManifest(name=pack_name, version="0.1.0", depends_on=tuple(depends_on))

    attrs: dict[str, Any] = {"created": 0, "__init__": __init__, "manifest": _manifest, **hooks}
    if name is not None:
        attrs["name"] = name
    if contract_version is not None:
        attrs["contract_version"] = contract_version
    return type(f"Pack_{pack_name}", (PackBase,), attrs)


async def _echo(invocation: ToolInvocation) -> object:
    return dict(invocation.arguments)


class AlwaysOk:
    name = "sempre_ok"

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        return ValidationResult(ok=True)


def make_good_pack(name: str = "good", **overrides: Any) -> type[PackBase]:
    """Pack completo: schema de configuração, prompt, uma tool nativa e um validator determinístico."""

    def manifest(self: Any) -> PackManifest:
        return PackManifest(
            name=name,
            version="0.1.0",
            preferred_flow="chat",
            requires_collections=("docs",),
            config_schema=GOOD_SCHEMA,
        )

    def system_prompt(self: Any, ctx: PackContext) -> str | None:
        return f"Prompt do pack {name}."

    def tools(self: Any, ctx: PackContext) -> tuple[ToolSpec, ...]:
        return (ToolSpec(name="echo", description="Eco.", parameters={"type": "object"}, kind="native", handler=_echo),)

    def validators(self: Any, ctx: PackContext) -> tuple[AlwaysOk, ...]:
        return (AlwaysOk(),)

    hooks: dict[str, Any] = {"system_prompt": system_prompt, "tools": tools, "validators": validators}
    hooks.update(overrides)
    return make_pack_class(name, manifest=manifest, **hooks)


GOOD_CONFIG: Mapping[str, JSONValue] = {"collection": "docs"}


class FakeDistributions:
    """Cria distribuições falsas (`*.dist-info` + módulo) num diretório do `sys.path`."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.modules: list[str] = []

    def add(
        self,
        distribution: str,
        *,
        version: str = "0.1.0",
        entry_points: Mapping[str, str],
        modules: Mapping[str, str] | None = None,
    ) -> None:
        for module, source in (modules or {}).items():
            (self.root / f"{module}.py").write_text(textwrap.dedent(source), encoding="utf-8")
            self.modules.append(module)
        info = self.root / f"{distribution.replace('-', '_')}-{version}.dist-info"
        info.mkdir()
        (info / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {distribution}\nVersion: {version}\n", encoding="utf-8"
        )
        lines = ["[ai_core.packs]", *(f"{name} = {target}" for name, target in entry_points.items())]
        (info / "entry_points.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        importlib.invalidate_caches()


GOOD_MODULE = """
from axon_ai_contracts import PackBase, PackManifest


class GoodPack(PackBase):
    name = "good"
    contract_version = "0.2"
    created = 0

    def __init__(self):
        type(self).created += 1

    def manifest(self):
        return PackManifest(
            name="good",
            version="0.1.0",
            config_schema={
                "type": "object",
                "properties": {"collection": {"type": "string"}},
                "required": ["collection"],
            },
        )

    def system_prompt(self, ctx):
        return "Prompt do pack good para " + ctx.config.get("collection", "?")
"""


def load_runtime(*packs: object, settings: Mapping[str, object] | None = None) -> object:
    """PackRuntime carregado com adapters em memória: `packs` são classes ou pares `(nome, classe)`."""
    from ai_core.packs.adapters.memory import InMemoryPackConfigSource, InMemoryPackSource
    from ai_core.packs.service import PackRuntime

    runtime = PackRuntime(InMemoryPackSource.of(*packs), InMemoryPackConfigSource(settings or {}))  # type: ignore[arg-type]
    runtime.load()
    return runtime
