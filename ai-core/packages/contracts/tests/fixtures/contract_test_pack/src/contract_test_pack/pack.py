"""ContractTestPack: pack mínimo e completo, escrito só contra os contratos."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from axon_ai_contracts import (
    RETRIEVAL_FILTERS_KEY,
    AnswerValidator,
    Chunk,
    JSONValue,
    NamedRetriever,
    PackBase,
    PackContext,
    PackManifest,
    Reranker,
    ToolInvocation,
    ToolSpec,
    TurnView,
    ValidationResult,
    ValidatorContext,
)

DOCUMENTS: tuple[Chunk, ...] = (
    Chunk(chunk_id="manual#1", text="Primeiro trecho.", score=0.9, document="Manual", status="vigente", page=1),
    Chunk(chunk_id="manual#2", text="Segundo trecho.", score=0.7, document="Manual", status="vigente", page=2),
    Chunk(chunk_id="antigo#1", text="Trecho revogado.", score=0.5, document="Antigo", status="revogado", page=9),
)


class MemoryRetriever:
    """Retriever em memória sobre chunks fixos."""

    def __init__(self, chunks: Sequence[Chunk]) -> None:
        self._chunks = tuple(chunks)

    async def search(
        self, query: str, *, top_k: int = 20, filters: Mapping[str, JSONValue] | None = None
    ) -> Sequence[Chunk]:
        return self._chunks[:top_k]


class TruncatingReranker:
    """Reranker que preserva a ordem e corta em `top_k`."""

    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]:
        return tuple(documents)[:top_k]


class NonEmptyAnswer:
    """Validator determinístico: reprova resposta vazia."""

    name = "non_empty_answer"

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        if view.answer and view.answer.strip():
            return ValidationResult(ok=True)
        return ValidationResult(ok=False, issues=("resposta vazia",), flags=frozenset({"empty_answer"}))


async def echo(invocation: ToolInvocation) -> object:
    """Tool nativa: devolve os argumentos e a data de referência da execução (nunca o relógio)."""
    return {"arguments": dict(invocation.arguments), "reference_time": invocation.reference_time.isoformat()}


class ContractTestPack(PackBase):
    name = "contract_test"
    contract_version = "0.2"

    def manifest(self) -> PackManifest:
        return PackManifest(
            name="contract_test",
            version="0.1.0",
            preferred_flow="chat",
            requires_collections=("test_docs",),
        )

    def system_prompt(self, ctx: PackContext) -> str | None:
        return "Você responde com base nos documentos de teste."

    async def prepare_context(self, view: TurnView, ctx: PackContext) -> Mapping[str, JSONValue]:
        """Função pura da Turn View: a vigência usa `reference_time`, nunca o relógio do sistema (ADR-013)."""
        return {
            "seen_question": view.question,
            RETRIEVAL_FILTERS_KEY: {"effective_on": view.reference_time.date().isoformat()},
        }

    def tools(self, ctx: PackContext) -> Sequence[ToolSpec]:
        return (
            ToolSpec(
                name="echo",
                description="Devolve os argumentos recebidos.",
                parameters={"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]},
                kind="native",
                handler=echo,
            ),
        )

    def retrievers(self, ctx: PackContext) -> Sequence[NamedRetriever]:
        return (
            NamedRetriever(
                name="docs",
                description="Busca nos documentos de teste.",
                collections=frozenset({"test_docs"}),
                retriever=MemoryRetriever(DOCUMENTS),
            ),
        )

    def reranker(self, ctx: PackContext) -> Reranker | None:
        return TruncatingReranker()

    def validators(self, ctx: PackContext) -> Sequence[AnswerValidator]:
        return (NonEmptyAnswer(),)
