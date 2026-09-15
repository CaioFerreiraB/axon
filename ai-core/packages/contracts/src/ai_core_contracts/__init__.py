"""Contratos públicos do núcleo (`ai-core-contracts`): a única superfície que um pack enxerga.

A superfície pública é exatamente o `__all__` deste módulo e o de `ai_core_contracts.testing` (FR-020).
"""

from __future__ import annotations

from ai_core_contracts._freeze import JSONValue
from ai_core_contracts._version import __version__
from ai_core_contracts.compat import (
    BumpKind,
    ChangeKind,
    Compatibility,
    InvalidSpecifier,
    InvalidVersion,
    Version,
    VersionRange,
    check_compatibility,
    declared_bump,
    derive_range,
    parse_contract_version,
    removal_version,
    required_bump,
)
from ai_core_contracts.declaration import ContractIssue, check_declaration
from ai_core_contracts.deprecation import ContractDeprecationWarning, contract_deprecated
from ai_core_contracts.llm import ChatChunk, ChatMessage, ChatResponse, ChatTool, ChatToolCall, ChatUsage, LLMProvider
from ai_core_contracts.mcp import MCPClient
from ai_core_contracts.pack import RETRIEVAL_FILTERS_KEY, AgentPack, PackBase, PackContext, PackManifest
from ai_core_contracts.retrieval import (
    RETRIEVAL_TOOL_PARAMETERS,
    Chunk,
    NamedRetriever,
    Reranker,
    Retriever,
    retrieval_tool_spec,
)
from ai_core_contracts.tools import NativeHandler, ToolInvocation, ToolKind, ToolResult, ToolSpec
from ai_core_contracts.validation import AnswerValidator, ValidationResult, ValidatorContext
from ai_core_contracts.view import Citation, Message, TurnView

__all__ = [
    "RETRIEVAL_FILTERS_KEY",
    "RETRIEVAL_TOOL_PARAMETERS",
    "AgentPack",
    "AnswerValidator",
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
    "Reranker",
    "Retriever",
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
]
