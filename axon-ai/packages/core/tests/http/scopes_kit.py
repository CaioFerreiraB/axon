"""Kit dos testes do incremento 9.7 na 008 (US13): a administração com a 003 e a 012 reais, em memória, e uma chave
por escopo. O grupo de administração é o mesmo nos dois módulos (`admin`), como na plataforma montada pela 011.

Os seams que estas rotas não devem alcançar são `Untouchable`: qualquer uso levanta, e a suíte prova que o 404 por
escopo acontece antes de qualquer seam (FR-047).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Final

import httpx
from assistants_testkit import assistant, claims, config
from fastapi.testclient import TestClient
from http_testkit import Platform, bearer
from identity_testkit import harness
from mcp_testkit import build

from axon_ai.http.ports import AdminSeams
from axon_ai.identity.ports import ErasedData

ADMIN: Final = "admin"

USERS_KEY: Final = "axn_00000000000000c3_provisionamento"
"""`svc:provisionamento`, sem grupos, só `users`."""
INFERENCE_KEY: Final = "axn_00000000000000d4_aplicativo"
"""`svc:aplicativo`, sem grupos, só `inference`."""
ADMIN_KEY: Final = "axn_00000000000000e5_administra"
"""`user:root`, do grupo de administração, com `inference` e `admin`."""
GROUP_ONLY_KEY: Final = "axn_00000000000000f6_sogrupo"
"""`user:root`, do grupo de administração, só com `inference` (a que a migração não promoveu; US13 cen. 9)."""
OPERATOR_KEY: Final = "axn_00000000000000a7_operador"
"""`svc:operador`, do grupo de administração, com `admin`: um ator que administra e não tem conta na identidade."""
CONSOLE_ROOT: Final = "tok-console-root"
"""Token da console de `user:root`, do grupo de administração."""

KEYS: Final = (
    (USERS_KEY, "00000000000000c3", "svc:provisionamento", frozenset(), frozenset({"users"})),
    (INFERENCE_KEY, "00000000000000d4", "svc:aplicativo", frozenset(), frozenset({"inference"})),
    (ADMIN_KEY, "00000000000000e5", "user:root", frozenset({ADMIN}), frozenset({"inference", "admin"})),
    (GROUP_ONLY_KEY, "00000000000000f6", "user:root", frozenset({ADMIN}), frozenset({"inference"})),
    (OPERATOR_KEY, "00000000000000a7", "svc:operador", frozenset({ADMIN}), frozenset({"admin"})),
)


@dataclass(frozen=True)
class MountedRoute:
    method: str
    path: str
    endpoint: Any

    @property
    def scopes(self) -> frozenset[str] | None:
        return getattr(self.endpoint, "axon_scopes", None)


def mounted_routes(app: Any, *prefixes: str) -> list[MountedRoute]:
    """As rotas efetivas da app, com o caminho já prefixado. A FastAPI 0.141 guarda o roteador incluído como um
    `_IncludedRouter`, com as rotas em `effective_route_contexts`; rotas de nível de app são `APIRoute`."""
    from fastapi.routing import APIRoute

    found: list[MountedRoute] = []
    for route in app.routes:
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            contexts = contexts()
        entries = (
            [(c.path, c.methods, c.endpoint) for c in contexts]
            if contexts is not None
            else [(route.path, route.methods, route.endpoint)]
            if isinstance(route, APIRoute)
            else []
        )
        for path, methods, endpoint in entries:
            if path.startswith(prefixes) and "{rest:path}" not in path:
                found.extend(MountedRoute(method, path, endpoint) for method in sorted(methods or ()))
    return found


class Untouchable:
    """Um seam que a rota não deve alcançar: qualquer atributo levanta."""

    def __init__(self, name: str) -> None:
        self._name = name

    def __getattr__(self, attribute: str) -> Any:
        raise AssertionError(f"o seam {self._name} foi alcançado ({attribute}) por quem não devia")


class Eraser:
    """Apagador de outro módulo, como a 011 o montaria: falha nas primeiras `fail` chamadas."""

    def __init__(self, name: str, *, fail: int = 0) -> None:
        self.name = name
        self.fail = fail

    async def erase(self, subject: str, *, actor: str, pseudonym: str) -> ErasedData:
        if self.fail > 0:
            self.fail -= 1
            raise RuntimeError("banco fora do ar")
        return ErasedData(counts={"conversations": 1})


@dataclass
class Kit:
    client: TestClient
    platform: Platform
    identity: Any
    responses: list[httpx.Response] = field(default_factory=list)

    def call(self, method: str, path: str, token: str | None, body: Any = None) -> httpx.Response:
        response = self.client.request(method, path, headers=bearer(token) if token else {}, json=body)
        self.responses.append(response)
        return response

    def admin(self, method: str, path: str, token: str | None, body: Any = None) -> httpx.Response:
        return self.call(method, f"/admin/v1{path}", token, body)

    def account(self, username: str) -> Any:
        return asyncio.run(self.identity.service.account(username))


def scopes_kit(*, erasers: tuple[Eraser, ...] = ()) -> Kit:
    identity = harness(erasers=erasers)
    asyncio.run(identity.service.start())
    asyncio.run(identity.add_account("root", name="Root", groups={ADMIN}))
    asyncio.run(identity.add_account("chefe", name="Chefe", groups={ADMIN, "equipe"}))
    asyncio.run(identity.add_account("ana", name="Ana", groups={"equipe"}))

    def admin_seams(platform: Platform) -> AdminSeams:
        return AdminSeams(
            assistants=platform.assistants,
            models=Untouchable("models"),  # type: ignore[arg-type]
            usage=Untouchable("usage"),  # type: ignore[arg-type]
            prices=Untouchable("prices"),  # type: ignore[arg-type]
            destinations=Untouchable("destinations"),  # type: ignore[arg-type]
            accounts=identity.service,
            login=identity.service,
            impact=Untouchable("impact"),  # type: ignore[arg-type]
        )

    platform = Platform(
        config({"geral": assistant(flow="chat")}, admin_group=ADMIN),
        oidc_tokens={CONSOLE_ROOT: claims("root", groups=[ADMIN], aud="axon-admin", ttl=3600)},
        admin_seams=admin_seams,
        extra_keys=KEYS,
        admin_group=ADMIN,
        mcp=build().service,
    )
    return Kit(client=TestClient(platform.app), platform=platform, identity=identity)
