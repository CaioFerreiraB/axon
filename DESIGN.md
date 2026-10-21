---
name: Axon — console de administração e login
description: Console de administração (spec 013) e páginas de login e "Minha conta" (spec 012) da plataforma Axon, no padrão da categoria.
colors:
  fundo-base: "#ffffff"
  fundo-sutil: "#f8fafc"
  fundo-realce: "#f1f5f9"
  borda-base: "#e5e7eb"
  borda-forte: "#d1d5db"
  texto-primario: "#111827"
  texto-secundario: "#556070"
  texto-terciario: "#666d7c"
  texto-sobre-acao: "#ffffff"
  acao-base: "#2563eb"
  acao-hover: "#1d4ed8"
  acao-sutil: "#eff4ff"
  acao-texto: "#1d4ed8"
  estado-ok-texto: "#15803d"
  estado-ok-fundo: "#ecfdf3"
  estado-ok-marca: "#16a34a"
  estado-aviso-texto: "#a15c07"
  estado-aviso-fundo: "#fef7e6"
  estado-aviso-marca: "#f59e0b"
  estado-erro-texto: "#c42b2b"
  estado-erro-fundo: "#fef2f2"
  estado-erro-marca: "#dc2626"
  serie-1: "#2a78d6"
  serie-2: "#eb6834"
  serie-3: "#1baf7a"
  serie-4: "#eda100"
  foco: "#2563eb"
  fundo-base-escuro: "#0b0f19"
  fundo-sutil-escuro: "#111724"
  fundo-realce-escuro: "#1a2130"
  borda-base-escuro: "#242b3a"
  borda-forte-escuro: "#353d4f"
  texto-primario-escuro: "#f1f3f7"
  texto-secundario-escuro: "#a3abbb"
  texto-terciario-escuro: "#8c94a6"
  acao-hover-escuro: "#1d4ed8"
  acao-sutil-escuro: "#14223f"
  acao-texto-escuro: "#93b4fb"
  estado-ok-texto-escuro: "#4cc38a"
  estado-ok-fundo-escuro: "#0f2a1c"
  estado-ok-marca-escuro: "#3fb97a"
  estado-aviso-texto-escuro: "#f5b544"
  estado-aviso-fundo-escuro: "#2e2210"
  estado-aviso-marca-escuro: "#f5a524"
  estado-erro-texto-escuro: "#f87171"
  estado-erro-fundo-escuro: "#2e1414"
  estado-erro-marca-escuro: "#ef4444"
  serie-1-escuro: "#3987e5"
  serie-2-escuro: "#d95926"
  serie-3-escuro: "#199e70"
  serie-4-escuro: "#c98500"
  foco-escuro: "#93b4fb"
typography:
  display:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif"
    fontSize: "3rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.017em"
  stat:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 600
    lineHeight: 1.1
    letterSpacing: "-0.014em"
  title:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  body-sm:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.4
  label:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.3
  caption:
    fontFamily: "Mona Sans, ui-sans-serif, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
  mono:
    fontFamily: "JetBrains Mono, ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "0.8125rem"
    fontWeight: 400
    lineHeight: 1.4
rounded:
  miudo: "4px"
  controle: "6px"
  painel: "8px"
  pilula: "999px"
spacing:
  espaco-1: "4px"
  espaco-2: "8px"
  espaco-3: "12px"
  espaco-4: "16px"
  espaco-5: "20px"
  espaco-6: "24px"
  espaco-8: "32px"
  espaco-10: "40px"
  espaco-12: "48px"
