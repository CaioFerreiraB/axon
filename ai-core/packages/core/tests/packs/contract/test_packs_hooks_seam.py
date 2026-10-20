"""Suíte de conformidade do seam Pack Hooks (contracts/pack-runtime-api.md; US3 cenários 2 a 4, SC-005; T025)."""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from typing import Any

import pytest
from packs_testkit import load_runtime, make_pack_class

from ai_core.packs.api import Composition, CompositionError, PackHookError, PackHooks, PackRegistry
from ai_core.packs.ports import PackSettings
from axon_ai_contracts import JSONValue, PackContext, TurnView, ValidationResult, ValidatorContext
from axon_ai_contracts.testing import turn_view


def _prepare(update: Any) -> Any:
    async def prepare_context(self: Any, view: TurnView, ctx: PackContext) -> Any:
        return update(view) if callable(update) else update

    return prepare_context


class _Validator:
    def __init__(self, name: str, result: ValidationResult | Exception) -> None:
        self.name = name
        self._result = result
        self.seen: list[str | None] = []

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        self.seen.append(view.answer)
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


def _runtime(*classes: type) -> Any:
    settings = {cls.name: PackSettings(enabled=True) for cls in classes}
    return load_runtime(*classes, settings=settings)


def test_system_prompts_follow_the_composition_order() -> None:
    a = make_pack_class("a", system_prompt=lambda self, ctx: "fragmento A")
    b = make_pack_class("b", system_prompt=lambda self, ctx: "fragmento B")
    silent = make_pack_class("silencioso")
    hooks: PackHooks = _runtime(a, b, silent)
    registry: PackRegistry = hooks  # type: ignore[assignment]
    assert hooks.system_prompts(registry.compose(["a", "silencioso", "b"])) == ("fragmento A", "fragmento B")
    assert hooks.system_prompts(registry.compose(["b", "a"])) == ("fragmento B", "fragmento A")


async def test_prepare_keeps_slices_separate_and_merges_shallowly() -> None:
    a = make_pack_class("a", prepare_context=_prepare({"chave": "de A"}))
    b = make_pack_class("b", prepare_context=_prepare({"chave": "de B"}))
    runtime = _runtime(a, b)
    slices: Mapping[str, Mapping[str, JSONValue]] = {"a": {"antiga": 1}}
    result = await runtime.prepare(runtime.compose(["a", "b"]), turn_view(), slices)
    assert result == {"a": {"antiga": 1, "chave": "de A"}, "b": {"chave": "de B"}}


async def test_dependent_sees_the_fresh_slice_of_its_dependency() -> None:
    a = make_pack_class("a", prepare_context=_prepare({"valor": 42}))
    b = make_pack_class(
        "b", depends_on=("a",), prepare_context=_prepare(lambda view: {"copiado": view.dependency_slices["a"]["valor"]})
    )
    runtime = _runtime(a, b)
    result = await runtime.prepare(runtime.compose(["a", "b"]), turn_view(), {})
    assert result["b"] == {"copiado": 42}


def test_dependency_order_is_enforced() -> None:
    runtime = _runtime(make_pack_class("a"), make_pack_class("b", depends_on=("a",)))
    for names in (["b", "a"], ["b"]):
        with pytest.raises(CompositionError) as excinfo:
            runtime.compose(names)
        assert set(excinfo.value.packs) == {"a", "b"}


async def test_reading_an_undeclared_slice_is_a_hook_error() -> None:
    a = make_pack_class("a", prepare_context=_prepare({"x": 1}))
    b = make_pack_class("b", prepare_context=_prepare(lambda view: {"lido": view.dependency_slices["a"]}))
    runtime = _runtime(a, b)
    with pytest.raises(PackHookError) as excinfo:
        await runtime.prepare(runtime.compose(["a", "b"]), turn_view(), {})
    assert (excinfo.value.pack, excinfo.value.hook) == ("b", "prepare_context")


@pytest.mark.parametrize("bad", [RuntimeError("falhou"), ["nao", "mapeamento"], {"quando": object()}])
async def test_prepare_context_failures_name_the_pack(bad: object) -> None:
    def update(view: TurnView) -> object:
        if isinstance(bad, Exception):
            raise bad
        return bad

    runtime = _runtime(make_pack_class("ruim", prepare_context=_prepare(update)))
    with pytest.raises(PackHookError) as excinfo:
        await runtime.prepare(runtime.compose(["ruim"]), turn_view(), {})
    assert excinfo.value.pack == "ruim" and "ruim" in str(excinfo.value)


