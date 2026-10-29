# ADR-054 — A geração declara gráficos em JSON na resposta

- **Status:** Aceita · 2026-10-29
- **Specs afetadas:** [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md) (filtro e leitura do
  bloco, aviso na geração)
- **Origem:** traces de produção do `geral` (2026-10-29, rc11). O controller buscava dados no Mango, que é paginado,
  e o loop acabava pela regra de ação repetida antes de ele chamar a `generic.chart`. A geração tinha todos os números
  e desenhou o gráfico em texto (tabela, barras ASCII). Pedido do mantenedor: gráficos interativos a partir de JSON, e
  nenhuma orientação ao controller sobre qual ferramenta escolher.

## Contexto

No ADR-052, o gráfico nasce de uma tool que o **controller** chama. Para isso, ele precisa decidir, no meio da busca,
que já tem os dados e que é hora de desenhar. Com fontes paginadas, ele segue buscando, e quem chega ao fim com os
números completos é a **geração**, que escreve a resposta. Ela não tem ferramentas (R54, R55), e, quando tentou
chamá-las como texto, o filtro de marcação esvaziou a resposta.

## Decisão

1. **A geração pode escrever um bloco ` ```axon-chart ` com um objeto JSON** no mesmo esquema do `Chart` (ADR-052,
   ADR-053): `kind`, `title`, `series` de `{name, points: [{x, y}]}` e os opcionais. Os pontos também podem vir como
   `[x, y]`.
2. **O motor tira o bloco do texto em streaming** (`graph/domain/chart_blocks.py`, puro). O filtro fica depois do de
   marcação de tool e antes dos validators do pack, e segura só o pedaço do fim que ainda pode abrir um bloco. Cada
   bloco fechado é lido e validado pelo próprio `Chart` do contrato. O eixo temporal é inferido de datas ISO, como na
   `generic.chart`.
3. **O gráfico válido segue o caminho do ADR-052:** um `ChartEvent` (com `tool` = `generation`) e o gráfico em
   `FinalEvent.charts`. A 008 o desenha e põe a tabela, sem mudança. Bloco inválido some do texto e vira um registro
   `ChartBlockInvalid` (`notice`), com o motivo. No máximo 4 gráficos por resposta, e o mesmo gráfico duas vezes conta
   uma só.
4. **A geração recebe o formato num aviso fixo (`CHART_BLOCK_INSTRUCTION`)** só em execuções com ferramentas (o
   `agentic`, ou o `rag_first` que escalou), como o aviso das imagens. O `chat` e o `rag_first` coberto do scouting
   não mudam. O aviso diz para usar o bloco quando o usuário pedir um gráfico, só com números dos resultados ou da
   conversa, e nunca desenhar gráfico em texto. O aviso das imagens deixa de dizer que todo gráfico depende de uma
   ferramenta.
5. **O controller não muda**, e a `generic.chart` continua no catálogo.

## Alternativas rejeitadas

- **Orientar o controller a preferir resumos ou a desenhar logo.** Recusado pelo mantenedor: a escolha da ferramenta é
  do controller.
- **Uma iteração reservada do controller para desenhar.** O controller não sabe que é a última e repetiria a busca.
- **Mandar à geração a `generic.chart` como tool real.** A geração roda sem tools (005), e reabrir o loop por ela
  duplicaria o controller.
- **Deixar o bloco no texto para o cliente desenhar.** O Open WebUI não desenha ECharts num bloco de código, e o JSON
  bruto ficaria na conversa e no histórico.

## Consequências

- O gráfico pode nascer de duas fontes, a tool do controller e a geração, com o mesmo contrato, desenho e tabela.
- O JSON não fica no texto da resposta nem no histórico: fica a tabela, como na tool.
- Nada muda nos contratos nem na API.