components:
  button-primary:
    backgroundColor: "{colors.acao-base}"
    textColor: "{colors.texto-sobre-acao}"
    rounded: "{rounded.controle}"
    padding: "0 12px"
    height: "32px"
  button-primary-hover:
    backgroundColor: "{colors.acao-hover}"
  button-secondary:
    backgroundColor: "{colors.fundo-base}"
    textColor: "{colors.texto-primario}"
    rounded: "{rounded.controle}"
    padding: "0 12px"
    height: "32px"
  button-secondary-hover:
    backgroundColor: "{colors.fundo-sutil}"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.texto-secundario}"
    rounded: "{rounded.controle}"
    height: "32px"
  button-ghost-hover:
    backgroundColor: "{colors.fundo-realce}"
    textColor: "{colors.texto-primario}"
  button-danger:
    backgroundColor: "{colors.fundo-base}"
    textColor: "{colors.estado-erro-texto}"
    rounded: "{rounded.controle}"
    height: "32px"
  button-danger-hover:
    backgroundColor: "{colors.estado-erro-fundo}"
  input:
    backgroundColor: "{colors.fundo-base}"
    textColor: "{colors.texto-primario}"
    typography: "{typography.body}"
    rounded: "{rounded.controle}"
    padding: "0 12px"
    height: "36px"
  input-readonly:
    backgroundColor: "{colors.fundo-realce}"
    textColor: "{colors.texto-secundario}"
  input-identificador:
    typography: "{typography.mono}"
  login-input:
    backgroundColor: "{colors.fundo-base}"
    textColor: "{colors.texto-primario}"
    rounded: "{rounded.controle}"
    height: "40px"
  login-button-primary:
    backgroundColor: "{colors.acao-base}"
    textColor: "{colors.texto-sobre-acao}"
    rounded: "{rounded.controle}"
    height: "44px"
    width: "100%"
  badge-ok:
    backgroundColor: "{colors.estado-ok-fundo}"
    textColor: "{colors.estado-ok-texto}"
    typography: "{typography.caption}"
    rounded: "{rounded.pilula}"
    height: "22px"
  badge-aviso:
    backgroundColor: "{colors.estado-aviso-fundo}"
    textColor: "{colors.estado-aviso-texto}"
    rounded: "{rounded.pilula}"
    height: "22px"
  badge-erro:
    backgroundColor: "{colors.estado-erro-fundo}"
    textColor: "{colors.estado-erro-texto}"
    rounded: "{rounded.pilula}"
    height: "22px"
  badge-info:
    backgroundColor: "{colors.acao-sutil}"
    textColor: "{colors.acao-texto}"
    rounded: "{rounded.pilula}"
    height: "22px"
  badge-neutro:
    backgroundColor: "{colors.fundo-realce}"
    textColor: "{colors.texto-secundario}"
    rounded: "{rounded.pilula}"
    height: "22px"
  panel:
    backgroundColor: "{colors.fundo-base}"
    rounded: "{rounded.painel}"
    padding: "20px"
  table-header:
    backgroundColor: "{colors.fundo-sutil}"
    textColor: "{colors.texto-secundario}"
    typography: "{typography.caption}"
    padding: "0 16px"
    height: "36px"
  table-row:
    typography: "{typography.body}"
    padding: "10px 16px"
    height: "48px"
  segmented:
    backgroundColor: "{colors.fundo-realce}"
    rounded: "{rounded.controle}"
    padding: "2px"
    height: "32px"
  segmented-item-on:
    backgroundColor: "{colors.fundo-base}"
    textColor: "{colors.texto-primario}"
    height: "28px"
  nav-item:
    textColor: "{colors.texto-secundario}"
    typography: "{typography.body}"
    rounded: "{rounded.controle}"
    padding: "0 8px"
    height: "32px"
  nav-item-active:
    backgroundColor: "{colors.fundo-realce}"
    textColor: "{colors.texto-primario}"
  sidebar:
    backgroundColor: "{colors.fundo-sutil}"
    width: "240px"
  toggle:
    backgroundColor: "{colors.borda-forte}"
    rounded: "{rounded.pilula}"
    width: "32px"
    height: "18px"
  toggle-on:
    backgroundColor: "{colors.acao-base}"
---

# Design System: Axon — console de administração e login

## Overview

**Creative North Star: "O padrão da categoria, bem-acabado"**

