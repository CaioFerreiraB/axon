# Contrato — `graph.jsonl` v2

O arquivo fica em `src/axon_scouting/data/index/graph.jsonl`, ao lado do índice, fora do manifesto, commitado no
pacote. Quem escreve é o `scripts/grafo.py build` (106), e quem lê é o `ArtifactGraphStore`. É UTF-8, um objeto JSON
por linha, na ordem `meta`, `entity`, `version`, `unit`, `edge`, `event`. As entidades ficam na ordem do catálogo curado,
que desempata o reconhecimento (R18), e os outros blocos, na ordem determinística do build. O mesmo artefato e os
mesmos YAML dão o mesmo arquivo, byte a byte.

| `kind` | Campos obrigatórios | Opcionais |
|---|---|---|
| `meta` | `version` (2), `chunking` (o do manifesto do índice), `built_at` (o do índice, para o arquivo ser reprodutível), `sources` (sha256 do `organizacao.yaml` e, a partir do G2, do `dominio.yaml` e da taxonomia) | `report` (contagens por tipo de aresta e origem, e as entradas descartadas com o motivo) |
| `entity` | `id`, `type`, `name`, `terms`, `source`, `origin` | `aliases`, `level` |
| `version` | `doc_key`, `document_id`, `type`, `role`, `status` | `scope`, `date`, `bodies`, `chunk_ids` e `ementa` (G5) |
| `unit` | `unit_id`, `doc_key`, `unit_kind`, `title`, `chunk_ids` | `branches`, `parent` |
| `edge` | `type`, `from`, `to`, `source`, `origin` | `mode` (no `SOBRE`), `checked` (no `modelo_conferido`), `attrs` (o `modo`, a `periodicidade`… da governança; em `ALTERA` e `CITA` de regra, a `regra` citada e o `casamento`, `titulo` ou `numero`; entre resoluções, o `numero`) |
| `event` | `id`, `doc_key`, `type`, `text`, `source` | `date`, `page`, `chunk_ids` (os trechos da ata na página e nas vizinhas, G4) |

**Regras:**
- **Chunking.** Um `meta.chunking` diferente do manifesto do índice faz a carga levantar `GraphUnavailable`.
- **Sem arquivo:** o grafo é vazio.
- **`kind` desconhecido:** é ignorado na carga, para a compatibilidade dentro da versão 2. Um campo obrigatório
  ausente é erro de carga, que nomeia a linha.
- **O v1** (`organ`, `section`, `relation`) não é lido: o teste de identidade do G1 compara com uma referência gravada
  do 0.11.1 (tasks T011).
- **Invariantes:** os do data-model, seção "Validação no build". O `tests/rag/graph/test_graph_artifact.py` os confere
  contra o arquivo commitado.
