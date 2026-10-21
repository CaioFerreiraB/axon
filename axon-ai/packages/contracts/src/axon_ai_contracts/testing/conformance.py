"""Suíte de conformidade de pack (specs/001-core-contracts/contracts/testing-kit.md).

As etapas 1 a 3 (forma, identidade, manifest) são a base: se falham, nada depois delas roda. As demais apontam tudo
o que encontrarem. Toda issue é construída com `code=` literal (ver `ISSUE_CODES`).
"""

from __future__ import annotations

import asyncio
import dataclasses
import inspect
import tempfile
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from axon_ai_contracts._freeze import JSONValue, is_json_value
from axon_ai_contracts.compat import check_compatibility
from axon_ai_contracts.declaration import (
    ContractIssue,
    _capability_issues,
    _identity_issues,
    _is_async_callable,
    _manifest_issues,
)
from axon_ai_contracts.deprecation import ContractDeprecationWarning
from axon_ai_contracts.eval import EvalMetric
from axon_ai_contracts.pack import RETRIEVAL_FILTERS_KEY, AgentPack, PackContext, PackManifest, PreparesData
from axon_ai_contracts.retrieval import Chunk, NamedRetriever, Reranker
from axon_ai_contracts.testing.distribution import (
    check_contracts_requirement,
    find_distribution,
    read_requirements,
)
from axon_ai_contracts.testing.fixtures import chunk, pack_context, turn_view, validator_context
from axon_ai_contracts.testing.imports import check_imports
from axon_ai_contracts.tools import ToolSpec
from axon_ai_contracts.validation import AnswerValidator, StreamingValidator, ValidationResult, ValidatorContext
from axon_ai_contracts.view import TurnView

_PACK_MEMBERS = (
    "name",
    "contract_version",
    "manifest",
    "system_prompt",
    "prepare_context",
    "tools",
    "retrievers",
    "reranker",
    "validators",
)


