"""Kit de testes para packs: fixtures de Turn View e suíte de conformidade. Só stdlib, qualquer runner (R17).

Faz parte da superfície pública versionada (FR-020), com o `__all__` abaixo.
"""

from __future__ import annotations

from typing import Final

from ai_core_contracts.testing.conformance import (
    ConformanceReport,
    aassert_pack_conforms,
    acheck_pack,
    assert_pack_conforms,
    check_pack,
)
from ai_core_contracts.testing.distribution import check_contracts_requirement
from ai_core_contracts.testing.fixtures import (
    REFERENCE_TIME,
    chunk,
    pack_context,
    tool_invocation,
    turn_view,
    validator_context,
)
from ai_core_contracts.testing.imports import check_imports
from ai_core_contracts.testing.services import acheck_llm_provider, acheck_mcp_client

ISSUE_CODES: Final[frozenset[str]] = frozenset(
    {
        "hook.missing",
        "hook.not_async",
        "hook.raised",
        "hook.return_type",
        "pack.name.invalid",
        "pack.contract_version.invalid",
        "pack.contract_version.incompatible",
        "manifest.type",
        "manifest.name_mismatch",
        "manifest.version.invalid",
        "manifest.preferred_flow.invalid",
        "manifest.self_dependency",
        "manifest.duplicate_dependency",
        "manifest.duplicate_collection",
        "manifest.config_schema.invalid",
        "reranker.contract",
        "tool.not_native",
        "tool.name.invalid",
        "tool.duplicate_name",
        "tool.parameters.invalid",
        "tool.handler.not_async",
        "retriever.name.invalid",
        "retriever.duplicate_name",
        "retriever.name_collision",
        "validator.name.invalid",
        "validator.duplicate_name",
        "validator.result_type",
        "validator.non_deterministic",
        "prepare_context.not_mapping",
        "prepare_context.not_json",
        "prepare_context.retrieval_filters.invalid",
        "prepare_context.non_deterministic",
        "imports.forbidden",
        "distribution.not_found",
        "distribution.missing_requirement",
        "distribution.direct_reference",
        "distribution.unsupported_specifier",
        "distribution.range_too_wide",
        "distribution.range_disjoint",
        "deprecation.used",
        "llm.response.invalid",
        "llm.stream.invalid",
        "mcp.discovery.invalid",
        "mcp.result.invalid",
    }
)
"""Todos os códigos de issue que a distribuição emite. Código novo é aditivo; remover é breaking (FR-020)."""

__all__ = [
    "ISSUE_CODES",
    "REFERENCE_TIME",
    "ConformanceReport",
    "aassert_pack_conforms",
    "acheck_llm_provider",
    "acheck_mcp_client",
    "acheck_pack",
    "assert_pack_conforms",
    "check_contracts_requirement",
    "check_imports",
    "check_pack",
    "chunk",
    "pack_context",
    "tool_invocation",
    "turn_view",
    "validator_context",
]
