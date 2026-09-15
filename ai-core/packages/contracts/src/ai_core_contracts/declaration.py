"""Regras de declaração de pack, compartilhadas pela carga (002) e pela suíte de conformidade (research R13).

Cada regra devolve `ContractIssue` com código estável (lista em specs/001-core-contracts/contracts/testing-kit.md).
O `code=` é sempre uma string literal na chamada, para que o teste de `ISSUE_CODES` o encontre.
"""

from __future__ import annotations

import inspect
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal

from ai_core_contracts._freeze import is_json_value
from ai_core_contracts.compat import InvalidVersion, Version, parse_contract_version
from ai_core_contracts.pack import PackManifest
from ai_core_contracts.retrieval import NamedRetriever
from ai_core_contracts.tools import ToolSpec
from ai_core_contracts.validation import AnswerValidator

_PACK_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_LOCAL_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,47}$")


@dataclass(frozen=True, slots=True, kw_only=True)
class ContractIssue:
    """Problema encontrado numa declaração de pack. `code` é estável e faz parte da superfície pública."""

    code: str
    message: str
    subject: str | None = None
    severity: Literal["error", "warning"] = "error"


def _schema_problems(schema: object, *, require_object: bool) -> list[str]:
    """Checagem estrutural de JSON Schema (research R14); o metaesquema completo é validado pelo core."""
    if not isinstance(schema, Mapping):
        return ["o esquema não é um mapeamento"]
    problems: list[str] = []
    if not is_json_value(schema):
        problems.append("o esquema não é serializável em JSON")
    if require_object and schema.get("type") != "object":
        problems.append('o esquema precisa de "type": "object" no topo')
    properties = schema.get("properties")
    if properties is not None and not (
        isinstance(properties, Mapping) and all(isinstance(item, Mapping) for item in properties.values())
    ):
        problems.append('"properties" precisa ser um mapeamento de mapeamentos')
    required = schema.get("required")
    if required is not None:
        if not isinstance(required, list | tuple) or not all(isinstance(name, str) for name in required):
            problems.append('"required" precisa ser uma lista de nomes')
        else:
            known = set(properties) if isinstance(properties, Mapping) else set()
            missing = [name for name in required if name not in known]
            if missing:
                problems.append(f'"required" cita propriedades inexistentes: {", ".join(missing)}')
    return problems


def _identity_issues(pack_name: object, contract_version: object) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    if not isinstance(pack_name, str) or not _PACK_NAME_PATTERN.match(pack_name):
        issues.append(
            ContractIssue(
                code="pack.name.invalid",
                message=f"nome de pack inválido: {pack_name!r} (esperado ^[a-z][a-z0-9_]{{0,31}}$)",
                subject="pack",
            )
        )
    try:
        parse_contract_version(contract_version)  # type: ignore[arg-type]
    except InvalidVersion:
        issues.append(
            ContractIssue(
                code="pack.contract_version.invalid",
                message=f"contract_version inválida: {contract_version!r} (esperado X.Y ou X.Y.Z)",
                subject="pack",
            )
        )
    return issues


def _manifest_issues(pack_name: str, manifest: object) -> list[ContractIssue]:
    if not isinstance(manifest, PackManifest):
        return [
            ContractIssue(
                code="manifest.type",
                message=f"manifest() precisa devolver PackManifest, devolveu {type(manifest).__name__}",
                subject="manifest",
            )
        ]
    issues: list[ContractIssue] = []
    if manifest.name != pack_name:
        issues.append(
            ContractIssue(
                code="manifest.name_mismatch",
                message=f"manifest.name {manifest.name!r} difere do nome do pack {pack_name!r}",
                subject="manifest",
            )
        )
    try:
        Version.parse(manifest.version)
    except InvalidVersion:
        issues.append(
            ContractIssue(
                code="manifest.version.invalid",
                message=f"manifest.version inválida: {manifest.version!r}",
                subject="manifest",
            )
        )
    if manifest.preferred_flow is not None and not manifest.preferred_flow.strip():
        issues.append(
            ContractIssue(
                code="manifest.preferred_flow.invalid",
                message="preferred_flow não pode ser vazio (use None para não preferir flow)",
                subject="manifest",
            )
        )
    if pack_name in manifest.depends_on:
        issues.append(
            ContractIssue(
                code="manifest.self_dependency",
                message=f"o pack {pack_name!r} declara dependência de si mesmo",
                subject="manifest",
            )
        )
    for name in _duplicates(manifest.depends_on):
        issues.append(
            ContractIssue(
                code="manifest.duplicate_dependency",
                message=f"dependência repetida em depends_on: {name!r}",
                subject="manifest",
            )
        )
    for name in _duplicates(manifest.requires_collections):
        issues.append(
            ContractIssue(
                code="manifest.duplicate_collection",
                message=f"coleção repetida em requires_collections: {name!r}",
                subject="manifest",
            )
        )
    if manifest.config_schema is not None:
        problems = _schema_problems(manifest.config_schema, require_object=False)
        if problems:
            issues.append(
                ContractIssue(
                    code="manifest.config_schema.invalid",
                    message="config_schema inválido: " + "; ".join(problems),
                    subject="manifest",
                )
            )
    return issues


