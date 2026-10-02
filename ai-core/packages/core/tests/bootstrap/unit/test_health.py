"""T029 — saúde agregada (contracts/health.md; research R16; clarificação 2), com checagens falsas."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest

from ai_core.assistants.api import AssistantStatus, ValidationReport
from ai_core.bootstrap.health import PlatformHealth
from ai_core.bootstrap.lifecycle import BootReport, StageOutcome, StageStatus
from ai_core.llm.api import ModelHealth, ModelPolicy, ModelRef
from ai_core.mcp.api import McpServer, SecurityPolicy, ServerHealth
from ai_core.packs.api import PackEntry, PackStatus

QWEN = ModelRef(provider="ollama", model="qwen3:1.7b")
LLAMA = ModelRef(provider="ollama", model="llama3:8b")


def pack(name: str, status: PackStatus = PackStatus.ENABLED, error: str | None = None) -> PackEntry:
    return PackEntry(name=name, version="0.1.0", contract_version="0.1", origin="code", status=status, error=error)


class Ticks:
    """Cronômetro controlado: a suíte decide quando o cache vence."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Routing:
    def __init__(self, *, down: Sequence[ModelRef] = (), slow: Sequence[ModelRef] = ()) -> None:
        self.down = set(map(str, down))
        self.slow = set(map(str, slow))
        self.calls = 0

    async def check(self, policy: ModelPolicy) -> tuple[ModelHealth, ...]:
        self.calls += 1
        results = []
        for role, ref in policy.roles.items():
            if str(ref) in self.slow:
                await asyncio.sleep(10)
            available = str(ref) not in self.down
            detail = None if available else "fora do ar: conexão recusada"
            results.append(ModelHealth(role=role, ref=ref, available=available, detail=detail))
        return tuple(results)


class Packs:
    def __init__(self, *entries: PackEntry) -> None:
        self._entries = entries

    def entries(self) -> Sequence[PackEntry]:
        return self._entries


class Assistants:
    def __init__(self, *statuses: AssistantStatus) -> None:
        self._report = ValidationReport(statuses=statuses)

    async def validate(self) -> ValidationReport:
        return self._report


class Database:
    def __init__(self, *, fails: bool = False, slow: bool = False) -> None:
        self.fails = fails
        self.slow = slow

    async def __call__(self) -> None:
        if self.slow:
            await asyncio.sleep(10)
        if self.fails:
            raise RuntimeError("porta 'database' (adapter Postgres): conexão recusada")


def boot(*outcomes: StageOutcome) -> BootReport:
    return BootReport(stages=outcomes or (StageOutcome(name="configuration", status=StageStatus.OK),))


def health(
    *,
    routing: Routing | None = None,
    database: Database | None = None,
    packs: Packs | None = None,
    assistants: Assistants | None = None,
    report: BootReport | None = None,
    ticks: Ticks | None = None,
    mcp: object | None = None,
) -> PlatformHealth:
    provider = PlatformHealth(
        mcp=mcp,  # type: ignore[arg-type]
        database=database,
        packs=packs or Packs(pack("generic")),
        assistants=assistants or Assistants(AssistantStatus(name="geral", origin="system", available=True)),
        routing=routing or Routing(),
        models=(QWEN, LLAMA),
        timeout=0.05,
        monotonic=ticks or Ticks(),
    )
    provider.report = report or boot()
    return provider


def by_name(report: object) -> dict[str, object]:
    return {item.name: item for item in report.items}  # type: ignore[attr-defined]


async def test_provider_fora_do_ar_degrada_nomeando_o_modelo_e_os_demais_saudaveis() -> None:
    """US5 cen. 1."""
    report = await health(routing=Routing(down=[QWEN])).health()

    assert report.status == "degraded"
    items = by_name(report)
    qwen = items["model:ollama/qwen3:1.7b"]
    assert not qwen.ok and not qwen.critical and "fora do ar" in qwen.detail  # type: ignore[attr-defined]
    for name in ("model:ollama/llama3:8b", "pack:generic", "assistant:geral", "boot:configuration"):
        assert items[name].ok, name  # type: ignore[attr-defined]


async def test_tudo_bem_e_ok() -> None:
    """US5 cen. 2."""
    report = await health(database=Database()).health()
    assert report.status == "ok"
    assert by_name(report)["database"].critical  # type: ignore[attr-defined]


async def test_banco_inacessivel_e_down() -> None:
    """US5 cen. 3: o armazenamento persistente é item crítico."""
    report = await health(database=Database(fails=True)).health()

    assert report.status == "down"
    database = by_name(report)["database"]
    assert not database.ok and database.critical  # type: ignore[attr-defined]
    assert "Postgres" in database.detail  # type: ignore[attr-defined]


async def test_sem_banco_nao_ha_item_de_banco() -> None:
    assert "database" not in by_name(await health().health())


async def test_checagem_lenta_vira_item_nao_saudavel_no_timeout() -> None:
    report = await health(routing=Routing(slow=[LLAMA]), database=Database(slow=True)).health()

    items = by_name(report)
    assert not items["model:ollama/llama3:8b"].ok  # type: ignore[attr-defined]
    assert "sem resposta" in items["model:ollama/llama3:8b"].detail  # type: ignore[attr-defined]
    assert items["model:ollama/qwen3:1.7b"].ok, "uma checagem lenta não atrasa nem derruba as outras"  # type: ignore[attr-defined]
    assert not items["database"].ok and report.status == "down"  # type: ignore[attr-defined]


async def test_segunda_consulta_dentro_da_janela_nao_repete_as_checagens() -> None:
    ticks = Ticks()
    routing = Routing()
    provider = health(routing=routing, ticks=ticks)

    await provider.health()
    calls = routing.calls
    ticks.now = 14.9
    await provider.health()
    assert routing.calls == calls, "dentro de 15 s, o resultado vem do cache"
    ticks.now = 15.1
    await provider.health()
    assert routing.calls == 2 * calls


