# ADR-038 — A marca da plataforma é Axon; a da instalação ocupa o lugar principal quando existe

- **Status:** Aceita · 2026-10-20
- **Specs afetadas:** [012-core-identity](../../specs/012-core-identity/spec.md) (FR-023: login, troca de senha e
  "Minha conta"), [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (barra lateral, acesso negado,
  título da aba, favicon, tokens), [008-core-http-api](../../specs/008-core-http-api/spec.md) (`me.instance.custom`, aditivo),
  [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (nome padrão de `AXON_DISPLAY_NAME`); `PRODUCT.md` e
  `DESIGN.md`
- **Origem:** decisão do mantenedor (2026-10-20), junto com o [ADR-037](ADR-037-a-plataforma-se-chama-axon.md):
  Axon é o padrão, a instalação sobrepõe; tokens da marca mapeados com contraste AA; tipografia mantida; símbolo
  vetorizado a partir do quadro de marca do mantenedor (`brand-kit/referencias/`) e aprovado por ele

## Contexto

Até aqui, a regra era "a marca visível é a da instalação; sem ela, um nome neutro da plataforma" (012 FR-023, 013,
`PRODUCT.md`). O nome neutro era o provisório "Agentic", desenhado como a inicial num quadrado de grafite. A plataforma
não tinha identidade própria, e o princípio I (núcleo agnóstico de domínio) só proibia marca **de domínio**.

O brand kit traz símbolo, paleta, tipografia e voz. A console e as páginas de login já têm um desenho aprovado no Penpot
(`DESIGN.md`, "o padrão da categoria, bem-acabado"), com contraste AA medido nos dois temas. Em três pontos, aplicar o
kit ao pé da letra quebraria esse acordo:

- `axon-blue` (`#3882F6`) com texto branco dá 3,7:1, abaixo dos 4,5:1 do AA para texto do botão primário. O azul de
  ação atual (`#2563EB`, 5,2:1) é o degrau mais escuro da mesma família.
- `axon-violet` (`#8B5CF6`) com texto branco também fica abaixo de 4,5:1, e o `DESIGN.md` reserva cor para ação e
  estado ("a cor tem função").
- O kit pede um símbolo em uma cor e sem gradiente (§3), mas o quadro de marca que o mantenedor trouxe tem o símbolo
  em degradê, com a base esmaecendo atrás do braço esquerdo. O mantenedor quer o símbolo igual a esse quadro.
- O kit sugere Inter, mas aceita manter a tipografia existente (§5). A Mona Sans já é servida pela console e pelas
  páginas, com regras próprias (algarismos, folga nos títulos).

## Decisão

1. **Sem marca da instalação, aparece o lockup Axon**: o símbolo mais o wordmark `axon`, no lugar da inicial em quadrado.
   É o caso de `AXON_DISPLAY_NAME` e `AXON_LOGO_FILE` não definidos, e o nome padrão passa de "Agentic" a "Axon".
2. **Com nome ou logotipo da instalação, eles ocupam o lugar principal**, como hoje, e o Axon fica discreto: "com Axon"
   e o símbolo pequeno no rodapé do cartão de login, da troca de senha, de "Minha conta" e da barra lateral da console.
   A atribuição não aparece quando o lugar principal já é o Axon. Para a console saber em qual dos dois casos está, o
   `GET /admin/v1/me` ganha `instance.custom` (aditivo): `true` quando a instalação definiu nome ou logotipo.
3. **O favicon é sempre o símbolo Axon**, na console e nas páginas da 012. O logotipo da instalação tem formato e
   proporção livres e não serve de favicon.
4. **Tokens: os da marca entram mapeados aos papéis do `DESIGN.md`, sem rebaixar contraste.**
   - O azul de ação continua `#2563EB` (texto branco a 5,2:1). O `axon-blue` fica no hover e no foco do tema
     escuro.
   - Os neutros passam do zinco à família fria da marca: `axon-ink` para o texto forte, `axon-slate` para o
     secundário, `axon-line` para os fios e `axon-mist` para o fundo sutil. Cada par texto/fundo é ajustado até passar
     no AA nos dois temas, inclusive sobre o fundo de realce.
   - O fundo escuro passa a `axon-night` (`#0B0F19`), e as superfícies do escuro derivam dele, um pouco mais claras.
   - O violeta fica como acento de marca, sem função de estado. Verde, âmbar e vermelho continuam os semânticos
     validados. O degradê do símbolo é do símbolo e não vira token de interface.
   - As regras do `DESIGN.md` continuam: a cor tem função, estado nunca só por cor, sombra só no que flutua.
5. **A tipografia fica**: Mona Sans para tudo, JetBrains Mono para identificadores. O wordmark `axon` é geométrico,
   com as medidas do quadro de marca (altura de x 58,5, traço 12, "x" a 53,2°), em contorno, sem depender de fonte.
6. **O símbolo é o do quadro de marca**: três terminais (o da esquerda é o maior), braços grossos, e uma base que sai
   do terminal da direita e some atrás do braço esquerdo. O contorno foi traçado da imagem e ajustado em Béziers
   contínuas. O degradê (`#5070FA` → `#C9D3FB` sobre fundo escuro; `#396EF9` → `#7A91FC` sobre claro) e o esmaecimento
   da base, linear de 0,07 a 0,97, foram medidos nela. **O degradê e o esmaecimento fazem parte da marca.**
   - A versão em uma cor (`currentColor`) mantém o esmaecimento.
   - O favicon é um ladrilho `#0B0F19` com o símbolo sem esmaecimento, legível a 16 px.
   - Os arquivos ficam em `brand-kit/svg/` e entram nos assets da console e da 012.

## Alternativas rejeitadas

*Só trocar "Agentic" por "Axon", sem atribuição.* Com nome de instalação, a plataforma desapareceria das telas. A marca
nova perderia o único lugar em que é vista por quem não lê o código.

*Sempre Axon, com a instalação como subtítulo.* Contraria o que o produto promete ao operador (a marca visível é a da
organização) e o desenho aprovado do login.

*`axon-blue` como azul de ação.* Reprova o AA no botão primário, que é o componente mais repetido.

*Símbolo chapado, em uma cor e sem degradê* (o que o kit pede, §3). Foi desenhado e testado nesta decisão, mas o
mantenedor quer o símbolo do quadro de marca. A versão em uma cor continua existindo para impressão e alto contraste.

*Inter no lugar da Mona Sans.* Exigiria refazer as regras tipográficas validadas e trocar as fontes servidas, sem ganho
de identidade que o símbolo e a cor já não deem.

## Consequências

- O princípio I não muda: Axon é a marca da plataforma, não de um domínio. Continua proibida marca de domínio no core,
  na console e no login.
- `DESIGN.md` ganha a seção "Marca" (símbolo, lockups, respiro, tamanho mínimo, atribuição) e os tokens remapeados.
- Um componente que desenhe o símbolo embutido várias vezes na mesma página precisa de ids únicos para o degradê e a
  máscara (`useId` na console).
  `PRODUCT.md` troca "Brand Commitments", e o Penpot ganha a página "Marca" e os "Fundamentos" atualizados.
- `tokens.css` (console) e `identity.css` (012) mudam juntos. Os valores continuam iguais nos dois, como já são.