def _is_async_callable(target: object) -> bool:
    """Função/método `async def`, ou objeto cujo `__call__` é `async def`."""
    if inspect.iscoroutinefunction(target):
        return True
    return callable(target) and inspect.iscoroutinefunction(type(target).__call__)


def _capability_issues(
    tools: Sequence[ToolSpec], retrievers: Sequence[NamedRetriever], validators: Sequence[AnswerValidator]
) -> list[ContractIssue]:
    issues: list[ContractIssue] = []
    for spec in tools:
        subject = f"tool:{spec.name}"
        if spec.kind != "native":
            issues.append(
                ContractIssue(
                    code="tool.not_native",
                    message=f"tool {spec.name!r} tem kind {spec.kind!r}: o pack só declara tools nativas "
                    "(retrieval vem dos retrievers; mcp, da descoberta do cliente MCP)",
                    subject=subject,
                )
            )
        if not _LOCAL_NAME_PATTERN.match(spec.name):
            issues.append(
                ContractIssue(
                    code="tool.name.invalid",
                    message=f"nome de tool inválido: {spec.name!r} (esperado ^[a-z][a-z0-9_]{{0,47}}$)",
                    subject=subject,
                )
            )
        problems = _schema_problems(spec.parameters, require_object=True)
        if problems:
            issues.append(
                ContractIssue(
                    code="tool.parameters.invalid",
                    message=f"parameters de {spec.name!r} inválido: " + "; ".join(problems),
                    subject=subject,
                )
            )
        if spec.handler is not None and not _is_async_callable(spec.handler):
            issues.append(
                ContractIssue(
                    code="tool.handler.not_async",
                    message=f"o handler de {spec.name!r} precisa ser assíncrono",
                    subject=subject,
                )
            )
    for name in _duplicates([spec.name for spec in tools]):
        issues.append(
            ContractIssue(code="tool.duplicate_name", message=f"duas tools com o nome {name!r}", subject=f"tool:{name}")
        )

    tool_names = {spec.name for spec in tools}
    for named in retrievers:
        subject = f"retriever:{named.name}"
        if not _LOCAL_NAME_PATTERN.match(named.name):
            issues.append(
                ContractIssue(
                    code="retriever.name.invalid",
                    message=f"nome de retriever inválido: {named.name!r} (esperado ^[a-z][a-z0-9_]{{0,47}}$)",
                    subject=subject,
                )
            )
        if named.name in tool_names:
            issues.append(
                ContractIssue(
                    code="retriever.name_collision",
                    message=f"o retriever {named.name!r} tem o nome de uma tool nativa do mesmo pack",
                    subject=subject,
                )
            )
        if not _is_async_callable(getattr(named.retriever, "search", None)):
            issues.append(
                ContractIssue(
                    code="hook.not_async",
                    message=f"search do retriever {named.name!r} precisa ser assíncrono",
                    subject=subject,
                )
            )
    for name in _duplicates([named.name for named in retrievers]):
        issues.append(
            ContractIssue(
                code="retriever.duplicate_name",
                message=f"dois retrievers com o nome {name!r}",
                subject=f"retriever:{name}",
            )
        )

    validator_names: list[str] = []
    for validator in validators:
        validator_name: object = getattr(validator, "name", None)
        subject = f"validator:{validator_name}"
        if not isinstance(validator_name, str) or not _LOCAL_NAME_PATTERN.match(validator_name):
            issues.append(
                ContractIssue(
                    code="validator.name.invalid",
                    message=f"nome de validator inválido: {validator_name!r} (esperado ^[a-z][a-z0-9_]{{0,47}}$)",
                    subject=subject,
                )
            )
        else:
            validator_names.append(validator_name)
        if not _is_async_callable(getattr(validator, "validate", None)):
            issues.append(
                ContractIssue(
                    code="hook.not_async",
                    message=f"validate do validator {validator_name!r} precisa ser assíncrono",
                    subject=subject,
                )
            )
    for name in _duplicates(validator_names):
        issues.append(
            ContractIssue(
                code="validator.duplicate_name",
                message=f"dois validators com o nome {name!r}",
                subject=f"validator:{name}",
            )
        )
    return issues


def check_declaration(
    *,
    pack_name: str,
    contract_version: str,
    manifest: PackManifest,
    tools: Sequence[ToolSpec] = (),
    retrievers: Sequence[NamedRetriever] = (),
    validators: Sequence[AnswerValidator] = (),
) -> tuple[ContractIssue, ...]:
    """Todas as regras de declaração: identidade, manifest e capacidades. Função pura."""
    issues = _identity_issues(pack_name, contract_version)
    issues.extend(_manifest_issues(pack_name, manifest))
    issues.extend(_capability_issues(tools, retrievers, validators))
    return tuple(issues)


def _duplicates(names: Sequence[str]) -> list[str]:
    return sorted(name for name, count in Counter(names).items() if count > 1)
