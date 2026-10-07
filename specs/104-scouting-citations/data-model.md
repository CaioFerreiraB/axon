# Data Model — 104 Scouting Citations, Fase 4

Decisões em [research.md](research.md). Nada persiste; tudo é derivado da Turn View.

## Marcador de citação (R3)

| Elemento | Regra |
|---|---|
| Forma no texto do modelo | `[[<chunk_id>]]` — regex `\[\[\s*([^\[\]]+?)\s*\]\]` |
| Chave de comparação | o id sem nenhum espaço, em minúsculas (`casefold`) |
| Válido | a chave existe entre as chaves dos trechos de `view.generation_context` (o primeiro vence em colisão) |
| Forma no texto entregue | `[n]` para válido (n pela primeira aparição); removido, com o espaço anterior, para inválido |

## `Citation` (contrato 001 — FR-005)

`chunk_id` (o do trecho, canônico), `document`, `version`, `status`, `section`, `page` — copiados do `Chunk` do
contexto de geração. A lista `citations` traz os válidos únicos na ordem de `n`: a posição `n-1` é a citação `[n]`.

## Status de vigência (clarificação 2 — valores da 102)

| Status do trecho (dobrado: minúsculo, sem acento) | Aviso |
|---|---|
| `vigente` | nenhum |
| `revogado`, `substituido`, `rascunho` | "não vigente", com documento, versão e status |
| vazio ou qualquer outro | "vigência não confirmada" |

## Resultado de `citation_integrity`

| Situação | `answer` | `citations` | `issues` | `flags` | `ok` |
|---|---|---|---|---|---|
| `view.answer is None` | `None` | `None` | — | — | `True` |
| todas válidas | com `[n]` | válidas | — | — | `True` |
| algumas inválidas | com `[n]`, inválidas removidas | válidas | uma por inválida | `invalid_citation` | `False` |
| nenhuma válida (ou nenhum marcador) | sem marcadores + aviso "não fundamentada" | `()` | inválidas + "nenhuma citação válida" | `ungrounded` (+ `invalid_citation` se houve) | `False` |

## Resultado de `validity_notice`

| Situação | `answer` | `issues` | `flags` | `ok` |
|---|---|---|---|---|
| sem citações, ou todas vigentes | `None` | — | — | `True` |
| alguma não vigente, aviso já presente para todas | `None` | — | `non_current_source` | `True` |
| alguma não vigente, aviso faltando | resposta + bloco de avisos faltantes | — | `non_current_source` | `True` |

"Aviso já presente" para `[n]`: a linha padrão de `[n]` no texto, ou uma frase com `[n]` e uma marca do status
(`revogad`, `substitu`, `nao vigente`, `nao esta vigente`, `rascunho`; `vigencia nao confirmada` para o desconhecido),
comparando o texto dobrado.

## Ordem

`citation_integrity` → `validity_notice`: o segundo lê `view.citations` e `view.answer` já reescritos pelo primeiro
(o Pack Runtime encadeia — 002).
