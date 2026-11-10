# Contrato — `scripts/grafo.py`

Só offline, na máquina do mantenedor. É rodado de dentro de `axon-scouting/` com
`XDG_DATA_HOME=$HOME/.local/share uv run python scripts/grafo.py …`. Não vai para a instalação.

## `build`

```text
grafo.py build [--index DIR] [--organization corpus/organizacao.yaml] [--domain corpus/dominio.yaml]
               [--taxonomy corpus/taxonomia.yaml] [--minutes corpus/resumos/atas] [--summarize-resolutions]
```

- Monta o grafo e grava `<index>/graph.jsonl` (v2).
- Imprime o relatório: entidades por tipo, arestas por tipo e origem, e o que ficou de fora, com o motivo (fonte "a
  verificar", fonte que não resolve, título ambíguo).
- **Saídas:**
  - `0` quando monta;
  - `2` quando um YAML é inválido, nomeando a entrada;
  - `1` quando um invariante falha (por exemplo, um tipo da taxonomia sem papel).
- **`--summarize-resolutions` (G5):**
  - imprime a estimativa de custo e pede confirmação antes de qualquer chamada;
  - lê a chave só de `AXON_OPENROUTER_API_KEY`;
  - grava as propostas conferidas em `corpus/resumos/resolucoes/`, como as fichas, para o build seguinte não chamar o
    modelo de novo.

## `query`

```text
grafo.py query sobre cargo:escotista [ramo:pioneiro …] [--modo todas] [--papeis norma,orientacao] [--tipos …]
grafo.py query aplicavel_a inst:ge_inah [--papeis norma]
grafo.py query documentos [--tipo politica] [--emissor orgao:dr_sp] [--area area:espacos_seguros]
grafo.py query itens [--tipo-de-unidade especialidade] [--de inst:ueb] [--ramo ramo:senior]
grafo.py query linha_do_tempo doc:regulamento-regional-sp [--eventos deliberacao] [--de 2014-01-01]
grafo.py query ligados <unit_id|doc:…|entidade> [--relacoes ALTERA,REVOGA]
grafo.py query reconhecer "um pioneiro pode ser escotista?"
grafo.py plan "um pioneiro pode ser escotista?"      # a derivação da 101 mostra entities e plan (composição pelo pack)
```

- Roda as mesmas funções do `DomainGraphService`.
- Imprime uma linha por evidência: o documento, a unidade e o título, o papel, a data, o tipo, a fonte e a origem da
  aresta.
- `--json` grava a evidência como JSON.

## `export --arrows`

```text
grafo.py export --arrows [--entidade cargo:escotista --saltos 2] [--sem-unidades] > grafo.arrows.json
```

- Grava um subgrafo no formato do arrows.app (`nodes`, `relationships`, `style`), o mesmo de
  `corpus/Organização Escoteira.revisado.json`.
- **Rótulos:** o nó leva o prefixo como rótulo e a fonte e a origem como propriedades.
- **Tamanho:** sem `--entidade`, só as entidades e as arestas entre elas, sem unidades, para caber no editor.
