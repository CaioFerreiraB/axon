"""Serviços da 003: implementam os seams de `api.py` orquestrando `domain/` e as portas.

`AssistantsService` resolve grants, oferece o diretório e valida referências; `AccessService` autentica e administra
chaves. A ordem da resolução é a de research R4 — ACL antes de tudo, orçamento por último. Não importa `adapters/`.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from ai_core.assistants.api import (
    NAME_PATTERN,
    SCHEME_OF_SURFACE,
    SUBJECT_PATTERN,
    USER_PREFIX,
    ApiKeyInfo,
    AssistantSummary,
    AssistantUnavailable,
    Conflict,
    ExecutionGrant,
    IssuedApiKey,
    Limits,
    NoApplicablePolicy,
    NotFound,
    PolicyViolation,
    Principal,
    RateLimited,
    RequestRejected,
    UserAssistant,
    UserAssistantDraft,
    ValidationReport,
)
from ai_core.assistants.domain.access import OidcClaims, is_admin, principal_from_claims
from ai_core.assistants.domain.definitions import AssistantDefinition, AssistantsConfig
from ai_core.assistants.domain.keys import (
    KEY_ID_BYTES,
    SECRET_BYTES,
    ApiKeyRecord,
    compose_key,
    hash_key,
    matches,
    parse_key,
)
from ai_core.assistants.domain.policies import applicable_policy, conform, user_definition
from ai_core.assistants.domain.rate import RATE_WINDOW
from ai_core.assistants.domain.resolution import (
    build_grant,
    effective_flow,
    not_found,
    select_models,
    split_model_id,
)
from ai_core.assistants.domain.validation import reference_reasons, status_of
from ai_core.assistants.ports import (
    ApiKeyStore,
    Clock,
    CollectionCatalog,
    McpDirectory,
    OidcVerifier,
    RateCounterStore,
    StoredUserAssistant,
    TokenGenerator,
    UserAssistantStore,
)
from ai_core.graph import api as engine
from ai_core.packs.api import Composition, CompositionError, PackRegistry


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
    ) -> None:
        self._config = config
        self._packs = packs
        self._flows = frozenset(flows)
        self._users = users
        self._mcp = mcp
        self._collections = collections
        self._rate = rate
        self._clock = clock

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
            definition = self._config.assistants[name]
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
            definition = self._config.assistants[name]
            statuses.append(status_of(definition, (await self._availability(definition)).reasons))
        for stored in await self._users.all():
            definition = user_definition(stored.draft, owner=stored.owner, allow=(), limits=Limits())
            statuses.append(status_of(definition, (await self._availability(definition)).reasons))
        return ValidationReport(statuses=tuple(statuses))

    # --- interno --------------------------------------------------------------------------------------------------

    async def _find(self, name: str, principal: Principal) -> AssistantDefinition | None:
        if not name.startswith(USER_PREFIX):
            return self._config.assistants.get(name)
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
        return conform(draft, policy, owner=principal.subject, mcp_aliases=mcp, preferred=self._preferred_flow)

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
        )
        return _Availability(reasons=reasons, flow=flow, composition=composition)

    def _preferred_flow(self, pack: str) -> str | None:
        entry = self._packs.entry(pack)
        if entry is None or entry.capabilities is None:
            return None
        return entry.capabilities.preferred_flow


class AccessService:
    """`Authenticator` e `ApiKeyAdmin`. A superfície decide o esquema: pública só OIDC, privada só chave (FR-001)."""

    def __init__(
        self,
        *,
        keys: ApiKeyStore,
        oidc: OidcVerifier,
        tokens: TokenGenerator,
        clock: Clock,
        claims: OidcClaims,
        admin_group: str | None,
    ) -> None:
        self._keys = keys
        self._oidc = oidc
        self._tokens = tokens
        self._clock = clock
        self._claims = claims
        self._admin_group = admin_group

    # --- Authenticator --------------------------------------------------------------------------------------------

    async def authenticate(self, *, surface: str, credential: str | None) -> Principal | None:
        """Credencial ausente, malformada, expirada ou revogada devolve `None`. Falha de armazenamento **não** vira
        `None`: seria dizer "credencial inválida" quando o problema é da plataforma."""
        scheme = SCHEME_OF_SURFACE.get(surface)
        if scheme is None or credential is None or not credential.strip():
            return None
        if scheme == "oidc":
            claims = await self._oidc.verify(credential)
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
        return await self.issue_as_operator(subject=subject, groups=groups, label=label)

    async def keys(self, *, actor: Principal) -> Sequence[ApiKeyInfo]:
        self._require_admin(actor)
        return await self.keys_as_operator()

    async def revoke(self, *, actor: Principal, key_id: str) -> ApiKeyInfo:
        self._require_admin(actor)
        return await self.revoke_as_operator(key_id=key_id)

    # --- autoridade do operador (CLI: quem tem o host é o operador) ------------------------------------------------

    async def issue_as_operator(
        self, *, subject: str, groups: Collection[str] = (), label: str | None = None
    ) -> IssuedApiKey:
        if not SUBJECT_PATTERN.fullmatch(subject):
            raise RequestRejected(f"subject precisa ser 'user:<id>' ou 'svc:<id>': {subject!r}", field="subject")
        names = frozenset(group.removeprefix("group:").strip() for group in groups)
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

    def is_admin(self, principal: Principal) -> bool:
        """Chave de API **e** grupo de administração (FR-015). Cumpre a porta `AdminGate` da 008 (research R20 dela)."""
        return is_admin(principal, self._admin_group)

    def _require_admin(self, actor: Principal) -> None:
        """Quem não administra recebe o mesmo que um recurso inexistente (US2 cen. 5)."""
        if not self.is_admin(actor):
            raise NotFound("recurso não encontrado")
