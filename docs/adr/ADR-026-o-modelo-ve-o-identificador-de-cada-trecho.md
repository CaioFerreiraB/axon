# ADR-026 — O modelo vê o identificador de cada trecho

- **Status:** Aceita · 2026-10-09
- **Specs afetadas:** [004-core-capability-gateway](../../specs/004-core-capability-gateway/spec.md) (a renderização do
  resultado de uma tool de recuperação ganha o `chunk_id`), [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md)
  (a geração do `rag_first` mostra os trechos no mesmo formato — US3), [101-scouting-pack](../../specs/101-scouting-pack/spec.md)
  (o prompt ensina a citar pelo identificador — FR-008), [104-scouting-citations](../../specs/104-scouting-citations/spec.md)
  (a sintaxe `[[chunk_id]]` passa a ser praticável; os validators não mudam)
- **Origem:** clarificação de 2026-10-09 da 101 (pergunta 5), aceita pelo mantenedor

## Contexto

A citação é verificada mecanicamente (ADR-007): o `citation_integrity` da 104 só aceita `[[chunk_id]]` de um trecho que
esteve em `generation_context`. Mas o modelo nunca vê esse identificador. A 004 renderiza cada trecho de uma tool de
recuperação como `[documento — seção, p. N]` seguido do texto, e a geração do `rag_first` (005) ainda não tem formato.
Sem o id visível, nenhuma citação passa no validator, e toda resposta do scouting sairia "não fundamentada".

## Decisão

1. Todo trecho que o core entrega ao modelo traz o identificador na linha de referência, sempre neste formato:

   ```text
   [<documento> — <seção>, p. <página> · id: <chunk_id>]
   <texto do trecho>
   ```

   Seção e página saem quando ausentes, como hoje; o `· id: <chunk_id>` está sempre lá.
2. A 004 aplica o formato na renderização do resultado de tool de recuperação; a 005 usa o mesmo formato na geração do
   `rag_first`, na passada da US3. Uma função só, no domínio da 004, publicada no `api.py` dela para a 005 reaproveitar
   (seta 005 → 004, que já existe).
3. O formato é uma garantia aos packs: um prompt de pack pode mandar citar "o identificador que aparece depois de `id:`".
   Mudá-lo é mudar essa garantia — exige ADR que substitua este.
4. O texto do `Chunk` não muda: o identificador é apresentação, não dado do trecho.

## Alternativas rejeitadas

*O pack põe o id no texto do `Chunk`.* Resolve sem tocar o core, mas mistura apresentação com dado, e cada pack que
quisesse citar teria de repetir o truque. A verificação mecânica é princípio do core, e mostrar o id é o complemento
dela.

*Citar por documento e página.* O modelo já vê os dois, mas a comparação fica frouxa (duas unidades na mesma página) e
muda a 104.

## Consequências

- O `citation_integrity` passa a funcionar ponta a ponta no `agentic` (tool `search_docs`) e no `rag_first`.
- Cada trecho custa alguns tokens a mais no contexto (o id tem ~25–40 caracteres) — irrelevante diante do texto.
- O `ai-generic` e outros packs não são afetados: ver o id não obriga ninguém a citar.
