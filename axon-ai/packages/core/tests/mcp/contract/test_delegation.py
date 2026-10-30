"""D01/D02/D04: identidade por execução, sem cache ou fallback."""

import asyncio
from dataclasses import replace

import pytest
from mcp_testkit import FINANCEIRO_URL, build, global_draft, grant

from axon_ai.mcp.api import DelegatedAuthorization, McpRejected


@pytest.mark.asyncio
async def test_concurrent_delegation_never_shares_discovery_or_identity(server_store):
    kit = build(store=server_store)
    await kit.service.create_global(global_draft(auth_type="delegated"))
    descriptor = await kit.service.delegation_for(grant("financeiro"))
    assert descriptor.endpoint == FINANCEIRO_URL
    a = DelegatedAuthorization(alias="financeiro", endpoint=FINANCEIRO_URL, authorization="Bearer secret-a")
    b = DelegatedAuthorization(alias="financeiro", endpoint=FINANCEIRO_URL, authorization="Bearer secret-b")
    assert "secret-a" not in repr(a)
    ca = kit.service.client_for(grant("financeiro"), delegation=a)
    cb = kit.service.client_for(grant("financeiro"), delegation=b)
    await asyncio.gather(ca.discover(["financeiro"]), cb.discover(["financeiro"]))
    await ca.discover(["financeiro"])
    await cb.execute("financeiro", "saldo", {})
    headers = [target.headers["Authorization"] for _, target in kit.transport.calls]
    assert sorted(headers[:2]) == ["Bearer secret-a", "Bearer secret-b"]
    assert headers[2:] == ["Bearer secret-a", "Bearer secret-b"]


@pytest.mark.asyncio
async def test_missing_or_changed_destination_fails_closed():
    kit = build(secrets={"static": "must-not-be-used"})
    draft = global_draft(auth_type="delegated")
    await kit.service.create_global(draft)
    empty = await kit.service.client_for(grant("financeiro")).discover(["financeiro"])
    assert empty.unavailable and not kit.transport.calls
    auth = DelegatedAuthorization(alias="financeiro", endpoint=FINANCEIRO_URL, authorization="Bearer secret-a")
    client = kit.service.client_for(grant("financeiro"), delegation=auth)
    await kit.service.update_global("financeiro", replace(draft, endpoint="https://other.example/mcp"))
    assert (await client.discover(["financeiro"])).unavailable
    assert not kit.transport.calls
    await kit.service.update_global("financeiro", replace(draft, auth_type="bearer", credential_ref="static"))
    assert (await client.discover(["financeiro"])).unavailable
    assert not kit.transport.calls


@pytest.mark.asyncio
async def test_one_delegated_alias_and_explicit_exclusive_configuration():
    kit = build()
    for overrides in (
        {"credential_ref": "static"},
        {"user_access": True},
        {"transport": "sse"},
        {"endpoint": "http://example.com/mcp"},
    ):
        with pytest.raises(McpRejected):
            await kit.service.create_global(global_draft(auth_type="delegated", **overrides))
    await kit.service.create_global(global_draft(auth_type="delegated"))
    await kit.service.create_global(global_draft(alias="second", auth_type="delegated"))
    with pytest.raises(McpRejected):
        await kit.service.delegation_for(grant("financeiro", "second"))


@pytest.mark.parametrize("value", ["", "secret", "Bearer ", "Bearer a b", "Bearer a\nb", "Bearer " + "x" * 4097])
def test_confidential_validation(value):
    with pytest.raises(McpRejected):
        DelegatedAuthorization(alias="financeiro", endpoint=FINANCEIRO_URL, authorization=value)