@dataclass(frozen=True, slots=True, kw_only=True)
class ConformanceReport:
    """Resultado da suíte. `ok` é verdadeiro quando não há issue de severidade `error`."""

    pack_name: str
    issues: tuple[ContractIssue, ...]

    @property
    def ok(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def render(self) -> str:
        if not self.issues:
            return f"pack {self.pack_name!r}: conforme"
        lines = [f"pack {self.pack_name!r}: {len(self.issues)} issue(s)"]
        lines.extend(
            f"- [{issue.severity}] {issue.code} ({issue.subject or '-'}): {issue.message}" for issue in self.issues
        )
        return "\n".join(lines)


@dataclass(slots=True)
class _Run:
    pack: object
    config: Mapping[str, JSONValue]
    views: Sequence[TurnView] | None
    check_distribution: bool
    data_dir: Path | None = None
    issues: list[ContractIssue] = field(default_factory=list)
    pack_name: str = "?"
    manifest: PackManifest | None = None
    tools: tuple[ToolSpec, ...] = ()
    retrievers: tuple[NamedRetriever, ...] = ()
    validators: tuple[AnswerValidator, ...] = ()

    @property
    def agent(self) -> AgentPack:
        return cast("AgentPack", self.pack)

    def add(self, issue: ContractIssue) -> None:
        if issue not in self.issues:
            self.issues.append(issue)


def _raised(hook: str, error: BaseException) -> ContractIssue:
    return ContractIssue(
        code="hook.raised",
        message=f"{hook} levantou {type(error).__name__}: {error}",
        subject=f"hook:{hook}",
    )


def _check_shape(run: _Run) -> bool:
    missing = [member for member in _PACK_MEMBERS if not hasattr(run.pack, member)]
    for member in missing:
        run.add(
            ContractIssue(
                code="hook.missing",
                message=f"o pack não tem {member!r} (herde de PackBase para ganhar os hooks opcionais)",
                subject=f"hook:{member}",
            )
        )
    name = getattr(run.pack, "name", None)
    if isinstance(name, str):
        run.pack_name = name
    if not missing and not inspect.iscoroutinefunction(run.agent.prepare_context):
        run.add(
            ContractIssue(
                code="hook.not_async",
                message="prepare_context precisa ser assíncrono (async def)",
                subject="hook:prepare_context",
            )
        )
    return not run.issues


def _check_identity(run: _Run) -> bool:
    before = len(run.issues)
    for issue in _identity_issues(run.agent.name, run.agent.contract_version):
        run.add(issue)
    if len(run.issues) == before:
        compatibility = check_compatibility(run.agent.contract_version)
        if not compatibility.ok:
            run.add(
                ContractIssue(
                    code="pack.contract_version.incompatible",
                    message=compatibility.message or "contract_version incompatível",
                    subject="pack",
                )
            )
    return len(run.issues) == before


def _check_manifest(run: _Run) -> bool:
    try:
        manifest = run.agent.manifest()
    except Exception as error:
        run.add(_raised("manifest", error))
        return False
    issues = _manifest_issues(run.pack_name, manifest)
    for issue in issues:
        run.add(issue)
    if issues:
        return False
    run.manifest = manifest
    return True


def _return_type(hook: str, result: object, expected: str) -> ContractIssue:
    return ContractIssue(
        code="hook.return_type",
        message=f"{hook} devolveu {type(result).__name__}; esperado {expected}",
        subject=f"hook:{hook}",
    )


def _sequence_of(value: object, item_type: type | tuple[type, ...]) -> bool:
    return (
        isinstance(value, Sequence)
        and not isinstance(value, str | bytes)
        and all(isinstance(item, item_type) for item in value)
    )


def _views(run: _Run) -> Sequence[TurnView]:
    if run.views is not None:
        return run.views
    depends_on = run.manifest.depends_on if run.manifest is not None else ()
    return [turn_view(dependency_slices={dependency: {} for dependency in depends_on})]


def _call_catalog_hook(run: _Run, hook: str) -> tuple[bool, object]:
    try:
        return True, getattr(run.agent, hook)(pack_context(run.pack_name, run.config, data_dir=run.data_dir))
    except Exception as error:
        run.add(_raised(hook, error))
        return False, None


async def _check_reranker(run: _Run, reranker: object) -> None:
    if not isinstance(reranker, Reranker):
        run.add(_return_type("reranker", reranker, "Reranker | None"))
        return
    if not _is_async_callable(reranker.rerank):
        run.add(
            ContractIssue(
                code="hook.not_async", message="rerank precisa ser assíncrono (async def)", subject="reranker"
            )
        )
        return
    documents = (chunk("a"), chunk("b"), chunk("c"))
    try:
        result = await reranker.rerank("consulta", documents, top_k=2)
    except Exception as error:
        run.add(_raised("reranker", error))
        return
    known = {item.chunk_id for item in documents}
    if not _sequence_of(result, Chunk) or len(result) > 2 or any(item.chunk_id not in known for item in result):
        run.add(
            ContractIssue(
                code="reranker.contract",
                message="rerank(top_k=2) precisa devolver no máximo 2 chunks, todos vindos da entrada",
                subject="reranker",
            )
        )


def _check_prepare(run: _Run) -> None:
    """Etapa 3b (ADR-041), só se o pack tem `prepare`: síncrono, devolve `None` e não levanta em duas chamadas
    seguidas no mesmo diretório — a segunda é a prova de idempotência que um build com cache precisa."""
    if not isinstance(run.pack, PreparesData) or run.data_dir is None:
        return
    if inspect.iscoroutinefunction(run.pack.prepare):
        run.add(
            ContractIssue(code="hook.not_sync", message="prepare precisa ser síncrono (def)", subject="hook:prepare")
        )
        return
    run.data_dir.mkdir(parents=True, exist_ok=True)
    context = pack_context(run.pack_name, run.config, data_dir=run.data_dir)
    prepare: Callable[[PackContext], object] = run.pack.prepare  # o pack pode devolver algo, e isso é o que se confere
    for _ in range(2):
        try:
            result = prepare(context)
        except Exception as error:
            run.add(_raised("prepare", error))
            return
        if result is not None:
            run.add(_return_type("prepare", result, "None"))
            return


async def _check_catalog(run: _Run) -> None:
    """Etapas 4 e 5: hooks de catálogo chamados uma vez (FR-019) e regras de declaração."""
    called, prompt = _call_catalog_hook(run, "system_prompt")
    if called and prompt is not None and not isinstance(prompt, str):
        run.add(_return_type("system_prompt", prompt, "str | None"))
    called, tools = _call_catalog_hook(run, "tools")
    if called:
        if _sequence_of(tools, ToolSpec):
            run.tools = tuple(cast("Sequence[ToolSpec]", tools))
        else:
            run.add(_return_type("tools", tools, "Sequence[ToolSpec]"))
    called, retrievers = _call_catalog_hook(run, "retrievers")
    if called:
        if _sequence_of(retrievers, NamedRetriever):
            run.retrievers = tuple(cast("Sequence[NamedRetriever]", retrievers))
        else:
            run.add(_return_type("retrievers", retrievers, "Sequence[NamedRetriever]"))
    called, reranker = _call_catalog_hook(run, "reranker")
    if called and reranker is not None:
        await _check_reranker(run, reranker)
    called, validators = _call_catalog_hook(run, "validators")
    if called:
        if _sequence_of(validators, AnswerValidator):
            run.validators = tuple(cast("Sequence[AnswerValidator]", validators))
        else:
            run.add(_return_type("validators", validators, "Sequence[AnswerValidator]"))
    for issue in _capability_issues(run.tools, run.retrievers, run.validators):
        run.add(issue)
    if hasattr(run.agent, "eval_metrics"):
        called, metrics = _call_catalog_hook(run, "eval_metrics")
        if called:
            _check_eval_metrics(run, metrics)


_BETTER = frozenset({"higher", "lower"})


def _check_eval_metrics(run: _Run, metrics: object) -> None:
    """O hook opcional de métricas de domínio (ADR-027): sequência de `EvalMetric`, nomes únicos, `better` e
    `deterministic` válidos e `measure` síncrono — o harness o chama item a item, sem loop de eventos."""
    if not _sequence_of(metrics, EvalMetric):
        run.add(_return_type("eval_metrics", metrics, "Sequence[EvalMetric]"))
        return
    seen: set[str] = set()
    for metric in cast("Sequence[EvalMetric]", metrics):
        name = metric.name
        if not isinstance(name, str) or not name.strip():
            run.add(
                ContractIssue(code="eval_metric.name.invalid", message="métrica sem nome", subject="hook:eval_metrics")
            )
            continue
        if name in seen:
            run.add(
                ContractIssue(
                    code="eval_metric.duplicate_name",
                    message=f"métrica {name!r} declarada mais de uma vez",
                    subject=f"eval_metric:{name}",
                )
            )
        seen.add(name)
        problems = []
        if metric.better not in _BETTER:
            problems.append(f"better precisa ser 'higher' ou 'lower', não {metric.better!r}")
        if not isinstance(metric.deterministic, bool):
            problems.append("deterministic precisa ser bool")
        if _is_async_callable(metric.measure):
            problems.append("measure precisa ser síncrono")
        if problems:
            run.add(
                ContractIssue(code="eval_metric.contract", message="; ".join(problems), subject=f"eval_metric:{name}")
            )


async def _check_prepare_context(run: _Run) -> None:
    """Etapa 6: atualização rasa da própria fatia, em JSON, com `retrieval_filters` válido e determinística."""
    subject = "hook:prepare_context"
    context = pack_context(run.pack_name, run.config, data_dir=run.data_dir)
    for view in _views(run):
        try:
            first = await run.agent.prepare_context(view, context)
            second = await run.agent.prepare_context(view, context)
        except Exception as error:
            run.add(_raised("prepare_context", error))
            return
        if not isinstance(first, Mapping):
            run.add(
                ContractIssue(
                    code="prepare_context.not_mapping",
                    message=f"prepare_context devolveu {type(first).__name__}; esperado Mapping (atualização da fatia)",
                    subject=subject,
                )
            )
            continue
        if not is_json_value(first):
            run.add(
                ContractIssue(
                    code="prepare_context.not_json",
                    message="a atualização da fatia precisa ser serializável em JSON (a fatia vai para checkpoint)",
                    subject=subject,
                )
            )
        filters = first.get(RETRIEVAL_FILTERS_KEY)
        if RETRIEVAL_FILTERS_KEY in first and not (isinstance(filters, Mapping) and is_json_value(filters)):
            run.add(
                ContractIssue(
                    code="prepare_context.retrieval_filters.invalid",
                    message=f"{RETRIEVAL_FILTERS_KEY} precisa ser um mapeamento JSON",
                    subject=subject,
                )
            )
        if first != second:
            run.add(
                ContractIssue(
                    code="prepare_context.non_deterministic",
                    message="prepare_context devolveu atualizações diferentes para a mesma entrada",
                    subject=subject,
                )
            )


async def _check_validators(run: _Run) -> None:
    """Etapa 7: cada validator devolve ValidationResult e é determinístico."""
    for view in _views(run):
        for validator in run.validators:
            if not _is_async_callable(validator.validate):
                continue
            subject = f"validator:{validator.name}"
            context = validator_context(run.pack_name, run.config)
            try:
                first = await validator.validate(view, context)
                second = await validator.validate(view, context)
            except Exception as error:
                run.add(
                    ContractIssue(
                        code="hook.raised",
                        message=f"validate levantou {type(error).__name__}: {error}",
                        subject=subject,
                    )
                )
                continue
            if not isinstance(first, ValidationResult) or not isinstance(second, ValidationResult):
                run.add(
                    ContractIssue(
                        code="validator.result_type",
                        message=f"validate devolveu {type(first).__name__}; esperado ValidationResult",
                        subject=subject,
                    )
                )
            elif first != second:
                run.add(
                    ContractIssue(
                        code="validator.non_deterministic",
                        message="validate devolveu resultados diferentes para a mesma entrada",
                        subject=subject,
                    )
                )
            elif isinstance(validator, StreamingValidator) and view.answer is not None:
                _check_stream(run, validator, view, context, first, subject)


def _partitions(text: str) -> list[list[str]]:
    """Três partições da resposta: inteira, um caractere por vez e pedaços de 7 (ADR-024)."""
    return [[text], list(text), [text[index : index + 7] for index in range(0, len(text), 7)]]


def _check_stream(
    run: _Run,
    validator: StreamingValidator,
    view: TurnView,
    context: ValidatorContext,
    expected: ValidationResult,
    subject: str,
) -> None:
    """A sessão de streaming dá o mesmo resultado de `validate`, e o fim só acrescenta ao que já saiu (ADR-024)."""
    answer = view.answer or ""
    opened = dataclasses.replace(view, answer=None, citations=())
    for parts in _partitions(answer):
        try:
            session = validator.open_stream(opened, context)
            emitted = "".join(session.feed(part) for part in parts)
            result = session.finish()
        except Exception as error:
            run.add(
                ContractIssue(
                    code="hook.raised",
                    message=f"open_stream/feed/finish levantou {type(error).__name__}: {error}",
                    subject=subject,
                )
            )
            return
        if not isinstance(result, ValidationResult):
            run.add(
                ContractIssue(
                    code="validator.result_type",
                    message=f"finish devolveu {type(result).__name__}; esperado ValidationResult",
                    subject=subject,
                )
            )
            return
        final = result.answer if result.answer is not None else answer
        if not final.startswith(emitted):
            run.add(
                ContractIssue(
                    code="validator.stream.not_append_only",
                    message="a resposta final de finish não começa com o texto que feed já liberou",
                    subject=subject,
                )
            )
            return
        if result != expected:
            run.add(
                ContractIssue(
                    code="validator.stream.mismatch",
                    message=f"finish difere de validate quando a resposta chega em {len(parts)} pedaço(s)",
                    subject=subject,
                )
            )
            return


def _check_imports_step(run: _Run) -> None:
    package = type(run.pack).__module__.split(".")[0]
    try:
        issues = check_imports(package)
    except (ModuleNotFoundError, ValueError):
        return
    for issue in issues:
        run.add(issue)


def _check_distribution_step(run: _Run) -> None:
    """Etapa 9: a dependência de axon-ai-contracts declarada pelo pacote do pack cabe na faixa derivada."""
    if not run.check_distribution:
        return
    distribution = find_distribution(run.pack)
    if distribution is None:
        run.add(
            ContractIssue(
                code="distribution.not_found",
                message="distribuição do pack não localizada; a dependência declarada não foi verificada",
                subject="distribution",
                severity="warning",
            )
        )
        return
    for issue in check_contracts_requirement(read_requirements(distribution), run.agent.contract_version):
        run.add(issue)


async def _run_steps(run: _Run) -> None:
    if not (_check_shape(run) and _check_identity(run) and _check_manifest(run)):
        return
    _check_prepare(run)
    await _check_catalog(run)
    await _check_prepare_context(run)
    await _check_validators(run)
    _check_imports_step(run)
    _check_distribution_step(run)


def _report_deprecations(run: _Run, caught: list[warnings.WarningMessage]) -> None:
    for record in caught:
        if issubclass(record.category, ContractDeprecationWarning):
            run.add(
                ContractIssue(
                    code="deprecation.used",
                    message=str(record.message),
                    subject="deprecation",
                    severity="warning",
                )
            )
        else:
            warnings.warn_explicit(record.message, record.category, record.filename, record.lineno)


async def acheck_pack(
    pack: object,
    *,
    config: Mapping[str, JSONValue] | None = None,
    views: Sequence[TurnView] | None = None,
    check_distribution: bool = True,
    data_dir: Path | None = None,
) -> ConformanceReport:
    """Roda a suíte de conformidade contra um pack instanciado.

    `data_dir` é onde a etapa de preparo chama `prepare` e o que os hooks seguintes recebem no `PackContext`; sem ele,
    `<temporário>/<nome do pack>`, apagado no fim.
    """
    run = _Run(pack=pack, config=config or {}, views=views, check_distribution=check_distribution)
    with tempfile.TemporaryDirectory(prefix="axon-pack-data-") as scratch:
        name = getattr(pack, "name", None)
        run.data_dir = data_dir or Path(scratch) / (name if isinstance(name, str) and name else "pack")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ContractDeprecationWarning)
            await _run_steps(run)
    _report_deprecations(run, caught)
    return ConformanceReport(pack_name=run.pack_name, issues=tuple(run.issues))


