# Contrato — seams Trace Sink e Trace (`ai_core.observability.api`)

Superfície pública do módulo. Mudar qualquer linha daqui é mudar um seam: exige ADR e atualização das specs
consumidoras (004, 005, 006, 008, 011) — **com uma exceção**: acrescentar um tipo de evento, sob as condições do
[ADR-017](../../../docs/adr/ADR-017-trace-sink-cresce-por-eventos-aditivos.md) (nenhum evento ou campo existente muda;
o evento nunca carrega argumentos, conteúdo, prompt ou credencial; a spec emissora declara o toque e atualiza esta
pasta). Só importa stdlib e `ai_core_contracts`.

## Nomes públicos

```python
# Eventos (o que se emite)
ExecutionStarted, ModelCall, ValidationRun, ToolCall, ControllerDecision, CoverageGate, ExecutionError,
ExecutionFinished
DecisionAction                 # Literal["tool", "answer", "invalid", "limit"]
GateRoute                      # Literal["generate", "controller", "fallback"]
type TraceEvent = (ExecutionStarted | ModelCall | ValidationRun | ToolCall | ControllerDecision | CoverageGate
                   | ExecutionError | ExecutionFinished)

# Leitura
TraceRecord, Trace

# Seams
class TraceSink(Protocol): ...
class TraceQuery(Protocol): ...

# Erro
TraceQueryUnavailable          # RuntimeError
```

`ToolCall` foi acrescentado pela 004 na Fase 3 (FR-014 dela), sob o ADR-013, que já previa o trace de chamadas de tool
do gateway: um tipo de evento a mais é aditivo — nenhum emissor muda e o registro continua genérico (`type` derivado do
nome da classe). Campos: `request_id`, `tool`, `kind` (ausente quando a tool não existe), `status`, `duration_ms`,
`size_bytes`, `truncated` — sem argumentos nem conteúdo.

`ControllerDecision` foi acrescentado pela 005 na Fase 3 (FR-016 dela), sob o ADR-017: uma decisão do controller do
flow `agentic` por iteração. Campos: `request_id`, `iteration` (inteiro ≥ 0; 0 só em `limit`), `action` (`tool`,
`answer`, `invalid`, `limit`), `tool` (só em `tool`), `reason` (só em `invalid` e `limit`; em `limit`, `iterations` ou
`context`) — sem argumentos nem saída do modelo.

`CoverageGate` foi acrescentado pela 005 na Fase 5 (FR-007 dela, research R39), sob o ADR-017: a decisão do portão de
cobertura do `rag_first`. Campos: `request_id`, `candidates` e `passages` (inteiros ≥ 0, `passages ≤ candidates`),
`best_score` (ausente exatamente quando `passages == 0`), `threshold` (ausente sem limiar; senão em `[0, 1]`),
`covered` e `route` (`generate`, `controller`, `fallback`; `covered` exatamente quando `generate`) — sem texto nem
identificador de trecho. É o que a 105 lê para calibrar o limiar.

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

## Fase 6 (2026-10-13): `Retrieval`

`Retrieval` e `RetrievedChunk` foram acrescentados pela 005 na Fase 6, sob o ADR-017: por execução com recuperação, os
trechos candidatos, reordenados e entregues à geração — identificador, score e proveniência (documento, versão, status,
seção, página), **nunca o texto**. O harness da 009 os lê pela consulta de trace (research R15).

