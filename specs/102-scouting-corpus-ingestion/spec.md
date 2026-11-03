# Feature Specification: Ingestão do corpus, chunking estrutural e modelo de vigência

**Feature Branch**: `102-scouting-corpus-ingestion`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §20 (ingestão e chunking), §22 (vigência, versão e revogação), Parte IX (modelo de embedding); princípio IX.

## Module Boundary *(mandatory)*

- **Módulo**: Corpus Ingestion — transforma documentos institucionais em chunks indexados com estrutura, metadados e vigência, preservando o texto original.
- **Repositório / distribuição**: `axon-scouting` → `src/axon_scouting/rag/ingestion/` (pipeline offline, não roda no caminho da requisição) e `src/axon_scouting/rag/index/` (seam do índice e seus adapters).
- **Consome (seams)**: forma de `Chunk` — 001.
- **Expõe (seams)**: **Índice do scouting** — modelo de chunk indexado (schema, metadados, modelo de vigência, identificadores estáveis, versão do índice) e porta de consulta `ChunkIndex` (busca híbrida com filtros) — consumido por 103 e 106; o modelo (valores de status de vigência) também por 104.
- **Depende de infraestrutura (via portas)**: base de vetores, modelo de embedding, armazenamento do texto original.
- **Não conhece**: o core, flows, prompts, como os resultados da busca são usados.
- **Substituição**: preservar o modelo de chunk indexado, a porta `ChunkIndex` e a estabilidade dos identificadores de chunk; base de vetores, parser, chunker e embeddings podem ser trocados com reindexação (são adapters).
- **Insumo técnico**: [design.md](design.md); [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## Clarifications

### Session 2026-10-07

- Q: Como o curador informa os metadados de cada documento (tipo, ramo, versão, datas de vigência, qual versão ele substitui) na ingestão? → A: Por um catálogo do corpus (`corpus.yaml`), com uma entrada por documento: arquivo (caminho relativo ao catálogo; os PDFs ficam fora do repositório do pack), `document_id` da linhagem, versão, tipo, título, ramo, jurisdição, datas e `supersedes`. A ingestão processa o catálogo inteiro.
- Q: Qual modelo de embedding denso a ingestão e a busca usam até a medição da Fase 6 decidir? → A: `multilingual-e5-small`, dentro do processo do pack (ONNX, CPU), na ingestão e na codificação das perguntas — provisório pelo princípio X. O `bge-m3` pelo Ollama (ingestão na GPU do curador, perguntas no CPU do servidor) é o próximo candidato a testar, como outro adapter de `Embedder` com reindexação. O índice registra o modelo que o gerou, e a busca recusa a codificação densa com um modelo diferente.
- Q: Como a ingestão decide se um documento é normativo (dividido por artigo ou regra) ou narrativo (dividido em janelas)? → A: Pelo tipo do documento no catálogo, numa tabela fixa do pack: `por`, `resolucao` e `estatuto` são normativos; `manual`, `programa_educativo` e `guia` são narrativos. Normativo sem nenhuma unidade reconhecida é tratado como narrativo, com aviso no relatório da ingestão.
- Q: Quando uma resolução altera só algumas regras do POR, a vigência é controlada por documento inteiro ou por regra? → A: Por documento. A edição consolidada do POR entra como nova versão da linhagem e substitui a anterior inteira; cada resolução é um documento próprio, com vigência própria. Vigência por regra fica fora do escopo da v1.
- Q: De onde vêm os PDFs do corpus inicial para a primeira ingestão real? → A: Do site oficial da UEB: um conjunto pequeno (POR consolidado, estatuto, uma resolução e um manual de ramo) baixado para uma pasta fora do repositório, com um `corpus.yaml` de rascunho (versões e datas tiradas dos próprios documentos) revisado pelo curador antes da ingestão real.

### Session 2026-10-08

- Q: Onde ficam o catálogo e os PDFs do corpus — fora do repositório do pack, como dizem as clarificações 1 e 5? → A: No repositório do `axon-scouting`, em `corpus/`, no git normal (sem LFS): o corpus inicial tem ~33 MB, e o maior arquivo, 24 MB, fica bem abaixo dos 100 MB por arquivo do GitHub. Cada entrada do catálogo traz `source_url`, o link oficial do arquivo, que vai para o registro do documento no índice. Substitui o "fora do repositório do pack" das clarificações 1 e 5.

### Session 2026-10-21

- Q: Onde a ingestão roda e o que ela produz depois do [ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md)? → A: No desenvolvimento ou no CI do pack, nunca na instalação. Ela grava o **artefato do índice**, dado do pacote Python: os trechos com metadados e termos esparsos, os registros de documento com o texto original e um manifesto com a versão — e um conjunto de vetores densos por modelo. Atualizar o corpus é lançar uma versão nova do pack.
- Q: Como o artefato guarda mais de um modelo? → A: Os trechos e os ids não dependem do modelo (a ingestão é determinística); cada modelo tem o próprio arquivo de vetores, com nome, impressão digital, dimensões e sha256 no manifesto. Uma ingestão codifica com um modelo (`--embedder e5|pplx`) e preserva os vetores dos outros para os trechos cujo texto não mudou; um conjunto que deixaria algum trecho sem vetor sai do artefato até o `reindex` daquele modelo.
- Q: Qual o segundo modelo, e como ele se compara ao e5? → A: `perplexity/pplx-embed-v1-0.6b`, pelo OpenRouter (1024 dimensões, normalizado na ingestão e na pergunta, sem prefixo), com a chave `AXON_SCOUTING_EMBEDDING_API_KEY`. Ele substitui o `bge-m3` pelo Ollama como próximo candidato; a escolha é do eval da 105. Default: `e5`.
- Q: E o Qdrant? → A: Opção para corpus grande: `axon-scouting-corpus load-qdrant` carrega o artefato num Qdrant (sem PDF nem modelo), e o pack o usa com `store: qdrant` (101). O índice de produção é o artefato em memória, com as fórmulas do `MemoryIndex` (RRF sobre denso e esparso).

### Session 2026-10-27

Revisão do RAG ([docs/revisao-rag-scouting-2026-10.md](../../docs/revisao-rag-scouting-2026-10.md)): no índice de 593
documentos, 175 trechos só com "O Marco Simbólico", 108 das 197 regras do POR só com o título, 1.113 trechos com a marca
de hifenização do PDFium e 12,9% dos trechos além do que o e5 lê. Os PDFs saíram do git em 2026-10-26 (decisão do
mantenedor; substitui a clarificação de 2026-10-08 nesse ponto): o catálogo, a proveniência e o artefato ficam.

- Q: Por que o corpo das regras do POR se perde, se o texto está na página? → A: O PDF desenha o título de cada regra depois do corpo da página inteira, e o PDFium entrega o texto nessa ordem; os manuais fazem o mesmo com títulos de seção e imprimem o cabeçalho de margem duas vezes. A ingestão passa a ler a página **na ordem de leitura**, pela geometria das linhas: sem duplicatas e, numa página de uma coluna, de cima para baixo. Página de várias colunas fica na ordem do PDFium. O original preservado (FR-009) continua o texto bruto.
- Q: Cabeçalho corrido de várias linhas e título de capítulo repetido nas páginas dele — como reconhecer sem apagar texto de verdade? → A: Pelas primeiras e últimas linhas de cada página (até 4, no máximo um terço da página), com dígitos neutralizados: corrida é a linha em mais da metade das páginas, em 80% das páginas entre a primeira e a última ocorrência, ou que traz o número da própria página. O marcador de unidade sozinho na linha ("REGRA", "Art.") nunca é corrido.
- Q: E o que sobra sem corpo, e os trechos grandes demais para o e5? → A: Corpo sem nenhuma frase terminada e com menos de 40 letras não vira trecho: segue para a seção seguinte. Títulos em mais de uma linha e o nome do capítulo depois de "CAPÍTULO N" entram no título; o prefixo normativo leva o nome do agrupamento. A janela passa a 250–450 tokens estimados (`estrutural-v2`), e a "frase" maior que a janela (lista sem pontuação) se divide entre palavras. Unidade normativa continua inteira (FR-002).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Curador ingere um documento (Priority: P1)

O curador do corpus registra um documento (PDF) no catálogo do corpus e roda a ingestão. Ela extrai a estrutura, gera chunks, enriquece com os metadados do catálogo, calcula representações densa e esparsa e indexa na coleção.

**Why this priority**: Fase 5; sem corpus não há RAG.

**Independent Test**: Ingerir um manual de teste e consultar a coleção: todos os chunks têm texto, metadados obrigatórios e as duas representações.

**Acceptance Scenarios**:

1. **Given** um PDF de manual, **When** ingerido, **Then** a coleção contém seus chunks com identificador estável, metadados e representações densa e esparsa.
2. **Given** o mesmo documento ingerido duas vezes, **When** a segunda ingestão termina, **Then** os identificadores de chunk são os mesmos e não há duplicatas.

---

### User Story 2 - Norma dividida pela própria estrutura (Priority: P1)

Para material normativo, a unidade é a estrutura: um artigo é um chunk, com parágrafos, incisos e alíneas dentro dele. Cada chunk carrega o caminho ancestral (documento · título · capítulo · seção) como prefixo.

**Why this priority**: O chunk fica auto-contido para o modelo e a citação é derivável do próprio chunk.

**Independent Test**: Ingerir uma norma de teste; cada artigo (ou regra) vira exatamente um chunk, com o prefixo completo.

**Acceptance Scenarios**:

1. **Given** uma lei com títulos, capítulos, seções e artigos, **When** ingerida, **Then** cada artigo é um chunk prefixado por "[Lei X · Título II · Capítulo III · Seção I]".
2. **Given** um artigo que atravessa páginas, **When** ingerido, **Then** o chunk registra a faixa de páginas.

---

### User Story 3 - Vigência e substituição modeladas (Priority: P1)

Cada documento registra versão, início e fim de vigência, qual documento o substituiu e status (vigente, revogado, substituído, rascunho). Ingerir uma versão nova atualiza a versão anterior como substituída.

**Why this priority**: "Guardar versão e data não basta; é preciso modelar a substituição" — é o problema central do domínio normativo.

**Independent Test**: Ingerir a versão 2023 e depois a 2026 de um manual; a 2023 fica `substituído` apontando para a 2026.

**Acceptance Scenarios**:

1. **Given** o manual 2023 vigente, **When** o manual 2026 é ingerido como sucessor, **Then** a 2023 fica `substituído`, com fim de vigência e referência à 2026.
2. **Given** um documento marcado como rascunho, **When** ingerido, **Then** fica fora da busca default.

---

### User Story 4 - Material narrativo em janelas semânticas (Priority: P2)

Para manuais narrativos, os chunks são janelas de tamanho moderado que respeitam fronteiras semânticas (seções, parágrafos).

**Why this priority**: Nem todo documento tem estrutura normativa.

**Independent Test**: Ingerir um capítulo narrativo; nenhum chunk corta uma frase no meio.

**Acceptance Scenarios**:

1. **Given** um texto narrativo, **When** ingerido, **Then** os chunks respeitam fronteiras de parágrafo e ficam na faixa de tamanho configurada.

---

### User Story 5 - Texto original preservado e reindexação (Priority: P2)

O texto original de cada documento permanece armazenado e recuperável; chunks são índice, não substituto. Mudar a estratégia de chunking ou o modelo de embedding reindexa a coleção de forma controlada.

**Why this priority**: Princípio IX; e a escolha de embedding só será decidida por medição (105).

**Independent Test**: Reindexar a coleção com outro modelo de embedding sem perder documentos nem alterar identificadores de documento.

**Acceptance Scenarios**:

1. **Given** um chunk qualquer, **When** o original é solicitado, **Then** o trecho original correspondente é recuperável.
2. **Given** uma troca de modelo de embedding, **When** a reindexação termina, **Then** todos os documentos estão presentes e a versão do índice é registrada.

---

### User Story 6 - Texto indexado fiel à página (Priority: P1)

O texto que vira trecho segue a ordem em que a página se lê, sem cabeçalhos e rodapés repetidos, sem marcas da
extração e sem trechos vazios — e cada regra do POR traz o próprio texto debaixo do próprio título.

**Why this priority**: A revisão do RAG de 2026-10-27 mostrou que a recuperação não alcançava regras, lemas e faixas
etárias que só o POR enuncia: o corpo delas estava em trechos sem regra, e stubs ocupavam as vagas de candidato.

**Independent Test**: Os invariantes do artefato (nenhum trecho sem corpo, toda regra do POR com corpo, nenhuma marca
de hifenização, poucos trechos além do que o e5 lê) passam, e o `fact_recall` do conjunto de regressão da 105 sobe.

**Acceptance Scenarios**:

1. **Given** uma página que desenha o título da regra depois do corpo, **When** ingerida, **Then** o trecho da regra
   começa pelo título dela e traz o texto que vem debaixo dele, e nenhum texto de outra regra.
2. **Given** um cabeçalho de margem de duas linhas, impresso duas vezes, nas páginas de um capítulo, **When**
   ingerido, **Then** ele não aparece em nenhum trecho, e nenhum trecho é só esse cabeçalho.
3. **Given** uma página em duas colunas, **When** ingerida, **Then** a ordem do texto é a do parser.
4. **Given** o marcador "REGRA" sozinho no topo de muitas páginas, **When** ingerido, **Then** ele continua no texto.

---

### User Story 7 - Documento como árvore de unidades tipadas (Priority: P1)

Cada documento entra no índice com a própria estrutura: o POR por regra, a norma por artigo, a ata por item de pauta,
o guia de especialidades por eixo, especialidade e insígnia, o guia de progressão por eixo e bloco. Cada trecho sabe a
que unidade pertence e qual é o caminho dela no documento, e a lista das unidades de um tipo pode ser lida sem busca
([ADR-048](../../docs/adr/ADR-048-arvore-de-unidades-e-enumeracao-no-scouting.md)).

**Why this priority**: No teste do mantenedor em 2026-10-27, "quais são as especialidades do ramo pioneiro?" não trouxe a
lista: o trecho dela ficou em 86º no denso e 142º no BM25, e o sumário do guia, que tem as 32 com página, é descartado
na limpeza. O eixo de cada especialidade e o ramo de cada insígnia só estão no rodapé, também descartado. 17 normas
catalogadas como `manual` são cortadas em janelas, sem os artigos.

**Independent Test**: Com o artefato `estrutural-v4`, `units("especialidade", filtros do Pioneiro)` devolve as 32
especialidades do guia Sênior/Pioneiro com página e eixo, e nenhuma do Lobinho/Escoteiro; o Regulamento da RNJL tem um
trecho por artigo; os invariantes do artefato e o `fact_recall` da 105 não pioram.

**Acceptance Scenarios**:

1. **Given** um documento numa pasta da taxonomia, **When** ingerido, **Then** o registro dele traz categoria,
   subcategoria, nível e tipo semântico da entrada; **Given** um arquivo fora de qualquer pasta da taxonomia, **Then**
   a validação do catálogo o recusa, nomeando a pasta.
2. **Given** um regulamento catalogado como `manual`, **When** ingerido, **Then** o tipo semântico dá o perfil
   `artigos`, e cada artigo é uma unidade.
3. **Given** o guia Sênior/Pioneiro e a declaração dele no `estrutura.yaml`, **When** ingerido, **Then** cada entrada do
   sumário na faixa de especialidades é uma unidade `especialidade` com o eixo do rodapé como pai, e o trecho de
   Gastronomia tem o rótulo "Eixo: Habilidades para a Vida · Especialidade: Gastronomia · Fazer".
4. **Given** uma faixa declarada que não casa com o sumário (entrada fora da faixa ou faixa sem entrada), **When** a
   ingestão roda, **Then** ela recusa o documento, nomeando a faixa.
5. **Given** as insígnias do grupo "Ramo Pioneiro", **When** a busca filtra `branch="lobinho"`, **Then** nenhuma delas
   aparece; **Given** um documento sem ramos, **Then** ele continua valendo para todo ramo.
6. **Given** o Art. 12 do Estatuto (seis incisos curtos), **When** ingerido, **Then** o trecho tem `shape="list"`.

---

### Edge Cases

- PDF escaneado sem camada de texto: sinalizado e rejeitado na v1 (OCR fora de escopo).
- PDF com fonte sem mapeamento de caracteres ("Aƴa dŸ XIX FŹƞƼū"): o texto sai corrompido sem erro; a curadoria troca
  o arquivo pelo derivado OCR (4 documentos no corpus de 593, research R29).
- Documento de tipo normativo sem nenhuma unidade (artigo ou regra) reconhecível: tratado como narrativo, com aviso no relatório da ingestão.
- Dois documentos vigentes na mesma linhagem: a ingestão rejeita e pede resolução ao curador.
- Metadado obrigatório ausente: documento rejeitado com lista de campos faltantes; como toda rejeição, impede a execução inteira (FR-011).
- Modelo de embedding da consulta diferente do registrado no índice (pesos atualizados, adapter trocado sem reindexar): busca recusada, nomeando os dois modelos (FR-012).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A ingestão DEVE extrair estrutura, gerar chunks, enriquecer metadados e produzir representações densa e esparsa para cada chunk.
- **FR-002**: Material normativo DEVE ser dividido por artigo (ou regra, a unidade numerada do POR), mantendo parágrafos, incisos e alíneas dentro do chunk da unidade. Normativo ou narrativo decorre do tipo do documento no catálogo, por uma tabela fixa do pack: `por`, `resolucao` e `estatuto` são normativos; `manual`, `programa_educativo` e `guia`, narrativos. Tipo fora da tabela é metadado inválido (FR-011).
- **FR-003**: Cada chunk normativo DEVE ser prefixado pelo caminho ancestral.
- **FR-004**: Material narrativo DEVE ser dividido em janelas que respeitam fronteiras semânticas, com tamanho configurável.
- **FR-005**: Cada chunk DEVE ter identificador estável e determinístico, derivado de documento, versão, seção e página.
- **FR-006**: Cada chunk DEVE carregar os metadados da tabela do design (documento, tipo, título, ramo, jurisdição, capítulo, seção, subseção, página, artigo, versão, datas, substituição, status).
- **FR-007**: O modelo de vigência DEVE registrar versão, início e fim de vigência, documento sucessor e status (`vigente`, `revogado`, `substituído`, `rascunho` — no índice, ids ASCII: `substituido`). A vigência é do documento inteiro: todos os chunks de uma versão compartilham a vigência dela. Alteração parcial (uma resolução que muda algumas regras) entra como nova versão consolidada da linhagem e como documento próprio da resolução; vigência por artigo ou regra está fora do escopo.
- **FR-008**: Ingerir um sucessor DEVE atualizar o antecessor; no máximo um documento vigente por linhagem.
- **FR-009**: O texto original DEVE ser preservado e recuperável a partir de qualquer chunk.
- **FR-010**: A reindexação DEVE ser idempotente e registrar a versão do índice (estratégia de chunking + modelo de embedding, identificado pelo nome e pela impressão digital dos pesos).
- **FR-011**: A ingestão DEVE ler os metadados do catálogo do corpus — uma entrada por documento, com arquivo (caminho relativo ao catálogo), `document_id` da linhagem, versão, tipo, título, ramo, jurisdição, datas de vigência, a versão que ele substitui (`supersedes`) e, opcional, o link oficial do arquivo (`source_url`) — e DEVE rejeitar a entrada sem metadado obrigatório, listando os campos faltantes. Qualquer rejeição impede a execução inteira: nada é aplicado e o índice publicado fica como estava.
- **FR-012**: A busca DEVE codificar a pergunta com o mesmo modelo de embedding (e o mesmo codificador esparso) registrado na versão do índice; com um diferente, a busca DEVE ser recusada, e a falha DEVE nomear os dois (falha fechada, princípio VII).
- **FR-013**: A ingestão DEVE gravar o artefato do índice ([ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md)) — `manifest.json`, `chunks.jsonl`, `documents.jsonl` e `vectors/<modelo>.f32` — num diretório (default, o do pacote), com publicação de uma vez e integridade conferida por sha256 na carga; o mesmo corpus e o mesmo modelo DEVEM produzir os mesmos arquivos, salvo o manifesto.
- **FR-014**: O artefato DEVE guardar um conjunto de vetores por modelo, sobre os mesmos trechos; publicar com um modelo DEVE preservar os vetores dos outros quando cobrem todo trecho com o mesmo texto, e retirá-los quando não cobrem. Cada leitor DEVE carregar só os vetores do próprio modelo, e a busca com um modelo ausente DEVE ser `IndexMismatch`.
- **FR-015**: O sistema DEVE oferecer o embedder remoto `pplx` pelo OpenRouter, com a chave do pack, vetores normalizados e falha explícita (sem a chave, provedor fora, resposta inesperada), sem nunca pôr a chave numa mensagem.
- **FR-016**: A CLI DEVE oferecer `--embedder` e `--dir` em `ingest`, `reindex`, `status` e `original`, e `load-qdrant`, que publica no Qdrant um build igual ao do artefato, tudo ou nada.
- **FR-017**: O parser DEVE entregar, além do texto bruto (o original, FR-009), o texto de cada página na ordem de leitura, decidida pela geometria das linhas: sem as linhas impressas em duplicata e, em página de uma coluna, de cima para baixo (linhas da mesma faixa na ordem do parser); página de várias colunas ou com linha sem posição, na ordem do parser. O chunking lê a ordem de leitura.
- **FR-018**: A limpeza DEVE remover cabeçalho e rodapé corridos de várias linhas — procurados nas primeiras e últimas linhas da página, em mais da metade das páginas, em 80% das páginas do trecho em que aparecem ou com o número da própria página —, sem nunca remover o marcador de unidade normativa; e DEVE tratar a marca de hifenização do PDFium (U+FFFE, U+00AD) como o hífen de quebra e tirar o número de página colado a um título em maiúsculas.
- **FR-019**: Nenhum trecho DEVE ser só um título: corpo sem frase terminada e com menos de 40 letras segue para a seção seguinte (ou, no fim, para o último trecho; a janela final assim, para a anterior; entre unidades normativas, para a unidade seguinte); títulos em mais de uma linha e o nome do capítulo depois de "CAPÍTULO N" fazem parte do título; o prefixo normativo DEVE trazer o nome de cada agrupamento.
- **FR-020**: As janelas narrativas DEVEM ficar entre 250 e 450 tokens estimados (`estrutural-v2`), e a frase maior que a janela DEVE ser dividida entre palavras; a unidade normativa continua inteira (FR-002).
- **FR-021**: O índice DEVE expor o seam *Catálogo de documentos* (`DocumentCatalog.catalog(filters)`): uma `CatalogEntry` por documento que os `IndexFilters` admitem, com a semântica de vigência, ramo e tipo da busca e o link do original, em todo adapter ([ADR-047](../../docs/adr/ADR-047-lista-de-documentos-do-acervo-no-scouting.md)).
- **FR-022**: O chunking narrativo DEVE dar hierarquia aos títulos: título em maiúsculas recorrente no documento é subtítulo do último título não recorrente; item numerado cuja numeração recomeça, cujo número é um ano ou cuja frase continua na linha seguinte não é título; e a sobra antes de uma unidade normativa NÃO DEVE cortar a frase da primeira linha dela (`estrutural-v3`, research R32).
- **FR-023**: Todo arquivo do corpus DEVE morar numa pasta de entrada da taxonomia (`corpus/taxonomia.yaml`; a região ou a UEL como subpasta; a cópia OCR no mesmo caminho sob `ocr/`); a validação do catálogo DEVE recusar arquivo fora delas, e o registro de documento DEVE levar categoria, subcategoria, nível e tipo semântico da entrada ([ADR-048](../../docs/adr/ADR-048-arvore-de-unidades-e-enumeracao-no-scouting.md), research R33).
- **FR-024**: A ingestão DEVE ler `corpus/estrutura.yaml` e dar a cada documento o perfil da primeira exceção que casa (por pasta ou `document_id`) ou, sem exceção, o do tipo semântico (`profile_by_type`); DEVE recusar tipo sem perfil, tipo de unidade fora de `unit_kinds` e faixa de páginas declarada que não casa com o sumário do documento.
- **FR-025**: A ingestão DEVE montar uma árvore por documento — nó com id, tipo de unidade, título, páginas e filhos — e gravar em cada trecho o caminho até a raiz; o rótulo do trecho DEVE trazer o tipo e o título de cada nível; unidade maior que a janela vira filhos aninhados, e a menor fica num trecho só; as unidades normativas mantêm a FR-002 (`estrutural-v4`).
- **FR-026**: O esqueleto da árvore DEVE vir, em ordem de autoridade, dos marcadores normativos, do sumário do PDF, dos bookmarks, do cabeçalho ou rodapé corrido e da hierarquia de títulos, conforme o perfil; sumário e rodapé saem do texto do trecho (FR-018) mas ficam como estrutura, e o detector de sumário DEVE aceitar pontilhado e tracejado.
- **FR-027**: Cada trecho DEVE ter `shape`: `list` quando a maior parte do corpo são itens marcados (•, incisos, alíneas, numeração) e curtos; senão, `prose`.
- **FR-028**: Documento e grupo de unidades DEVEM aceitar `branches` declarados no `estrutura.yaml`; o filtro de ramo DEVE admitir o trecho cujos ramos contêm o pedido e, sem ramos, continuar tratando-o como geral.
- **FR-029**: O seam *Índice do scouting* DEVE expor, em todo adapter, `path`, `unit_kind`, `shape` e `branches` em `IndexedChunk`, `shape` em `IndexFilters`, os tipos de unidade do build com os plurais (`unit_kinds()`), `units(kind, filters)` — as unidades de um tipo que os filtros admitem, com título, páginas e caminho — e `outline(doc_key)`, a árvore do documento sem texto.
- **FR-030** ([ADR-049](../../docs/adr/ADR-049-taxonomia-e-a-tipologia-do-acervo-no-scouting.md)): O catálogo NÃO DEVE ter `type`; o tipo do documento DEVE ser o `tipo` da entrada da taxonomia da pasta, como id (`taxonomy_id`), e o índice DEVE gravar também os órgãos (ids da categoria e da subcategoria) e a abrangência (o nível da taxonomia, senão o da jurisdição) e filtrar por eles (`IndexFilters.bodies`, `scopes`) em todo adapter. Sem taxonomia e estrutura, a ingestão NÃO DEVE rodar.
- **FR-031** ([ADR-050](../../docs/adr/ADR-050-leitura-fiel-e-trecho-que-cabe-no-embedder-no-scouting.md)): Numa página de colunas de texto, a ordem de leitura DEVE ser coluna a coluna, da esquerda para a direita, com fronteira de parágrafo entre as colunas; colunas alinhadas linha a linha (tabela) DEVEM ficar na ordem do parser. Quando o documento tem estilos de título (fonte, tamanho, negrito), o título DEVE ser a linha num desses estilos, com o nível pelo tamanho; linha em maiúsculas ou numerada na fonte do corpo NÃO DEVE ser título.
- **FR-032** (ADR-050): Nenhum trecho DEVE passar do que o embedder denso lê (512 tokens do tokenizador do e5, rótulo incluído): a unidade normativa maior DEVE ser dividida nas linhas do corpo, com "Art. N (parte i de n)" no rótulo e o caput curto repetido; a janela, nas linhas e frases. Seção menor que o mínimo da janela DEVE juntar-se à mãe ou à irmã anterior, com o título dela no corpo, salvo quando o título abre unidade com nome.
- **FR-033** (ADR-050): A ingestão DEVE aceitar a transcrição de um documento digitalizado em `ocr/<caminho do original>.txt`, uma página por bloco separado por quebra de página (U+000C), e lê-la como o texto do documento.
- **FR-034** (ADR-050): Nos documentos de `ocr/`, a ingestão DEVE tirar do trecho (sem tirar do original) o carimbo repetido, a linha com menos da metade das palavras plausíveis e o rabo ilegível, com o vocabulário dos documentos nascidos digitais da mesma execução.

### Key Entities

- **Corpus Catalog**: arquivo do curador (`corpus.yaml`) com uma entrada por documento; é a única fonte dos metadados e da relação de substituição. Mora no repositório do pack, em `corpus/`, com a proveniência de cada original (`fontes.yaml`); os PDFs, em caminhos relativos ao catálogo, ficam na máquina de quem ingere, fora do git (clarificação de 2026-10-27).
- **Document**: identificador, tipo, título, ramo, jurisdição, versão, datas de vigência, sucessor, status, original.
- **Chunk**: identificador estável, texto com prefixo ancestral, metadados, representações densa e esparsa.
- **Index Version**: estratégia de chunking + modelo de embedding (nome e impressão digital dos pesos) + data.
- **Chunk Index**: porta de consulta do índice (busca densa e esparsa com fusão, filtros de vigência e de contexto, e a similaridade densa de cada resultado — ADR-025), consumida por 103 e 106.
- **Corpus Taxonomy**: `corpus/taxonomia.yaml`, o mapeamento semântico do acervo (do mantenedor, com as linhas inferidas marcadas): categoria, subcategoria, nível e tipo semântico; cada entrada é uma pasta de `corpus/` (ADR-048).
- **Document Structure**: `corpus/estrutura.yaml` — tipos de unidade, vocabulário (eixos e blocos), perfis, o perfil de cada tipo semântico e as exceções por pasta ou documento.
- **Unit**: nó da árvore de um documento — id, tipo, título, páginas, ramos e filhos; o trecho guarda o caminho das unidades acima dele.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos chunks normativos têm caminho ancestral completo e permitem derivar uma citação válida.
- **SC-002**: Reingerir o mesmo documento produz 0 duplicatas e os mesmos identificadores.
- **SC-003**: 0 linhagens com mais de um documento vigente.
- **SC-004**: Uma reindexação completa do corpus inicial conclui dentro da janela de manutenção definida pelo operador (meta a medir).
- **SC-005**: O corpus inicial real (POR consolidado, estatuto, uma resolução e um manual de ramo), com o catálogo revisado pelo curador, é ingerido sem rejeição, e SC-001 a SC-003 valem nele.
- **SC-006**: No corpus de 593 documentos: 0 trechos só com título (salvo ruído de OCR e campos de formulário, no máximo 5), 0 regras do POR sem corpo, 0 marcas de hifenização e no máximo 2,5% dos trechos além de 512 tokens do e5 (unidades normativas inteiras e tabelas de relatório).

## Assumptions

- Ingestão é offline, disparada pelo curador/operador; não há ingestão de longa duração que exija motor de workflow (ADR-010).
- Modelo de embedding decidido por medição na Fase 6 (candidatos no design); até lá, `multilingual-e5-small` dentro do processo, e o `bge-m3` pelo Ollama é o próximo a testar. A escolha não altera o modelo de chunk indexado nem a porta `ChunkIndex` — cada candidato é um adapter de embedding.
- Onde o texto original fica armazenado é decidido no plano; o acesso é por porta, e o armazenamento é adapter.
- O corpus inicial é de documentos institucionais em português, públicos no site oficial da UEB; o catálogo fica em `corpus/` no repositório do pack e os PDFs, fora do git (clarificações de 2026-10-08 e 2026-10-27), e o rascunho do catálogo é revisado pelo curador antes da ingestão real. Os testes automatizados usam documentos sintéticos.
