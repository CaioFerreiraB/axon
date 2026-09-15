# Design — 104 Scouting Citations

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §22, §23, §8; ADR-007.

## Proveniência (arch-v1 §23)

```json
{
  "chunk_id": "man-pio-2026#4.2.1@p87",
  "document": "Manual Pioneiro",
  "version": "2026",
  "status": "vigente",
  "section": "4.2.1",
  "page": 87
}
```

## A verificação que importa

> **Toda citação emitida pelo modelo deve mapear para um `chunk_id` que esteve de fato no contexto daquela geração.**

Checagem puramente mecânica, custo zero de tokens. A fonte da verdade é `TurnView.generation_context` (contrato 001, ADR-011) — não `retrieved` nem `reranked`.

Citação que não resolve é removida e registrada em `errors`; se nenhuma sobreviver, a resposta é marcada como não fundamentada.

Julgamento por LLM (a resposta é fiel ao trecho?) pertence ao harness offline (009/105).

## Vigência na resposta (arch-v1 §22)

Quando um chunk citado vem de documento não vigente, a resposta precisa marcar isso. Citar norma revogada sem aviso é o pior erro possível neste domínio.

## Sintaxe de citação — proposta (não definida na arch-v1)

A arch-v1 não define como o modelo emite citações. Proposta para o plano:

```text
... conforme o manual [[man-pio-2026#4.2.1@p87]].
```

- Delimitador duplo `[[...]]`, fácil de ensinar a modelo pequeno e de extrair por regex.
- Normalização: remover espaços, comparar sem diferenciar maiúsculas.
- Os chunks entregues à geração vêm rotulados com o mesmo identificador no prompt.

## Validators

```python
class CitationIntegrityValidator:   # AnswerValidator (001)
    name = "citation_integrity"
    # extrai [[id]] → compara com generation_context → remove inválidas → flag "ungrounded" se nenhuma sobra

class ValidityNoticeValidator:       # AnswerValidator (001)
    name = "validity_notice"
    # para cada citação com status != vigente → garante aviso padrão na resposta
```

Ordem declarada pelo pack: `citation_integrity` antes de `validity_notice` (o aviso só considera citações válidas).

## Portas e adapters **[ADR-012]**

Não há portas nem adapters: os dois validators são **núcleo funcional puro** — recebem a Turn View e devolvem um
`ValidationResult`, sem I/O, sem relógio e sem modelo. É o exemplo mais direto do princípio V aplicado ao código, e é
testável só com fixtures de Turn View.

| Porta | Tipo | Adapters | Teste |
|---|---|---|---|
| `AnswerValidator` (contrato 001) | porta de plug-in implementada | `validators/` | fixtures de Turn View (citação inventada, cortada por orçamento, fonte substituída) |