A console e as páginas de login são ferramentas de operador no acabamento que se espera de Vercel e Linear: neutros frios da marca Axon sobre branco (no escuro, o `axon-night` com cinzas azulados), um único azul de ação e verde, âmbar e vermelho só para estado. A convenção é o compromisso. Nada de enfeite de outro mundo, nada de painel SaaS genérico de cartões de métrica com ícone e gradiente, nada de frieza de terminal.

A densidade é de ferramenta de trabalho: corpo em 14px, linhas de tabela de 48px, controles de 32px, página com 32–40px de respiro. A profundidade vem de fios de 1px e de três tons de fundo, não de sombra. A tipografia é uma sans só, Mona Sans, com JetBrains Mono restrita a identificadores. Um admin lê `openrouter/openai/gpt-4.1-mini` e sabe que é um valor literal que a plataforma aceita.

O login e "Minha conta" (HTML do servidor, sem script) usam os mesmos valores, com celular primeiro: alvos de 44px, campo de 16px para o navegador não dar zoom e cartão com fio só a partir de 640px. Sem marca da instalação, aparece o lockup Axon; com nome ou logotipo da instalação, eles ocupam o lugar principal e o Axon fica só no rodapé (ver Brand). Nunca a marca de um domínio.

**Key Characteristics:**
- Neutros frios da marca, um azul de ação, três cores de estado e quatro cores de série de dados.
- Mona Sans 400–700 em tudo; JetBrains Mono só em identificadores.
- Fios de 1px, sem sombra; sombra só no que flutua.
- Raio de 6px nos controles e de 8px nos painéis.
- Temas claro e escuro com os mesmos nomes de token.
- Todo estado de tela é desenhado: vazio, carregando, erro, travado, definido na instalação, acesso negado.

## Brand

O símbolo e o lockup são os de `brand-kit/svg/` (ADR-038), vetorizados do quadro de marca do mantenedor: três terminais, braços grossos e uma base que some atrás do braço esquerdo. **O degradê e o esmaecimento fazem parte do símbolo** e não viram token de interface. Sobre fundo escuro a rampa vai de `#5070FA` a `#C9D3FB`, e sobre fundo claro de `#396EF9` a `#7A91FC`. O wordmark `axon` é geométrico e não depende de fonte.

- **Lugar principal:** barra lateral da console (símbolo de 32px, wordmark de 12px e a legenda "Console" abaixo), cabeçalho do cartão de login e de "Minha conta" (símbolo de 28px e wordmark de 14px) e cartão de acesso negado.
- **Com marca da instalação:** nome e logotipo dela ocupam o lugar principal, e o rodapé do login e da barra lateral leva o símbolo de 16px e "com Axon" em caption terciário.
- **Lockup:** símbolo com 1,85× a altura de x, centrado nela, e vão de 0,45× a altura de x. Largura mínima de 96px; abaixo disso, só o símbolo.
- **Favicon:** ladrilho `#0B0F19` com o símbolo, sem esmaecimento, legível a 16px. É sempre o do Axon, mesmo com marca da instalação.
- **Embutido em linha:** cada instância precisa de ids únicos para o degradê e a máscara (`useId` na console).

## Colors

Paleta de neutros frios (a família ink, slate, line e mist do Axon) com um azul de ação. A cor existe para dizer "aja aqui" ou "isto está bem, em atenção ou com erro", e para mais nada.

### Primary
- **Azul de ação** (`acao-base`): botão primário, interruptor ligado, caixa marcada, cursor de texto, anel de foco no claro. No escuro o valor de fundo continua o mesmo (texto branco a 5,2:1), e o hover escurece como no claro (`acao-hover-escuro`, o mesmo `#1d4ed8`, 6,7:1; ADR-039). O `axon-blue` (`#3882f6`) fica no símbolo, não como fundo de texto.
- **Azul de texto** (`acao-texto`): links, valor sobreposto, o selo e o aviso informativos. No escuro clareia para `acao-texto-escuro`, que também é o anel de foco.
- **Azul sutil** (`acao-sutil`): fundo do selo e do aviso informativos, do avatar de quem está logado e da seleção de texto.

