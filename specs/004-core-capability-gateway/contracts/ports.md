# Contrato — portas secundárias da 004 (`ai_core.capabilities.ports`)

| Porta | Motivo | Em memória | Real | Conformidade |
|---|---|---|---|---|
| `AuditLog` | banco | lista de registros | `audit_postgres.py`, schema `capabilities` (ADR-015) | `contract/test_audit_log.py`, com Postgres por `AI_CORE_TEST_POSTGRES_DSN` |
| `PackToolSource` | troca prevista: a forma que a 004 exige da 002 até a passada dela (002 US3 cen. 1) | `StaticPackTools` (tools e retrievers dados) | o `PackRuntime` da 002, quando o expuser | `contract/test_pack_tool_source.py` — roda contra o real na passada da 002 |
| `Clock` | tempo (ADR-013) | relógio fixo da 005 | relógio do sistema da 005 | — (o mesmo relógio da 011) |

```python
class PackToolSource(Protocol):
    def toolset(self, composition: Composition) -> Sequence[PackTool]:
        """Uma entrada por tool nativa e por retriever dos packs da composição, na ordem da composição, com o nome
        `<pack>.<tool>` (002 FR-007). Sem I/O: a 002 coleta o catálogo de cada pack uma vez, na carga."""

class Clock(Protocol):
    def now(self) -> datetime: ...
    def monotonic(self) -> float: ...
```

`AuditLog` em [contracts/audit.md](audit.md).

O cliente MCP e o Trace Sink não são portas deste módulo: chegam pelos seams da 007 (`McpClients`) e da 009
(`TraceSink`), já montados pela composition root.