async def test_pack_em_erro_e_assistant_indisponivel_degradam_sem_derrubar() -> None:
    provider = health(
        packs=Packs(
            pack("generic"),
            pack("quebrado", PackStatus.ERROR, "contrato incompatível"),
        ),
        assistants=Assistants(
            AssistantStatus(name="geral", origin="system", available=True),
            AssistantStatus(name="orfao", origin="system", available=False, reasons=("packs: 'quebrado' em erro",)),
        ),
        report=boot(
            StageOutcome(name="packs", status=StageStatus.DEGRADED, detail="pack 'quebrado': contrato incompatível"),
        ),
    )
    report = await provider.health()

    assert report.status == "degraded"
    items = by_name(report)
    assert items["pack:quebrado"].detail == "contrato incompatível"  # type: ignore[attr-defined]
    assert not items["assistant:orfao"].ok and "quebrado" in items["assistant:orfao"].detail  # type: ignore[attr-defined]
    assert not items["boot:packs"].ok  # type: ignore[attr-defined]


async def test_assistants_de_usuario_nao_aparecem() -> None:
    """A saúde responde a qualquer chave: nomes de Assistants privados de usuários não podem vazar por ela."""
    provider = health(
        assistants=Assistants(
            AssistantStatus(name="geral", origin="system", available=True),
            AssistantStatus(name="~segredo", origin="user", available=False, reasons=("x",), owner="user:ana"),
        )
    )
    report = await provider.health()
    assert not any("segredo" in item.name for item in report.items)
    assert report.status == "ok"


async def test_etapa_critica_que_falhou_e_down() -> None:
    report = await health(
        report=boot(StageOutcome(name="adapters", status=StageStatus.FAILED, detail="porta 'database'"))
    ).health()
    assert report.status == "down"


async def test_antes_do_relatorio_de_boot_a_saude_diz_que_o_boot_esta_em_andamento() -> None:
    provider = health()
    provider.report = None
    report = await provider.health()
    assert report.status == "down"
    assert by_name(report)["boot"].detail == "boot em andamento"  # type: ignore[attr-defined]


# --- Fase 3 (T046; contracts/health.md, "Fase 3"; clarificação 1): servidores MCP globais -----------------------------


class Registry:
    """Registry falso da 007: `globals()` e `check(alias)` programados; conta as checagens."""

    def __init__(
        self,
        *aliases: str,
        down: Sequence[str] = (),
        missing: dict[str, tuple[str, ...]] | None = None,
        slow: Sequence[str] = (),
        lists: bool = True,
    ) -> None:
        self.aliases = aliases
        self.down = set(down)
        self.missing = missing or {}
        self.slow = set(slow)
        self.lists = lists
        self.checks = 0

    async def globals(self) -> Sequence[McpServer]:
        if not self.lists:
            raise RuntimeError("armazenamento do registry indisponível")
        return tuple(
            McpServer(alias=alias, scope="global", owner=None, transport="http", endpoint=f"https://{alias}.test/mcp",
                      policy=SecurityPolicy(allowed_tools=("eco",)), origin="file")
            for alias in self.aliases
        )

    async def check(self, alias: str, *, owner: str | None = None) -> ServerHealth:
        self.checks += 1
        if alias in self.slow:
            await asyncio.sleep(10)
        if alias in self.down:
            return ServerHealth(alias=alias, ok=False, detail="sem resposta: conexão recusada")
        missing = self.missing.get(alias, ())
        return ServerHealth(alias=alias, ok=not missing, tools=("eco",), missing=missing)


@pytest.mark.us5
async def test_servidor_mcp_fora_do_ar_degrada_sem_derrubar() -> None:
    report = await health(mcp=Registry("demo", "crm", down=["crm"])).health()
    assert report.status == "degraded"
    items = by_name(report)
    crm = items["mcp:crm"]
    assert not crm.ok and not crm.critical and "conexão recusada" in crm.detail  # type: ignore[attr-defined]
    assert items["mcp:demo"].ok  # type: ignore[attr-defined]


@pytest.mark.us5
async def test_tool_da_allowlist_que_o_servidor_nao_anuncia_e_nomeada() -> None:
    report = await health(mcp=Registry("demo", missing={"demo": ("apagar",)})).health()
    demo = by_name(report)["mcp:demo"]
    assert not demo.ok and "apagar" in demo.detail  # type: ignore[attr-defined]


@pytest.mark.us5
async def test_registry_que_nao_lista_vira_item_mcp_nao_critico() -> None:
    report = await health(mcp=Registry(lists=False)).health()
    item = by_name(report)["mcp"]
    assert not item.ok and not item.critical and "indisponível" in item.detail  # type: ignore[attr-defined]
    assert report.status == "degraded"


@pytest.mark.us5
async def test_servidor_lento_passa_do_prazo() -> None:
    report = await health(mcp=Registry("lento", slow=["lento"])).health()
    assert "sem resposta em" in by_name(report)["mcp:lento"].detail  # type: ignore[attr-defined]


@pytest.mark.us5
async def test_consulta_dentro_da_janela_nao_repete_as_checagens() -> None:
    ticks = Ticks()
    registry = Registry("demo")
    provider = health(mcp=registry, ticks=ticks)
    await provider.health()
    ticks.now = 5.0
    await provider.health()
    assert registry.checks == 1


@pytest.mark.us5
async def test_sem_registry_nao_ha_item_de_mcp() -> None:
    report = await health().health()
    assert not [name for name in by_name(report) if name.startswith("mcp")]