### Neutral
- **Branco base / quase preto** (`fundo-base`): superfície de trabalho, painéis, tabelas, campos.
- **Névoa** (`fundo-sutil`): barra lateral, cabeçalho de tabela, hover de linha, fundo atrás do cartão de login no desktop.
- **Realce** (`fundo-realce`): item de navegação ativo, trilho do seletor segmentado, campo somente leitura, esqueleto, selo neutro.
- **Fio base** (`borda-base`): todo contorno de painel e tabela, divisória de linha, separador de abas.
- **Fio forte** (`borda-forte`): contorno de campo e de botão secundário, interruptor desligado, polegar da barra de rolagem.
- **Texto primário, secundário e terciário** (`texto-primario`, `texto-secundario`, `texto-terciario`): valor e título; legenda, ajuda e cabeçalho de coluna; placeholder, eixo do gráfico e conteúdo esmaecido.

### Estado
- **Verde ok**, **âmbar aviso** e **vermelho erro**, cada um em três papéis: `-texto` (a palavra), `-fundo` (o selo ou aviso) e `-marca` (a bolinha, o ícone, a borda de campo inválido).

### Séries de dados
- **Série 1 a 4** (`serie-1` a `serie-4`: azul, laranja, verde e ouro). Usadas só no gráfico de custo e em sua legenda e tabela, atribuídas por ordem de custo. A partir da quinta, "Outros" fica com a cor 4. Nunca se gera uma cor nova.

### Named Rules
**The Cor Tem Função Rule.** A cor marca ação (azul) ou estado (ok, aviso, erro). Títulos, ícones de navegação, cabeçalhos e números ficam em neutro. As únicas exceções são as séries do gráfico e o logotipo de terceiros (o "G" do Google).

**The Estado Nunca Só Por Cor Rule.** Todo estado leva bolinha de 6px ou ícone junto com o texto: "Disponível" com bolinha, "Definido na instalação" com cadeado, "Incompleto: 1 modelo sem preço" com triângulo. Cor sozinha não carrega significado.

**The Sobreposto É Informação Rule.** Valor sobreposto pela console usa o azul de texto com bolinha azul. É a única leitura de estado do azul, e ele nunca entra no verde, âmbar ou vermelho.

## Typography

**Body Font:** Mona Sans 400/500/600/700 (com ui-sans-serif e system-ui), servida pela própria console e pelas páginas de login
**Label/Mono Font:** JetBrains Mono 400/500 (com ui-monospace e Menlo)

**Character:** Uma sans de trabalho, levemente larga, que segura título e número sem precisar de display, e uma mono que aparece só onde o texto é um identificador literal.

### Hierarchy
- **Display** (600, 3rem, 1.1, −0.025em): a figura principal da faixa de números, o custo do período. Uma por tela.
- **Stat** (600, 1.75rem, 1.1, −0.014em): os demais números da faixa (requisições, chamadas, tokens).
- **Headline** (600, 1.5rem, 1.2, −0.017em): título da página e `h1` do login.
- **Title** (600, 1rem, 1.3): título de painel, de seção e de diálogo.
- **Body** (400, 0.875rem, 1.5): texto corrente, células de tabela, itens de navegação, campos.
- **Body-sm** (400, 0.8125rem): subtítulos, ajudas longas, notas, metadados ("Sobreposto por ana em 14/10 às 22:42").
- **Label** (500, 0.8125rem): rótulo de campo, rótulo da faixa de números, item do segmentado.
- **Caption** (500, 0.75rem): cabeçalho de coluna, selo, eixo e legenda do gráfico, erro e ajuda de campo (estes em 400).
- **Mono** (400–500, 0.8125rem; 0.92em quando em linha): identificadores.

