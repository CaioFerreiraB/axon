"""Seam `PackEvalMetrics` (ADR-027; spec 009 Fase 6, T021): as métricas de domínio da composição, colhidas na carga."""

from __future__ import annotations

from typing import Any

import pytest
from packs_testkit import load_runtime, make_pack_class

from axon_ai.packs.api import Composition, CompositionError, PackEvalMetric, PackEvalMetrics, PackStatus
from axon_ai.packs.ports import PackSettings
from axon_ai_contracts import EvalItem, EvalObservation, PackContext

pytestmark = pytest.mark.us2


class Metric:
    def __init__(self, name: str) -> None:
        self.name = name
        self.better = "higher"
        self.deterministic = True

    def measure(self, item: EvalItem, observation: EvalObservation) -> float | None:
        return 1.0


def _runtime(*classes: type) -> Any:
    return load_runtime(*classes, settings={cls.name: PackSettings(enabled=True) for cls in classes})


def test_metricas_na_ordem_da_composicao_coletadas_uma_vez() -> None:
    calls: list[str] = []
    a_metric, b_metric = Metric("a1"), Metric("b1")

    def hook(metric: Metric) -> Any:
        def eval_metrics(self: Any, ctx: PackContext) -> tuple[Metric, ...]:
            calls.append(ctx.pack_name)
            return (metric,)

        return eval_metrics

    a = make_pack_class("a", eval_metrics=hook(a_metric))
    b = make_pack_class("b", eval_metrics=hook(b_metric))
    sem = make_pack_class("sem")
    runtime = _runtime(a, b, sem)
    seam: PackEvalMetrics = runtime
    found = seam.eval_metrics(runtime.compose(["b", "sem", "a"]))
    assert found == (PackEvalMetric(pack="b", metric=b_metric), PackEvalMetric(pack="a", metric=a_metric))
    seam.eval_metrics(runtime.compose(["a"]))
    assert sorted(calls) == ["a", "b"], "o hook roda uma vez, na carga"


def test_pack_sem_o_metodo_nao_tem_metricas() -> None:
    class SemHook:
        name = "solto"
        contract_version = "0.2"

        def manifest(self) -> Any:
            from axon_ai_contracts import PackManifest

            return PackManifest(name="solto", version="0.1.0")

        def system_prompt(self, ctx: Any) -> None:
            return None

        async def prepare_context(self, view: Any, ctx: Any) -> dict[str, Any]:
            return {}

        def tools(self, ctx: Any) -> tuple[()]:
            return ()

        def retrievers(self, ctx: Any) -> tuple[()]:
            return ()

        def reranker(self, ctx: Any) -> None:
            return None

        def validators(self, ctx: Any) -> tuple[()]:
            return ()

    runtime = _runtime(SemHook)
    assert runtime.entry("solto").status == PackStatus.ENABLED
    assert runtime.eval_metrics(runtime.compose(["solto"])) == ()


@pytest.mark.parametrize(
    "hook",
    [
        lambda self, ctx: (object(),),
        lambda self, ctx: "não é sequência",
    ],
)
def test_tipo_errado_deixa_o_pack_em_erro(hook: Any) -> None:
    runtime = _runtime(make_pack_class("ruim", eval_metrics=hook))
    entry = runtime.entry("ruim")
    assert entry.status == PackStatus.ERROR and "eval_metrics" in (entry.error or "")


def test_hook_que_levanta_deixa_o_pack_em_erro() -> None:
    def hook(self: Any, ctx: Any) -> Any:
        raise RuntimeError("sem métricas")

    entry = _runtime(make_pack_class("quebrado", eval_metrics=hook)).entry("quebrado")
    assert entry.status == PackStatus.ERROR and "eval_metrics" in (entry.error or "")


def test_composicao_revalidada() -> None:
    runtime = load_runtime(make_pack_class("a"), make_pack_class("off"), settings={"a": PackSettings(enabled=True)})
    with pytest.raises(CompositionError):
        runtime.eval_metrics(Composition(packs=("a", "off")))
