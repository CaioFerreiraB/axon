"""Contratos públicos do núcleo (`axon-ai-contracts`): a única superfície que um pack enxerga.

A superfície pública é exatamente o `__all__` deste módulo e o de `axon_ai_contracts.testing` (FR-020).
"""

from __future__ import annotations

from axon_ai_contracts._freeze import JSONValue
from axon_ai_contracts._version import __version__
from axon_ai_contracts.attachments import ATTACHMENT_MIME_TYPES, Attachment
from axon_ai_contracts.charts import (
    CHART_KINDS,
    CHART_MAX_POINTS,
    CHART_MAX_SERIES,
    CHART_X_TYPES,
    Chart,
    ChartKind,
    ChartPoint,
    ChartSeries,
    ChartXType,
    UnitPosition,
)
from axon_ai_contracts.compat import (
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
from axon_ai_contracts.declaration import ContractIssue, check_declaration
from axon_ai_contracts.deprecation import ContractDeprecationWarning, contract_deprecated
from axon_ai_contracts.eval import (
    EvalChunk,
    EvalEvidence,
    EvalItem,
    EvalMetric,
    EvalObservation,
    ProvidesEvalMetrics,
)
from axon_ai_contracts.llm import ChatChunk, ChatMessage, ChatResponse, ChatTool, ChatToolCall, ChatUsage, LLMProvider
from axon_ai_contracts.mcp import MCPClient
from axon_ai_contracts.pack import (
    RETRIEVAL_FILTERS_KEY,
    AgentPack,
    PackBase,
    PackContext,
    PackManifest,
    PreparesData,
)
from axon_ai_contracts.retrieval import (
    RETRIEVAL_TOOL_PARAMETERS,
    Chunk,
    NamedRetriever,
    Reranker,
    Retriever,
    retrieval_tool_spec,
)
from axon_ai_contracts.tools import NativeHandler, ToolInvocation, ToolKind, ToolResult, ToolSpec
from axon_ai_contracts.validation import (
    AnswerStream,
    AnswerValidator,
    StreamingValidator,
    ValidationResult,
    ValidatorContext,
)
from axon_ai_contracts.view import Citation, Message, TurnView

__all__ = [
    "ATTACHMENT_MIME_TYPES",
    "CHART_KINDS",
    "CHART_MAX_POINTS",
    "CHART_MAX_SERIES",
    "CHART_X_TYPES",
    "RETRIEVAL_FILTERS_KEY",
    "RETRIEVAL_TOOL_PARAMETERS",
    "AgentPack",
    "AnswerStream",
    "AnswerValidator",
    "Attachment",
    "BumpKind",
    "ChangeKind",
    "Chart",
    "ChartKind",
    "ChartPoint",
    "ChartSeries",
    "ChartXType",
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
    "Reranker",
    "Retriever",
    "StreamingValidator",
    "ToolInvocation",
    "ToolKind",
    "ToolResult",
    "ToolSpec",
    "TurnView",
    "UnitPosition",
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
