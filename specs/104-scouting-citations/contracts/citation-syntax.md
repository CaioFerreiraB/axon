# Contrato — sintaxe de citação (104 → instruções da 101 na Fase 5)

O que as instruções do pack ensinam ao modelo na Fase 5 (FR-007) e o que a geração recebe; decisão em
[research.md](../research.md) R3.

- O modelo cita com `[[<chunk_id>]]`, logo depois da afirmação que o trecho apoia.
- Cada trecho entregue à geração vem rotulado, no prompt, com o mesmo `chunk_id` (responsabilidade do flow da Fase 5).
- Só identificadores de trechos entregues contam; qualquer outro é removido e registrado.
- O usuário não vê `[[…]]`: vê `[n]`, e a lista estruturada de citações traz a proveniência de cada `[n]` (FR-009).

Na Fase 4 nada disso é ensinado: as instruções da 101 proíbem citar (101 FR-011).
