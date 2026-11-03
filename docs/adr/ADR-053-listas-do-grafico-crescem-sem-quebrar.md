# ADR-053 — As listas fechadas do gráfico crescem sem quebrar, e o waterfall entra

- **Status:** Aceita · 2026-10-29
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md) (`CHART_KINDS`, `ChartKind`,
  regra do diff de superfície), [008-core-http-api](../../specs/008-core-http-api/spec.md) (desenho do waterfall),
  [010-core-generic-pack](../../specs/010-core-generic-pack/spec.md) (`generic.chart`)
- **Origem:** pedido do mantenedor (2026-10-29): em produção, o `geral` recebeu dois pedidos de "gráfico de waterfall"
  e, sem o tipo, improvisou barras e texto. Acrescentar um tipo ao `Chart` (ADR-052) é, pela regra do FR-020, mudança
  breaking — `CHART_KINDS` é constante, e `ChartKind` é um alias `Literal`.

## Contexto

O diff de superfície (FR-020, ADR-014) trata a mudança de valor de qualquer constante, e de qualquer alias, como
breaking. A exceção é o `ISSUE_CODES`, comparado como conjunto: código novo é aditivo, código removido é breaking.
Isso porque o pack usa os códigos e não os enumera. Com o `Chart`, acontece o mesmo: o pack **produz** gráficos, e
quem os lê é o core (004, 005, 008). Um tipo novo não muda o que um pack já produz. Um pack que não conhece o
waterfall continua válido, e o core sabe desenhar todos os tipos da versão dele.

Pela regra atual, o waterfall levaria os contratos a `0.3.0`, e com isso o core e todo pack (o `axon-scouting` pede
`<0.3`) para uma série nova, só para aumentar uma lista que nenhum pack consome.

## Decisão

1. **As listas fechadas do gráfico crescem como conjuntos.** `CHART_KINDS` e `CHART_X_TYPES` entram nas constantes
   comparadas item a item (`SET_CONSTANTS` de `tools/api_surface.py`). `ChartKind` e `ChartXType` entram como aliases
   `Literal` comparados membro a membro (`WIDENING_ALIASES`): membro novo é aditivo, membro removido é breaking. Os
   demais aliases e constantes seguem a regra geral.
2. **O tipo `waterfall`** (contratos `0.2.5`): uma série só, com x nominal; cada ponto é uma etapa, em ordem, e o `y`
   é a variação dela, positiva ou negativa. O **total final** é calculado e desenhado por quem desenha, não vem no
   `Chart`.
3. **O desenho (008)** usa a série `candlestick` do ECharts. Cada etapa vai do acumulado anterior ao novo, para
   qualquer sinal, inclusive quando o acumulado cruza o zero. A barra de total vai do zero ao resultado. As cores são:
   aumento na cor de série 1, redução na cor 2 e total neutro. A dica mostra a variação e o acumulado. A tabela tem
   as colunas etapa, variação e acumulado, mais a linha de total.
4. **A tool** `generic.chart` aceita `waterfall` (`axon-generic` 0.3.1, `contract_version` 0.2.5), e a descrição dela
   diz para não incluir o total.

## Alternativas rejeitadas

- **Contratos `0.3.0`.** Pela regra antiga, uma série nova para o core e para todo pack, por uma mudança que nenhum
  pack sente.
- **Waterfall como `bar` mais um campo opcional.** Um tipo disfarçado: quem lê o `Chart` teria de saber que um `bar`
  com o campo não é uma barra.
- **O total como último ponto do `Chart`.** O modelo costuma mandar o "Resultado" como mais uma variação e dobra o
  total. Calcular o total na hora de desenhar elimina esse erro.
- **Barra empilhada com base transparente.** Quebra quando o acumulado cruza o zero, porque o ECharts empilha os
  negativos à parte.

## Consequências

- Contratos `0.2.5`; o core pede `>=0.2.5,<0.3`. O `axon-scouting` não muda.
- Remover um tipo de gráfico continua sendo breaking.
- O mesmo vale para o próximo tipo: basta acrescentá-lo às listas e ao desenho.
