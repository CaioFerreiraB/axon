---
version: 1
slug: "axon-ai-console"
primary_target: "axon-ai/console"
related_targets: []
---

# Console de administração — superfície

Escopo: a SPA `axon-ai/console/` (spec 013) e as páginas HTML da identidade (spec 012: login, troca de senha, "Minha
conta"). Modo: Operate. Público: admins técnicos de uma instalação pequena (console, desktop e tablet); pessoas do chat
(login e "Minha conta", celular primeiro). Tarefa: aplicar o que o deploy permite e acompanhar uso e custo. Tela
inicial: uso e custo do período. Estados obrigatórios: vazio, carregando, erro, travado, "Definido na instalação",
acesso negado, sem preço. Tema claro e escuro, seguindo o sistema.

## Direction contract

THESIS: A console de administração como os melhores produtos da categoria a fazem — Vercel e Linear —, sem nada de
outro mundo; recusa o painel SaaS genérico de cartões com ícone e gradiente e a frieza de terminal.

OWN-WORLD: Neutros de grafite sobre branco (escuro: quase preto com cinzas frios), um azul de ação, verde, âmbar e
vermelho só para estado, séries de dados da paleta validada. Uma família sans de trabalho com algarismos tabulares e uma
mono só para identificadores e valores medidos. Fios de 1px, raio 6–8px, sem sombra exceto em camadas flutuantes.

STORY: O admin entende em segundos quanto a plataforma gastou e o que mudou; acha o Assistant, vê o que o YAML define, o
que foi sobreposto e o que vale, troca dentro do permitido e sabe sempre por que algo está travado.

FIRST VIEWPORT: Barra lateral de 240px (nome da instalação, navegação, usuário e tema); cabeçalho com título, período
7/30/90 e filtros numa linha; faixa única de números (custo como figura principal, requisições, chamadas, tokens, cada
um com o histórico); gráfico de barras empilhadas por dia com legenda; tabela por modelo começando na dobra.

FORM: o padrão da categoria (saída escolhida pelo usuário sobre a mão sorteada), referências Vercel e Linear. seed: none (unavailable)

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
