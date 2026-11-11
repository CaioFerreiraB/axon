# Quickstart — 106 Grafo de domínio

Tudo roda de dentro de `axon-scouting/`, com `export XDG_DATA_HOME=$HOME/.local/share`. O seam está em
[contracts/domain-graph-seam.md](contracts/domain-graph-seam.md) e a linha de comando em
[contracts/grafo-cli.md](contracts/grafo-cli.md).

## 1. Construir e conferir o grafo

```bash
uv run python scripts/grafo.py build                 # grava src/axon_scouting/data/index/graph.jsonl (v2)
uv run pytest -q tests/rag/graph                     # consultas, executor, plano, conformidade e invariantes
```

O build termina com 0 e imprime as contagens por tipo de aresta e origem e o que ficou de fora, com o motivo. A suíte
confere os invariantes (FR-019): a fonte resolve, não há id órfão, o modelo foi conferido, todo tipo tem papel e o
chunking bate com o do índice.

## 2. Consultar como a busca consulta

```bash
uv run python scripts/grafo.py query reconhecer "Quem fiscaliza as contas da Diretoria Regional?"
uv run python scripts/grafo.py query sobre tipo_orgao:diretoria_regional --papeis norma
uv run python scripts/grafo.py plan "Um pioneiro pode atuar como escotista?"
```

**Esperado no G1:** a segunda consulta lista as seções do Estatuto e do Regulamento da Região SP do ADR-063, da norma
de cima para a de baixo, com a fonte e `origin: regra`.

**Esperado do G2 em diante:** o `plan` mostra `sobre([ramo:pioneiro, cargo:escotista], modo=todas)`.

## 3. Ver o grafo no arrows.app

```bash
uv run python scripts/grafo.py export --arrows --entidade cargo:escotista --saltos 2 > .cache/escotista.arrows.json
```

Abra o arquivo no arrows.app (Import → JSON). Cada nó leva a fonte e a origem como propriedades.

## 4. Os quatro conjuntos, antes e depois, por item (105 FR-026)

O procedimento é o da seção 9 do [quickstart da 105](../105-scouting-evaluation/quickstart.md):

```bash
export AXON_PROFILE=test AXON_PACKS_FILE=eval/packs.yaml AXON_ASSISTANTS_FILE=eval/assistants.yaml \
  AXON_RAG_CANDIDATES=20 AXON_RAG_PASSAGES=20 AXON_TOOL_MAX_RESPONSE_BYTES=65536
for s in acervo regression sintese programa-adultos; do
  uv run --python 3.14 --group platform axon eval run --golden eval/$s.yaml --baseline eval/$s-baseline.json \
    --report .cache/depois-$s.json
  uv run python scripts/eval_diff.py eval/$s-baseline.json .cache/depois-$s.json --golden eval/$s.yaml
done
```

**Esperado no G1:** "Nenhum item mudou" nos quatro (SC-001).

**Esperado do G2 em diante:** nenhum conjunto abaixo da linha de base (tolerância 0,02), e a lista de itens que
mudaram vai para a PARADA 4.

## 5. O teste de identidade do G1

```bash
uv run pytest -q tests/rag/graph/test_g1_identity.py
```

Para cada pergunta do acervo, compara os `chunk_id` à frente (`graph_rank`) do v1 e do v2. Esperado: iguais, na mesma
ordem.

## 6. A verificação completa do pack

```bash
uv run pytest && uv run mypy && uv run ruff check && uv run lint-imports
uv run --python 3.14 --group platform pytest tests/integration
```

O import-linter tem os contratos novos (R14):
- as camadas da 106;
- `context` limitado a `rag.graph.api`;
- a infraestrutura só em `rag.graph.adapters`.