### Named Rules
**The Mono É Identificador Rule.** JetBrains Mono vai só em identificadores: referências de modelo, papéis (`generation`), aliases de MCP e de tools, endereços, nomes de usuário, valores do YAML. Números medidos (custo, tokens, contagens) e datas ficam em Mona Sans.

**The Algarismo Proporcional Rule.** Os números usam os algarismos proporcionais padrão da Mona Sans. Não se liga `tnum`, porque o algarismo tabular dela traz o zero cortado. O alinhamento das colunas numéricas vem do alinhamento à direita.

**The Título Com Folga Rule.** Todo título em 600 (`h1`–`h3`) leva `word-spacing: 0.06em`. O espaço da Mona Sans nesse peso é estreito, e sem a folga "Custo por dia" se lê "Custo pordia".

**The Identificador Inteiro Rule.** Um identificador mono nunca quebra no meio. Ele desce inteiro para a linha de baixo e, se ainda não couber, termina em reticências. A única quebra permitida é a de endereço (abaixo de 1100px, sob o nome do servidor), e só depois de "/" ou ".".

## Layout

**Console.** É uma grade de duas colunas: barra lateral fixa de 240px (nome da instalação, navegação, tema e pessoa) e área principal. A página tem largura máxima de 1440px, respiro de 32px em cima, 40px dos lados e 48px embaixo, e coluna com 24px entre blocos. O cabeçalho da página põe título e subtítulo à esquerda e ações ou filtros à direita, na mesma linha, quebrando se faltar espaço. O ritmo segue a escala de 4px (`espaco-1` a `espaco-12`): 8px entre controles vizinhos, 16px entre campos, 20px de respiro interno de painel e 24px entre seções.

**Abaixo de 1100px:**
- A barra lateral vira um trilho de ícones de 64px. Nome, rótulos e dados da pessoa ficam só para leitor de tela, e o seletor de tema empilha na vertical.
- Colunas secundárias de tabela somem (marcadas `wideOnly`).
- O valor tirado da tabela reaparece sob o nome, em linha menor: o YAML na aba Modelos e o endereço em Servidores MCP.
- A faixa de números passa de 4 para 2 colunas, e formulários e grades de três colunas passam a uma ou duas.

**Abaixo de 1024px** o respiro da página cai para 24px.

**Login e "Minha conta".** É uma coluna de até 420px. No celular, a página inteira é a superfície. A partir de 640px o conteúdo vira cartão centrado com fio e 32px de respiro, sobre o fundo `fundo-sutil`.

## Elevation & Depth

O sistema é plano. A profundidade vem de três tons de fundo (base, sutil, realce) e de fios de 1px. Painéis, tabelas, faixa de números, cartões de login e de servidor MCP ficam no plano, sem sombra.

### Shadow Vocabulary
- **Sombra flutuante** (`--sombra-flutuante`: no claro, `0 8px 24px -6px rgb(24 24 27 / 0.14), 0 2px 6px -2px rgb(24 24 27 / 0.08)`; no escuro, `0 12px 32px -8px rgb(0 0 0 / 0.6), 0 2px 8px -2px rgb(0 0 0 / 0.5)`): diálogo, dica do gráfico e menu de ações.
- **Véu** (`--veu`: `rgb(24 24 27 / 0.36)` no claro, `rgb(0 0 0 / 0.6)` no escuro): o fundo atrás do diálogo.

### Named Rules
**The Sombra Só No Que Flutua Rule.** Sombra existe só em camada que sai do plano e se sobrepõe ao conteúdo: diálogo, dica e menu. Nada que mora na página tem sombra. O anel de foco do campo (`0 0 0 1px` na cor de foco) é contorno, não elevação.

## Shapes

Os cantos são levemente arredondados, sempre em degraus fixos. O controle tem 6px (`rounded.controle`): botão, campo, item de navegação, menu, seletor segmentado. Painel, tabela, aviso, menu flutuante e dica têm 8px (`rounded.painel`). Detalhes miúdos têm 4px: caixa de seleção, esqueleto, topo da barra do gráfico, contorno de foco de link. Selo e interruptor são pílula. Os fios têm sempre 1px. A única linha de 2px é o sublinhado da aba ativa.

