"""Pack Runtime: carga do registry (research R5) e implementação dos seams Pack Registry e Pack Hooks.

Montado pela composition root (spec 011) com uma `PackSource` e uma `PackConfigSource`; `load()` roda uma vez, no boot.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

from ai_core.packs.api import (
    Composition,
    CompositionError,
    PackCapabilities,
    PackEntry,
    PackHookError,
    PackStatus,
    RetrieverCapability,
    Slices,
    ValidationOutcome,
    ValidatorRun,
)
from ai_core.packs.domain.composition import composition_error
from ai_core.packs.domain.config import config_error
from ai_core.packs.domain.dependencies import dependency_errors
from ai_core.packs.domain.hooks import apply_validation, merge_slice, scope_view
from ai_core.packs.domain.identity import read_identity
from ai_core.packs.ports import DiscoveredPack, PackConfigSource, PackSettings, PackSource
from ai_core_contracts import (
    AgentPack,
    AnswerValidator,
    InvalidVersion,
    JSONValue,
    NamedRetriever,
    PackContext,
    PackManifest,
    Reranker,
    ToolSpec,
    TurnView,
    ValidationResult,
    ValidatorContext,
    check_compatibility,
    check_declaration,
)

logger = logging.getLogger("ai_core.packs")


@dataclass(frozen=True, slots=True, kw_only=True)
class LoadedPack:
    """Pack habilitado, com o catálogo coletado uma vez na carga (001 FR-019). Interno à 002."""

    instance: AgentPack
    manifest: PackManifest
    context: PackContext
    validator_context: ValidatorContext
    system_prompt: str | None
    tools: tuple[ToolSpec, ...]
    retrievers: tuple[NamedRetriever, ...]
    reranker: Reranker | None
    validators: tuple[AnswerValidator, ...]


class _PackLoadError(Exception):
    """Falha de um pack numa etapa da carga; vira `PackEntry` com `status == error`."""


def _items(value: object) -> tuple[object, ...] | None:
    """Itens de uma sequência que não seja texto, ou `None`."""
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return tuple(value)
    return None


class PackRuntime:
    """Implementa `PackRegistry` e `PackHooks` (ai_core.packs.api)."""

    def __init__(self, source: PackSource, config_source: PackConfigSource) -> None:
        self._source = source
        self._config_source = config_source
        self._entries: dict[str, PackEntry] = {}
        self._loaded: dict[str, LoadedPack] = {}
        self._is_loaded = False

    # ------------------------------------------------------------------------------------------------ carga

    def load(self) -> None:
        """Monta o registry uma vez. `PackConfigError` da configuração propaga (a 011 para o boot)."""
        if self._is_loaded:
            raise RuntimeError("o Pack Registry já foi carregado; mudar packs ou configuração exige restart")
        settings = self._config_source.load()
        found: dict[str, list[DiscoveredPack]] = {}
        for discovered in self._source.discover():
            found.setdefault(discovered.name, []).append(discovered)
        entries: dict[str, PackEntry] = {}
        for name, candidates in found.items():
            if len(candidates) > 1:
                distributions = ", ".join(sorted(candidate.distribution for candidate in candidates))
                entries[name] = self._failed(name, f"nome duplicado: '{name}' registrado por {distributions}")
                continue
            entry, loaded = self._load_one(candidates[0], settings.get(name, PackSettings()))
            entries[name] = entry
            if loaded is not None:
                self._loaded[name] = loaded
        for name, pack_settings in settings.items():
            if pack_settings.enabled and name not in found:
                entries[name] = self._failed(name, "não instalado")
        self._apply_dependency_errors(entries)
        self._entries = dict(sorted(entries.items()))
        self._is_loaded = True

    @staticmethod
    def _failed(name: str, message: str, *, version: str | None = None, contract: str | None = None) -> PackEntry:
        logger.error("pack %r em erro: %s", name, message)
        return PackEntry(
            name=name, version=version, contract_version=contract, origin="code", status=PackStatus.ERROR, error=message
        )

    def _apply_dependency_errors(self, entries: dict[str, PackEntry]) -> None:
        """Falha em cascata: dependência indisponível ou ciclo deixa o dependente em erro (FR-010)."""
        status = {name: entry.status for name, entry in entries.items()}
        depends_on = {name: loaded.manifest.depends_on for name, loaded in self._loaded.items()}
        for name, message in dependency_errors(status, depends_on).items():
            entry = entries[name]
            entries[name] = self._failed(name, message, version=entry.version, contract=entry.contract_version)
            self._loaded.pop(name, None)

    def _load_one(self, discovered: DiscoveredPack, settings: PackSettings) -> tuple[PackEntry, LoadedPack | None]:
        contract_version: str | None = None
        try:
            try:
                target = discovered.load()
            except Exception as error:
                raise _PackLoadError(f"falha ao importar: {type(error).__name__}: {error}") from error
            identity = read_identity(discovered.name, target)
            if isinstance(identity, str):
                raise _PackLoadError(identity)
            _, contract_version = identity
            self._check_contract(contract_version)
            if not settings.enabled:
                return self._entry(discovered, contract_version, PackStatus.DISABLED), None
            loaded = self._instantiate(discovered.name, target, contract_version, settings)
        except _PackLoadError as error:
            return self._failed(
                discovered.name, str(error), version=discovered.version, contract=contract_version
            ), None
        return self._entry(discovered, contract_version, PackStatus.ENABLED, capabilities=_capabilities(loaded)), loaded

    @staticmethod
    def _check_contract(contract_version: str) -> None:
        try:
            compatibility = check_compatibility(contract_version)
        except InvalidVersion as error:
            raise _PackLoadError(f"contract_version inválida: {error}") from error
        if not compatibility.ok:
            raise _PackLoadError(compatibility.message or "contract_version incompatível")

    @staticmethod
    def _entry(
        discovered: DiscoveredPack,
        contract_version: str | None,
        status: PackStatus,
        *,
        error: str | None = None,
        capabilities: PackCapabilities | None = None,
    ) -> PackEntry:
        return PackEntry(
            name=discovered.name,
            version=discovered.version,
            contract_version=contract_version,
            origin="code",
            status=status,
            error=error,
            capabilities=capabilities,
        )

    def _instantiate(self, name: str, target: object, contract_version: str, settings: PackSettings) -> LoadedPack:
        assert isinstance(target, type)
        try:
            instance = target()
        except Exception as error:
            raise _PackLoadError(f"falha ao instanciar: {type(error).__name__}: {error}") from error
        pack: AgentPack = instance
        manifest = _call(pack, "manifest")
        issues = [
            issue
            for issue in check_declaration(
                pack_name=name,
                contract_version=contract_version,
                manifest=manifest,  # type: ignore[arg-type]
            )
            if issue.severity == "error"
        ]
        if issues:
            raise _PackLoadError("manifest inválido: " + "; ".join(issue.message for issue in issues))
        assert isinstance(manifest, PackManifest)
        problem = config_error(settings.config, manifest.config_schema)
        if problem is not None:
            raise _PackLoadError(problem)
        context = PackContext(pack_name=name, config=settings.config)
        loaded = _collect_catalog(pack, manifest, context)
        declaration = [
            issue
            for issue in check_declaration(
                pack_name=name,
                contract_version=contract_version,
                manifest=manifest,
                tools=loaded.tools,
                retrievers=loaded.retrievers,
                validators=loaded.validators,
            )
            if issue.severity == "error"
        ]
        if declaration:
            raise _PackLoadError("declaração inválida: " + "; ".join(issue.message for issue in declaration))
        return loaded

    # ------------------------------------------------------------------------------------------------ Pack Registry

    def entries(self) -> Sequence[PackEntry]:
        return tuple(self._entries.values())

    def entry(self, name: str) -> PackEntry | None:
        return self._entries.get(name)

    def compose(self, pack_names: Sequence[str]) -> Composition:
        names = tuple(pack_names)
        problem = composition_error(names, self._entries)
        if problem is not None:
            message, packs = problem
            raise CompositionError(message, packs=packs)
        return Composition(packs=names)

    # ------------------------------------------------------------------------------------------------ Pack Hooks

    def _members(self, composition: Composition) -> list[tuple[str, LoadedPack]]:
        """Revalida a composição (pode ter sido montada à mão) e devolve os packs carregados, na ordem."""
        names = self.compose(composition.packs).packs
        return [(name, self._loaded[name]) for name in names]

    def system_prompts(self, composition: Composition) -> tuple[str, ...]:
        return tuple(loaded.system_prompt for _, loaded in self._members(composition) if loaded.system_prompt)

    async def prepare(self, composition: Composition, view: TurnView, slices: Slices) -> Slices:
        members = self._members(composition)
        current: dict[str, dict[str, JSONValue]] = {name: dict(slices.get(name, {})) for name, _ in members}
        for name, loaded in members:
            scoped = scope_view(view, name, loaded.manifest.depends_on, current)
            try:
                update = await loaded.instance.prepare_context(scoped, loaded.context)
            except Exception as error:
                raise PackHookError(
                    f"prepare_context do pack '{name}' levantou {type(error).__name__}: {error}",
                    pack=name,
                    hook="prepare_context",
                ) from error
            try:
                current[name] = merge_slice(current[name], update)
            except TypeError as error:
                raise PackHookError(
                    f"prepare_context do pack '{name}' {error}", pack=name, hook="prepare_context"
                ) from error
        return current

    async def validate(self, composition: Composition, view: TurnView, slices: Slices) -> ValidationOutcome:
        runs: list[ValidatorRun] = []
        flags: set[str] = set()
        current = view
        for name, loaded in self._members(composition):
            for validator in loaded.validators:
                hook = f"validate:{validator.name}"
                scoped = scope_view(current, name, loaded.manifest.depends_on, slices)
                try:
                    result = await validator.validate(scoped, loaded.validator_context)
                except Exception as error:
                    raise PackHookError(
                        f"validator '{validator.name}' do pack '{name}' levantou {type(error).__name__}: {error}",
                        pack=name,
                        hook=hook,
                    ) from error
                if not isinstance(result, ValidationResult):
                    raise PackHookError(
                        f"validator '{validator.name}' do pack '{name}' devolveu {type(result).__name__}",
                        pack=name,
                        hook=hook,
                    )
                runs.append(ValidatorRun(pack=name, validator=validator.name, result=result))
                flags.update(result.flags)
                current = apply_validation(current, result)
        return ValidationOutcome(
            ok=all(run.result.ok for run in runs),
            answer=current.answer,
            citations=tuple(current.citations),
            flags=frozenset(flags),
            runs=tuple(runs),
        )


def _call(pack: AgentPack, hook: str, *args: object) -> object:
    try:
        return getattr(pack, hook)(*args)
    except Exception as error:
        raise _PackLoadError(f"hook {hook} levantou {type(error).__name__}: {error}") from error


def _collect_catalog(pack: AgentPack, manifest: PackManifest, context: PackContext) -> LoadedPack:
    """Chama cada hook de catálogo exatamente uma vez e confere o tipo do que ele devolve."""
    prompt = _call(pack, "system_prompt", context)
    if prompt is not None and not isinstance(prompt, str):
        raise _PackLoadError(f"hook system_prompt devolveu {type(prompt).__name__}; esperado str | None")
    tools = _items(_call(pack, "tools", context))
    if tools is None or not all(isinstance(item, ToolSpec) for item in tools):
        raise _PackLoadError("hook tools devolveu valor que não é sequência de ToolSpec")
    retrievers = _items(_call(pack, "retrievers", context))
    if retrievers is None or not all(isinstance(item, NamedRetriever) for item in retrievers):
        raise _PackLoadError("hook retrievers devolveu valor que não é sequência de NamedRetriever")
    reranker = _call(pack, "reranker", context)
    if reranker is not None and not isinstance(reranker, Reranker):
        raise _PackLoadError(f"hook reranker devolveu {type(reranker).__name__}; esperado Reranker | None")
    validators = _items(_call(pack, "validators", context))
    if validators is None or not all(isinstance(item, AnswerValidator) for item in validators):
        raise _PackLoadError("hook validators devolveu valor que não é sequência de AnswerValidator")
    return LoadedPack(
        instance=pack,
        manifest=manifest,
        context=context,
        validator_context=ValidatorContext(pack_name=context.pack_name, config=context.config),
        system_prompt=prompt,
        tools=cast("tuple[ToolSpec, ...]", tools),
        retrievers=cast("tuple[NamedRetriever, ...]", retrievers),
        reranker=reranker,
        validators=cast("tuple[AnswerValidator, ...]", validators),
    )


def _capabilities(loaded: LoadedPack) -> PackCapabilities:
    return PackCapabilities(
        system_prompt=bool(loaded.system_prompt),
        tools=tuple(tool.name for tool in loaded.tools),
        retrievers=tuple(
            RetrieverCapability(name=named.name, collections=named.collections) for named in loaded.retrievers
        ),
        reranker=loaded.reranker is not None,
        validators=tuple(validator.name for validator in loaded.validators),
        preferred_flow=loaded.manifest.preferred_flow,
        depends_on=tuple(loaded.manifest.depends_on),
        requires_collections=tuple(loaded.manifest.requires_collections),
    )