async def test_validate_threads_answer_and_aggregates() -> None:
    first = _Validator("aviso", ValidationResult(ok=False, answer="resposta + aviso", flags=frozenset({"marcado"})))
    second = _Validator(
        "confere", ValidationResult(ok=True, citations=[{"chunk_id": "c9"}], flags=frozenset({"visto"}))
    )
    a = make_pack_class("a", validators=lambda self, ctx: (first,))
    b = make_pack_class("b", validators=lambda self, ctx: (second,))
    runtime = _runtime(a, b)
    outcome = await runtime.validate(runtime.compose(["a", "b"]), turn_view(answer="resposta"), {})
    assert second.seen == ["resposta + aviso"]
    assert outcome.ok is False and outcome.answer == "resposta + aviso"
    assert [citation["chunk_id"] for citation in outcome.citations] == ["c9"]
    assert outcome.flags == frozenset({"marcado", "visto"})
    assert [(run.pack, run.validator) for run in outcome.runs] == [("a", "aviso"), ("b", "confere")]


async def test_validator_exception_is_a_hook_error() -> None:
    broken = _Validator("quebrado", RuntimeError("falhou"))
    runtime = _runtime(make_pack_class("a", validators=lambda self, ctx: (broken,)))
    with pytest.raises(PackHookError) as excinfo:
        await runtime.validate(runtime.compose(["a"]), turn_view(answer="x"), {})
    assert (excinfo.value.pack, excinfo.value.hook) == ("a", "validate:quebrado")


async def test_hand_made_composition_is_revalidated() -> None:
    runtime = load_runtime(
        make_pack_class("a"), make_pack_class("desligado"), settings={"a": PackSettings(enabled=True)}
    )
    with pytest.raises(CompositionError):
        runtime.system_prompts(Composition(packs=("a", "desligado")))
    with pytest.raises(CompositionError):
        await runtime.prepare(Composition(packs=("desligado",)), turn_view(), {})


async def test_every_valid_pair_composes_and_runs() -> None:
    """SC-005: todo par ordenado de packs válidos que respeita as dependências é executável."""
    ok = _Validator("ok", ValidationResult(ok=True))
    packs = [
        make_pack_class("prompt", system_prompt=lambda self, ctx: "P"),
        make_pack_class("contexto", prepare_context=_prepare({"k": "v"})),
        make_pack_class("valida", validators=lambda self, ctx: (ok,)),
        make_pack_class("dependente", depends_on=("contexto",), prepare_context=_prepare({"d": 1})),
    ]
    runtime = _runtime(*packs)
    for first, second in itertools.permutations([cls.name for cls in packs], 2):
        try:
            composition = runtime.compose([first, second])
        except CompositionError as error:
            assert "dependente" in error.packs, (first, second)
            continue
        runtime.system_prompts(composition)
        slices = await runtime.prepare(composition, turn_view(), {})
        await runtime.validate(composition, turn_view(answer="r"), slices)


# --- filtro da geração (ADR-024) -------------------------------------------------------------------------------------


class _Stream:
    """Sessão que tira o caractere `drop` à medida que chega e acrescenta `tail` no fim."""

    def __init__(self, drop: str, tail: str, flag: str) -> None:
        self._drop, self._tail, self._flag = drop, tail, flag
        self._raw = ""

    def feed(self, delta: str) -> str:
        self._raw += delta
        return delta.replace(self._drop, "")

    def finish(self) -> ValidationResult:
        answer = self._raw.replace(self._drop, "") + self._tail
        return ValidationResult(ok=True, answer=answer, flags=frozenset({self._flag}))


class _StreamingValidator:
    def __init__(self, name: str, drop: str, tail: str = "") -> None:
        self.name, self._drop, self._tail = name, drop, tail
        self.opened: list[TurnView] = []

    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult:
        answer = (view.answer or "").replace(self._drop, "") + self._tail
        return ValidationResult(ok=True, answer=answer, flags=frozenset({self.name}))

    def open_stream(self, view: TurnView, ctx: ValidatorContext) -> _Stream:
        self.opened.append(view)
        return _Stream(self._drop, self._tail, self.name)


def _feed_all(answer_filter: Any, parts: list[str]) -> str:
    return "".join(answer_filter.feed(part) for part in parts)


