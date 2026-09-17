# Contrato — seams Trace Sink e Trace (`ai_core.observability.api`)

Superfície pública do módulo. Mudar qualquer linha daqui é mudar um seam: exige ADR e atualização das specs
consumidoras (004, 005, 006, 008, 011). Só importa stdlib e `ai_core_contracts`.

## Nomes públicos

```python
# Eventos (o que se emite)
ExecutionStarted, ModelCall, ValidationRun, ExecutionError, ExecutionFinished
type TraceEvent = ExecutionStarted | ModelCall | ValidationRun | ExecutionError | ExecutionFinished

# Leitura
TraceRecord, Trace

# Seams
class TraceSink(Protocol): ...
class TraceQuery(Protocol): ...

# Erro
TraceQueryUnavailable          # RuntimeError
```

Campos de cada evento: [data-model.md](../data-model.md). Todos são dataclasses congeladas, `kw_only`, com validação
de campo não vazio na construção.

## Seam Trace Sink (emissão) — consumido por 004, 005, 006

```python
class TraceSink(Protocol):
    def emit(self, event: TraceEvent) -> None:
        """Registra um dado de trace. NUNCA levanta e NUNCA bloqueia perceptivelmente."""
```

Garantias para quem emite:

| Garantia | Detalhe |
|---|---|
| Não levanta | qualquer falha do backend é contada e registrada em log, nunca propagada (FR-011) |
| Não bloqueia | uma serialização e um `write` bufferizado por evento; sem fila, sem rede no adapter da fase |
| Ordem preservada | os registros de uma requisição são lidos na ordem em que foram emitidos |
| Instante é do módulo | o emissor não passa horário; o serviço estampa pelo relógio injetado (ADR-013) |
| Sem credencial | texto livre e mapeamentos passam por redação antes de sair do processo (FR-002) |

Acrescentar um tipo de evento (tool na Fase 3, recuperação na Fase 5) é acrescentar uma dataclass e um membro ao
`TraceEvent` — a assinatura de `emit` não muda, e nenhum emissor existente é afetado.

## Seam Trace (consulta) — consumido por 008 e pelo operador

```python
class TraceQuery(Protocol):
    def trace(self, request_id: str) -> Trace:
        """Eventos da requisição, na ordem de emissão. Levanta TraceQueryUnavailable se o backend não lê."""

    def dropped_events(self) -> int:
        """Quantos eventos foram descartados por falha do backend desde o início do processo (FR-011)."""
```

| Situação | Resposta |
|---|---|
| Requisição com eventos | `Trace(request_id, records)` em ordem |
| Requisição sem eventos | `Trace` com `records` vazio |
| Perfil sem backend de leitura | `TraceQueryUnavailable`, nomeando o backend configurado |

`dropped_events()` é monotônico no processo e é o que a saúde agregada (011 US5) consome.

## O que estes seams NÃO fazem

- Não agregam métricas nem calculam estatística — isso é do harness (US2–US4, Fase 6).
- Não decidem amostragem: todo evento emitido é registrado (amostragem, se um dia fizer sentido, é do adapter).
- Não expõem o formato do backend: quem lê recebe `TraceRecord`, não linhas de arquivo ([research.md](../research.md) R9).
- Não conhecem quem emite: nenhum tipo de 002, 005 ou 006 aparece aqui — assistant, flow, packs, papel e provider
  entram como texto.
