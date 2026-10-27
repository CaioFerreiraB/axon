"""Superfície pública exata (contracts/python-api.md e contracts/testing-kit.md; T056).

Acrescentar ou remover símbolo público exige mudar este teste de propósito — e o bump de versão exigido pelo FR-020.
"""

from __future__ import annotations

import axon_ai_contracts
import axon_ai_contracts.testing

RUNTIME_API = {
    "AgentPack",
    "AnswerStream",
    "AnswerValidator",
    "Attachment",
    "BumpKind",
    "ChangeKind",
    "ChatChunk",
    "ChatMessage",
    "ChatResponse",
    "ChatTool",
    "ChatToolCall",
    "ChatUsage",
    "Chunk",
    "Citation",
    "Compatibility",
    "ContractDeprecationWarning",
    "ContractIssue",
    "EvalChunk",
    "EvalEvidence",
    "EvalItem",
    "EvalMetric",
    "EvalObservation",
    "InvalidSpecifier",
    "InvalidVersion",
    "JSONValue",
    "LLMProvider",
    "MCPClient",
    "Message",
    "NamedRetriever",
    "NativeHandler",
    "PackBase",
    "PackContext",
    "PackManifest",
    "PreparesData",
    "ProvidesEvalMetrics",
    "ATTACHMENT_MIME_TYPES",
    "RETRIEVAL_FILTERS_KEY",
    "RETRIEVAL_TOOL_PARAMETERS",
    "Reranker",
    "Retriever",
    "StreamingValidator",
    "ToolInvocation",
    "ToolKind",
    "ToolResult",
    "ToolSpec",
    "TurnView",
    "ValidationResult",
    "ValidatorContext",
    "Version",
    "VersionRange",
    "__version__",
    "check_compatibility",
    "check_declaration",
    "contract_deprecated",
    "declared_bump",
    "derive_range",
    "parse_contract_version",
    "removal_version",
    "required_bump",
    "retrieval_tool_spec",
}

TESTING_API = {
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
}


def test_runtime_surface_is_exactly_the_documented_one() -> None:
    assert set(axon_ai_contracts.__all__) == RUNTIME_API


def test_testing_surface_is_exactly_the_documented_one() -> None:
    assert set(axon_ai_contracts.testing.__all__) == TESTING_API


def test_every_exported_name_is_importable() -> None:
    for module in (axon_ai_contracts, axon_ai_contracts.testing):
        for name in module.__all__:
            assert hasattr(module, name), f"{module.__name__}.{name}"
