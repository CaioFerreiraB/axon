# ADR-052 — Gráficos na conversa

- **Status:** Aceita · 2026-10-28
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md) (`Chart`, `ToolResult.charts`),
  [004-core-capability-gateway](../../specs/004-core-capability-gateway/spec.md) (marca e resumo),
  [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md) (`ChartEvent`, `FinalEvent.charts`),
  [008-core-http-api](../../specs/008-core-http-api/spec.md) (tabela, `embeds` atrás de `x-axon-charts`, rota estática do
  ECharts), [010-core-generic-pack](../../specs/010-core-generic-pack/spec.md) (tool `generic.chart`),
  [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (endereço do script),
  [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (repasse de `/static/` no nginx)
- **Origem:** pedido do mantenedor (2026-10-28): ver no Open WebUI um gráfico interativo — série temporal, rosca,
  barras — pedido na conversa ou montado a partir dos dados que um MCP devolve. O visual do Vega-Lite nativo foi
  recusado; o pedido é o do Apache ECharts ou do Plotly. Depois, "o máximo de cores possível" (8, abaixo).

## Contexto

O controller do `agentic` já recebe dados (de um MCP, por exemplo) e escolhe tools. O que falta é um caminho até a tela.
O ADR-044 já resolveu um caso parecido, o das imagens. A tool devolve a imagem num canal lateral (`ToolResult.attachments`),
e o modelo só vê uma marca. O motor publica a imagem (`AttachmentEvent`, `FinalEvent.attachments`), e a 008 a entrega
depois do texto.

O que o Open WebUI v0.12 oferece, verificado no contêiner do dev (`ghcr.io/open-webui/open-webui:v0.12.0`):

- **Blocos nativos.** O Open WebUI desenha ```` ```vega-lite ````, ```` ```vega ```` e ```` ```mermaid ```` no texto da
  mensagem, para qualquer backend. Não há bloco nativo para ECharts nem Plotly.
- **Evento `embeds`.** `utils/middleware.py` repassa ao emissor de eventos qualquer `event` de um chunk de conexão
  externa, o mesmo caminho do ADR-028 e do ADR-051. Para o tipo `embeds`, `socket/main.py` grava `message.embeds`, e
  só em chat salvo.
  - **Como é desenhado.** O front-end desenha cada item num iframe `srcdoc`, com `sandbox="allow-scripts allow-forms
    allow-popups allow-downloads"`, sem `allow-same-origin`. Por padrão não há CSP (`IFRAME_CSP` vazio).
  - **Altura e tema.** A altura vem do iframe por `postMessage({type: "iframe:height", height})`. O tema da interface
    não chega ao iframe.
  - **Vários eventos.** Na tela ao vivo, cada evento `embeds` **substitui** a lista, e o banco a acumula em ordem
    inversa.
- **`<details>` no conteúdo.** Um `<details>` sem `type` é desenhado como bloco recolhível, com o miolo em markdown, e
  volta ao modelo no histórico. O front-end tira só os de tipo `reasoning` e `code_interpreter`.

Protótipo do passo 0 (página que imita esse iframe, Playwright, 2026-10-28):

- **Carga.** O ECharts 6.1.0 vem de outra origem com `integrity` + `crossorigin` e carrega no iframe de origem `null`.
- **Interação.** Funcionam o locale pt-BR, a altura pelo `postMessage`, a troca de tema ao vivo por
  `prefers-color-scheme` e a dica de eixo com mira.
- **Escape.** Um título `</script><img onerror=…>` sai como texto.
- **Paleta.** As quatro cores de série da marca são as quatro primeiras da paleta de referência de oito da skill de
  visualização, validada nessa ordem. No validador, sobre os fundos do Open WebUI (`#ffffff` no claro, `#171717` no
  escuro), as **oito** passam nas checagens entre vizinhas, nos dois temas. No claro, as cores 3, 4 e 5 ficam abaixo de
  3:1, o que exige rótulo ou tabela. Entre **todos os pares**, falham a partir da quinta: rosa × laranja (ΔE 12,9),
  vermelho × laranja (7,1) e, para o daltônico protanope, verde × laranja (3,2).

## Decisão

1. **A tool entrega dados, nunca HTML.** O contrato ganha `Chart` (001, `0.2.4`, aditivo), com `ChartSeries` e
   `ChartPoint`.
   - **Campos:** `kind` (`line | area | bar | stacked_bar | scatter | pie | donut`), `title`, `subtitle`, `x_type`
     (`temporal | quantitative | nominal`), `x_label`, `y_label`, `unit` e `unit_position` (`prefix | suffix`).
   - **Validação na construção**, como no `Attachment`:
     - os textos são limpos e curtos;
     - `pie`/`donut` têm uma série, `y ≥ 0` e soma positiva;
     - `temporal` exige data ISO;
     - os pontos são finitos;
     - no máximo **8 séries** (as oito cores validadas; uma nona cor nunca é gerada) e **500 pontos**.
   - **Identidade:** `id` = `chart-` + 12 hexadecimais do SHA-256 da forma canônica.
   - **Onde vai:** `ToolResult.charts: tuple[Chart, ...]`, ao lado de `attachments`.
2. **O gráfico segue pelo canal lateral do ADR-044.**
   - A 004 deduplica por id e põe no resultado cercado a marca `[gráfico <id> mostrado ao usuário: <título>]`, depois
     do corte. O `tool_call` da 009 e a auditoria levam só o resumo (id, tipo, séries, pontos).
   - A 005 publica `ChartEvent` e `FinalEvent.charts`. O modelo não recebe os dados de volta, só a marca.
3. **Só a 008 escreve o HTML, a partir do `Chart`**, num domínio puro (`http/domain/charts.py`).
   - **Opção do ECharts** por tipo:
     - tooltip de eixo com mira contínua nas cartesianas e tooltip de item na pizza;
     - rosca `['45%', '70%']`;
     - eixo `time` com `dataZoom` acima de 30 pontos;
     - legenda com duas séries ou mais, e nenhuma na pizza, que tem rótulos;
     - barra até 24px com canto de 4px no topo;
     - linha de 2px e área a ~12%;
     - grade contínua e discreta;
     - números, datas e percentuais em pt-BR.
   - **Cores:** as oito de série, na ordem fixa — azul, laranja, verde-água, ouro, rosa, verde, violeta e vermelho —,
     claro e escuro, escolhidas no navegador por `prefers-color-scheme`. A cor segue a série (a posição dela no
     `Chart`), nunca a ordem de grandeza.
   - **Pizza e rosca** com mais de oito fatias desenham as sete maiores e "Outros". Fatias, barras empilhadas e barras
     agrupadas só encostam a vizinha, separada por 2px da cor do fundo: as oito valem como estão.
   - **Linha, área e dispersão com cinco séries ou mais** não confiam só na cor, porque ali qualquer série cruza com
     qualquer outra e a checagem entre todos os pares falha. Cada linha leva o nome na ponta (`endLabel`), e cada
     série de dispersão, uma forma de marcador própria.
   - **Segurança da página:** os formatadores são código fixo da página, e o texto entra só por `textContent` ou pelo
     escape do ECharts. O JSON embutido escapa `<`, `>`, `&`, U+2028 e U+2029.
4. **Entrega no dialeto do Open WebUI, atrás de `x-axon-charts`** (`none`, o padrão, ou `embeds`; outro valor → 400
   antes de executar, como o `x-axon-citations`).
   - **Com `embeds` e streaming:** sai **um** evento `{"type": "embeds", "data": {"embeds": [html, …], "replace":
     true}}`, uma página por gráfico. Ele vem depois do texto, da tabela e das imagens, e antes das fontes e do chunk
     final.
   - **Sem streaming:** nada sai, porque o Open WebUI só lê `event` no streaming.
5. **A tabela sempre vai no texto.** Depois do texto da resposta, cada gráfico deixa `<details><summary>Dados do
   gráfico: <título></summary>` com a tabela em markdown (a pizza com todas as fatias). Ela serve:
   - à acessibilidade (a dica nunca é o único caminho até um valor);
   - aos clientes sem `embeds`;
   - ao histórico: é o que o modelo lê no turno seguinte.

   `x_axon.charts` leva o `Chart` em JSON, para outros clientes desenharem como quiserem.
6. **O ECharts é servido pela plataforma.**
   - **Arquivo:** o `echarts.min.js` 6.1.0 (Apache-2.0, com `LICENSE` e `NOTICE`) e o `langPT-br.js` são
     vendorizados no pacote.
   - **Rota:** `GET /static/echarts/6.1.0/<arquivo>`, pública e sem autenticação, com `Cache-Control: public,
     max-age=31536000, immutable`, `Access-Control-Allow-Origin: *` e `nosniff`. O nginx da console (013,
     `deploy/nginx.conf.template`) repassa `/static/` ao core, como os outros prefixos: com console, o
     `AXON_PUBLIC_URL` é o domínio dela.
   - **Integridade:** a página usa `integrity` (sha384), conferido em teste contra o arquivo.
   - **Endereço:** o base vem de `AXON_CHARTS_SCRIPT_BASE_URL` (011), senão de `AXON_PUBLIC_URL`. Sem nenhum dos dois,
     `embeds` vira `none` e a saúde mostra um aviso não crítico `charts`.
7. **A tool é do `axon-generic`** (`generic.chart`). Os parâmetros cabem no subconjunto estrito: sem `$ref`, sem
   `allOf`, sem regex e com objetos fechados. Um erro de validação volta como `ToolResult(error=…)` legível, para o
   controller corrigir. A descrição manda agregar antes de plotar. O prompt segue neutro quanto ao flow (FR-008 da 010).

## Alternativas rejeitadas

- **HTML escrito pela tool, pelo pack ou pelo modelo.** É conteúdo ativo opaco, o motivo pelo qual o ADR-044 recusou
  SVG. Com o esquema fechado, o que roda no navegador é só código da plataforma.
- **Vega-Lite nativo** (bloco ```` ```vega-lite ```` no texto). Não precisa de iframe, servidor de script nem cabeçalho,
  mas o mantenedor recusou o visual. Um Vega-Lite livre vindo de pack ou MCP também precisaria de saneamento
  (`data.url`, `href`, mark `image`).
- **Plotly.js.** O visual também atende e o caminho seria o mesmo (`embeds`, script servido pela plataforma). O
  mantenedor escolheu o ECharts pelo acabamento padrão: animação, slider de zoom e rosca nativa.
- **Biblioteca embutida em cada página.** Seria 1,1 MB por gráfico, gravado em cada mensagem do banco do Open WebUI.
- **CDN público fixo.** Quebra numa instalação sem saída para a internet ou com `IFRAME_CSP`, e o script não seria da
  plataforma.
- **Um evento `embeds` por gráfico.** A tela ao vivo mostra só o último, e o banco grava em ordem inversa.
- **Ficar nas quatro cores do DESIGN.md.** Era a regra da console, onde só o gráfico de custo usa cor de série. Na
  conversa, uma rosca de seis categorias ou uma comparação de seis séries é pedido comum, e as cores 5 a 8 da paleta
  de referência passam nas checagens que valem para cada tipo, com o reforço do rótulo onde não passam.
- **Mais de oito cores.** Uma nona cor seria gerada, não validada. O excedente vira "Outros" (pizza) ou volta ao
  controller como erro (séries), que pode desenhar dois gráficos.
- **Referência ao resultado de uma tool anterior** em vez de repetir os dados nos argumentos (`data_ref`). Pouparia
  tokens, mas toca o estado interno da 005. Fica para um ADR próprio, se a medição mostrar a necessidade.

## Consequências

- **Versões.** Contratos `0.2.4`. O core pede `>=0.2.4,<0.3`, e o `axon-generic` sobe de minor.
- **Marca.** As cores de série 5 a 8 entram nos tokens (`brand-kit/brand-tokens.*` e DESIGN.md) como cores de gráfico
  da conversa. A console continua com as quatro. O verde e o vermelho de série lembram as cores de estado, mas o
  gráfico da conversa não usa cor de estado.
- **Instalação.** O `axon-deploy/template`, o `axon-cfblabs` e o dev mandam `x-axon-charts: embeds`. O proxy expõe
  `/static/echarts/` no host da API. Com `IFRAME_CSP`, o operador libera esse host em `script-src` e
  `'unsafe-inline'`. O `check-webui.py` confere `embeds` na mensagem gravada.
- **Assistants.** Um Assistant que desenha gráficos declara `flow: agentic` (ou `rag_first` com `controller`) e
  `generic.chart` em `allowed_tools`. O `chat` sem controller não desenha.
- **Persistência.** Em chat temporário do Open WebUI, o gráfico some ao recarregar e a tabela fica.
- **Tema.** O tema do gráfico segue o do sistema, não a escolha manual no Open WebUI.
- **Peso.** Um build do ECharts só com os tipos usados (cerca de 400 KB) fica para depois, se o peso pesar.
