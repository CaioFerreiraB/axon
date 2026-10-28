# ADR-051 — Link da citação e fontes no Open WebUI

- **Status:** Aceita · 2026-10-28
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md) (`Citation.url`),
  [008-core-http-api](../../specs/008-core-http-api/spec.md) (eventos `source` atrás de `x-axon-citations`),
  [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md) (`IndexedChunk.source_url`),
  [104-scouting-citations](../../specs/104-scouting-citations/spec.md) (o link na citação)
- **Origem:** teste do mantenedor no Assistant `scouting` pelo Open WebUI (2026-10-28): o `[1]` da resposta é texto
  puro, não abre o documento, e não há lista de referências

## Contexto

O `citation_integrity` (104) troca cada `[[chunk_id]]` válido por `[n]` e devolve a lista de citações com documento,
versão, status, seção e página. O core leva essa lista até o fim: `FinalEvent.citations`, `x_axon.citations` na
resposta e `citations` na conversa guardada. O Open WebUI v0.12 descarta `x_axon`. Ele só torna o `[n]` clicável, e só
mostra o botão colapsável "N Fontes" com a lista, quando a mensagem tem `sources`, e `sources` só nasce de eventos
`source` (ou `citation`) na chave `event` de um chunk. O streaming repassa essa chave ao emissor de eventos, que grava
cada fonte na mensagem (`socket/main.py`), e é o mesmo caminho da timeline de status (ADR-028).

No front-end do v0.12:

- `ContentRenderer.svelte` numera as fontes pela ordem de `metadata.source` (ou `source.id`), sem repetir. O `[n]` vira
  um chip com o `metadata.name` da fonte n.
- O clique no chip abre `source.embed_url` no painel lateral, se houver (em conversa somente leitura, abre em nova
  aba); senão, abre o modal da fonte. O painel (`Embeds.svelte`) é um iframe com `sandbox`, e o Chrome não mostra PDF
  em iframe com sandbox: no dev, o POR aparece como "This page has been blocked by Chrome".
- No modal (`CitationModal.svelte`), o nome é link para `source.url`, o conteúdo é `document[i]` e a página é
  `metadata.page + 1`.
- A lista colapsável (`Citations.svelte`) mostra `n` e o nome. Um id que é URL vira o nome da fonte.

Nenhuma camada leva o link do original. O `source_url` está no catálogo do corpus e no registro de cada documento do
índice do scouting, mas não chega ao trecho, nem à `Citation`, que não tem campo para ele.

## Decisão

1. **`Citation.url`** (001, `0.2.3`, aditivo): chave opcional, o endereço do original para o usuário abrir. Quem o
   monta é o pack, porque só ele sabe o que o original é: o `#page=N` é coisa de PDF, e o core não sabe que a fonte é
   um PDF.
2. **Fontes no dialeto do Open WebUI, atrás de um cabeçalho** (008): com `x-axon-citations: sources` num pedido com
   streaming, a API manda, depois do último texto e antes do chunk final, um evento `source` por citação, na ordem do
   `[n]`.
   - `source`: id = `chunk_id`, `name` = legenda, `url` = `Citation.url`, e nunca `embed_url`. O clique no `[n]` abre
     o modal, onde o nome abre o PDF numa aba nova, já na página.
   - `document`: uma linha com documento, versão, situação, seção e página.
   - `metadata`: `source` = `chunk_id`, `name` = legenda, `page` = página − 1.

   A legenda segue o ADR-026: `Documento — seção, p. N`, sem as partes ausentes. Sem o cabeçalho, ou com `none`, nada
   muda; qualquer outro valor é 400 antes de executar. Sem streaming, nada sai, porque o Open WebUI só lê `event` no
   streaming.
3. **O id da fonte é o `chunk_id`, não a URL.** Duas citações do mesmo PDF são duas fontes, e a numeração do Open WebUI
   precisa casar com o `[n]`. Uma URL como id também trocaria o nome pelo domínio.
4. **O core só repassa URL `http` ou `https`.** O link vai a um `href` da interface, e um esquema como `javascript:`
   não pode chegar lá. Citação sem URL válida sai sem `url`, e o modal mostra o nome sem link.
5. **No scouting**, o trecho do índice leva o `source_url` do documento (`IndexedChunk.source_url`, reescrito do
   registro quando a ingestão reaproveita o documento), e o `Chunk` o leva nos metadados (`source_url`, a chave que a
   ficha do acervo já usa). O `citation_integrity` monta `url` = `source_url#page=N` (sem página, só o
   `source_url`).
6. **A instalação liga o cabeçalho** na conexão do Open WebUI, ao lado de `x-axon-store` e `x-axon-progress`.

## Alternativas rejeitadas

- **Markdown no texto da resposta** (`[[1]](url)` e um bloco `<details>` de referências): funciona em qualquer cliente
  e só mexe no pack. Mas o markdown entra no texto guardado e no histórico que volta ao modelo, e a lista não é a do
  Open WebUI. O mantenedor preferiu as fontes nativas.
- **O PDF no painel lateral** (`embed_url`), num clique: foi a primeira escolha do mantenedor. Os hosts dos PDFs não
  mandam `X-Frame-Options`, mas o painel do Open WebUI é um iframe com `sandbox`, onde o Chrome bloqueia PDF. Na
  verificação no dev, o painel abriu com a legenda certa e o corpo bloqueado, e o mantenedor ficou com o modal.
- **As fontes junto do `x-axon-progress: status`**: é outro assunto. Um cliente pode querer um e não o outro, e o R42
  da 008 já recusou impor o dialeto do Open WebUI a todo cliente.
- **`url` no `Chunk` do contrato**: o core não usa o link do trecho, e o pack já tem os metadados para isso.
- **Juntar o link do documento na leitura** (o adapter do índice consultando o registro a cada busca): o Qdrant
  precisaria de outra consulta por busca. O campo do documento no trecho já é o padrão (`document_title`, vigência),
  e `with_document` o mantém em dia.

## Consequências

- Contratos `0.2.3`. O core pede `>=0.2.3,<0.3`, e o pack `scouting`, `0.8.0`.
- A instalação (`axon-deploy/template`, `axon-cfblabs`) e o dev mandam `x-axon-citations: sources`. O
  `check-webui.py` confere as fontes gravadas.
- O artefato do índice é regravado com o link em cada trecho, sem reencodar: os trechos e os vetores não mudam.
- O texto da resposta, o eval e a conversa guardada não mudam de forma; `x_axon.citations` e `citations` ganham `url`.
