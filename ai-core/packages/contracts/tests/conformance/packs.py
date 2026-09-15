"""Packs de teste para a suíte de conformidade: um bom e variações defeituosas, montadas por `make_pack`."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ai_core_contracts import JSONValue, PackBase, PackContext, PackManifest, TurnView


class GoodPack(PackBase):
    name = "good"
    contract_version = "0.1"

    def manifest(self) -> PackManifest:
        return PackManifest(name="good", version="0.1.0")


def make_pack(
    *,
    name: str = "good",
    contract_version: str = "0.1",
    manifest: PackManifest | Callable[[Any], PackManifest] | None = None,
    **hooks: Callable[..., Any],
) -> PackBase:
    """Cria um pack herdando de PackBase, com identidade, manifest e hooks sobrescritos."""

    def _manifest(self: Any) -> PackManifest:
        if callable(manifest):
            return manifest(self)
        return manifest or PackManifest(name=name, version="0.1.0")

    attrs: dict[str, Any] = {"name": name, "contract_version": contract_version, "manifest": _manifest, **hooks}
    return type("DynamicPack", (PackBase,), attrs)()


class SyncPreparePack(GoodPack):
    def prepare_context(self, view: TurnView, ctx: PackContext) -> Mapping[str, JSONValue]:  # type: ignore[override]
        return {}


class NotAPack:
    name = "not_a_pack"
