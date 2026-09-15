# ADR-014 — Política de versões 0.x de `ai-core-contracts`

- **Status:** Aceita · 2026-09-15
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md) (FR-016, FR-018, FR-020),
  [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md) (verificação de compatibilidade),
  [101-scouting-pack](../../specs/101-scouting-pack/spec.md) e todo pack externo (faixa declarada); constituição
  ("Restrições de ambiente", linha "Versionamento")
- **Origem:** `/speckit-clarify` da 001 (2026-09-15), que fixou a política; `/speckit-analyze` da 001, que apontou o
  conflito dessa política com o texto da constituição

## Contexto

A constituição dizia: "semver estrito em `ai-core-contracts`; breaking change = major; janela de depreciação de um
minor", e fixava a faixa dos packs em `>=0.1,<0.2`. O design.md da 001 dizia "campo novo = minor; remoção = major".

As duas regras não se sustentam juntas em 0.x. Com a faixa `>=0.1,<0.2`, "campo novo = minor" tira todo pack da faixa a
cada mudança aditiva — o que o próprio design.md reconheceu, delegando a decisão ao plano. A clarificação da 001 escolheu
a convenção 0.x deslocada, que diverge da frase "breaking change = major" da constituição. Divergir de uma decisão
pré-aprovada da constituição exige ADR e emenda.

## Decisão

1. **Enquanto o major for 0**: mudança aditiva (campo, hook ou tipo opcional novo; correção) sobe o **patch**; mudança
   breaking (remoção, renomeação, mudança de semântica ou de forma incompatível) sobe o **minor**.
2. **A partir de 1.0**: aditiva sobe o minor; breaking sobe o major (semver padrão).
3. **Faixa do pack derivada da `contract_version`**: `0.N[.P]` → `>=0.N[.P],<0.(N+1)`; `X.Y[.Z]` com X ≥ 1 →
   `>=X.Y[.Z],<(X+1)`. É a mesma leitura dos requisitos `^0.y` do Cargo e do npm.
4. **Janela de depreciação de uma série compatível**: um símbolo só é removido depois de depreciado em ao menos uma
   versão da série anterior (depreciado em 0.N.x → removível a partir de 0.(N+1).0; depreciado em X.Y → removível a
   partir de (X+1).0).
5. **Verificação**: o CI da distribuição compara o bump exigido com o declarado e barra remoção sem depreciação prévia
   (001 FR-020).

## Alternativas rejeitadas

*Breaking = major também em 0.x.* É coerente com o texto original da constituição: em 0.x só haveria patches, e a
primeira quebra depois da 0.1 viraria 1.0.0. Mas leva os contratos a 1.0 na primeira quebra depois da tag, ainda na
fase em que eles mais mudam, e gasta o sinal de "API estável" que o 1.0 deveria dar.

*Campo novo = minor com faixa `>=0.1,<1` nos packs.* Os packs continuariam na faixa depois de campos novos, mas a faixa
deixaria de protegê-los contra breaking changes.

*Semver padrão para 0.x ("qualquer coisa pode mudar").* Nenhuma faixa protegeria os packs.

## Consequências

- Packs com `>=0.1,<0.2` recebem mudanças aditivas como patch, sem mexer na faixa
- Uma breaking change em 0.x tira os packs da faixa até que adotem a série nova — o que só pode acontecer depois da
  janela de depreciação
- A constituição é emendada na linha "Versionamento" (via `/speckit-constitution`)
- No design.md da 001, ficam superadas por este ADR as linhas "campo novo = minor; remoção, renomeação ou mudança de
  semântica = major", "Semver estrito em `ai-core-contracts` — breaking change = major" e "Janela de depreciação — um
  minor antes de remover"
- Custo: a regra "breaking = minor" vale só até o 1.0; quem lê a versão precisa saber em que regime ela está — por isso a
  regra mora no código (`compat.py`) e na mensagem de incompatibilidade, não na memória de quem publica
