# ADR-039 — No tema escuro, o hover do botão primário escurece, como no claro

- **Status:** Aceita · 2026-10-20
- **Specs afetadas:** [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (`tokens.css`) e
  [012-core-identity](../../specs/012-core-identity/spec.md) (`identity.css`), que usam os mesmos tokens; `DESIGN.md`.
  Substitui o [ADR-038](ADR-038-marca-da-plataforma-e-marca-da-instalacao.md) **só no item 4, quanto ao hover do
  tema escuro**: o resto do ADR-038 continua valendo
- **Origem:** decisão do mantenedor (2026-10-20), na passada da 013 do renome (ADR-037), sobre a pendência registrada na
  passada da 012

## Contexto

O ADR-038 (item 4) manteve o azul de ação `#2563EB` (texto branco a 5,2:1) e pôs o `axon-blue` (`#3882F6`) "no hover e no
foco do tema escuro". No foco, o `axon-blue` é anel sobre o fundo `axon-night` (5,2:1), e isso passa. No hover, ele é
fundo do botão primário, e o texto branco fica a 3,69:1, abaixo dos 4,5:1 do WCAG 2.2 AA para texto. A console e as
páginas da 012 já tinham esse defeito antes da marca (`#3B82F6`, 3,68:1). O teste de contraste da 012 o deixou de fora,
como pendência desta decisão.

## Decisão

1. No tema escuro, o hover do botão primário usa o mesmo `#1D4ED8` do claro (`acao-hover`; texto branco a 6,70:1). O botão
   escurece ao receber o mouse nos dois temas.
2. O `axon-blue` (`#3882F6`) não é fundo de texto em nenhum tema. Ele continua no símbolo e no anel de foco do escuro
   (`foco-escuro` segue `#93B4FB`, que é o valor aprovado).
3. `tokens.css` (013) e `identity.css` (012) mudam juntos, e o par "texto sobre o hover" entra nos testes de contraste dos
   dois. O `DESIGN.md` registra `acao-hover-escuro: #1d4ed8`.

## Alternativas rejeitadas

*Clarear menos, para `#2F6FE8`* (texto branco a 4,61:1). Passa no limite e mantém a ideia de clarear no escuro, mas não é
mais o `axon-blue` e deixa o hover a 0,1 da reprovação.

*Manter o `#3882F6`.* Aceitaria texto abaixo do AA no componente mais repetido da interface.

*Texto escuro no hover* (`#0B0F19` sobre `#3882F6`, 5,19:1). Trocar a cor do texto ao passar o mouse é um efeito que o
desenho não tem em nenhum outro componente.

## Consequências

- O hover escuro perde o efeito de "acender", e o contraste com o fundo da página fica menor (o botão continua delimitado
  pela própria forma e pelo texto).
- A pendência registrada na passada da 012 se fecha na passada da 013, para os dois CSS.
