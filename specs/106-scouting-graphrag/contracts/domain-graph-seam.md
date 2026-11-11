# Contrato — seam *Grafo de domínio* (`axon_scouting.rag.graph.api`)

Dono: 106. Consumidores: 103 (`run`), 101 pelo `pack.py` (`aliases`, `reconhecer`, `QueryPlan`) e `scripts/grafo.py`
(`query`). O ADR-064 decide o seam, e uma mudança aqui pede outro ADR.

```python
Role = Literal["norma", "orientacao", "registro", "comunicacao"]
Mode = Literal["disciplina", "orienta", "registra", "comunica"]
Origin = Literal["curado", "regra", "modelo_conferido"]
QueryName = Literal["sobre", "aplicavel_a", "documentos", "itens", "linha_do_tempo", "ligados"]

ROLES: Final[Mapping[str, Role]]          # taxonomy_id → papel (R3)
MODE_OF: Final[Mapping[Role, Mode]]

Aliases = Mapping[str, tuple[str, ...]]   # id da entidade → termos normalizados

def reconhecer(texto: str, apelidos: Aliases) -> tuple[str, ...]:
    """Os ids das entidades que o texto (já normalizado pela 101) nomeia, pelo termo mais longo, sem sobreposição, na
    ordem da primeira menção. Puro."""

class PlanInvalid(ValueError):
    field: str                            # o campo, por exemplo "consultas[0].args.papeis"

@dataclass(frozen=True, slots=True, kw_only=True)
class QueryStep:
    q: QueryName
    args: Mapping[str, JSONValue]

@dataclass(frozen=True, slots=True, kw_only=True)
class QueryPlan:
    version: Literal[1] = 1
    forma: Literal["simples", "para_cada", "intersecao"] = "simples"
    consultas: tuple[QueryStep, ...] = ()
    para_cada: tuple[str, ...] = ()
    def to_json(self) -> dict[str, JSONValue]: ...
    @classmethod
    def from_json(cls, raw: Mapping[str, JSONValue]) -> QueryPlan: ...   # PlanInvalid

@dataclass(frozen=True, slots=True, kw_only=True)
class EdgeRef:
    type: str
    source: str
    origin: Origin

@dataclass(frozen=True, slots=True, kw_only=True)
class EventRef:
    type: Literal["reuniao", "deliberacao", "eleicao", "alteracao"]
    text: str
    page: int | None

@dataclass(frozen=True, slots=True, kw_only=True)
class Evidence:
    query: QueryName
    target: str
    doc_key: str
    unit_id: str | None
    chunk_ids: tuple[str, ...]
    role: Role
    scope: str | None
    date: date | None
    edge: EdgeRef
    event: EventRef | None = None

@dataclass(frozen=True, slots=True, kw_only=True)
class FrontGroup:
    step: int                             # o índice do passo no plano
    entity: str | None                    # em para_cada, a entidade do grupo
    evidence: tuple[Evidence, ...]        # toda a evidência, ordenada (o corte em documentos é da 103)

Frentes = tuple[FrontGroup, ...]

class GraphUnavailable(Exception):
    """O graph.jsonl é de outro build (o chunking difere do índice). A mensagem manda rodar scripts/grafo.py build."""

@runtime_checkable
class DomainGraphSource(Protocol):
    async def aliases(self) -> Aliases:
        """Os termos de todas as entidades reconhecíveis. Sem grafo, {}."""
    async def run(self, plan: QueryPlan) -> Frentes:
        """Executa o plano. Plano vazio → (). Entidade inexistente no plano → o passo volta vazio."""
    async def query(self, name: QueryName, /, **args: JSONValue) -> list[Evidence]:
        """Uma consulta solta, para a linha de comando. Argumento desconhecido → PlanInvalid."""
```

## Garantias que a conformidade testa

1. **Determinismo.** O mesmo grafo e o mesmo plano dão as mesmas `Frentes`, na mesma ordem.
2. **Ordem.** Dentro de um grupo de `sobre`, a ordem é a posição da entidade em `entidades` (a ordem da menção), depois
   o papel (norma, orientação, registro, comunicação), o nível (do mundial ao local), o `doc_key` e o `unit_id`, que é
   a ordem do `sorted` do ADR-063 estendida. Os eventos vão por data, e os documentos de `documentos` vão por `doc_key`.
3. **Sem corte.** O executor entrega toda a evidência de cada grupo, na ordem da garantia 2. O corte em 3 documentos
   (pela relevância à pergunta dentro do mesmo papel, nível e camada) e a escolha dos trechos são da 103 (R19).
4. **Governança.** `run` nunca devolve aresta de governança. Só `query("ligados", …)` as devolve (FR-007).
5. **Fonte.** Toda `Evidence` tem `edge.source` e `edge.origin`.
6. **Vazio.** Sem `graph.jsonl`, `aliases() == {}` e `run(p) == ()`. Com um grafo de outro build, a primeira chamada
   levanta `GraphUnavailable`.
7. **Reconhecimento.** "conselho consultivo regional" → `tipo_orgao:conselho_consultivo_regional`, e não o nacional
   (o termo mais longo vence).
8. **G1.** Com o plano `sobre([órgão], papeis=["norma"])`, os documentos e a ordem das unidades são os do
   `NormGraph.sections` do 0.11.1.
