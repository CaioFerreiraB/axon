"""Adapter primário HTTP da 012: o protocolo OIDC e as páginas do provedor (contracts/oidc.md, contracts/pages.md).

`router(service, settings)` devolve um `APIRouter` que a composition root inclui no app da 008 (ADR-030). Aqui só se
traduz HTTP: formulário, cookie, cabeçalhos e a base do pedido (com `X-Forwarded-*` só de proxy confiável, R8); as
decisões são do `IdentityService`.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qs, unquote_plus, urlsplit

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ai_core.identity.adapters import pages
from ai_core.identity.domain.clients import redirect_origins
from ai_core.identity.domain.outcomes import (
    FORM_REJECTED,
    AccountPage,
    ErrorPage,
    LoggedOut,
    LoginForm,
    PasswordForm,
    Redirect,
    SignedIn,
    TokenResponse,
    token_error,
)
from ai_core.identity.service import IdentityService

FORM_LIMIT: Final = 16 * 1024
"""Teto do corpo dos formulários do provedor (R4)."""

STYLESHEET: Final = Path(__file__).parent / "assets" / "identity.css"
FONTS: Final = Path(__file__).parent / "assets" / "fonts"
"""Mona Sans (SIL OFL 1.1, `fonts/OFL.txt`), a fonte do desenho aprovado, servida pela própria página: sem terceiros."""

type Network = ipaddress.IPv4Network | ipaddress.IPv6Network


@dataclass(frozen=True, slots=True, kw_only=True)
class IdentityHttpSettings:
    """O que só o HTTP precisa: marca da instalação, cookie e proxies confiáveis (011, contracts/configuration.md)."""

    display_name: str = pages.DEFAULT_NAME
    logo: tuple[bytes, str] | None = None
    """Conteúdo e tipo do `AI_CORE_LOGO_FILE` (SVG ou PNG)."""
    cookie_secure: bool = True
    trusted_proxies: tuple[str, ...] = ()
    """IPs ou redes (CIDR) cujos `X-Forwarded-*` valem."""
    networks: tuple[Network, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        networks = tuple(ipaddress.ip_network(entry.strip(), strict=False) for entry in self.trusted_proxies)
        object.__setattr__(self, "networks", networks)

    @property
    def cookie_name(self) -> str:
        """`__Host-` exige `Secure`, `Path=/` e nenhum `Domain`; em `http` de desenvolvimento, sem o prefixo (R5)."""
        return "__Host-aic_session" if self.cookie_secure else "aic_session"


_COMMON_HEADERS: Final = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "same-origin",
}


class _Http:
    """Estado do router: serviço, ajustes, CSP e o CSS com o nome pelo hash."""

    def __init__(self, service: IdentityService, settings: IdentityHttpSettings) -> None:
        self.service = service
        self.settings = settings
        self.css = STYLESHEET.read_bytes()
        self.fonts = {path.name: path.read_bytes() for path in FONTS.glob("*.woff2")}
        self.css_name = f"identity.{hashlib.sha256(self.css).hexdigest()[:12]}.css"
        self.brand = pages.Brand(
            name=settings.display_name.strip() or pages.DEFAULT_NAME,
            has_logo=settings.logo is not None,
            stylesheet=f"/oauth2/assets/{self.css_name}",
        )
        public = urlsplit(service.config.public_url)
        self.public_origin = f"{public.scheme}://{public.netloc}"
        origins = " ".join(origin for origin in redirect_origins(tuple(service.clients.values())))
        self.csp = (
            "default-src 'none'; style-src 'self'; font-src 'self'; img-src 'self' data:; "
            + f"form-action 'self' {origins}".rstrip()
            + "; frame-ancestors 'none'; base-uri 'none'"
        )

    # --- pedido --------------------------------------------------------------------------------------------------

    def _trusted(self, host: str | None) -> bool:
        if not host or not self.settings.networks:
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            return False
        return any(address in network for network in self.settings.networks)

    def source(self, request: Request) -> str | None:
        """IP de quem pede: o do socket, ou o primeiro não confiável de `X-Forwarded-For` vindo de proxy (R11)."""
        peer = request.client.host if request.client else None
        if not self._trusted(peer):
            return peer
        hops = [hop.strip() for hop in request.headers.get("x-forwarded-for", "").split(",") if hop.strip()]
        for hop in reversed(hops):
            if not self._trusted(hop):
                return hop
        return hops[0] if hops else peer

    def base(self, request: Request) -> str:
        """Esquema e host pelos quais o pedido chegou (R8)."""
        peer = request.client.host if request.client else None
        scheme, host = request.url.scheme, request.headers.get("host", request.url.netloc)
        if self._trusted(peer):
            scheme = request.headers.get("x-forwarded-proto", scheme).split(",")[0].strip() or scheme
            host = request.headers.get("x-forwarded-host", host).split(",")[0].strip() or host
        return f"{scheme}://{host}"

    def origin_ok(self, request: Request) -> bool:
        """Formulário vindo de outro site é recusado; sem `Origin`, vale o token sincronizador (R5)."""
        origin = request.headers.get("origin")
        return origin is None or origin in (self.public_origin, self.base(request))

    def session_token(self, request: Request) -> str | None:
        return request.cookies.get(self.settings.cookie_name) or None

    # --- respostas -----------------------------------------------------------------------------------------------

    def page(self, content: str, *, status: int = 200) -> HTMLResponse:
        return HTMLResponse(
            content,
            status_code=status,
            headers={**_COMMON_HEADERS, "Cache-Control": "no-store", "Content-Security-Policy": self.csp},
        )

    def redirect(self, location: str, *, status: int = 302) -> RedirectResponse:
        return RedirectResponse(location, status_code=status, headers={**_COMMON_HEADERS, "Cache-Control": "no-store"})

    def json(self, body: Mapping[str, object], *, status: int = 200, cache: str = "no-store") -> JSONResponse:
        headers = {**_COMMON_HEADERS, "Cache-Control": cache}
        if cache == "no-store":
            headers["Pragma"] = "no-cache"
        return JSONResponse(dict(body), status_code=status, headers=headers)

    def outcome(self, result: object, *, post: bool = False) -> Response:
        if isinstance(result, SignedIn):
            response = self.redirect(result.location, status=303)
            response.set_cookie(
                self.settings.cookie_name,
                result.session_token,
                max_age=result.max_age,
                path="/",
                secure=self.settings.cookie_secure,
                httponly=True,
                samesite="lax",
            )
            return response
        if isinstance(result, Redirect):
            return self.redirect(result.location, status=303 if post else 302)
        if isinstance(result, LoginForm):
            return self.page(pages.login_page(result, self.brand), status=401 if result.error else 200)
        if isinstance(result, PasswordForm):
            return self.page(pages.password_page(result, self.brand), status=400 if result.errors else 200)
        if isinstance(result, AccountPage):
            return self.page(pages.account_page(result, self.brand), status=400 if result.errors else 200)
        if isinstance(result, ErrorPage):
            return self.page(pages.error_page(result, self.brand), status=result.status)
        raise TypeError(f"desfecho desconhecido: {type(result).__name__}")

    def token(self, result: TokenResponse) -> JSONResponse:
        response = self.json(result.body, status=result.status)
        if result.status == 401:
            response.headers["WWW-Authenticate"] = 'Basic realm="ai-core"'
        return response


async def _form(request: Request) -> dict[str, str] | int:
    """Corpo `application/x-www-form-urlencoded` (R4); senão, o status do erro (415 ou 413)."""
    kind = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if kind != "application/x-www-form-urlencoded":
        return 415
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > FORM_LIMIT:
        return 413
    body = b""
    async for chunk in request.stream():
        body += chunk
        if len(body) > FORM_LIMIT:
            return 413
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True, strict_parsing=False)
    except UnicodeDecodeError:
        return 400
    return {key: values[0] for key, values in parsed.items()}


def _basic(request: Request) -> tuple[str, str] | bool | None:
    """`client_secret_basic` (RFC 6749 §2.3.1); `False` = cabeçalho malformado."""
    header = request.headers.get("authorization", "")
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "basic":
        return False
    try:
        decoded = base64.b64decode(value.strip(), validate=True).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return False
    client_id, separator, secret = decoded.partition(":")
    if not separator:
        return False
    return unquote_plus(client_id), unquote_plus(secret)


def _bearer(request: Request) -> str | None:
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer":
        return None
    return value.strip() or None


def router(service: IdentityService, settings: IdentityHttpSettings | None = None) -> APIRouter:
    http = _Http(service, settings or IdentityHttpSettings())
    api = APIRouter()

    def bad_form(status: int) -> Response:
        page = ErrorPage(status=status, title="Formulário inválido", message="Volte ao aplicativo e entre de novo.")
        return http.outcome(page)

    @api.get("/.well-known/openid-configuration")
    async def discovery(request: Request) -> Response:
        return http.json(service.discovery(http.base(request)), cache="public, max-age=300")

    @api.get("/oauth2/authorize")
    async def authorize(request: Request) -> Response:
        params = {key: value for key, value in request.query_params.items()}
        return http.outcome(await service.authorize(params, http.session_token(request)))

    @api.post("/oauth2/login")
    async def login(request: Request) -> Response:
        form = await _form(request)
        if isinstance(form, int):
            return bad_form(form)
        if not http.origin_ok(request):
            return http.outcome(FORM_REJECTED)
        result = await service.login(
            request=form.get("request", ""),
            identifier=form.get("identifier", ""),
            password=form.get("password", ""),
            csrf=form.get("csrf", ""),
            source=http.source(request),
        )
        return http.outcome(result, post=True)

    @api.post("/oauth2/password")
    async def password(request: Request) -> Response:
        form = await _form(request)
        if isinstance(form, int):
            return bad_form(form)
        if not http.origin_ok(request):
            return http.outcome(FORM_REJECTED)
        result = await service.change_temporary_password(
            request=form.get("request", ""),
            csrf=form.get("csrf", ""),
            new_password=form.get("new_password", ""),
            confirm=form.get("confirm", ""),
        )
        return http.outcome(result, post=True)

    @api.get("/oauth2/account")
    async def account(request: Request) -> Response:
        return http.outcome(await service.account_page(http.session_token(request)))

    @api.post("/oauth2/account")
    async def change_password(request: Request) -> Response:
        form = await _form(request)
        if isinstance(form, int):
            return bad_form(form)
        if not http.origin_ok(request):
            return http.outcome(FORM_REJECTED)
        result = await service.change_own_password(
            session_token=http.session_token(request),
            csrf=form.get("csrf", ""),
            current_password=form.get("current_password", ""),
            new_password=form.get("new_password", ""),
            confirm=form.get("confirm", ""),
            source=http.source(request),
        )
        return http.outcome(result, post=True)

    @api.post("/oauth2/token")
    async def token(request: Request) -> Response:
        form = await _form(request)
        basic = _basic(request)
        if isinstance(form, int):
            return http.token(token_error("invalid_request", "corpo application/x-www-form-urlencoded esperado"))
        if basic is False:
            return http.token(token_error("invalid_client", "cabeçalho Authorization inválido", status=401))
        return http.token(await service.token(form, basic if isinstance(basic, tuple) else None))

    @api.get("/oauth2/userinfo")
    async def userinfo(request: Request) -> Response:
        claims = await service.userinfo(_bearer(request))
        if claims is None:
            response = http.json({"error": "invalid_token"}, status=401)
            response.headers["WWW-Authenticate"] = 'Bearer error="invalid_token"'
            return response
        return http.json(claims)

    @api.get("/oauth2/jwks")
    async def jwks() -> Response:
        return http.json(service.jwks(), cache="public, max-age=300")

    @api.post("/oauth2/revoke")
    async def revoke(request: Request) -> Response:
        form = await _form(request)
        basic = _basic(request)
        if isinstance(form, int):
            return http.token(token_error("invalid_request", "corpo application/x-www-form-urlencoded esperado"))
        if basic is False:
            return http.token(token_error("invalid_client", "cabeçalho Authorization inválido", status=401))
        return http.token(await service.revoke(form, basic if isinstance(basic, tuple) else None))

    @api.get("/oauth2/logout")
    async def logout(request: Request) -> Response:
        params = {key: value for key, value in request.query_params.items()}
        result: LoggedOut = await service.logout(params, http.session_token(request))
        response: Response
        if result.location is not None:
            response = http.redirect(result.location)
        else:
            response = http.page(pages.logged_out_page(http.brand))
        response.delete_cookie(
            http.settings.cookie_name, path="/", secure=http.settings.cookie_secure, httponly=True, samesite="lax"
        )
        return response

    @api.get("/oauth2/google/start")
    async def google_start(request: Request) -> Response:
        return http.outcome(await service.google_start(request.query_params.get("request", "")))

    @api.get("/oauth2/google/callback")
    async def google_callback(request: Request) -> Response:
        params = {key: value for key, value in request.query_params.items()}
        return http.outcome(await service.google_callback(params))

    @api.get("/oauth2/assets/{name}")
    async def asset(name: str) -> Response:
        if name == http.css_name:
            return Response(
                http.css,
                media_type="text/css; charset=utf-8",
                headers={**_COMMON_HEADERS, "Cache-Control": "public, max-age=31536000, immutable"},
            )
        if name in http.fonts:
            return Response(
                http.fonts[name],
                media_type="font/woff2",
                headers={**_COMMON_HEADERS, "Cache-Control": "public, max-age=604800"},
            )
        if name == "logo" and http.settings.logo is not None:
            content, media_type = http.settings.logo
            headers: dict[str, Any] = {**_COMMON_HEADERS, "Cache-Control": "public, max-age=3600"}
            # SVG não executa script embutido (contracts/oidc.md).
            headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'"
            return Response(content, media_type=media_type, headers=headers)
        return Response(status_code=404, headers={**_COMMON_HEADERS, "Cache-Control": "no-store"})

    return api
