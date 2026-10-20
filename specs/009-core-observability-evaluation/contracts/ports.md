# Contrato — portas secundárias do módulo de trace (`axon_ai.observability.ports`)

Três portas. Cada uma tem adapter em memória e suíte de conformidade que roda contra os dois adapters (princípio
XIII). Portas secundárias **não** são seams: são internas do módulo e só a composition root (011) escolhe adapter.

```python
class TraceExporter(Protocol):
    def export(self, record: TraceRecord) -> None:
        """Entrega um registro ao backend. Pode levantar — quem chama trata (FR-011)."""

class TraceReader(Protocol):
    def read(self, request_id: str) -> Sequence[TraceRecord]:
        """Registros da requisição, na ordem de emissão. Vazio quando não há nenhum."""

class Clock(Protocol):
    def now(self) -> datetime:
        """Instante atual, sempre com timezone (ADR-013)."""
```

`TraceReader` é **opcional** no perfil: um backend que só escreve (ferramenta externa) não o fornece, e a consulta
então levanta `TraceQueryUnavailable` ([research.md](../research.md) R5).

## Suíte de conformidade — `TraceExporter` × `TraceReader`

Parametrizada sobre `InMemoryTraceBackend` e `JsonlTraceBackend` (este em `tmp_path`):

| Caso | Esperado |
|---|---|
| Exportar e ler a mesma requisição | os registros voltam iguais aos exportados, na mesma ordem |
| Duas requisições intercaladas | `read` devolve só os registros do identificador pedido |
| Requisição desconhecida | sequência vazia, sem erro |
| Registro com atributos aninhados (mapeamento e lista) | volta com a mesma estrutura e os mesmos tipos JSON |
| `at` com timezone | volta com timezone e no mesmo instante |
| Muitos registros (centenas) | ordem preservada |

Específico do JSONL: o arquivo do dia é criado se não existir; cada registro é uma linha JSON válida; escrever duas
vezes anexa (não sobrescreve); registros de dias diferentes vão para arquivos diferentes e a leitura encontra os dois;
linha corrompida no arquivo é ignorada na leitura, com aviso em log, em vez de derrubar a consulta.

## Suíte de conformidade — `Clock`

| Caso | Esperado |
|---|---|
| `now()` tem timezone | `tzinfo` presente em ambos os adapters |
| Relógio fixo | duas chamadas dão o mesmo instante (torna o trace determinístico em teste) |
| Relógio de sistema | duas chamadas não retrocedem |

## Adapters da Fase 1

| Adapter | Portas | Observação |
|---|---|---|
| `InMemoryTraceBackend` | `TraceExporter`, `TraceReader` | lista por identificador; usada no perfil de teste (011 US3) |
| `JsonlTraceBackend(directory)` | `TraceExporter`, `TraceReader` | `trace-YYYY-MM-DD.jsonl` pela data do registro, `flush` por linha |
| `FixedClock(instant)` | `Clock` | teste e perfil de teste com relógio fixado (011 US3 cenário 2) |
| `SystemClock()` | `Clock` | `datetime.now(UTC)` |

`FailingTraceExporter` (só em teste) levanta em `export` para provar FR-011: a execução segue e o contador de
descartes sobe.

## Fase 9 (2026-10-14)

| Porta | Métodos | Real | Memória / teste | Conformidade |
|---|---|---|---|---|
| `TraceDestination` | `name`, `accepts_content`, `export(record)` (não bloqueia), `flush()` (async), `stats()` | `UsageDestination`, `LangfuseDestination` | destino gravador e destino que falha/trava | falha isolada; fila cheia descarta e conta; conteúdo só onde aceito |
| `UsageStore` | `append(rows)`, `daily(query)`, `previous_total(query)`, `purge(before)` | Postgres `observability.model_calls`/`executions` | listas com a mesma agregação em Python | fuso, origem, agrupamentos |
| `PriceStore` | `all()`, `add(price)`, `effective(provider, model, day)` | Postgres `observability.prices` | lista | vigência |
| `DestinationSettingsStore` | `get()`, `put(settings, expected_version)` | Postgres `observability.destination_settings` | valor | versão |
| `SecretCipher` | `seal`, `open` | AES-GCM + HKDF (`axon-ai/observability/v1`; era `ai-core/…`, ADR-037) | o real com chave fixa | ida e volta; chave errada |
| `LangfuseTransport` | `send(spans)`, `check(host, public, secret)`, `shutdown()` | OTel SDK + OTLP/HTTP (serviço `axon`, R39) | coletor OTLP falso local; transporte que trava | lote; descarta sem bloquear; autenticação |
