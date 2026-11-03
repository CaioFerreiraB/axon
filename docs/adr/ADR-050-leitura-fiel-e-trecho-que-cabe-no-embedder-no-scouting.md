# ADR-050 — No scouting, a ingestão lê colunas e títulos pela tipografia, todo trecho cabe no embedder e o OCR vira transcrição revisável

- **Status:** Aceita · 2026-10-28
- **Specs afetadas:** [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md) (ordem de
  leitura, títulos, teto do trecho, junção de seções pequenas, transcrição, ruído de OCR, unidades `under`, fontes
  por exceção), [105-scouting-evaluation](../../specs/105-scouting-evaluation/spec.md) (linha de base)
- **Origem:** pedido do mantenedor em 2026-10-28, a partir do relatório "Anatomia do RAG do scouting" e de um teste no
  dev: perguntado sobre Caio Ferreira Bernardo, o assistente respondeu que ele ganhou o Prêmio Aldo Chioratto, e não o
  Walter Dohme

## Contexto

Cinco defeitos da `estrutural-v4`, todos com evidência no artefato:

1. **Colunas.** Na p. 33 do Relatório Anual 2023, o PDF desenha a coluna da direita (Walter Dohme) antes da esquerda
   (Aldo Chioratto). A ordem de leitura, ao detectar duas colunas, desistia e ficava com a do parser; logo depois de
   "CAIO FERREIRA BERNARDO … Inah de Mello 147/SP" vinha "Prêmio Aldo Chioratto…".
2. **Títulos pelo texto.** O nome em maiúsculas virava título ("[Relatório 2023 · CAIO FERREIRA BERNARDO]"), e
   "Prêmio Walter Dohme", em minúsculas, não. A tipografia diz o contrário: os títulos são Gotcha Gothic de 14 pt e o
   corpo, Avenir de 10 pt. O mesmo erro picava manuais (o item "10. Deliberar…" de uma lista virava título) e escondia
   os cargos do guia de Perfis.
3. **Trecho truncado.** O e5 lê 512 tokens e descarta o resto em silêncio. Medido com o tokenizador dele, 378 trechos
   passavam disso: 82 artigos e regras, porque a unidade normativa virava um trecho só do tamanho que tivesse (o maior
   com 5.717 tokens), e 296 janelas, porque o texto real tem até 1,6 vez a estimativa de caracteres ÷ 4.
4. **Ruído de OCR.** Carimbo de cartório lido como texto ("(XX) 41 - 3225-3905 CURITIBA") virava título e sumário;
   restos de letras sob o carimbo poluíam o trecho. As 57 cópias OCR eram PDFs de origem desconhecida, sem como
   revisar, e 31 atas novas da Assembleia Regional de SP (1994–2020) não têm camada de texto.
5. **Unidades declaradas que não saíam.** 0 competências, 0 cargos, 0 reuniões no Clã, Desafio Sênior sem eixo nem
   bloco: as fontes `under` não existiam, o sumário do guia de cargos cobria os títulos dos cargos, e o eixo no rodapé
   colado ao número da página ("100MEIO AMBIENTE") não era reconhecido como rodapé corrido.

## Decisão

1. **Colunas de texto lidas uma a uma.** Numa página de colunas, cada faixa entre linhas largas é lida coluna a coluna,
   da esquerda para a direita, com uma linha vazia (fronteira de parágrafo) entre as colunas. Colunas cujas linhas
   compartilham o topo (60% das linhas da menor com par a até 1,5 pt) são tabela e ficam na ordem do parser
   (`leitura-v2`).
2. **Títulos pela tipografia.** O parser lê, por linha, o tamanho efetivo da fonte (tamanho × escala da matriz do
   texto), a família e o negrito. Quando o documento tem estilos de título — maiores que o corpo, ou do mesmo tamanho
   em negrito ou noutra família, com linhas curtas, em até 30% dos caracteres e repetidos em 2 páginas —, só é título a
   linha num desses estilos; o nível vem do tamanho dos estilos que se repetem em 3 páginas ou mais (até 4 níveis);
   título que quebra em linhas seguidas se junta; mais de 3 linhas seguidas no estilo são um destaque, não título; e a
   linha que termina em ponto, com 3 palavras ou mais, é frase. Com tipografia, título pelo texto só "CAPÍTULO N".
   Documento sem estilo de título (OCR, transcrição) fica com os títulos pelo texto (`tipografia-v1`).
3. **Seções pequenas se juntam.** Com os títulos mais finos, seção menor que o mínimo da janela (250 tokens estimados)
   junta-se à anterior quando é filha, neta ou irmã dela e as duas cabem numa janela: o caminho fica o comum, e os
   títulos que saíram dele entram no corpo, cada um como parágrafo. Nunca sai do caminho um título que abre unidade
   com nome (entrada do sumário na faixa declarada, bloco do vocabulário, padrão de título, filho de `under`).
