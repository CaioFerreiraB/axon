# ADR-017 — O Trace Sink cresce por eventos aditivos

- **Status:** Aceita · 2026-10-01
- **Specs afetadas:** [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md)
  (contracts/trace-api.md, contracts/record-format.md, data-model.md),
  [004-core-capability-gateway](../../specs/004-core-capability-gateway/spec.md) (evento `ToolCall`, FR-014),
  [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md) (evento `ControllerDecision`, FR-016)
- **Origem:** clarificação de 2026-10-01 da 005 (pergunta 4), que também resolve a pendência aberta na passada da 004

## Contexto

O seam Trace Sink (009) é uma união fechada de eventos tipados: `type TraceEvent = ExecutionStarted | ModelCall | …`.
Cada spec que emite precisa de um evento com os campos dela, e esses eventos chegam aos poucos, fase a fase — o
ADR-013 já previa trace de tool na Fase 3 e de recuperação na Fase 5.

O contrato da 009 diz duas coisas que não fecham:

1. "Mudar qualquer linha daqui é mudar um seam: exige ADR e atualização das specs consumidoras."
2. "Acrescentar um tipo de evento (tool na Fase 3, recuperação na Fase 5) é acrescentar uma dataclass e um membro ao
   `TraceEvent` — a assinatura de `emit` não muda, e nenhum emissor existente é afetado."

A passada da 004 acrescentou `ToolCall` seguindo a segunda frase, sem ADR, e deixou a tensão registrada. A passada da
005 (Fase 3) precisa de outro evento — a decisão do controller, por iteração. Sem regra, cada evento novo reabre a
mesma discussão, ou entra sem rastro de decisão.

## Decisão

1. Acrescentar um **tipo de evento** ao Trace Sink é mudança aditiva e **não** exige ADR próprio, desde que:
   - nenhum evento ou campo existente mude de nome, tipo ou significado;
   - o evento seja uma dataclass congelada, `kw_only`, com `request_id` e validação na construção, como os demais;
   - o evento **nunca** carregue argumentos de tool, conteúdo de resultado, texto de prompt ou de resposta, nem
     credenciais — só identificadores, contagens, status, durações e motivos curtos escritos pelo emissor;
   - a spec que emite declare o toque na 009 no plano dela (como "toque declarado"), e a passada atualize, na 009,
     `contracts/trace-api.md`, `contracts/record-format.md`, `data-model.md` e o teste de nomes públicos.
2. Remover ou renomear um evento ou campo, mudar o significado de um campo, ou mudar a assinatura de `emit` e da
   consulta continua exigindo ADR.
3. Este ADR cobre os dois eventos já decididos: `ToolCall` (004, Fase 3) e `ControllerDecision` (005, Fase 3).

## Alternativas rejeitadas

*Um ADR por evento.* Burocracia sem decisão: o formato do registro já é genérico (`type` derivado do nome da classe,
atributos num mapeamento), então um evento a mais não muda nenhum emissor nem leitor existente.

*Sem evento novo; reconstruir a decisão do controller pela combinação de `ModelCall`, `ToolCall` e `ExecutionError`.*
Inferência frágil: a decisão "responder" seria a ausência de um `ToolCall`, e as métricas da Fase 6 (iterações por
resposta, taxa de ação inválida) dependeriam dessa reconstrução.

*Um evento genérico (`Custom` com nome e mapeamento livre).* Perde a validação na construção e abre a porta para
qualquer emissor despejar conteúdo no trace, que é justamente o que a regra de privacidade proíbe.

## Consequências

- A frase "mudar qualquer linha exige ADR" do contrato da 009 passa a valer com a exceção acima, anotada lá com
  remissão a este ADR.
- A união `TraceEvent` cresce; consumidores que fazem `match` exaustivo sobre ela (hoje, só a própria 009) precisam do
  caso novo — por isso a atualização na 009 faz parte da passada que acrescenta o evento.
- A regra de privacidade fica explícita para todo evento futuro, inclusive o de recuperação da Fase 5.
