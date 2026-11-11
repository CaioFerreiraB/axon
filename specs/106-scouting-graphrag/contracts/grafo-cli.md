# Contrato — `scripts/grafo.py`

Só offline, na máquina do mantenedor. É rodado de dentro de `axon-scouting/` com
`XDG_DATA_HOME=$HOME/.local/share uv run python scripts/grafo.py …`. Não vai para a instalação.

## `build`

```text
grafo.py build [--index DIR] [--organization corpus/organizacao.yaml] [--domain corpus/dominio.yaml]
               [--taxonomy corpus/taxonomia.yaml] [--minutes corpus/resumos/atas] [--subjects corpus/resumos/resolucoes/assuntos.yaml]
```

- Monta o grafo e grava `<index>/graph.jsonl` (v2).
- Imprime o relatório: entidades por tipo, arestas por tipo e origem, e o que ficou de fora, com o motivo (fonte "a
  verificar", fonte que não resolve, título ambíguo).
- **Saídas:**
  - `0` quando monta;
  - `2` quando um YAML é inválido, nomeando a entrada;
  - `1` quando um invariante falha (por exemplo, um tipo da taxonomia sem papel).
- **`--subjects` (G5; default `corpus/resumos/resolucoes/assuntos.yaml`):** as propostas de assunto das resoluções que
  a ementa não resolve, feitas por um modelo offline e conferidas pelo build (a entidade no catálogo, o trecho citado
  num trecho da resolução). O `--summarize-resolutions` com o OpenRouter não foi implementado: por decisão do
  mantenedor, as propostas do G5 saíram da própria sessão (R22).
- O relatório do build conta as resoluções (com ementa, com assunto pela ementa, pelo modelo conferido e sem assunto)
  e as ligações por tipo, e lista as descartadas com o motivo.

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
