"""O juiz offline pelo Model Router da 006 (FR-006; research R19).

Uma política só da rodada — o papel `generation` é o modelo juiz e a allowlist só o admite —, roteada como qualquer
chamada: allowlist, trace (`ModelCall` com o `request_id` do julgamento) e saída por `response_format`. Nunca no
caminho da requisição: só o harness o monta.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

from ai_core.eval.api import EvalInputError
from ai_core.eval.domain.judging import RESPONSE_FORMAT, messages, parse
from ai_core.eval.ports import Judgement
from ai_core.llm.api import ModelCallFailed, ModelPolicy, ModelRef, ModelRouting, ModelRoutingError


class RoutedJudge:
    def __init__(self, routing: ModelRouting, model: str) -> None:
        try:
            self._ref = ModelRef.parse(model)
        except ValueError as error:
            raise EvalInputError(f"juiz inválido: {error}") from error
        self._routing = routing
        self._policy = ModelPolicy(roles={"generation": self._ref}, allow=(f"{self._ref.provider}/{self._ref.model}",))
        try:  # resolver não faz I/O (006): provider desconhecido falha aqui, antes de qualquer item
            routing.for_execution(policy=self._policy, request_id="eval-judge-check").for_role("generation")
        except ModelRoutingError as error:
            raise EvalInputError(f"juiz {model}: {error}") from error

    @property
    def name(self) -> str:
        return f"{self._ref.provider}/{self._ref.model}"

    async def judge(
        self, *, question: str, answer: str, passages: Sequence[str], reference: str | None, request_id: str
    ) -> Judgement:
        client = self._routing.for_execution(policy=self._policy, request_id=request_id).for_role("generation")
        try:
            response = await client.complete(
                messages(question=question, answer=answer, passages=passages, reference=reference),
                response_format=RESPONSE_FORMAT,
            )
        except ModelCallFailed:
            return Judgement(faithfulness=None, coverage=None)
        content = response["message"].get("content") or ""
        try:
            return parse(json.loads(content))
        except json.JSONDecodeError:
            return Judgement(faithfulness=None, coverage=None)
