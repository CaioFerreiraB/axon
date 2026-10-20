"""Seams da spec 009: Trace Sink (emissão) e Trace (consulta).

Contrato em specs/009-core-observability-evaluation/contracts/trace-api.md.

Único módulo da 009 que outros módulos importam. Depende só da stdlib e da API pública de `axon_ai_contracts`: nenhum
tipo de biblioteca de observabilidade aparece aqui (FR-013, research R1). Acrescentar um tipo de evento é acrescentar
uma dataclass e um membro de `TraceEvent` — a assinatura de `emit` não muda.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Final, Literal, Protocol

from axon_ai_contracts import JSONValue


class TraceQueryUnavailable(RuntimeError):
    """O backend configurado não oferece consulta de trace (research R5)."""


def _require_text(field: str, value: str) -> None:
    if not value.strip():
        raise ValueError(f"{field} não pode ser vazio")


def _require_aware(field: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} precisa ter timezone")


def _require_non_negative(field: str, value: float | None) -> None:
    if value is not None and value < 0:
        raise ValueError(f"{field} não pode ser negativo")


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionStarted:
    """Começo de uma execução.

    `reference_time` é a data de referência da execução (ADR-013), não o instante do evento.
    """

    request_id: str
    assistant: str
    flow: str
    packs: tuple[str, ...] = ()
    reference_time: datetime

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("assistant", self.assistant)
        _require_text("flow", self.flow)
        _require_aware("reference_time", self.reference_time)


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelCall:
    """Uma chamada de provider de modelo. `role` é texto: o vocabulário de papéis é da 006.

    `cost_usd` é o custo que o provider **informou** na resposta (o OpenRouter informa), acrescentado sob o ADR-035;
    ausente quando ele não informa — aí o relatório de uso calcula pela tabela de preços.
    """

    request_id: str
    role: str
    provider: str
    model: str
    duration_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    finish_reason: str | None = None
    cost_usd: float | None = None

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("role", self.role)
        _require_text("provider", self.provider)
        _require_text("model", self.model)
        _require_non_negative("duration_ms", self.duration_ms)
        _require_non_negative("input_tokens", self.input_tokens)
        _require_non_negative("output_tokens", self.output_tokens)
        _require_non_negative("cost_usd", self.cost_usd)
        if self.cost_usd is not None and self.cost_usd != self.cost_usd:  # NaN, sem importar `math`
            raise ValueError("cost_usd não pode ser NaN")


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationRun:
    """Execução de um validator de pack."""

    request_id: str
    pack: str
    validator: str
    ok: bool
    issues: tuple[str, ...] = ()
    flags: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("pack", self.pack)
        _require_text("validator", self.validator)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionError:
    """Erro durante a execução. `message` é texto livre — é redigido e truncado na serialização (FR-002)."""

    request_id: str
    stage: str
    kind: str
    message: str

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("stage", self.stage)
        _require_text("kind", self.kind)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutionFinished:
    """Fim de uma execução. `reason` é livre: o vocabulário de desfechos é interno da 005 (research R2)."""

    request_id: str
    ok: bool
    duration_ms: float
    reason: str | None = None

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_non_negative("duration_ms", self.duration_ms)


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolCall:
    """Uma chamada de tool pelo gateway (004 FR-014). Sem argumentos nem conteúdo: o trace não guarda dado de usuário;
    a auditoria guarda os de escrita. `kind` é `None` quando a tool não existe no catálogo."""

    request_id: str
    tool: str
    kind: str | None
    status: str
    duration_ms: float
    size_bytes: int
    truncated: bool = False

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("tool", self.tool)
        _require_text("status", self.status)
        _require_non_negative("duration_ms", self.duration_ms)
        _require_non_negative("size_bytes", self.size_bytes)


type DecisionAction = Literal["tool", "answer", "invalid", "limit"]

_DECISION_ACTIONS: Final[frozenset[str]] = frozenset({"tool", "answer", "invalid", "limit"})
_LIMIT_REASONS: Final[frozenset[str]] = frozenset({"iterations", "context"})


@dataclass(frozen=True, slots=True, kw_only=True)
class ControllerDecision:
    """Uma decisão do controller no loop `agentic` (005 FR-016), acrescentada sob o ADR-017.

    Nunca leva argumentos de tool nem saída do modelo: só a iteração, a ação, o nome pedido (em `tool`) e um motivo
    curto escrito pelo motor (em `invalid` e `limit`). `iteration` 0 só existe em `limit`, quando o teto de contexto
    impede até a primeira chamada.
    """

    request_id: str
    iteration: int
    action: DecisionAction
    tool: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        if self.action not in _DECISION_ACTIONS:
            raise ValueError(f"ação desconhecida: {self.action!r}")
        if isinstance(self.iteration, bool) or not isinstance(self.iteration, int) or self.iteration < 0:
            raise ValueError(f"iteration precisa ser inteiro não negativo: {self.iteration!r}")
        if self.iteration == 0 and self.action != "limit":
            raise ValueError("iteration 0 só existe na ação limit")
        if (self.action == "tool") != (self.tool is not None):
            raise ValueError("tool é obrigatório na ação tool e ausente nas outras")
        if self.tool is not None:
            _require_text("tool", self.tool)
        if (self.action in ("invalid", "limit")) != (self.reason is not None):
            raise ValueError("reason é obrigatório nas ações invalid e limit e ausente nas outras")
        if self.reason is not None:
            _require_text("reason", self.reason)
        if self.action == "limit" and self.reason not in _LIMIT_REASONS:
            raise ValueError(f"motivo de limite desconhecido: {self.reason!r}")


type GateRoute = Literal["generate", "controller", "fallback"]

_GATE_ROUTES: Final[frozenset[str]] = frozenset({"generate", "controller", "fallback"})


def _require_count(field: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} precisa ser inteiro não negativo: {value!r}")


@dataclass(frozen=True, slots=True, kw_only=True)
class CoverageGate:
    """A decisão do portão de cobertura do `rag_first` (005 FR-007, research R39), acrescentada sob o ADR-017.

    Sem texto nem identificador de trecho: as contagens de candidatos e de trechos, o melhor score dos trechos, o
    limiar do operador (`None` = sem limiar), se cobriu e a rota — `generate` (com os trechos), `controller` (escalada
    para o loop) ou `fallback` (geração sem trechos). É o que a 105 lê para calibrar o limiar.
    """

    request_id: str
    candidates: int
    passages: int
    best_score: float | None
    threshold: float | None
    covered: bool
    route: GateRoute

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_count("candidates", self.candidates)
        _require_count("passages", self.passages)
        if self.passages > self.candidates:
            raise ValueError(f"passages ({self.passages}) maior que candidates ({self.candidates})")
        if (self.best_score is None) != (self.passages == 0):
            raise ValueError("best_score existe exatamente quando há trechos")
        if self.best_score is not None and self.best_score != self.best_score:  # NaN, sem importar `math`
            raise ValueError("best_score não pode ser NaN")
        if self.threshold is not None and not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"threshold fora de [0, 1]: {self.threshold!r}")
        if self.route not in _GATE_ROUTES:
            raise ValueError(f"rota desconhecida: {self.route!r}")
        if self.covered != (self.route == "generate"):
            raise ValueError("covered vale exatamente quando a rota é generate")


@dataclass(frozen=True, slots=True, kw_only=True)
class RetrievedChunk:
    """Um trecho num evento `Retrieval`: identificador, score e a proveniência do `Chunk` (001). `text` só nos
    entregues à geração — o que o modelo viu, para o juiz da avaliação —, cortado e redigido na serialização."""

    chunk_id: str
    score: float
    document: str
    version: str | None = None
    status: str | None = None
    section: str | None = None
    page: int | None = None
    text: str | None = None

    def __post_init__(self) -> None:
        _require_text("chunk_id", self.chunk_id)
        _require_text("document", self.document)
        if isinstance(self.score, bool) or not isinstance(self.score, int | float):
            raise TypeError(f"score precisa ser número: {self.score!r}")
        if self.score != self.score:  # NaN, sem importar `math`
            raise ValueError("score não pode ser NaN")
        if self.page is not None and self.page < 1:
            raise ValueError("page precisa ser >= 1")


@dataclass(frozen=True, slots=True, kw_only=True)
class Retrieval:
    """Os trechos de uma execução (009 Fase 6, research R15), acrescentado sob o ADR-017: candidatos (`retrieved`),
    reordenados (`reranked`) e entregues à geração (`delivered`), como a Turn View os projeta. Emitido pela 005 na
    validação; é o que o harness de avaliação lê para medir recuperação e rerank. Só os entregues levam texto."""

    request_id: str
    retrieved: tuple[RetrievedChunk, ...] = ()
    reranked: tuple[RetrievedChunk, ...] = ()
    delivered: tuple[RetrievedChunk, ...] = ()

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        for name in ("retrieved", "reranked", "delivered"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if any(chunk.text is not None for chunk in (*self.retrieved, *self.reranked)):
            raise ValueError("só os trechos entregues levam texto")


type ExchangeRole = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True, slots=True, kw_only=True)
class ExchangeMessage:
    """Uma mensagem enviada ao modelo: papel e texto. Partes não textuais chegam como marcador (research R35)."""

    role: ExchangeRole
    content: str


@dataclass(frozen=True, slots=True, kw_only=True)
class ModelExchange:
    """O texto de uma chamada de modelo — as mensagens enviadas e a saída —, emitido pela 006 logo depois do `ModelCall`
    (ADR-034, research R29). É o único evento com texto de prompt e resposta: o `TraceService` o descarta com a captura
    desligada e, ligada, o entrega só a destinos que aceitam conteúdo, redigido e cortado. O primário nunca o recebe."""

    request_id: str
    role: str
    provider: str
    model: str
    messages: tuple[ExchangeMessage, ...] = ()
    output: str = ""

    def __post_init__(self) -> None:
        _require_text("request_id", self.request_id)
        _require_text("role", self.role)
        _require_text("provider", self.provider)
        _require_text("model", self.model)
        object.__setattr__(self, "messages", tuple(self.messages))


type TraceEvent = (
    ExecutionStarted
    | ModelCall
    | ModelExchange
    | ValidationRun
    | ToolCall
    | ControllerDecision
    | CoverageGate
    | Retrieval
    | ExecutionError
    | ExecutionFinished
)
"""Dados de trace que os emissores mandam. Tipo novo entra aqui sem mudar o seam."""


@dataclass(frozen=True, slots=True, kw_only=True)
class TraceRecord:
    """Um registro de trace, como o backend guarda e a consulta devolve (contracts/record-format.md)."""

    at: datetime
    type: str
    request_id: str
    attributes: Mapping[str, JSONValue]


@dataclass(frozen=True, slots=True, kw_only=True)
class Trace:
    """Os registros de uma requisição, na ordem de emissão."""

    request_id: str
    records: tuple[TraceRecord, ...] = ()


class TraceSink(Protocol):
    """Porta de emissão (ADR-013), consumida por 004, 005 e 006."""

    def emit(self, event: TraceEvent) -> None:
        """Registra um dado de trace. NUNCA levanta e NUNCA bloqueia perceptivelmente (FR-011)."""
        ...


class TraceQuery(Protocol):
    """Consulta de trace por requisição, consumida pela 008 e pelo operador."""

    def trace(self, request_id: str) -> Trace:
        """Eventos da requisição, em ordem. Levanta `TraceQueryUnavailable` se o backend não lê."""
        ...

    def dropped_events(self) -> int:
        """Eventos descartados por falha do backend desde o início do processo (FR-011)."""
        ...


# ---------------------------------------------------------------------------------------------------------------------
# Fase 9 (ADR-034; research R28 a R35): uso e custo, preços e destinos do trace
# ---------------------------------------------------------------------------------------------------------------------

type UsageGrouping = Literal["model", "assistant"]
type UsageOrigin = Literal["production", "evaluation", "all"]
type SettingSource = Literal["installation", "runtime", "default"]
type PriceState = Literal["current", "superseded", "scheduled"]
type DestinationState = Literal["ok", "degraded", "off"]

MAX_REPORT_DAYS: Final = 366
PRICE_SCALE: Final = 6
"""Casas decimais dos preços (USD por milhão de tokens) e dos custos antes da apresentação (R31)."""


class InvalidQuery(ValueError):
    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class InvalidPrice(ValueError):
    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class InvalidField(ValueError):
    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class InstallationDefined(ValueError):
    """Ajuste definido pela instalação (variável de ambiente): a administração só o lê (ADR-033)."""

    def __init__(self, message: str, *, field: str) -> None:
        super().__init__(message)
        self.field = field


class MasterKeyMissing(RuntimeError):
    """Sem `AI_CORE_MASTER_KEY`, o segredo do Langfuse não pode ser gravado (ADR-033)."""


class Conflict(RuntimeError):
    """Ajustes gravados sobre uma versão desatualizada; `current_version` é a guardada."""

    def __init__(self, message: str, *, current_version: int | None = None) -> None:
        super().__init__(message)
        self.current_version = current_version


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageQuery:
    """Período em dias locais (inclusivos) no fuso `tz`, agrupado por modelo ou por Assistant, de uma origem."""

    start: date
    end: date
    tz: str = "UTC"
    by: UsageGrouping = "model"
    origin: UsageOrigin = "production"

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise InvalidQuery("o início do período é depois do fim", field="start")
        if (self.end - self.start).days + 1 > MAX_REPORT_DAYS:
            raise InvalidQuery(f"o período passa de {MAX_REPORT_DAYS} dias", field="end")
        if self.by not in ("model", "assistant"):
            raise InvalidQuery(f"agrupamento desconhecido: {self.by!r}", field="by")
        if self.origin not in ("production", "evaluation", "all"):
            raise InvalidQuery(f"origem desconhecida: {self.origin!r}", field="origin")
        if not self.tz.strip():
            raise InvalidQuery("fuso vazio", field="tz")

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageRow:
    """Uso de uma chave num dia ou no período. `key` = `provider/model` ou o Assistant; `None` = fora de Assistant.
    `cost` ausente quando falta preço vigente em algum dia da linha (`priced` falso)."""

    key: str | None
    calls: int = 0
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost: Decimal | None = None
    priced: bool = True


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageDay:
    day: date
    rows: tuple[UsageRow, ...] = ()
    requests: int = 0
    """Requisições distintas do dia (ADR-036): somar as linhas por modelo contaria duas vezes a que usa dois."""


@dataclass(frozen=True, slots=True, kw_only=True)
class UsageReport:
    query: UsageQuery
    days: tuple[UsageDay, ...] = ()
    totals: tuple[UsageRow, ...] = ()
    total_cost: Decimal | None = None
    requests: int = 0
    """Requisições distintas que chamaram algum modelo no período (somar por modelo contaria duas vezes)."""
    incomplete: bool = False
    """Algum modelo usado no período não tinha preço vigente: o custo total é parcial."""
    previous_total_cost: Decimal | None = None
    """Custo do período de mesmo tamanho imediatamente anterior, para a comparação."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Price:
    """USD por milhão de tokens de entrada e de saída, vigente a partir de `effective_from` (R31)."""

    provider: str
    model: str
    usd_per_mtok_in: Decimal
    usd_per_mtok_out: Decimal
    effective_from: date
    created_by: str
    created_at: datetime
    state: PriceState = "current"


