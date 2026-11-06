# Contrato — seams de uso, preços e destinos (Fase 9)

Em `axon_ai/observability/api.py`. Consumidos pela 008 (superfície de administração), que traduz HTTP e decide quem é
admin — estes seams não conhecem Principal (ADR-031). Value objects em [data-model.md](../data-model.md) (Fase 9).

```python
class UsageReportSeam(Protocol):
    async def report(self, query: UsageQuery) -> UsageReport: ...

class PriceBook(Protocol):
    async def prices(self) -> tuple[Price, ...]: ...
    async def add_price(self, *, provider: str, model: str, usd_per_mtok_in: Decimal, usd_per_mtok_out: Decimal,
                        effective_from: date, actor: str) -> Price: ...
    async def unpriced_models(self, *, start: date, end: date) -> tuple[str, ...]: ...   # usados sem preço vigente

class TraceDestinations(Protocol):
    async def settings(self) -> DestinationSettingsView: ...
    async def set_langfuse(self, *, enabled: bool | None = None, host: str | None = None,
                           public_key: str | None = None, secret_key: str | None = None,
                           actor: str, version: int) -> DestinationSettingsView: ...
    async def set_capture(self, *, enabled: bool, actor: str, version: int) -> DestinationSettingsView: ...
    async def test_langfuse(self, *, host: str | None = None, public_key: str | None = None,
                            secret_key: str | None = None) -> ConnectionCheck: ...
    def health(self) -> tuple[DestinationHealth, ...]: ...
```

| Situação | Resultado |
|---|---|
| `query.start > query.end`, período > 366 dias, fuso desconhecido | `InvalidQuery(field)` |
| campo definido pela instalação | `InstallationDefined(field)` |
| `secret_key` sem chave mestra | `MasterKeyMissing` (os demais campos do mesmo pedido não gravam) |
| `version` desatualizada | `Conflict` |
| `host` não `https` (exceto `localhost`/nome sem ponto) | `InvalidField("host")` |
| preço negativo ou com mais de 6 casas | `InvalidPrice(field)` |
| `test_langfuse` sem argumentos | usa os ajustes efetivos; nunca devolve o segredo |

Ligar a captura de conteúdo é ação do seam; a confirmação do aviso de privacidade é da interface (013) e da 008, que
exige um campo `acknowledged: true` no pedido.

## Conformidade (`tests/observability/contract/`)

`test_usage_report.py` (dias no fuso, agrupamentos, origem, sem preço, incompleto, período anterior — SC-005),
`test_price_book.py` (vigência; preço no passado recalcula), `test_trace_destinations.py` (precedência, segredo só de
escrita, conflito, `MasterKeyMissing`, `reload`).

## Passada de 2026-11-03: Impact Report (US9; ADR-056)

```python
class ImpactReportSeam(Protocol):
    async def report(self, query: ImpactQuery) -> ImpactReport: ...
```

| Situação | Resultado |
|---|---|
| `start > end`; grão, agrupamento, origem ou fuso desconhecidos | `InvalidQuery(field)` |
| grão `day` com mais de 366 dias | `InvalidQuery("grain")` |
| início antes da retenção (outros grãos) | relatório com `clipped_start` = o primeiro dia guardado |
| estimativa desligada pela instalação | `ImpactReport(enabled=False)`, sem baldes nem totais |
| nenhuma chamada no período | `enabled=True`, baldes com zeros, `totals` com cobertura `calls=0` |

Os baldes cobrem do que contém `start` ao que contém `end`, recortados ao período; `previous` usa o mesmo número de
dias imediatamente antes. As linhas (`rows`) são do período inteiro; `buckets[i].rows`, do balde.

### Conformidade

`test_impact_report.py` (memória × Postgres): os cinco grãos com semana ISO e semestre, fuso local, origem, as duas
chaves, cobertura, respostas estimadas, período anterior, recorte da retenção, desligado; totais iguais à soma das
estimativas gravadas (SC-010).

## `ObservabilityErasure` — pseudônimo nos autores (incremento 9.7, US10; ADR-059; research R53)

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class ObservabilityErasureReport:
    prices: int = 0
    destination_settings: int = 0

class ObservabilityErasure(Protocol):                 # consumido pela 011
    async def erase_subject(self, subject: str, *, pseudonym: str) -> ObservabilityErasureReport: ...
```

| Regra | Origem | Verificada por |
|---|---|---|
| Só `created_by` dos preços e `updated_by` dos ajustes mudam; valores, vigência, instantes e versão ficam | FR-031 | `test_observability_erasure.py`, `test_settings_store.py`/`test_price_store.py` (memória × Postgres) |
| Idempotente; outros autores intactos | FR-031 | idem |
| Subject ou pseudônimo fora do formato → `InvalidField` nomeando o campo, sem tocar os dados | FR-032 | `test_observability_erasure.py` |
| Nenhuma linha do schema `observability` cita o subject | SC-012 | `test_observability_erasure.py` (Postgres) |