4. **Teto do trecho medido pelo embedder.** Depois da árvore, todo trecho cujo texto (rótulo incluído, com `passage: `
   e os tokens especiais) passa de 512 tokens do tokenizador do e5 é dividido: a unidade normativa nas linhas do corpo
   (caput, parágrafos, incisos), com "Art. N (parte i de n)" no rótulo e o caput curto (até 80 tokens) repetido nas
   continuações; a janela, nas linhas e frases; o que nem assim cabe, entre palavras. O teto é o do e5 para qualquer
   embedder, porque o artefato tem um conjunto só de trechos, e entra na versão do índice (`teto=512:e5-tok:<sha>`).
5. **OCR como transcrição em texto.** A transcrição de um documento digitalizado mora em
   `corpus/ocr/<caminho do original>.txt`, uma página por bloco (U+000C), versionada e revisável; a ingestão a lê pelo
   `.txt` (`transcricao-v1`). A de partida é o Tesseract 5 local (`scripts/ocr.py tesseract`, contêiner
   `jbarlow83/ocrmypdf`, sem custo); a revisão, por um transcritor com visão (`scripts/ocr.py pages` → o Codex, pelo
   prompt em `scripts/ocr-codex-prompt.md`) conferida contra o Tesseract (`check`, concordância por página). Nada de
   API paga para isso, por decisão do mantenedor.
6. **Filtro de ruído nos documentos de `ocr/`.** Sai do trecho (fica no original): o carimbo — linha curta que
   reaparece quase igual em 3 páginas e tem telefone, CEP, CNPJ ou metade das palavras de cartório e endereço —, a
   linha com menos da metade das palavras plausíveis e o rabo de 2 palavras ou mais não plausíveis. Plausível é a
   palavra do vocabulário dos documentos nascidos digitais da mesma execução (2 documentos ou mais), o nome próprio ou
   a sigla bem formados e o número. A impressão digital do vocabulário entra na chave de conteúdo dos documentos de OCR.
7. **Unidades declaradas.** `under` vira fonte: é da unidade o título logo abaixo de um dos nomes declarados; uma
   exceção pode trocar as fontes do perfil (`sources`; o guia de cargos lê só os títulos) e limpar o título da unidade
   (`trim`, o cabeçalho de tabela "PRELIMINAR INTERMEDIÁRIO AVANÇADO" colado ao nome da competência); unidade do mesmo
   tipo dentro de outra é seção dela; a linha da borda colada ao número da própria página conta como corrida. Os níveis
   das especialidades ficam no texto da especialidade (`children: nivel` sai).

## Alternativas rejeitadas

- **Ordenar toda página de colunas coluna a coluna**, sem distinguir tabela: uma tabela "Distrito | Comissário" seria
  lida por coluna, e cada nome perderia o seu distrito.
- **Janela medida em tokens reais.** Mudaria o tamanho de todo trecho e acoplaria o corte ao tokenizador; o teto como
  passo final corta só os 378 que passam, e a janela continua comparável com as medições da 105.
- **Transcrição por modelo de visão pago (OpenRouter).** Medida numa ata de 2005: recupera o texto sob o carimbo
  ("pagá-lo", "disponibilizado"), a US$ 0,003 por página, mas o mantenedor não quer o custo; o Codex faz o mesmo papel.
- **Vocabulário de um dicionário externo.** Mais uma dependência e um dado fora do acervo; os nomes de órgãos, siglas
  e termos do movimento já estão nos documentos nascidos digitais.

## Consequências

- `estrutural-v5`: reingestão completa (639 documentos, 15.607 trechos, nenhum acima de 512 tokens). `fact_recall`
  (105 R24): regressão 0,991 → 0,977 e acervo 0,910 → 0,892 — a Regra 178 e o capítulo do marco simbólico, que antes
  acertavam por um trecho grande que o e5 truncava, agora dependem de qual parte sobe; semente com MRR 0,435 → 0,551.
  As linhas de base foram regravadas.
- Os documentos com tipografia de título ganham caminhos mais fiéis, e a contagem de trechos muda; o artefato passa a
  ter invariantes de teto (nenhum trecho acima de 512 tokens do e5).
- As 57 cópias OCR em PDF ficam até a transcrição revisada; quando ela chegar, o catálogo passa a apontar para os
  `.txt`.
- A ingestão offline pode codificar na GPU (`AXON_SCOUTING_EMBEDDING_DEVICE=cuda`, num venv com o `onnxruntime-gpu`;
  102 R40): 251 trechos/s contra ~10 na CPU, com o mesmo vetor (cosseno ≥ 0,9999998). A produção segue na CPU.
- A tipografia é uma heurística sobre o que o PDF declara: PDF que desenha títulos como imagem (os eixos dos guias de
  especialidades) continua dependendo do rodapé e do sumário.
