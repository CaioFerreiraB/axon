# Contrato — validators `citation_integrity` e `validity_notice` (Fase 4)

Implementam `AnswerValidator` da 001 em `ai_scouting.validators`. **Não publicados** pelo pack na Fase 4 (FR-008): a
101 os liga no `pack.py` na Fase 5, nesta ordem — `citation_integrity`, depois `validity_notice`. Regras em
[data-model.md](../data-model.md); decisões em [research.md](../research.md).

## Garantias comuns

| Garantia | Verificada por |
|---|---|
| Determinístico: mesma Turn View, mesmo `ValidationResult` | `tests/test_integrity.py`, `tests/test_notice.py` |
| Nunca levanta: resposta `None` ou vazia, contexto vazio, citações vazias | idem |
| Sem modelo, sem relógio, sem I/O (FR-006) | import-linter, `tests/test_purity.py` |
| Fonte da verdade: `view.generation_context` | `tests/test_integrity.py` (trecho recuperado mas cortado é inválido) |

## Textos (R7)

| Constante | Texto |
|---|---|
| `UNGROUNDED_NOTICE` | `Atenção: esta resposta não se apoia em nenhum documento do acervo consultado. Confirme a informação na fonte oficial.` |
| `NON_CURRENT_NOTICE` | `Atenção: [{n}] cita {source}, que está {status} — não é a versão vigente.` |
| `UNCONFIRMED_NOTICE` | `Atenção: [{n}] cita {source}, cuja vigência não foi confirmada.` |

`{source}` = `documento (versão)` ou só `documento` sem versão; `{status}` como veio no trecho. Avisos acrescentados
ficam ao fim, separados da resposta por uma linha em branco, um por linha.

## Registros

| Validator | `issues` | `flags` |
|---|---|---|
| `citation_integrity` | `citação fora do contexto da geração: <id como escrito>` (uma por marcador inválido); `nenhuma citação válida` | `invalid_citation`, `ungrounded` |
| `validity_notice` | — | `non_current_source` |

O core transforma cada `issue` num registro `notice` (`<pack>.<validator>: <issue>`) e soma as `flags` ao evento final.

## Casos de aceite

| # | Turn View | Esperado |
|---|---|---|
| 1 (US1 cen. 1) | resposta com `[[a]]`, `[[b]]`, `[[x]]`; contexto com `a`, `b` | `[1]`, `[2]`, sem `[[x]]`; 2 citações; issue sobre `x`; `invalid_citation` |
| 2 (US1 cen. 2) | `[[c]]`; `c` em `reranked`, não em `generation_context` | removida; `ungrounded` |
| 3 (US2) | só citações inválidas, ou nenhuma | aviso "não fundamentada" ao fim; `ungrounded` |
| 4 (US3 cen. 1) | citação válida de trecho `substituído`, sem aviso | linha `NON_CURRENT_NOTICE` acrescentada |
| 5 (US3 cen. 2) | o mesmo, com aviso já presente | resposta inalterada (`answer=None`) |
| 6 (US4) | citação válida | `Citation` com os seis campos do trecho |
| 7 (bordas) | `[[ A ]]` com `a` no contexto; `[[a]]` duas vezes | válida; um `[1]` repetido no texto, uma citação |
| 8 (clarificação 2) | trecho com `status=None` | `UNCONFIRMED_NOTICE` |