def check_pack(
    pack: object,
    *,
    config: Mapping[str, JSONValue] | None = None,
    views: Sequence[TurnView] | None = None,
    check_distribution: bool = True,
    data_dir: Path | None = None,
) -> ConformanceReport:
    """Versão síncrona de `acheck_pack`, para testes sem loop de eventos."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            acheck_pack(pack, config=config, views=views, check_distribution=check_distribution, data_dir=data_dir)
        )
    raise RuntimeError("check_pack não roda dentro de um loop de eventos em execução; use `await acheck_pack(...)`")


async def aassert_pack_conforms(
    pack: object,
    *,
    config: Mapping[str, JSONValue] | None = None,
    views: Sequence[TurnView] | None = None,
    check_distribution: bool = True,
    data_dir: Path | None = None,
) -> None:
    report = await acheck_pack(
        pack, config=config, views=views, check_distribution=check_distribution, data_dir=data_dir
    )
    if not report.ok:
        raise AssertionError(report.render())


def assert_pack_conforms(
    pack: object,
    *,
    config: Mapping[str, JSONValue] | None = None,
    views: Sequence[TurnView] | None = None,
    check_distribution: bool = True,
    data_dir: Path | None = None,
) -> None:
    report = check_pack(pack, config=config, views=views, check_distribution=check_distribution, data_dir=data_dir)
    if not report.ok:
        raise AssertionError(report.render())
