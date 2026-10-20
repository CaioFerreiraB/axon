"""Páginas do provedor: login, troca de senha obrigatória, "Minha conta", erro e saída (contracts/pages.md; R3).

HTML montado aqui mesmo, sem motor de templates: toda substituição passa por `html.escape`, e só trechos marcados como
`Safe` entram crus — e todos eles são montados neste arquivo. Nenhum script: a CSP é `script-src 'none'` (por isso o
botão de mostrar a senha do desenho não existe aqui). Desenho aprovado no Penpot, página "Login e conta"; a marca segue
o ADR-038 (lockup Axon sem marca da instalação; com ela, "com Axon" no rodapé do cartão).
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from urllib.parse import urlencode

from axon_ai.identity.api import Account
from axon_ai.identity.domain.outcomes import AccountPage, ErrorPage, LoginForm, PasswordForm

DEFAULT_NAME = "Axon"


class Safe(str):
    """Trecho já seguro, montado neste módulo."""

    __slots__ = ()


def esc(value: object) -> Safe:
    if isinstance(value, Safe):
        return value
    return Safe(html.escape(str(value), quote=True))


def join(*parts: object) -> Safe:
    return Safe("".join(esc(part) for part in parts))


@dataclass(frozen=True, slots=True, kw_only=True)
class Brand:
    """Nome e logotipo da instalação (FR-023). `custom` diz se ela tem marca própria — nome diferente de "Axon" ou
    logotipo: então a marca dela ocupa o lugar principal e o Axon vai ao rodapé; senão, o lockup Axon (ADR-038)."""

    name: str = DEFAULT_NAME
    has_logo: bool = False
    custom: bool = False
    stylesheet: str = "/oauth2/assets/identity.css"


# ---------------------------------------------------------------------------------------------------------------------
# Peças
# ---------------------------------------------------------------------------------------------------------------------

_ALERT_ICON = Safe(
    '<svg class="alert-icon" viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">'
    '<path fill="currentColor" d="M8 1.5c.4 0 .8.2 1 .6l6 10.6c.4.8-.1 1.8-1 1.8H2c-.9 0-1.4-1-1-1.8'
    "L7 2.1c.2-.4.6-.6 1-.6Z"
    'm0 4a.75.75 0 0 0-.75.75v3a.75.75 0 0 0 1.5 0v-3A.75.75 0 0 0 8 5.5Zm0 6.75a.9.9 0 1 0 0-1.8.9.9 0 0 0 0 1.8Z"/>'
    "</svg>"
)
_GOOGLE_ICON = Safe(
    '<svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true" focusable="false">'
    '<path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92'
    'c1.7-1.57 2.68-3.88 2.68-6.62Z"/>'
    '<path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.8.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7'
    'H.96v2.33A9 9 0 0 0 9 18Z"/>'
    '<path fill="#FBBC05" d="M3.97 10.72A5.4 5.4 0 0 1 3.68 9c0-.6.1-1.18.29-1.72V4.95H.96A9 9 0 0 0 0 9c0 1.45.35 2.83'
    '.96 4.05l3.01-2.33Z"/>'
    '<path fill="#EA4335" d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95'
    "l3.01 2.33"
    'C4.68 5.16 6.66 3.58 9 3.58Z"/>'
    "</svg>"
)
_SIGN_OUT_ICON = Safe(
    '<svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">'
    '<path fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" '
    'd="M6 2.75H3.5a.75.75 0 0 0-.75.75v9c0 .41.34.75.75.75H6M10.5 11l3-3-3-3M13.25 8H6"/></svg>'
)


_LOCKUP = Safe(
    '<span class="brand brand-axon"><picture>'
    '<source media="(prefers-color-scheme: dark)" srcset="/oauth2/assets/axon-lockup-dark.svg">'
    '<img class="lockup" src="/oauth2/assets/axon-lockup-light.svg" alt="Axon" width="106" height="32">'
    "</picture></span>"
)
_ATTRIBUTION = Safe(
    '<p class="attribution"><picture>'
    '<source media="(prefers-color-scheme: dark)" srcset="/oauth2/assets/axon-symbol.svg">'
    '<img src="/oauth2/assets/axon-symbol-light.svg" alt="" width="16" height="16">'
    "</picture><span>com Axon</span></p>"
)
_FAVICON = Safe('<link rel="icon" type="image/svg+xml" href="/oauth2/assets/favicon.svg">\n')


def _brand(brand: Brand) -> Safe:
    if not brand.custom:
        return _LOCKUP
    if brand.has_logo:
        mark = Safe('<img class="mark-image" src="/oauth2/assets/logo" alt="" width="28" height="28">')
    else:
        mark = join(
            Safe('<span class="mark" aria-hidden="true">'), (brand.name.strip()[:1] or "A").upper(), Safe("</span>")
        )
    return join(
        Safe('<span class="brand">'), mark, Safe('<span class="brand-name">'), brand.name, Safe("</span></span>")
    )


def _hidden(name: str, value: str) -> Safe:
    return join(Safe(f'<input type="hidden" name="{name}" value="'), value, Safe('">'))


def _alert(title: str, body: str, *, kind: str = "error") -> Safe:
    return join(
        Safe(f'<div class="alert alert-{kind}" role="alert">'),
        _ALERT_ICON if kind == "error" else Safe(""),
        Safe('<div><p class="alert-title">'),
        title,
        Safe('</p><p class="alert-body">'),
        body,
        Safe("</p></div></div>"),
    )


def _field(
    name: str,
    label: str,
    *,
    kind: str = "text",
    autocomplete: str,
    value: str = "",
    placeholder: str = "",
    hint: str | None = None,
    error: str | None = None,
    autofocus: bool = False,
) -> Safe:
    described = []
    if hint:
        described.append(f"{name}-hint")
    if error:
        described.append(f"{name}-error")
    attributes = [
        f'id="{name}"',
        f'name="{name}"',
        f'type="{kind}"',
        f'autocomplete="{autocomplete}"',
        "required",
    ]
    if kind == "text":
        attributes += ['autocapitalize="none"', 'spellcheck="false"']
    if described:
        attributes.append(f'aria-describedby="{" ".join(described)}"')
    if error:
        attributes.append('aria-invalid="true"')
    if autofocus:
        attributes.append("autofocus")
    parts: list[object] = [
        Safe('<div class="field">'),
        Safe(f'<label for="{name}">'),
        label,
        Safe("</label>"),
        Safe(f"<input {' '.join(attributes)}"),
    ]
    if value:
        parts += [Safe(' value="'), value, Safe('"')]
    if placeholder:
        parts += [Safe(' placeholder="'), placeholder, Safe('"')]
    parts.append(Safe(">"))
    if hint:
        parts += [Safe(f'<p class="hint" id="{name}-hint">'), hint, Safe("</p>")]
    if error:
        parts += [Safe(f'<p class="field-error" id="{name}-error">'), error, Safe("</p>")]
    parts.append(Safe("</div>"))
    return join(*parts)


def _document(title: str, brand: Brand, body: Safe, *, wide: bool = False) -> str:
    return join(
        Safe('<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'),
        Safe('<meta name="viewport" content="width=device-width, initial-scale=1">\n'),
        Safe('<meta name="color-scheme" content="light dark">\n'),
        Safe('<meta name="robots" content="noindex">\n'),
        _FAVICON,
        Safe("<title>"),
        title,
        Safe(" · "),
        brand.name,
        Safe('</title>\n<link rel="stylesheet" href="'),
        brand.stylesheet,
        Safe('">\n</head>\n<body>\n<main class="shell'),
        Safe(" shell-wide" if wide else ""),
        Safe('">\n<div class="card">\n'),
        body,
        Safe("\n" + _ATTRIBUTION) if brand.custom else Safe(""),
        Safe("\n</div>\n</main>\n</body>\n</html>\n"),
    )


# ---------------------------------------------------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------------------------------------------------


def login_page(form: LoginForm, brand: Brand) -> str:
    alert = Safe("")
    if form.error == "invalid":
        alert = _alert(
            "Não foi possível entrar com esses dados",
            "Confira o usuário e a senha e tente de novo. Depois de 5 tentativas, o login fica bloqueado por "
            "15 minutos.",
        )
    elif form.error == "google_unknown":
        email = form.google_email or "Essa conta Google"
        alert = _alert(
            "Conta Google não cadastrada",
            f"{email} não tem conta nesta instalação. Peça a um administrador para cadastrar você com esse e-mail.",
        )
    elif form.error == "google_refused":
        alert = _alert(
            "Não foi possível entrar com essa conta Google",
            "Tente de novo ou entre com o seu usuário e senha.",
        )
    google = Safe("")
    if form.google:
        href = "/oauth2/google/start?" + urlencode({"request": form.request})
        google = join(
            Safe('<div class="divider"><span>ou</span></div>\n<a class="button button-secondary" href="'),
            href,
            Safe('">'),
            _GOOGLE_ICON,
            Safe("<span>Entrar com Google</span></a>\n"),
        )
    body = join(
        _brand(brand),
        Safe('\n<h1>Entrar</h1>\n<p class="lead">Use a conta que a sua equipe criou para você.</p>\n'),
        alert,
        Safe('\n<form method="post" action="/oauth2/login">\n'),
        _hidden("request", form.request),
        _hidden("csrf", form.csrf),
        _field(
            "identifier",
            "Usuário ou e-mail",
            autocomplete="username",
            value=form.identifier,
            placeholder="ana ou ana@exemplo.org",
            autofocus=not form.identifier,
        ),
        _field(
            "password",
            "Senha",
            kind="password",
            autocomplete="current-password",
            placeholder="Sua senha",
            autofocus=bool(form.identifier),
        ),
        Safe('<button type="submit" class="button button-primary">Entrar</button>\n</form>\n'),
        google,
        Safe('<p class="foot">Esqueceu a senha? Peça a um administrador para redefinir.</p>'),
    )
    return _document("Entrar", brand, body)


def password_page(form: PasswordForm, brand: Brand) -> str:
    body = join(
        _brand(brand),
        Safe("\n<h1>Escolha uma nova senha</h1>\n"),
        Safe('<p class="lead">A senha que você recebeu é temporária. Troque-a para continuar.</p>\n'),
        Safe('<form method="post" action="/oauth2/password">\n'),
        _hidden("request", form.request),
        _hidden("csrf", form.csrf),
        _field(
            "new_password",
            "Nova senha",
            kind="password",
            autocomplete="new-password",
            placeholder="De 12 a 128 caracteres",
            hint="Use de 12 a 128 caracteres. Uma frase longa é mais fácil de lembrar.",
            error=form.errors.get("new_password"),
            autofocus=True,
        ),
        _field(
            "confirm",
            "Confirme a nova senha",
            kind="password",
            autocomplete="new-password",
            placeholder="Digite de novo",
            error=form.errors.get("confirm"),
        ),
        Safe('<button type="submit" class="button button-primary">Salvar e continuar</button>\n</form>'),
    )
    return _document("Nova senha", brand, body)


def _detail(label: str, value: str) -> Safe:
    return join(Safe('<div class="row"><dt>'), label, Safe("</dt><dd>"), value, Safe("</dd></div>"))


def _account_details(account: Account) -> Safe:
    groups = ", ".join(sorted(account.groups)) or "Nenhum"
    google = Safe("")
    if account.google_linked:
        google = join(
            Safe('<div class="row row-google">'),
            _GOOGLE_ICON,
            Safe('<div><p class="row-title">Conta Google vinculada</p><p class="row-sub">'),
            account.email,
            Safe("</p></div></div>"),
        )
    return join(
        Safe('<dl class="details">'),
        _detail("Nome", account.name),
        _detail("Usuário", account.username),
        _detail("E-mail", account.email),
        _detail("Grupos", groups),
        google,
        Safe('</dl>\n<p class="note">Nome, e-mail e grupos são mantidos pelos administradores.</p>\n'),
    )


def account_page(page: AccountPage, brand: Brand) -> str:
    header = join(
        Safe('<div class="topbar">'),
        _brand(brand),
        Safe('<a class="link-quiet" href="/oauth2/logout">'),
        _SIGN_OUT_ICON,
        Safe("<span>Sair</span></a></div>\n<h1>Minha conta</h1>\n"),
    )
    status = Safe("")
    if page.message:
        status = join(
            Safe('<div class="alert alert-ok" role="status"><p class="alert-title">'),
            page.message,
            Safe("</p></div>\n"),
        )
    if page.csrf is None:
        form = Safe(
            '<h2>Senha</h2>\n<p class="note">Esta conta entra só com o Google e não tem senha nesta instalação.</p>'
        )
    else:
        form = join(
            Safe('<h2>Trocar senha</h2>\n<form method="post" action="/oauth2/account">\n'),
            _hidden("csrf", page.csrf),
            _field(
                "current_password",
                "Senha atual",
                kind="password",
                autocomplete="current-password",
                placeholder="Sua senha de hoje",
                error=page.errors.get("current_password"),
            ),
            _field(
                "new_password",
                "Nova senha",
                kind="password",
                autocomplete="new-password",
                placeholder="De 12 a 128 caracteres",
                error=page.errors.get("new_password"),
            ),
            _field(
                "confirm",
                "Confirme a nova senha",
                kind="password",
                autocomplete="new-password",
                placeholder="Digite de novo",
                error=page.errors.get("confirm"),
            ),
            Safe('<button type="submit" class="button button-primary">Trocar senha</button>\n</form>\n'),
            Safe('<p class="note">Ao trocar, as suas outras sessões são encerradas. Esta continua aberta.</p>'),
        )
    return _document("Minha conta", brand, join(header, status, _account_details(page.account), form))


def error_page(page: ErrorPage, brand: Brand) -> str:
    body = join(
        _brand(brand),
        Safe("\n<h1>"),
        page.title,
        Safe('</h1>\n<p class="lead">'),
        page.message,
        Safe("</p>"),
    )
    return _document(page.title, brand, body)


def logged_out_page(brand: Brand) -> str:
    body = join(
        _brand(brand),
        Safe('\n<h1>Você saiu</h1>\n<p class="lead">A sua sessão foi encerrada. Pode fechar esta página.</p>'),
    )
    return _document("Você saiu", brand, body)