@dataclass(frozen=True, slots=True, kw_only=True)
class DestinationSettingsView:
    """Os ajustes dos destinos com a origem de cada campo (ADR-033). Nunca traz o segredo do Langfuse."""

    langfuse_enabled: bool = False
    langfuse_host: str | None = None
    langfuse_public_key: str | None = None
    langfuse_secret_set: bool = False
    capture_content: bool = False
    sources: Mapping[str, SettingSource] = field(default_factory=dict)
    version: int = 0


@dataclass(frozen=True, slots=True, kw_only=True)
class DestinationHealth:
    name: str
    state: DestinationState
    dropped_24h: int = 0
    last_error: str | None = None
    last_sent_at: datetime | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class ConnectionCheck:
    ok: bool
    detail: str


class UsageReportSeam(Protocol):
    """Relatório de uso e custo — consumido pela 008 (superfície de administração)."""

    async def report(self, query: UsageQuery) -> UsageReport: ...


class PriceBook(Protocol):
    """Tabela de preços com vigência — consumida pela 008."""

    async def prices(self) -> tuple[Price, ...]: ...

    async def add_price(
        self,
        *,
        provider: str,
        model: str,
        usd_per_mtok_in: Decimal,
        usd_per_mtok_out: Decimal,
        effective_from: date,
        actor: str,
    ) -> Price: ...

    async def unpriced_models(self, *, start: date, end: date) -> tuple[str, ...]:
        """Modelos usados no período sem preço vigente em algum dia dele."""
        ...


class TraceDestinations(Protocol):
    """Ajustes do Langfuse e da captura de conteúdo, e a saúde dos destinos — consumido pela 008 e pela 011."""

    async def settings(self) -> DestinationSettingsView: ...

    async def set_langfuse(
        self,
        *,
        enabled: bool | None = None,
        host: str | None = None,
        public_key: str | None = None,
        secret_key: str | None = None,
        actor: str,
        version: int,
    ) -> DestinationSettingsView: ...

    async def set_capture(self, *, enabled: bool, actor: str, version: int) -> DestinationSettingsView: ...

    async def test_langfuse(
        self, *, host: str | None = None, public_key: str | None = None, secret_key: str | None = None
    ) -> ConnectionCheck: ...

    def health(self) -> tuple[DestinationHealth, ...]: ...
