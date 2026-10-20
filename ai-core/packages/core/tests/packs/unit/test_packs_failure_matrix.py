"""Falha fechada: cada defeito injetado deixa só o pack defeituoso em erro (US2, SC-002, quickstart §4; T018)."""

from __future__ import annotations

import logging
from typing import Any, NoReturn

import pytest
from packs_testkit import GOOD_CONFIG, make_good_pack, make_pack_class

from ai_core.packs.adapters.memory import InMemoryPackConfigSource, InMemoryPackSource
from ai_core.packs.api import PackStatus
from ai_core.packs.ports import DiscoveredPack, PackSettings
from ai_core.packs.service import PackRuntime
from axon_ai_contracts import PackContext, PackManifest, ToolInvocation, ToolSpec
from axon_ai_contracts import __version__ as contracts_version


def _boom(*args: Any) -> NoReturn:
    raise RuntimeError("boom")


async def _handler(invocation: ToolInvocation) -> object:
    return None


def _duplicated_tools(self: Any, ctx: PackContext) -> tuple[ToolSpec, ...]:
    spec = ToolSpec(name="echo", description="d", parameters={"type": "object"}, kind="native", handler=_handler)
    return (spec, spec)


def _entry(name: str, load: Any, distribution: str | None = None) -> DiscoveredPack:
    return DiscoveredPack(name=name, distribution=distribution or f"dist-{name}", version="0.1.0", load=load)


def _run(extra: list[DiscoveredPack], enabled: list[str]) -> PackRuntime:
    good = make_good_pack()
    entries = [_entry("good", lambda: good), *extra]
    settings = {"good": PackSettings(enabled=True, config=GOOD_CONFIG)}
    settings.update({name: PackSettings(enabled=True) for name in enabled})
    runtime = PackRuntime(InMemoryPackSource(entries), InMemoryPackConfigSource(settings))
    runtime.load()
    good_entry = runtime.entry("good")
    assert good_entry is not None and good_entry.status is PackStatus.ENABLED
    return runtime


def _single(name: str, cls: Any) -> list[DiscoveredPack]:
    return [_entry(name, lambda: cls)]


CASES = [
    (
        "incompativel",
        _single("incompativel", make_pack_class("incompativel", "0.3")),
        f"requer axon-ai-contracts>=0.3, instalado {contracts_version}",
    ),
    (
        "manifesto",
        _single("manifesto", make_pack_class("manifesto", manifest=PackManifest(name="outro", version="0.1.0"))),
        "manifest inválido:",
    ),
    (
        "construtor",
        _single("construtor", make_pack_class("construtor", init=_boom)),
        "falha ao instanciar: RuntimeError: boom",
    ),
    ("tools", _single("tools", make_pack_class("tools", tools=_boom)), "hook tools levantou RuntimeError: boom"),
    (
        "declaracao",
        _single("declaracao", make_pack_class("declaracao", tools=_duplicated_tools)),
        "declaração inválida:",
    ),
    ("importacao", [_entry("importacao", _boom)], "falha ao importar: RuntimeError: boom"),
    (
        "apelido",
        _single("apelido", make_pack_class("real")),
        "entry point 'apelido' aponta para classe com name 'real'",
    ),
]


@pytest.mark.parametrize(("name", "extra", "prefix"), CASES, ids=[case[0] for case in CASES])
def test_defect_leaves_only_that_pack_in_error(
    name: str, extra: list[DiscoveredPack], prefix: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="ai_core.packs"):
        runtime = _run(extra, enabled=[name])
    entry = runtime.entry(name)
    assert entry is not None and entry.status is PackStatus.ERROR
    assert entry.error is not None and entry.error.startswith(prefix), entry.error
    assert any(name in record.getMessage() for record in caplog.records)


def test_duplicate_names_put_every_copy_in_error() -> None:
    one, other = make_pack_class("dup"), make_pack_class("dup")
    runtime = _run([_entry("dup", lambda: one, "dist-a"), _entry("dup", lambda: other, "dist-b")], enabled=["dup"])
    entry = runtime.entry("dup")
    assert entry is not None and entry.status is PackStatus.ERROR
    assert entry.error == "nome duplicado: 'dup' registrado por dist-a, dist-b"
    assert one.created == 0 and other.created == 0


def test_dependency_on_disabled_pack() -> None:
    dependent = make_pack_class("dependente", depends_on=("desligado",))
    extra = [_entry("dependente", lambda: dependent), _entry("desligado", lambda: make_pack_class("desligado"))]
    runtime = _run(extra, enabled=["dependente"])
    entry = runtime.entry("dependente")
    assert entry is not None and entry.error == "depende de 'desligado', que está desabilitado"


def test_dependency_cycle() -> None:
    a, b = make_pack_class("a", depends_on=("b",)), make_pack_class("b", depends_on=("a",))
    runtime = _run([_entry("a", lambda: a), _entry("b", lambda: b)], enabled=["a", "b"])
    entry_a, entry_b = runtime.entry("a"), runtime.entry("b")
    assert entry_a is not None and entry_a.error == "dependência circular: a → b → a"
    assert entry_b is not None and entry_b.error == "dependência circular: b → a → b"


def test_configured_but_not_installed() -> None:
    runtime = _run([], enabled=["fantasma"])
    entry = runtime.entry("fantasma")
    assert entry is not None and entry.status is PackStatus.ERROR and entry.error == "não instalado"
    assert (entry.version, entry.contract_version) == (None, None)
