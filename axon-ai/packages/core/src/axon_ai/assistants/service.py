"""Serviços da 003: implementam os seams de `api.py` orquestrando `domain/` e as portas.

`AssistantsService` resolve grants, oferece o diretório e valida referências; `AccessService` autentica e administra
chaves. A ordem da resolução é a de research R4 — ACL antes de tudo, orçamento por último. Não importa `adapters/`.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

from axon_ai.assistants.api import (
    NAME_PATTERN,
    SCHEMES,
    SCHEMES_OF_SURFACE,
    SUBJECT_PATTERN,
    USER_PREFIX,
    ApiKeyInfo,
    AssistantSummary,
    AssistantUnavailable,
    AuthOverride,
    Conflict,
    ExecutionGrant,
    IssuedApiKey,
    Limits,
    McpOverride,
    ModelsOverride,
    NoApplicablePolicy,
    NotFound,
    OverrideHistoryEntry,
    OverridePayload,
    OverrideSection,
    OverrideView,
    PolicyViolation,
    Principal,
    RateLimited,
    RequestRejected,
    SystemAssistantView,
    UserAssistant,
    UserAssistantDraft,
    ValidationReport,
)
from axon_ai.assistants.domain.access import OidcAudiences, OidcClaims, is_admin, principal_from_claims
from axon_ai.assistants.domain.definitions import AssistantDefinition, AssistantsConfig, allowed_model, is_selector
from axon_ai.assistants.domain.keys import (
    KEY_ID_BYTES,
    KEY_PREFIX,
    SECRET_BYTES,
    ApiKeyRecord,
    compose_key,
    hash_key,
    matches,
    parse_key,
)
from axon_ai.assistants.domain.overrides import (
    UNREADABLE,
    OverrideStatus,
    StoredOverride,
    apply_auth,
    apply_mcp,
    apply_models,
    attribute,
    effective,
    payload_of,
    read_payload,
    section_fingerprint,
    yaml_auth,
    yaml_mcp,
)
from axon_ai.assistants.domain.policies import applicable_policy, conform, user_definition
from axon_ai.assistants.domain.rate import RATE_WINDOW
from axon_ai.assistants.domain.resolution import (
    build_grant,
    effective_flow,
    not_found,
    select_models,
    split_model_id,
)
from axon_ai.assistants.domain.validation import FlowRoles, reference_reasons, static_reasons, status_of
from axon_ai.assistants.ports import (
    ApiKeyStore,
    Clock,
    CollectionCatalog,
    McpDirectory,
    OidcVerifier,
    RateCounterStore,
    StoredUserAssistant,
    SystemOverrideStore,
    TokenGenerator,
    UserAssistantStore,
)
from axon_ai.graph import api as engine
from axon_ai.llm.api import ModelRef
from axon_ai.packs.api import Composition, CompositionError, PackRegistry

SYSTEM_PREFIX: Final = "svc:"
"""O prefixo do subject de um sistema: ele é o subject das chaves, sem cadastro próprio (ADR-040)."""

_UNREADABLE_PLACEHOLDER: Final[dict[OverrideSection, OverridePayload]] = {
    "models": ModelsOverride(roles={}),
    "mcp": McpOverride(),
    "auth": AuthOverride(),
}
"""O que a visão mostra no lugar de um conteúdo guardado ilegível, que nunca é aplicado."""


def _engine_grant(grant: ExecutionGrant) -> engine.ExecutionGrant:
    """Não faz nada em execução. Existe para o mypy — que não cobre os testes — recusar qualquer divergência entre o
    grant desta spec e o `Protocol` que o motor (005) lê (research R1)."""
    return grant


@dataclass(frozen=True, slots=True, kw_only=True)
class _Availability:
    reasons: tuple[str, ...]
    flow: str | None
    composition: Composition | None

    @property
    def blocked(self) -> bool:
        return bool(self.reasons) or self.flow is None or self.composition is None


NO_POLICY = "nenhuma política de Assistants de usuário se aplica a você"


def _plain_name(name: str) -> str | None:
    """Nome sem o `~`, ou `None` se fora do formato — tratado como inexistente, não como erro de entrada."""
    plain = name.removeprefix(USER_PREFIX)
    return plain if NAME_PATTERN.fullmatch(plain) else None


def _summary(definition: AssistantDefinition) -> AssistantSummary:
    return AssistantSummary(
        name=definition.name,
        origin=definition.origin,
        description=definition.description,
        generation=definition.roles["generation"],
        allow=definition.allow,
    )


class AssistantsService:
    """`GrantResolver`, `AssistantDirectory` e a validação de referências (FR-011)."""

    def __init__(
        self,
        *,
        config: AssistantsConfig,
        packs: PackRegistry,
        flows: Collection[str],
        users: UserAssistantStore,
        mcp: McpDirectory,
        collections: CollectionCatalog,
        rate: RateCounterStore,
        clock: Clock,
        flow_roles: FlowRoles | None = None,
        overrides: SystemOverrideStore | None = None,
        override_cache_ttl: timedelta = timedelta(seconds=5),
    ) -> None:
        self._config = config
        self._packs = packs
        self._flows = frozenset(flows)
        self._flow_roles = flow_roles
        self._users = users
        self._mcp = mcp
        self._collections = collections
        self._rate = rate
        self._clock = clock
        self._overrides = overrides
        self._override_ttl = override_cache_ttl
        self._effective: dict[str, tuple[datetime, AssistantDefinition, tuple[OverrideStatus, ...]]] = {}

    # --- GrantResolver --------------------------------------------------------------------------------------------

    async def resolve(self, *, model: str, principal: Principal) -> ExecutionGrant:
        selection = split_model_id(model)
        # Passos 2 e 3 pelo mesmo caminho: inexistente e não autorizado levantam o mesmo erro, com a mesma mensagem,
        # antes de qualquer verificação de disponibilidade — um privado quebrado não se revela (SC-001). Assistant de
        # usuário é procurado só no escopo de quem pede: `~x` alheio e `~x` inexistente são a mesma leitura vazia.
        definition = await self._find(selection.assistant, principal)
        if definition is None or not definition.access.permits(principal):
            raise not_found(selection.assistant)

        availability = await self._availability(definition)
        if availability.blocked or availability.flow is None or availability.composition is None:
            raise AssistantUnavailable(f"assistant '{definition.name}' indisponível", reasons=availability.reasons)

        models = select_models(definition, selection.requested)

        # Passo 7, o último: só consome cota o que de fato executaria (research R4).
        decision = await self._rate.acquire(
            (principal.subject, definition.name),
            now=self._clock.now(),
            limit=definition.limits.rpm,
            window=RATE_WINDOW,
        )
        if not decision.allowed:
            wait = (decision.retry_after or RATE_WINDOW).total_seconds()
            raise RateLimited(
                f"limite de {definition.limits.rpm} execuções por minuto atingido em '{definition.name}'",
                retry_after=wait,
            )

        return build_grant(
            definition,
            principal=principal,
            flow=availability.flow,
            composition=availability.composition,
            models=models,
        )

    # --- AssistantDirectory ---------------------------------------------------------------------------------------

    async def discover(self, principal: Principal) -> Sequence[AssistantSummary]:
        """Exatamente o que `resolve` aceitaria: a mesma ACL e a mesma disponibilidade, nenhuma regra duplicada
        (FR-008). `visibility` não filtra."""
        found = []
        for name in sorted(self._config.assistants):
            definition, _ = await self._system(name)
            if definition.access.permits(principal) and not (await self._availability(definition)).blocked:
                found.append(_summary(definition))
        for stored in await self._users.list(principal.subject):
            definition = await self._user_definition(stored, principal)
            if definition.access.permits(principal) and not (await self._availability(definition)).blocked:
                found.append(_summary(definition))
        return found

    async def mine(self, principal: Principal) -> Sequence[UserAssistant]:
        return [await self._view(stored, principal) for stored in await self._users.list(principal.subject)]

    async def get(self, principal: Principal, name: str) -> UserAssistant:
        plain = _plain_name(name)
        stored = await self._users.get(principal.subject, plain) if plain is not None else None
        if stored is None:
            raise not_found(name)
        return await self._view(stored, principal)

    async def create(self, principal: Principal, draft: UserAssistantDraft) -> UserAssistant:
        await self._conform(draft, principal)
        now = self._clock.now()
        record = StoredUserAssistant(owner=principal.subject, draft=draft, created_at=now, updated_at=now)
        if not await self._users.insert(record):
            raise Conflict(f"você já tem um Assistant '{USER_PREFIX}{draft.name}'")
        return await self._view(record, principal)

    async def update(self, principal: Principal, name: str, draft: UserAssistantDraft) -> UserAssistant:
        """Substitui o rascunho inteiro — a última escrita vence (R10). O nome não muda: remove-se e cria-se outro."""
        plain = _plain_name(name)
        existing = await self._users.get(principal.subject, plain) if plain is not None else None
        if existing is None:
            raise not_found(name)
        if draft.name != plain:
            raise RequestRejected("o nome não muda na atualização: remova e crie outro", field="name")
        await self._conform(draft, principal)
        record = StoredUserAssistant(
            owner=principal.subject, draft=draft, created_at=existing.created_at, updated_at=self._clock.now()
        )
        if not await self._users.replace(record):
            raise not_found(name)
        return await self._view(record, principal)

    async def delete(self, principal: Principal, name: str) -> None:
        plain = _plain_name(name)
        if plain is None or not await self._users.delete(principal.subject, plain):
            raise not_found(name)

    # --- validação ------------------------------------------------------------------------------------------------

    async def validate(self) -> ValidationReport:
        """Um estado por Assistant: os de sistema por nome, depois os de usuário por dono e nome.

        Dos de usuário, só as referências: a conformidade com a política depende dos grupos do Principal, conhecidos
        apenas na resolução (R14).
        """
        statuses = []
        for name in sorted(self._config.assistants):
            definition, _ = await self._system(name)
            statuses.append(status_of(definition, (await self._availability(definition)).reasons))
        for stored in await self._users.all():
            definition = user_definition(stored.draft, owner=stored.owner, allow=(), limits=Limits())
            statuses.append(status_of(definition, (await self._availability(definition)).reasons))
        return ValidationReport(statuses=tuple(statuses))

    # --- SystemAssistantAdmin (ADR-032) ---------------------------------------------------------------------------

    async def system_assistants(self, *, actor: Principal) -> tuple[SystemAssistantView, ...]:
        self._require_admin(actor)
        return tuple([await self._system_view(name) for name in sorted(self._config.assistants)])

    async def system_assistant(self, name: str, *, actor: Principal) -> SystemAssistantView:
        self._require_admin(actor)
        self._system_yaml(name)
        return await self._system_view(name)

    async def override_models(
        self, name: str, override: ModelsOverride, *, actor: Principal, version: int | None
    ) -> SystemAssistantView:
        self._require_admin(actor)
        yaml = self._overridable(name, "models")
        for role, ref in sorted(override.roles.items()):
            if not allowed_model(ref, yaml.allow):
                allow = ", ".join(yaml.allow)
                raise RequestRejected(f"models.{role}: {ref} fora da allowlist ({allow})", field=f"models.{role}")
        candidate = apply_models(await self._without(name, "models"), override)
        self._reject_static(candidate)
        return await self._save(name, "models", override, yaml=yaml, actor=actor, version=version)

    async def override_mcp(
        self, name: str, override: McpOverride, *, actor: Principal, version: int | None
    ) -> SystemAssistantView:
        self._require_admin(actor)
        yaml = self._overridable(name, "mcp")
        available = await self._mcp.aliases(owner=None)
        for alias in override.aliases:
            if alias not in available:
                raise RequestRejected(f"mcp: MCP '{alias}' não existe ou não é visível", field="mcp.aliases")
        for field, entries in (("mcp.allowed", override.allowed), ("mcp.write", override.write)):
            for entry in sorted(entries):
                namespace, dot, tool = entry.partition(".")
                if not dot or not tool or namespace not in override.aliases:
                    raise RequestRejected(
                        f"{field}: '{entry}' precisa ser <alias>.<tool> de um servidor escolhido", field=field
                    )
        if override.write and yaml.visibility == "public":
            raise RequestRejected(
                "mcp.write: Assistant público nunca concede tools de escrita (FR-012)", field="mcp.write"
            )
        if override.allowed and not override.write <= override.allowed:
            extra = ", ".join(sorted(override.write - override.allowed))
            raise RequestRejected(f"mcp.write: '{extra}' precisa estar também entre as permitidas", field="mcp.write")
        base = await self._without(name, "mcp")
        candidate = apply_mcp(base, override, pack_tools=self._pack_tools(base.packs))
        self._reject_static(candidate)
        return await self._save(name, "mcp", override, yaml=yaml, actor=actor, version=version)

    async def override_auth(
        self, name: str, override: AuthOverride, *, actor: Principal, version: int | None
    ) -> SystemAssistantView:
        """Quem pode usar o Assistant (ADR-040, R43). Não confere se subjects e grupos existem (FR-032): entrada sem
        correspondência não concede nada."""
        self._require_admin(actor)
        yaml = self._overridable(name, "auth")
        unknown = sorted(set(override.schemes) - set(SCHEMES))
        if not override.schemes or unknown:
            detail = f"; recebido: {', '.join(unknown)}" if unknown else ""
            raise RequestRejected(f"auth.schemes: não vazio, entre {', '.join(SCHEMES)}{detail}", field="auth.schemes")
        invalid = [selector for selector in override.allow if not is_selector(selector)]
        if not override.allow or invalid:
            detail = f"; inválidos: {', '.join(invalid)}" if invalid else ""
            raise RequestRejected(
                f"auth.allow: não vazio, com '*', 'user:…', 'svc:…' ou 'group:…'{detail}", field="auth.allow"
            )
        if yaml.visibility == "private" and "*" in override.allow:
            raise RequestRejected(
                "auth.allow: '*' não é permitido em Assistant privado: nomeie subjects ou grupos (FR-012)",
                field="auth.allow",
            )
        self._reject_static(apply_auth(await self._without(name, "auth"), override))
        return await self._save(name, "auth", override, yaml=yaml, actor=actor, version=version)

    async def discard_override(
        self, name: str, section: OverrideSection, *, actor: Principal, version: int
    ) -> SystemAssistantView:
        self._require_admin(actor)
        self._system_yaml(name)
        store = self._override_store()
        if not await store.delete(name, section, expected_version=version, actor=actor.subject, at=self._clock.now()):
            raise NotFound(f"'{name}' não tem sobreposição de {section}")
        self._effective.pop(name, None)
        return await self._system_view(name)

    async def history(self, name: str, *, actor: Principal) -> tuple[OverrideHistoryEntry, ...]:
        self._require_admin(actor)
        self._system_yaml(name)
        records = await self._override_store().history(name)
        return tuple(
            OverrideHistoryEntry(
                section=record.section,
                action=record.action,
                payload=read_payload(record.section, record.payload) if record.payload is not None else None,
                version=record.version,
                actor=record.actor,
                at=record.at,
            )
            for record in records
        )

    async def declared_models(self) -> tuple[ModelRef, ...]:
        """Os modelos efetivos dos Assistants de sistema — o item de modelos da saúde consulta isto (011 R41)."""
        refs: dict[str, ModelRef] = {}
        for name in sorted(self._config.assistants):
            definition, _ = await self._system(name)
            for ref in definition.roles.values():
                refs.setdefault(str(ref), ref)
        return tuple(refs[key] for key in sorted(refs))

    async def overrides_as_operator(self) -> tuple[tuple[str, OverrideView], ...]:
        """Todas as sobreposições e o estado delas, com a autoridade do operador (`assistants validate`, T082)."""
        if self._overrides is None:
            return ()
        found: list[tuple[str, OverrideView]] = []
        for name in sorted(self._config.assistants):
            found.extend((name, view) for view in (await self._system_view(name)).overrides)
        return tuple(found)

    def _require_admin(self, actor: Principal) -> None:
        """Quem não administra recebe o mesmo que um recurso inexistente (ADR-031)."""
        if not is_admin(actor, self._config.admin_group):
            raise NotFound("recurso não encontrado")

    def _system_yaml(self, name: str) -> AssistantDefinition:
        definition = self._config.assistants.get(name)
        if definition is None:
            raise not_found(name)
        return definition

    def _overridable(self, name: str, section: OverrideSection) -> AssistantDefinition:
        yaml = self._system_yaml(name)
        if section not in yaml.overrides:
            raise RequestRejected(
                f"{section}: a seção '{section}' de '{name}' só muda por novo deploy (fora de `overrides` no YAML)",
                field=section,
            )
        return yaml

    def _override_store(self) -> SystemOverrideStore:
        if self._overrides is None:
            raise RequestRejected("esta plataforma não guarda sobreposições", field="overrides")
        return self._overrides

    async def _without(self, name: str, section: OverrideSection) -> AssistantDefinition:
        """A definição efetiva sem a sobreposição de `section` — a base de uma gravação nova dessa seção."""
        yaml = self._system_yaml(name)
        stored = [record for record in await self._override_store().get(name) if record.section != section]
        definition, _ = effective(yaml, stored, pack_tools=self._pack_tools(yaml.packs))
        return definition

    def _reject_static(self, candidate: AssistantDefinition) -> None:
        """A régua da criação de Assistant de usuário (FR-020): o primeiro motivo vira o erro, nomeando o campo."""
        reasons = static_reasons(
            candidate,
            flow=effective_flow(candidate, self._preferred_flow),
            flow_roles=self._flow_roles,
            pack_tools=self._pack_tools(candidate.packs),
        )
        problems = [problem for problem in candidate.problems if problem.startswith("override.")]
        for reason in (*problems, *reasons):
            field = reason.removeprefix("override.").partition(":")[0].strip()
            raise RequestRejected(reason, field=field)

    async def _save(
        self,
        name: str,
        section: OverrideSection,
        override: OverridePayload,
        *,
        yaml: AssistantDefinition,
        actor: Principal,
        version: int | None,
    ) -> SystemAssistantView:
        record = StoredOverride(
            assistant=name,
            section=section,
            payload=payload_of(override),
            fingerprint=section_fingerprint(yaml, section),
            version=1,
            updated_by=actor.subject,
            updated_at=self._clock.now(),
        )
        await self._override_store().put(record, expected_version=version)
        self._effective.pop(name, None)
        return await self._system_view(name)

    async def _system(self, name: str) -> tuple[AssistantDefinition, tuple[OverrideStatus, ...]]:
        """A definição efetiva de um Assistant de sistema (o YAML mais as sobreposições ativas), com cache curto
        invalidado a cada gravação (research R31)."""
        yaml = self._config.assistants[name]
        if self._overrides is None:
            return yaml, ()
        now = self._clock.now()
        cached = self._effective.get(name)
        if cached is not None and now - cached[0] < self._override_ttl:
            return cached[1], cached[2]
        stored = await self._overrides.get(name)
        definition, statuses = effective(yaml, stored, pack_tools=self._pack_tools(yaml.packs))
        self._effective[name] = (now, definition, statuses)
        return definition, statuses

    async def _system_view(self, name: str) -> SystemAssistantView:
        yaml = self._config.assistants[name]
        self._effective.pop(name, None)
        definition, statuses = await self._system(name)
        availability = await self._availability(definition)
        flow = availability.flow
        required = tuple(self._flow_roles.get(flow, ())) if flow is not None and self._flow_roles else ()
        views = []
        for status in statuses:
            payload = status.payload
            state, reason = status.state, status.reason
            if payload is None:
                payload = _UNREADABLE_PLACEHOLDER[status.stored.section]
                state, reason = "inactive", UNREADABLE
            views.append(
                OverrideView(
                    section=status.stored.section,
                    payload=payload,
                    state=state,
                    reason=reason,
                    version=status.stored.version,
                    updated_by=status.stored.updated_by,
                    updated_at=status.stored.updated_at,
                )
            )
        return SystemAssistantView(
            name=name,
            description=yaml.description,
            visibility=yaml.visibility,
            flow=flow,
            status=status_of(definition, availability.reasons),
            overridable=yaml.overrides,
            yaml_models=yaml.roles,
            allow=yaml.allow,
            yaml_mcp=yaml_mcp(yaml),
            overrides=tuple(views),
            effective_models=definition.roles,
            effective_mcp=yaml_mcp(definition),
            yaml_vision=yaml.vision,
            effective_vision=definition.vision,
            required_roles=required,
            yaml_auth=yaml_auth(yaml),
            effective_auth=yaml_auth(definition),
        )

    # --- interno --------------------------------------------------------------------------------------------------

    async def _find(self, name: str, principal: Principal) -> AssistantDefinition | None:
        if not name.startswith(USER_PREFIX):
            return (await self._system(name))[0] if name in self._config.assistants else None
        plain = _plain_name(name)
        stored = await self._users.get(principal.subject, plain) if plain is not None else None
        return await self._user_definition(stored, principal) if stored is not None else None

    async def _user_definition(self, stored: StoredUserAssistant, principal: Principal) -> AssistantDefinition:
        """Passo 4: a definição sob a política aplicável **agora**. Fora dela, a definição carrega o motivo como
        problema — indisponível com erro que nomeia o campo, nunca resolvida com o que a política não concede."""
        policy = applicable_policy(self._config.policies, principal)
        if policy is None:
            return user_definition(
                stored.draft,
                owner=stored.owner,
                allow=(),
                limits=Limits(),
                problems=(f"policy: {NO_POLICY}",),
            )
        mcp = await self._mcp.aliases(owner=stored.owner) if stored.draft.mcp else frozenset[str]()
        try:
            return conform(stored.draft, policy, owner=stored.owner, mcp_aliases=mcp, preferred=self._preferred_flow)
        except PolicyViolation as violation:
            return user_definition(
                stored.draft,
                owner=stored.owner,
                allow=policy.models_allow,
                limits=Limits(),
                problems=(f"{violation.field}: {violation}",),
            )

    async def _conform(self, draft: UserAssistantDraft, principal: Principal) -> AssistantDefinition:
        policy = applicable_policy(self._config.policies, principal)
        if policy is None:
            raise NoApplicablePolicy(NO_POLICY, field="policy")
        mcp = await self._mcp.aliases(owner=principal.subject) if draft.mcp else frozenset[str]()
        definition = conform(draft, policy, owner=principal.subject, mcp_aliases=mcp, preferred=self._preferred_flow)
        # As regras da Fase 3 também valem na escrita: o usuário fica sabendo agora, não na primeira resolução (R22).
        reasons = static_reasons(
            definition,
            flow=effective_flow(definition, self._preferred_flow),
            flow_roles=self._flow_roles,
            pack_tools=self._pack_tools(definition.packs),
        )
        if reasons:
            field, _, _ = reasons[0].partition(":")
            raise RequestRejected(reasons[0], field=field)
        return definition

    async def _view(self, stored: StoredUserAssistant, principal: Principal) -> UserAssistant:
        definition = await self._user_definition(stored, principal)
        return UserAssistant(
            name=definition.name,
            owner=stored.owner,
            draft=stored.draft,
            created_at=stored.created_at,
            updated_at=stored.updated_at,
            status=status_of(definition, (await self._availability(definition)).reasons),
        )

    async def _availability(self, definition: AssistantDefinition) -> _Availability:
        flow = effective_flow(definition, self._preferred_flow)
        composition: Composition | None = None
        composition_error: str | None = None
        try:
            composition = self._packs.compose(definition.packs)
        except CompositionError as error:
            composition_error = str(error)
        mcp = await self._mcp.aliases(owner=definition.owner) if definition.mcp else frozenset[str]()
        collections = await self._collections.names() if definition.collections else frozenset[str]()
        reasons = reference_reasons(
            definition,
            flow=flow,
            flows=self._flows,
            composition_error=composition_error,
            mcp_aliases=mcp,
            collections=collections,
            flow_roles=self._flow_roles,
            pack_tools=self._pack_tools(definition.packs),
        )
        return _Availability(reasons=attribute(reasons, definition.overridden), flow=flow, composition=composition)

    def _pack_tools(self, packs: Sequence[str]) -> dict[str, frozenset[str]]:
        """Por pack com capacidades, as tools nativas e os retrievers que oferece — coletados na carga (002)."""
        offered: dict[str, frozenset[str]] = {}
        for name in packs:
            entry = self._packs.entry(name)
            if entry is not None and entry.capabilities is not None:
                capabilities = entry.capabilities
                offered[name] = frozenset((*capabilities.tools, *(r.name for r in capabilities.retrievers)))
        return offered

    def _preferred_flow(self, pack: str) -> str | None:
        entry = self._packs.entry(pack)
        if entry is None or entry.capabilities is None:
            return None
        return entry.capabilities.preferred_flow


class AccessService:
    """`Authenticator` e `ApiKeyAdmin`. A superfície decide os esquemas: pública só OIDC, privada só chave (FR-001),
    administração os dois (ADR-031); e, para OIDC, a audiência (research R26)."""

    def __init__(
        self,
        *,
        keys: ApiKeyStore,
        oidc: OidcVerifier,
        tokens: TokenGenerator,
        clock: Clock,
        claims: OidcClaims,
        admin_group: str | None,
        audiences: OidcAudiences | None = None,
    ) -> None:
        self._keys = keys
        self._oidc = oidc
        self._tokens = tokens
        self._clock = clock
        self._claims = claims
        self._admin_group = admin_group
        self._audiences = audiences or OidcAudiences()

    # --- Authenticator --------------------------------------------------------------------------------------------

    async def authenticate(self, *, surface: str, credential: str | None) -> Principal | None:
        """Credencial ausente, malformada, expirada ou revogada devolve `None`. Falha de armazenamento **não** vira
        `None`: seria dizer "credencial inválida" quando o problema é da plataforma."""
        schemes = SCHEMES_OF_SURFACE.get(surface)
        if schemes is None or credential is None or not credential.strip():
            return None
        # Com dois esquemas, decide o formato: o prefixo de chave segue o caminho de chave; o resto, OIDC (R25).
        if len(schemes) == 1:
            (scheme,) = schemes
        else:
            scheme = "api_key" if credential.startswith(KEY_PREFIX) else "oidc"
        if scheme == "oidc":
            audience = self._audiences.of(surface)
            claims = await self._oidc.verify(credential, audience=audience) if audience else None
            if claims is None:
                return None
            return principal_from_claims(claims, now=self._clock.now(), config=self._claims)

        key_id = parse_key(credential)
        if key_id is None:
            return None
        record = await self._keys.get(key_id)
        if record is None or not record.info.active or not matches(credential, record.key_hash):
            return None
        return Principal(subject=record.info.subject, scheme="api_key", groups=record.info.groups)

    # --- ApiKeyAdmin (superfície privada, grupo de administração) --------------------------------------------------

    async def issue(
        self,
        *,
        actor: Principal,
        subject: str,
        groups: Collection[str] = (),
        label: str | None = None,
    ) -> IssuedApiKey:
        self._require_admin(actor)
        # O grupo de administração só sai pela linha de comando: chave de admin é ato do operador (FR-036, R40).
        if self._admin_group is not None and self._admin_group in _group_names(groups):
            raise RequestRejected("o grupo de administração só é concedido pela linha de comando", field="groups")
        return await self.issue_as_operator(subject=subject, groups=groups, label=label)

    async def keys(self, *, actor: Principal) -> Sequence[ApiKeyInfo]:
        self._require_admin(actor)
        return await self.keys_as_operator()

    async def revoke(self, *, actor: Principal, key_id: str) -> ApiKeyInfo:
        self._require_admin(actor)
        return await self.revoke_as_operator(key_id=key_id)

    async def rotate(self, *, actor: Principal, key_id: str) -> IssuedApiKey:
        self._require_admin(actor)
        return await self.rotate_as_operator(key_id=key_id)

    # --- autoridade do operador (CLI: quem tem o host é o operador) ------------------------------------------------

    async def issue_as_operator(
        self, *, subject: str, groups: Collection[str] = (), label: str | None = None
    ) -> IssuedApiKey:
        if not SUBJECT_PATTERN.fullmatch(subject):
            raise RequestRejected(f"subject precisa ser 'user:<id>' ou 'svc:<id>': {subject!r}", field="subject")
        system = subject.removeprefix(SYSTEM_PREFIX) if subject.startswith(SYSTEM_PREFIX) else None
        if system is not None and not NAME_PATTERN.fullmatch(system):
            raise RequestRejected(f"o nome do sistema segue {NAME_PATTERN.pattern}: {subject!r}", field="subject")
        names = _group_names(groups)
        if any(not name or any(char.isspace() for char in name) for name in names):
            raise RequestRejected("grupos precisam ser nomes sem espaço", field="groups")

        key_id = self._tokens.token_hex(KEY_ID_BYTES)
        plaintext = compose_key(key_id, self._tokens.token_urlsafe(SECRET_BYTES))
        info = ApiKeyInfo(key_id=key_id, subject=subject, groups=names, label=label, created_at=self._clock.now())
        await self._keys.add(ApiKeyRecord(info=info, key_hash=hash_key(plaintext)))
        return IssuedApiKey(info=info, plaintext=plaintext)

    async def keys_as_operator(self) -> Sequence[ApiKeyInfo]:
        return [record.info for record in await self._keys.list()]

    async def revoke_as_operator(self, *, key_id: str) -> ApiKeyInfo:
        record = await self._keys.revoke(key_id, at=self._clock.now())
        if record is None:
            raise NotFound(f"chave '{key_id}' não existe")
        return record.info

    async def rotate_as_operator(self, *, key_id: str) -> IssuedApiKey:
        """Mesmo `key_id`, segredo novo; a troca do hash é da porta, condicionada a chave ativa (R38, R39)."""
        plaintext = compose_key(key_id, self._tokens.token_urlsafe(SECRET_BYTES))
        record = await self._keys.rotate(key_id, key_hash=hash_key(plaintext), at=self._clock.now())
        if record is None:
            if await self._keys.get(key_id) is None:
                raise NotFound(f"chave '{key_id}' não existe")
            raise Conflict(f"chave '{key_id}' revogada não rotaciona")
        return IssuedApiKey(info=record.info, plaintext=plaintext)

    def is_admin(self, principal: Principal) -> bool:
        """Membro do grupo de administração, em qualquer esquema (ADR-031, R27). Cumpre a porta `AdminGate` da 008."""
        return is_admin(principal, self._admin_group)

    def _require_admin(self, actor: Principal) -> None:
        """Quem não administra recebe o mesmo que um recurso inexistente (US2 cen. 5)."""
        if not self.is_admin(actor):
            raise NotFound("recurso não encontrado")


def _group_names(groups: Collection[str]) -> frozenset[str]:
    """Os grupos como a chave os guarda: sem o prefixo `group:` e sem espaço nas pontas."""
    return frozenset(group.removeprefix("group:").strip() for group in groups)
