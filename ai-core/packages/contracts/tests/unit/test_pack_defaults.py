"""Hooks opcionais devolvem vazio sem erro (US2 cenário 2; T026)."""

from __future__ import annotations

from axon_ai_contracts import AgentPack, PackBase, PackManifest
from axon_ai_contracts.testing import pack_context, turn_view


class MinimalPack(PackBase):
    name = "minimo"
    contract_version = "0.2"

    def manifest(self) -> PackManifest:
        return PackManifest(name="minimo", version="0.1.0")


def test_minimal_pack_has_full_shape() -> None:
    assert isinstance(MinimalPack(), AgentPack)


async def test_optional_hooks_return_empty() -> None:
    pack = MinimalPack()
    ctx = pack_context(pack.name)
    assert pack.system_prompt(ctx) is None
    assert await pack.prepare_context(turn_view(), ctx) == {}
    assert pack.tools(ctx) == ()
    assert pack.retrievers(ctx) == ()
    assert pack.reranker(ctx) is None
    assert pack.validators(ctx) == ()
