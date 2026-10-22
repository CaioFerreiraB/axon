"""A etapa `image_gate` do `chat` e do `rag_first` (ADR-044, item 8; research R51).

Roda só quando há imagem candidata — a resposta anterior mostrou imagens e a geração enxerga imagem — e o Assistant
declara `controller`: uma chamada a ele, com saída estruturada, decide quais imagens vão à geração. Fina como os outros
nós: formato, leitura e mensagens são de `domain/images.py` e `domain/transcript.py`.
"""

from __future__ import annotations

from typing import Any, Final

from langgraph.config import get_stream_writer
from langgraph.runtime import get_runtime

from axon_ai.graph.adapters.langgraph.nodes.common import PROGRESS, finished
from axon_ai.graph.adapters.langgraph.state import AgentContext, AgentState
from axon_ai.graph.api import ExecutionIssue, ImageGateOutcome
from axon_ai.graph.domain.images import gate_format, parse_gate
from axon_ai.graph.domain.transcript import gate_messages
from axon_ai.llm.api import ModelCallFailed
from axon_ai.observability.api import ControllerDecision

STAGE_IMAGE_GATE: Final = "image_gate"
INVALID_CHOICE: Final = "a escolha do controller não veio no formato pedido"


def _context() -> AgentContext:
    return get_runtime(AgentContext).context


async def image_gate(state: AgentState) -> dict[str, Any]:
    """Uma chamada ao `controller` escolhe as imagens; falha ou saída fora do formato segue sem imagem, com `notice`
    (a regra do FR-006a: a decisão é acessória, a resposta não)."""
    ctx = _context()
    ids = tuple(item.id for item in ctx.images.candidates)
    get_stream_writer()({"kind": PROGRESS, "stage": STAGE_IMAGE_GATE, "detail": f"{len(ids)} imagem(ns)"})
    model = ctx.router.for_role("controller")
    ref = str(model.ref)
    messages = gate_messages(state.get("messages", ()), ids, send_own=ctx.images.to_controller)
    reason: str | None = None
    kind = "ImageGateInvalid"
    try:
        response = await model.complete(messages, response_format=gate_format(ids))
        viewed = parse_gate(response["message"].get("content"), ids)
    except ModelCallFailed as error:
        viewed, reason, kind = None, str(error), type(error).__name__
    if viewed is None:
        finished(STAGE_IMAGE_GATE, ImageGateOutcome(model=ref, candidates=len(ids), failed=True))
        issue = ExecutionIssue(
            stage=STAGE_IMAGE_GATE,
            kind=kind,
            message=f"{reason or INVALID_CHOICE}; a resposta foi gerada sem as imagens anteriores",
            severity="notice",
        )
        return {"errors": [issue]}
    ctx.trace.emit(ControllerDecision(request_id=state["request_id"], iteration=1, action="view_image", images=viewed))
    finished(STAGE_IMAGE_GATE, ImageGateOutcome(model=ref, candidates=len(ids), viewed=viewed))
    return {"viewed": list(viewed)}
