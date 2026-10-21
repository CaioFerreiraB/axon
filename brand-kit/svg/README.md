# Axon — arquivos da marca

Vetores oficiais do símbolo e do lockup, aprovados pelo mantenedor em 2026-10-20 (ADR-038). O símbolo foi traçado sobre
`../referencias/quadro-de-marca-chatgpt.png` e ajustado em curvas de Bézier contínuas; o degradê, o esmaecimento da base e
as proporções do lockup foram medidos na mesma imagem. O wordmark `axon` é geométrico, com as medidas da referência
(altura de x 58,5, traço 12, "x" a 53,2°), e não depende de fonte.

| Arquivo | Uso |
|---|---|
| `axon-symbol.svg` | Símbolo em cor sobre fundo escuro (degradê `#5070FA` → `#C9D3FB`) |
| `axon-symbol-light.svg` | Símbolo em cor sobre fundo claro (degradê `#396EF9` → `#7A91FC`) |
| `axon-symbol-mono.svg` | Símbolo em uma cor (`currentColor`), com o esmaecimento da base |
| `axon-lockup-dark.svg` | Símbolo + `axon` em branco, para fundo escuro |
| `axon-lockup-light.svg` | Símbolo + `axon` em `#111827`, para fundo claro |
| `axon-lockup-mono.svg` | Lockup em uma cor (`currentColor`) |
| `axon-wordmark-light.svg` | Só o wordmark `axon` em `#111827`, para fundo claro: recorte do lockup, mesmo traço (`viewBox` do wordmark) |
| `axon-wordmark-dark.svg` | Só o wordmark `axon` em branco, para fundo escuro: recorte do lockup, mesmo traço |
| `favicon.svg` | Ladrilho `#0B0F19` com o símbolo, sem esmaecimento (legível a 16 px) |

Regras:
- O esmaecimento da base faz parte do desenho: ela some atrás do braço esquerdo. Não remova o esmaecimento, nem o
  troque por uma base sólida, fora do favicon.
- Cada arquivo tem ids com prefixo próprio (`axon-s-`, `axon-ld-`…), então dois SVGs podem ser embutidos na mesma
  página. Um componente que gere o símbolo várias vezes precisa de ids únicos por instância.
- O símbolo ocupa o grid de 32 com respiro de cerca de 1,7 unidade. Num lockup, o vão até o wordmark é de 0,45× a altura
  de x, e o símbolo mede 1,85× essa altura, centrado nela.
