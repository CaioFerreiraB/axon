# Design — 101 Scouting Pack

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §11, §13, §19, §30; ADR-006, ADR-012, ADR-013.

## Repositório `ai-scouting`

```text
ai-scouting/src/ai_scouting/
├── pack.py              # 101 — ScoutingPack; composition root do pack (instancia adapters de 102/103 pela configuração)
├── context/             # 101 — prepare_scouting_context (determinístico, puro) + léxico
├── prompts/             # 101
├── rag/
│   ├── index/           # 102 — seam "Índice do scouting": api.py (IndexedChunk, ChunkIndex) + adapters (Qdrant)
│   ├── ingestion/       # 102 — pipeline offline (pipes & filters): parser, chunking estrutural, metadados, embedding
│   ├── retrieval/       # 103 — retriever e reranker (domain/: filtros de vigência, boost por metadado)
│   └── graph/           # 106 — futuro
├── validators/          # 104 — integridade de citação, aviso de vigência (puros)
└── eval/                # 105 — conjunto dourado do domínio
```

Cada subpasta corresponde a uma spec. Os submódulos se enxergam só pelos contratos de 001 (`Retriever`, `Reranker`,
`AnswerValidator`) e pelo `api.py` do índice (102). Regras de import (import-linter no CI do `ai-scouting`, ADR-012):

- `rag/retrieval` e `rag/graph` importam de `rag/index` só o `api.py`;
- `context/` e `validators/` não importam `rag`;
- `domain/` de cada submódulo não importa `qdrant_client` nem bibliotecas de embedding;
- só o `pack.py` instancia adapters.

## Declaração

```toml
# ai-scouting/pyproject.toml
[project]
name = "ai-scouting"
version = "0.1.4"
dependencies = ["ai-core-contracts>=0.1,<0.2"]   # nunca ai-core

[project.entry-points."ai_core.packs"]
scouting = "ai_scouting.pack:ScoutingPack"

[tool.uv.sources]
ai-core-contracts = { git = "https://github.com/caio/ai-core", tag = "contracts-v0.1.0", subdirectory = "packages/contracts" }
```

Em desenvolvimento e CI, os contratos vêm da tag no repositório do core; na instalação, já estão na imagem base.

## Code pack

```python
class ScoutingPack:
    name = "scouting"
    contract_version = "0.1"

    def manifest(self) -> PackManifest:
        return PackManifest(
            name="scouting",
            version="0.1.4",
            preferred_flow="rag_first",
            requires_collections=["scouting_docs"],
            config_schema=SCOUTING_CONFIG_SCHEMA,
        )

    def system_prompt(self, ctx): ...
    async def prepare_context(self, view, ctx): ...     # [ADR-011] recebe TurnView, retorna a fatia
    def tools(self, ctx): ...
    def retrievers(self, ctx): ...
    def reranker(self, ctx): ...
    def validators(self, ctx): ...
```

## prepare_scouting_context (arch-v1 §19)

```text
"Quais competências do Pioneiro estão relacionadas à liderança?"

  branch          = pioneiro
  topic           = liderança
  document_types  = [manual, programa_educativo]
  effective_on    = view.reference_time     ← default de vigência (o dia da requisição) [ADR-013]
```

Consulta histórica:

```text
"O que dizia o manual anterior sobre X?"
"Qual era a regra em 2023?"

  → effective_on = 2023-XX-XX  (em vez de hoje)
  → status inclui revogado/substituído
  → resposta marca explicitamente que a fonte não está vigente (validator 104)
```

Sempre que possível por regra, léxico e metadado — **não** por chamada de LLM. É uma função pura de
(pergunta, léxico, `reference_time`): o pack não lê o relógio do sistema. Retorno:

```python
{"context": {...}, "retrieval_filters": {"branch": "pioneiro", "document_types": [...], "effective_on": "2026-09-10", "include_superseded": False}}
```

## Prioridades de fonte

1. Documentos institucionais sobre fontes secundárias
2. **Documentos vigentes** sobre revogados
3. Fontes específicas e primárias sobre genéricas
4. Recuperação precisa sobre recuperação ampla
5. Citação e proveniência sempre

## Portas e adapters **[ADR-012]**

O pack é um plug-in do microkernel (implementa o contrato 001) e, por dentro, segue o princípio XIII. Este submódulo
(101) não faz I/O: quem tem portas são 102 (índice), 103 (reranker hospedado, quando houver) e 106 (grafo).

| Porta | Tipo | Adapters | Teste |
|---|---|---|---|
| `AgentPack` e hooks (contrato 001) | porta de plug-in implementada | `pack.py` | suíte de conformidade de pack + fixtures de Turn View com `reference_time` fixo |
| Composição dos submódulos | composition root do pack | `pack.py` escolhe os adapters de 102/103 pela configuração do pack | pack montado com índice em memória |

## Assistant típico (definido pelo operador — spec 003)

```yaml
scouting:
  visibility: public
  flow: rag_first
  packs: [scouting]
  mcp: []
  collections: [scouting_docs]
```
