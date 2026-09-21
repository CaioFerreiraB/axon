# Contrato — portas secundárias da 005

Interna do módulo (`ai_core/graph/ports.py`): não é seam e nenhum outro módulo a importa. Quem escolhe o adapter é a
composition root (011).

## `Clock` — data de referência e cronômetro

```python
class Clock(Protocol):
    def now(self) -> datetime: ...        # sempre com timezone
    def monotonic(self) -> float: ...
```

| Método | Para quê | Origem |
|---|---|---|
| `now()` | fixar `reference_time` no início da execução, repetida em toda Turn View | ADR-013, FR-017 |
| `monotonic()` | duração da execução no `ExecutionFinished` | FR-016 |

Existe por não-determinismo: sem ela, `reference_time` viria do relógio do sistema dentro do serviço, e o conjunto
dourado da 105 deixaria de ser reproduzível — que é exatamente o problema que o ADR-013 resolve.

**Adapters** (`adapters/clock.py`): `SystemClock` (`datetime.now(UTC)` e `time.monotonic`) e `FixedClock`, que devolve
uma data fixa e leituras programadas. A 011 injeta o mesmo relógio em todos os módulos com porta de tempo (011 FR-008):
como as portas de 005, 006 e 009 são estruturais, um único adapter com `now()` e `monotonic()` satisfaz as três.

### Conformidade (`tests/graph/contract/test_graph_clock_port.py`)

1. `now()` sempre devolve instante com timezone, nos dois adapters;
2. leituras de `monotonic()` nunca diminuem;
3. no `FixedClock`, `now()` repete a mesma data quantas vezes for chamado — é o que torna `reference_time`
   verificável na suíte;
4. duas execuções com o mesmo `FixedClock` recebem a mesma data de referência (011 US3 cen. 2).

## Porta adiada

`CheckpointStore` está no `design.md` e entra na Fase 3, com o loop: nesta fase nenhuma execução é retomada, e uma
porta sem consumidor contraria o princípio XIII ([research.md](../research.md) R7).