## Components

### Buttons
Contidos e diretos, sem gradiente nem sombra.
- **Shape:** 6px; 32px de altura (28px no pequeno, 36px no grande), 12px de respiro lateral, texto em 500.
- **Primary:** fundo azul de ação com texto branco. É uma ação principal por área, e desabilitado fica a 45% de opacidade.
- **Secondary:** fundo base, fio forte, texto primário; no hover, fundo sutil.
- **Ghost:** sem fundo, texto secundário; no hover, fundo realce e texto primário. Usado em ações de linha e no fechar do diálogo.
- **Danger:** como o secundário, com texto vermelho; no hover, fundo e borda de erro.
- **Carregando:** o rótulo divide espaço com um giro de 14px em `currentColor`.
- **Login:** largura total, 44px no celular e 40px a partir de 640px.
- **Transição:** 120ms em `--curva-saida` (`cubic-bezier(0.16, 1, 0.3, 1)`), só de cor.

### Selos (Badge)
- **Style:** pílula de 22px, texto em caption, com bolinha de 6px ou ícone de 12px à esquerda.
- **Tons:** ok, aviso, erro, info (azul sutil, para "Sobreposto" e o grupo protegido) e neutro.
- **Bloqueios:** "Definido na instalação" é o selo neutro com cadeado. Seção travada mostra o cadeado e "Só muda por novo deploy". Na lista de Assistants, o selo é "Travado".

### Cards / Containers (Panel, Table)
- **Corner Style:** 8px.
- **Background:** fundo base.
- **Shadow Strategy:** nenhuma (ver Elevation & Depth).
- **Border:** fio base de 1px. Em painéis com corpo separado, outro fio entre cabeçalho e corpo.
- **Internal Padding:** 20px. A tabela usa 16px lateral, com cabeçalho de 36px em fundo sutil e caption secundário, e linhas de 48px.
- **Números em tabela:** alinhados à direita, sem quebra, em Mona Sans.

### Inputs / Fields
- **Style:** 36px de altura (32px compacto), fio forte, fundo base, 6px; rótulo em label acima, com 6px de vão, e ajuda em caption abaixo.
- **Hover / Focus:** no hover, a borda escurece para o texto terciário. No foco, a borda e o anel de 1px ficam na cor de ação.
- **Error / Disabled:** inválido tem borda e anel em vermelho, com a mensagem da API logo abaixo do campo. Somente leitura e desabilitado ficam com fundo realce, texto secundário e fio base.
- **Identificador:** campo de identificador em mono, a 13px.
- **Campo de modelo:** usa `datalist`, texto livre com sugestões dos modelos conhecidos, não `select`. A allowlist é do deploy, e a recusa vem da API, junto ao campo.
- **Select:** nativo, com a seta desenhada.
- **Login:** campo de 40px, texto em 16px.

### Navigation
- **Barra lateral:** 240px, fundo sutil, fio à direita. O item tem 32px de altura, ícone SVG de 16px (traço 1,5, `currentColor`) e texto secundário. Item ativo e hover ganham fundo realce e texto primário; o ativo vai em 500. Abaixo de 1100px vira trilho de ícones com dica nativa.
- **Abas (TabNav):** texto em 500, 40px de altura, fio base embaixo; a aba ativa leva um traço de 2px em texto primário.
- **Seletor segmentado:** trilho realce de 32px com 2px de respiro; o item ativo vira fundo base com fio base (no escuro, fio base com contorno forte). Usado para período 7/30/90, agrupamento, filtros e tema.

### Notice
Faixa de 8px de raio, ícone de 16px, título em 500 e texto em body-sm, nos tons info, ok, aviso, erro e neutro (com cadeado). O aviso de erro de carregamento leva a ação "Tentar de novo".

