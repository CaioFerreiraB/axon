"""Superfície de administração `/admin/v1` (spec 008 US9; ADR-031; contracts/admin-api.md; research R43 a R49).

Aceita o token da console (audiência `axon-admin`) ou uma chave de API — a 003 decide pela superfície `admin`. Só o
grupo de administração alcança; credencial inválida é 401; autenticado fora do grupo recebe, em **toda** rota, o mesmo
404 de uma rota inexistente — a rota final deste módulo autentica e devolve esse 404, para nenhuma rota se revelar.
Toda resposta sai com `Cache-Control: no-store` e um `X-Request-Id` (o middleware do prefixo); nenhuma traz valor de
segredo. Aqui só se traduz HTTP: as regras são dos módulos donos (003, 006, 009, 012), e os formatos, de
`domain/admin_*.py`.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Awaitable, Callable
from typing import Any, Final

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from axon_ai.assistants.api import ADMIN_SURFACE, Conflict, NotFound, OverrideSection, Principal
from axon_ai.http.adapters.auth import authenticated
from axon_ai.http.adapters.chat import REQUEST_ID_HEADER, json_body
from axon_ai.http.adapters.errors import ApiError, respond
from axon_ai.http.domain import admin_accounts, admin_assistants, admin_observability, admin_usage
from axon_ai.http.domain.admin_common import only
from axon_ai.http.domain.errors import admin_error_for, key_revoked
from axon_ai.http.domain.private import health_json, issue_request, key_json
from axon_ai.http.ports import AdminGate, AdminSeams, Clock, HealthProvider, InstanceBranding, RequestIds
from axon_ai.identity.api import AccountAdmin, AccountNotFound, IssuedPassword, LoginSettings
from axon_ai.llm.api import ModelPolicy

ADMIN_PREFIX: Final = "/admin/v1"
_METHODS: Final = ["GET", "POST", "PUT", "PATCH", "DELETE"]
_PATH_PARAM: Final = re.compile(r"{(\w+)}")
_SECTIONS: Final[dict[str, OverrideSection]] = {"models": "models", "mcp": "mcp", "auth": "auth"}

type Handler = Callable[..., Awaitable[Any]]


class AdminHeaders:
    """Middleware ASGI do prefixo: `Cache-Control: no-store` e o identificador da requisição em toda resposta da
    administração — inclusive as das rotas de MCP reaproveitadas e as dos tratadores de erro da app (FR-010, FR-027)."""

    def __init__(self, app: ASGIApp, *, request_ids: RequestIds) -> None:
        self._app = app
        self._ids = request_ids

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "") if scope["type"] == "http" else ""
        if not (path == ADMIN_PREFIX or path.startswith(f"{ADMIN_PREFIX}/")):
            await self._app(scope, receive, send)
            return
        request_id = self._ids.next()

        async def stamped(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "no-store"
                if REQUEST_ID_HEADER not in headers:
                    headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        await self._app(scope, receive, stamped)


async def _admin(request: Request) -> Principal:
    principal = await authenticated(request, ADMIN_SURFACE)
    gate: AdminGate = request.app.state.admin
    if not gate.is_admin(principal):
        # Quem não administra não fica sabendo que a rota existe — o 404 de recurso inexistente (FR-024).
        raise NotFound("recurso não encontrado")
    return principal


def _not_found() -> JSONResponse:
    response = admin_error_for(NotFound("recurso não encontrado"))
    assert response is not None
    return respond(response)


def admin_router(seams: AdminSeams, instance: InstanceBranding) -> APIRouter:
    router = APIRouter()

    def route(method: str, path: str, *, status: int = 200) -> Callable[[Handler], Handler]:
        """Uma rota de administração: autentica, exige o grupo e traduz os erros pela tabela da superfície (R46).

        O FastAPI lê a assinatura do endpoint; ela é montada só com a requisição e os parâmetros do caminho — o
        `Principal` é argumento do handler, não da requisição."""

        def decorate(handler: Handler) -> Handler:
            async def endpoint(request: Request, **params: str) -> Response:
                try:
                    principal = await _admin(request)
                    content = await handler(request, principal, **params)
                except ApiError as error:
                    return respond(error.response)
                except Exception as error:
                    mapped = admin_error_for(error)
                    if mapped is None:
                        raise
                    return respond(mapped)
                if isinstance(content, Response):
                    return content
                if status == 204:
                    return Response(status_code=204)
                return JSONResponse(status_code=status, content=content)

            parameters = [inspect.Parameter("request", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=Request)]
            parameters += [
                inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, annotation=str)
                for name in _PATH_PARAM.findall(path)
            ]
            endpoint.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
            endpoint.__name__ = handler.__name__
            endpoint.__doc__ = handler.__doc__
            router.add_api_route(path, endpoint, methods=[method], status_code=status)
            return handler

        return decorate

    def accounts() -> AccountAdmin:
        if seams.accounts is None:  # identidade desligada: as rotas existem e respondem como inexistentes
            raise NotFound("recurso não encontrado")
        return seams.accounts

    def login() -> LoginSettings:
        if seams.login is None:
            raise NotFound("recurso não encontrado")
        return seams.login

    def clock(request: Request) -> Clock:
        return request.app.state.clock  # type: ignore[no-any-return]

    # --- sessão ---------------------------------------------------------------------------------------------------

    @route("GET", "/me")
    async def me(request: Request, principal: Principal) -> Any:
        """Quem está na sessão e a marca da instalação (R48)."""
        username = principal.subject.split(":", 1)[-1]
        name = username
        if principal.scheme == "oidc" and seams.accounts is not None:
            try:
                name = (await seams.accounts.account(username)).name
            except AccountNotFound:
                name = username
        return {
            "subject": principal.subject,
            "username": username,
            "name": name,
            "groups": sorted(principal.groups),
            "scheme": principal.scheme,
            "instance": {"name": instance.name, "logo_url": instance.logo_url, "custom": instance.custom},
        }

    # --- Assistants de sistema (003) ------------------------------------------------------------------------------

    @route("GET", "/assistants")
    async def assistants(request: Request, principal: Principal) -> Any:
        views = await seams.assistants.system_assistants(actor=principal)
        return {"data": [admin_assistants.view_json(view) for view in views]}

    @route("GET", "/assistants/{name}")
    async def assistant(request: Request, principal: Principal, name: str) -> Any:
        return admin_assistants.view_json(await seams.assistants.system_assistant(name, actor=principal))

    @route("PUT", "/assistants/{name}/models")
    async def override_models(request: Request, principal: Principal, name: str) -> Any:
        override, version = admin_assistants.models_body(await json_body(request))
        view = await seams.assistants.override_models(name, override, actor=principal, version=version)
        return admin_assistants.view_json(view)

    @route("PUT", "/assistants/{name}/mcp")
    async def override_mcp(request: Request, principal: Principal, name: str) -> Any:
        override, version = admin_assistants.mcp_body(await json_body(request))
        view = await seams.assistants.override_mcp(name, override, actor=principal, version=version)
        return admin_assistants.view_json(view)

    @route("PUT", "/assistants/{name}/auth")
    async def override_auth(request: Request, principal: Principal, name: str) -> Any:
        """Quem pode usar o Assistant (ADR-040): a 003 confere o conteúdo e devolve o campo."""
        override, version = admin_assistants.auth_body(await json_body(request))
        view = await seams.assistants.override_auth(name, override, actor=principal, version=version)
        return admin_assistants.view_json(view)

    @route("DELETE", "/assistants/{name}/overrides/{section}")
    async def discard(request: Request, principal: Principal, name: str, section: str) -> Any:
        if section not in _SECTIONS:
            raise NotFound("recurso não encontrado")
        version = admin_assistants.version_param(request.query_params.get("version"))
        view = await seams.assistants.discard_override(name, _SECTIONS[section], actor=principal, version=version)
        return admin_assistants.view_json(view)

    @route("GET", "/assistants/{name}/history")
    async def history(request: Request, principal: Principal, name: str) -> Any:
        return admin_assistants.history_json(await seams.assistants.history(name, actor=principal))

    @route("POST", "/assistants/{name}/models/check")
    async def check_model(request: Request, principal: Principal, name: str) -> Any:
        """ "Testar modelo" (R47): a allowlist do Assistant é conferida sem I/O pelo `for_role` da 006 (fora dela, 422
        em `model`); depois, a sonda do provider, com o tempo medido pelo `Clock`."""
        role, ref = admin_assistants.check_body(await json_body(request))
        view = await seams.assistants.system_assistant(name, actor=principal)
        policy = ModelPolicy(roles={role: ref}, allow=tuple(view.allow))
        seams.models.for_execution(policy=policy, request_id="admin-check").for_role(role)
        started = clock(request).now()
        (health,) = await seams.models.check(policy)
        elapsed = (clock(request).now() - started).total_seconds() * 1000
        return {"available": health.available, "detail": health.detail, "latency_ms": round(elapsed)}

    @route("GET", "/providers")
    async def providers(request: Request, principal: Principal) -> Any:
        """Os providers registrados e se cada um está pronto (ADR-035)."""
        return {"data": [admin_assistants.provider_json(status) for status in await seams.models.providers()]}

    # --- uso e preços (009) ---------------------------------------------------------------------------------------

    @route("GET", "/usage")
    async def usage(request: Request, principal: Principal) -> Any:
        query = admin_usage.usage_query(
            dict(request.query_params), now=clock(request).now(), default_tz=seams.default_timezone
        )
        return admin_usage.report_json(await seams.usage.report(query))

    @route("GET", "/prices")
    async def prices(request: Request, principal: Principal) -> Any:
        return {"data": [admin_usage.price_json(price) for price in await seams.prices.prices()]}

    @route("POST", "/prices", status=201)
    async def add_price(request: Request, principal: Principal) -> Any:
        fields = admin_usage.price_body(await json_body(request))
        admin_usage.check_price_provider(fields["provider"], await seams.models.providers())
        return admin_usage.price_json(await seams.prices.add_price(**fields, actor=principal.subject))

    @route("GET", "/prices/unpriced")
    async def unpriced(request: Request, principal: Principal) -> Any:
        start, end = admin_usage.period_params(
            dict(request.query_params), now=clock(request).now(), default_tz=seams.default_timezone
        )
        return {"data": list(await seams.prices.unpriced_models(start=start, end=end))}

    # --- observabilidade (009) ------------------------------------------------------------------------------------

    async def observability_view() -> Any:
        return admin_observability.settings_json(await seams.destinations.settings(), seams.destinations.health())

    @route("GET", "/observability")
    async def observability(request: Request, principal: Principal) -> Any:
        return await observability_view()

    @route("PUT", "/observability/langfuse")
    async def set_langfuse(request: Request, principal: Principal) -> Any:
        fields = admin_observability.langfuse_body(await json_body(request))
        await seams.destinations.set_langfuse(**fields, actor=principal.subject)
        return await observability_view()

    @route("PUT", "/observability/capture")
    async def set_capture(request: Request, principal: Principal) -> Any:
        enabled, version = admin_observability.capture_body(await json_body(request))
        await seams.destinations.set_capture(enabled=enabled, actor=principal.subject, version=version)
        return await observability_view()

    @route("POST", "/observability/langfuse/test")
    async def test_langfuse(request: Request, principal: Principal) -> Any:
        fields = admin_observability.connection_body(await json_body(request))
        return admin_observability.check_json(await seams.destinations.test_langfuse(**fields))

    # --- contas, grupos e login (012) -----------------------------------------------------------------------------

    @route("GET", "/users")
    async def users(request: Request, principal: Principal) -> Any:
        params = admin_accounts.users_params(dict(request.query_params))
        return admin_accounts.page_json(await accounts().accounts(**params))

    @route("POST", "/users", status=201)
    async def create_user(request: Request, principal: Principal) -> Any:
        draft = admin_accounts.draft_body(await json_body(request))
        created = await accounts().create(draft, actor=principal.subject)
        if isinstance(created, IssuedPassword):
            return admin_accounts.issued_json(created)
        return {"account": admin_accounts.account_json(created)}  # só Google: sem senha (FR-002 da 012)

    @route("GET", "/users/{username}")
    async def user(request: Request, principal: Principal, username: str) -> Any:
        return admin_accounts.account_json(await accounts().account(username))

    @route("PATCH", "/users/{username}")
    async def update_user(request: Request, principal: Principal, username: str) -> Any:
        patch, version = admin_accounts.patch_body(await json_body(request))
        updated = await accounts().update(username, patch, actor=principal.subject, version=version)
        return admin_accounts.account_json(updated)

    @route("POST", "/users/{username}/password")
    async def reset_password(request: Request, principal: Principal, username: str) -> Any:
        return admin_accounts.issued_json(await accounts().reset_password(username, actor=principal.subject))

    @route("POST", "/users/{username}/disable")
    async def disable(request: Request, principal: Principal, username: str) -> Any:
        return admin_accounts.account_json(await accounts().disable(username, actor=principal.subject))

    @route("POST", "/users/{username}/enable")
    async def enable(request: Request, principal: Principal, username: str) -> Any:
        return admin_accounts.account_json(await accounts().enable(username, actor=principal.subject))

    @route("DELETE", "/users/{username}/google")
    async def unlink_google(request: Request, principal: Principal, username: str) -> Any:
        return admin_accounts.account_json(await accounts().unlink_google(username, actor=principal.subject))

    @route("GET", "/groups")
    async def groups(request: Request, principal: Principal) -> Any:
        return {"data": [admin_accounts.group_json(group) for group in await accounts().groups()]}

    @route("POST", "/groups", status=201)
    async def create_group(request: Request, principal: Principal) -> Any:
        name = admin_accounts.group_body(await json_body(request))
        return admin_accounts.group_json(await accounts().create_group(name, actor=principal.subject))

    @route("DELETE", "/groups/{name}", status=204)
    async def delete_group(request: Request, principal: Principal, name: str) -> Any:
        await accounts().delete_group(name, actor=principal.subject)

    @route("PUT", "/groups/{name}/members")
    async def set_members(request: Request, principal: Principal, name: str) -> Any:
        members = admin_accounts.members_body(await json_body(request))
        return admin_accounts.group_json(await accounts().set_members(name, members, actor=principal.subject))

    @route("GET", "/login-settings")
    async def login_settings(request: Request, principal: Principal) -> Any:
        return admin_accounts.login_json(await login().view())

    @route("PUT", "/login-settings")
    async def set_login_settings(request: Request, principal: Principal) -> Any:
        enabled, version = admin_accounts.login_body(await json_body(request))
        return admin_accounts.login_json(await login().set_google(enabled, actor=principal.subject, version=version))

    # --- chaves de API (003) e saúde (011) ------------------------------------------------------------------------

    @route("GET", "/keys")
    async def keys(request: Request, principal: Principal) -> Any:
        return {"data": [key_json(info) for info in await request.app.state.keys.keys(actor=principal)]}

    @route("POST", "/keys", status=201)
    async def issue_key(request: Request, principal: Principal) -> Any:
        subject, key_groups, label = issue_request(await json_body(request))
        issued = await request.app.state.keys.issue(actor=principal, subject=subject, groups=key_groups, label=label)
        return key_json(issued.info) | {"key": issued.plaintext}

    @route("DELETE", "/keys/{key_id}")
    async def revoke_key(request: Request, principal: Principal, key_id: str) -> Any:
        return key_json(await request.app.state.keys.revoke(actor=principal, key_id=key_id))

    @route("POST", "/keys/{key_id}/rotate")
    async def rotate_key(request: Request, principal: Principal, key_id: str) -> Any:
        """Segredo novo para a mesma chave, só nesta resposta (ADR-040, R56). Nenhum campo de corpo é aceito."""
        if await request.body():
            only(await json_body(request), ())
        try:
            rotated = await request.app.state.keys.rotate(actor=principal, key_id=key_id)
        except Conflict as error:
            raise ApiError(key_revoked(str(error))) from error
        return key_json(rotated.info) | {"key": rotated.plaintext}

    @route("GET", "/health")
    async def health(request: Request, principal: Principal) -> Any:
        provider: HealthProvider = request.app.state.health
        report = await provider.health()
        # Como na superfície privada: só item crítico tira a instância do ar (011 FR-012).
        return JSONResponse(status_code=503 if report.status == "down" else 200, content=health_json(report))

    return router


def admin_fallback_router() -> APIRouter:
    """Incluído por último no prefixo: qualquer outro caminho ou método autentica e responde o 404 de não admin."""
    router = APIRouter()

    async def unknown(request: Request, rest: str) -> Response:
        try:
            await authenticated(request, ADMIN_SURFACE)
        except ApiError as error:
            return respond(error.response)
        return _not_found()

    router.add_api_route("/{rest:path}", unknown, methods=_METHODS, include_in_schema=False)
    return router
