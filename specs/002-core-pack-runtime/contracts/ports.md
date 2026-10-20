# Contrato — portas secundárias da 002 (`axon_ai/packs/ports.py`)

Portas internas do módulo (não são seams). Cada uma tem adapter em memória e suíte de conformidade que roda contra ele e
contra o adapter real (princípio XIII).

```python
# axon_ai/packs/ports.py
from __future__ import annotations

@dataclass(frozen=True, slots=True, kw_only=True)
class DiscoveredPack:
    name: str
    distribution: str
    version: str
    load: Callable[[], object]          # importa a classe; pode levantar

@dataclass(frozen=True, slots=True, kw_only=True)
class PackSettings:
    enabled: bool = False
    config: Mapping[str, JSONValue] = ...   # default: mapeamento vazio

class PackSource(Protocol):
    def discover(self) -> Sequence[DiscoveredPack]: ...

class PackConfigSource(Protocol):
    def load(self) -> Mapping[str, PackSettings]: ...     # levanta PackConfigError
```

## Adapters por fase

| Porta | Adapter | Arquivo | Fase |
|---|---|---|---|
| `PackSource` | em memória (lista de classes) | `adapters/memory.py` | 1 (testes, perfil `test`) |
| `PackSource` | entry points `axon.packs` (era `ai_core.packs`; R51) | `adapters/entry_points.py` | 1 |
| `PackSource` | declarativo | `adapters/declarative.py` | P3 (US6) |
| `PackConfigSource` | em memória (mapeamento) | `adapters/memory.py` | 1 |
| `PackConfigSource` | `packs.yaml` | `adapters/config_yaml.py` | 1 |

## Suítes de conformidade

| Porta | O que a suíte verifica | Real rodado em |
|---|---|---|
| `PackSource` | lista um `DiscoveredPack` por entrada; `load()` devolve a classe; nome, distribuição e versão corretos; import quebrado só falha ao chamar `load()`; duas distribuições com o mesmo nome aparecem as duas | distribuições falsas em `tmp_path` (`*.dist-info` com `METADATA` e `entry_points.txt`) no `sys.path` |
| `PackConfigSource` | pack ausente → não aparece; `enabled` default falso; `config` default vazio; chave desconhecida, `enabled` não booleano ou `config` não mapeamento → `PackConfigError` com o caminho | arquivos YAML em `tmp_path` |