### Interruptor e caixa de seleção
- **Interruptor:** pílula de 32×18 em fio forte; ligado, azul de ação, com 160ms de deslize.
- **Caixa de seleção:** quadrado de 16px, raio de 4px; marcada, azul de ação com visto branco.

### Estados de tela
- **Vazio:** título em 500 e texto secundário de até 52ch, centrados, com ação opcional.
- **Carregando:** esqueleto em fundo realce, pulsando a 1,6s (parado com movimento reduzido), na forma do conteúdo.
- **Erro:** aviso de erro com o motivo da API e o botão "Tentar de novo".
- **Acesso negado:** cartão centrado sobre o fundo sutil, com a marca (lockup Axon ou a da instalação), o título "Sua conta não tem acesso à console" e a ação "Sair".
- **Definido na instalação** e **Só muda por novo deploy:** sempre com cadeado, nunca só com texto.

### Gráfico de custo por dia (componente assinatura)
Barras empilhadas em SVG próprio.
- **Barras:** largura de até 24px, topo do segmento de cima arredondado a 4px, base reta na linha zero, vão de 2px na cor do fundo entre segmentos.
- **Grade e eixos:** grade horizontal de 1px em fio base, com 3 divisões; eixo em caption terciário.
- **Legenda:** à direita do cabeçalho do painel, quadrados de 10px. Modelo sem preço aparece vazado, como "sem preço, fora do custo".
- **Marcos de mudança:** linha vertical de 1px em texto terciário, com rótulo em pílula de fio base (raio de 6px) numa faixa acima das barras. Cada rótulo fica a 6px da própria linha, de um lado ou do outro, em fileiras, sem tocar outro rótulo nem cruzar a linha de outro marco.
- **Dica:** pelo mouse e pelas setas do teclado (o gráfico recebe foco). Camada flutuante de 8px com sombra flutuante, mostrando dia, segmentos e total.
- **Acessibilidade:** tabela equivalente para leitor de tela.

## Do's and Don'ts

### Do:
- **Do** usar o azul (`acao-base`) só para ação e o verde, âmbar e vermelho só para estado, sempre com bolinha de 6px ou ícone junto do texto.
- **Do** pôr JetBrains Mono em identificadores (modelos, papéis, aliases, endereços, nomes de usuário, valores do YAML) e Mona Sans em todo o resto, inclusive números e datas.
- **Do** dar `word-spacing: 0.06em` a todo título em 600.
- **Do** desenhar contornos com fio de 1px (`borda-base` em superfície, `borda-forte` em controle) e reservar a sombra flutuante para diálogo, dica e menu.
- **Do** usar 6px de raio em controle e 8px em painel, tabela, aviso e camada flutuante.
- **Do** desenhar todos os estados de cada tela: vazio, carregando com esqueleto, erro com "Tentar de novo", travado e "Definido na instalação" com cadeado, acesso negado.
- **Do** esconder colunas secundárias abaixo de 1100px e devolver o valor sob o nome, sem perder informação.
- **Do** oferecer, em todo gráfico, dica pelo teclado e tabela equivalente para leitor de tela.
- **Do** usar `datalist` em campo que aceita texto livre com sugestões (referência de modelo).

### Don't:
- **Don't** ligar `tnum` na Mona Sans: o algarismo tabular dela traz o zero cortado.
- **Don't** quebrar identificador mono no meio. Endereço só quebra depois de "/" ou ".".
- **Don't** pôr sombra em painel, tabela, cartão ou faixa de números.
- **Don't** usar cartões de métrica com ícone, gradiente ou cor decorativa: a faixa de números é uma tabela de uma linha, com fios.
- **Don't** gerar cor de série além das quatro validadas; o excedente vira "Outros".
- **Don't** usar `select` para referência de modelo.
- **Don't** pôr marca, termo ou imagem de domínio na console ou no login. A marca é o Axon ou a da instalação (ADR-038).
- **Don't** redesenhar, recolorir, achatar ou tirar o esmaecimento do símbolo; use os arquivos de `brand-kit/svg/`.