async def test_filtro_encadeia_o_prefixo_de_validators_com_streaming() -> None:
    tira_x = _StreamingValidator("tira_x", "X")
    tira_y = _StreamingValidator("tira_y", "Y", tail=" fim")
    lote = _Validator("lote", ValidationResult(ok=True, answer=None))
    a = make_pack_class("a", validators=lambda self, ctx: (tira_x, tira_y, lote))
    runtime = _runtime(a)
    composition = runtime.compose(["a"])

    answer_filter = runtime.open_answer_stream(composition, turn_view(), {})
    emitted = _feed_all(answer_filter, ["aX", "bY", "cXY"])
    streamed = answer_filter.finish()

    assert emitted == "abc"
    assert streamed.tail == " fim"
    assert streamed.answer == "abc fim"
    assert [run.validator for run in streamed.runs] == ["tira_x", "tira_y"]

    outcome = await runtime.validate(composition, turn_view(), {}, streamed=streamed)
    assert lote.seen == ["abc fim"]  # só o validator fora do prefixo roda, sobre a resposta filtrada
    assert [run.validator for run in outcome.runs] == ["tira_x", "tira_y", "lote"]
    assert outcome.answer == "abc fim"
    assert outcome.flags == frozenset({"tira_x", "tira_y"})


async def test_validator_sem_streaming_encerra_o_prefixo() -> None:
    lote = _Validator("lote", ValidationResult(ok=True))
    tira_x = _StreamingValidator("tira_x", "X")
    runtime = _runtime(make_pack_class("a", validators=lambda self, ctx: (lote, tira_x)))
    answer_filter = runtime.open_answer_stream(runtime.compose(["a"]), turn_view(), {})
    assert _feed_all(answer_filter, ["aXb"]) == "aXb"  # o primeiro validator é em lote: nada filtra
    assert answer_filter.finish().runs == ()
    assert tira_x.opened == []


async def test_sessao_que_nao_so_acrescenta_no_fim_e_erro_do_pack() -> None:
    class _Ruim(_StreamingValidator):
        def open_stream(self, view: TurnView, ctx: ValidatorContext) -> _Stream:
            stream = _Stream("X", "", "ruim")
            stream.feed = lambda delta: delta  # type: ignore[method-assign]
            return stream

    runtime = _runtime(make_pack_class("a", validators=lambda self, ctx: (_Ruim("ruim", "X"),)))
    answer_filter = runtime.open_answer_stream(runtime.compose(["a"]), turn_view(), {})
    answer_filter.feed("aXb")
    with pytest.raises(PackHookError) as excinfo:
        answer_filter.finish()
    assert (excinfo.value.pack, excinfo.value.hook) == ("a", "stream:ruim")


async def test_sem_validators_o_filtro_deixa_tudo_passar() -> None:
    runtime = _runtime(make_pack_class("a"))
    answer_filter = runtime.open_answer_stream(runtime.compose(["a"]), turn_view(), {})
    assert _feed_all(answer_filter, ["Bras", "ília"]) == "Brasília"
    streamed = answer_filter.finish()
    assert (streamed.tail, streamed.answer, streamed.runs) == ("", "Brasília", ())


# --- reranker por pack (005 Fase 5, research R38; T062) --------------------------------------------------------------


class _Reranker:
    async def rerank(self, query: str, documents: Any, *, top_k: int = 5) -> Any:
        return list(documents)[:top_k]


def test_reranker_e_o_objeto_coletado_na_carga() -> None:
    reranker = _Reranker()
    calls: list[str] = []

    def hook(self: Any, ctx: PackContext) -> Any:
        calls.append(ctx.pack_name)
        return reranker

    com = make_pack_class("com", reranker=hook)
    sem = make_pack_class("sem")
    runtime = _runtime(com, sem)
    composicao = runtime.compose(["com", "sem"])
    assert runtime.reranker(composicao, "com") is reranker
    assert runtime.reranker(composicao, "com") is reranker
    assert runtime.reranker(composicao, "sem") is None
    assert calls == ["com"], "o hook de catálogo roda uma vez, na carga"


def test_reranker_de_pack_fora_da_composicao_e_erro_nomeando_o_pack() -> None:
    runtime = _runtime(make_pack_class("a"), make_pack_class("b"))
    with pytest.raises(ValueError, match="'b'"):
        runtime.reranker(runtime.compose(["a"]), "b")


def test_reranker_revalida_a_composicao() -> None:
    runtime = load_runtime(
        make_pack_class("a"), make_pack_class("desligado"), settings={"a": PackSettings(enabled=True)}
    )
    with pytest.raises(CompositionError):
        runtime.reranker(Composition(packs=("a", "desligado")), "a")
