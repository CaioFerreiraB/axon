# Research — 102 Corpus Ingestion, Fase 5 (US1–US5)

Insumos pré-aprovados: [design.md](design.md), [spec.md](spec.md) §Clarifications (sessão de 2026-10-07),
[ADR-010](../../docs/adr/ADR-010-temporal-fora.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md),
[ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md), [ADR-021](../../docs/adr/ADR-021-workspace-ai-core-permanece-no-repositorio-da-plataforma.md);
constituição (princípios II, V, VII, IX, X, XII, XIII; tabela de stack: "Qdrant — adapter do índice do scouting").
Consumidores conferidos: 103 (spec e design: `ChunkIndex.search`, fusão nativa, vigência por default, erro explícito),
104 (data-model: status dobrados `vigente`/`revogado`/`substituido`/`rascunho`; marcador `[[chunk_id]]`), 101
([contracts/retrieval-filters.md](../101-scouting-pack/contracts/retrieval-filters.md): vigência como intervalo,
`include_superseded`, `previous_version`; ids ASCII do léxico). Verificações feitas em 2026-10-07: PyPI (versões e
wheels para Python 3.12–3.14 e `aarch64`), Hugging Face (revisão e hashes do `multilingual-e5-small`) e uma sonda
contra o Qdrant `v1.19.2` em container e no modo local do `qdrant-client` 1.19.1 (R12). Escopo: **US1–US5** (a spec
inteira é Fase 5).

## R1 — Escopo, localização e toques fora do módulo

**Decision** (design.md, Module Boundary): o módulo vive em dois pacotes do `ai-scouting` —
`src/ai_scouting/rag/index/` (o seam *Índice do scouting*: modelo, `ChunkIndex`, portas de codificação e de
armazenamento, adapters Qdrant e em memória, codificadores) e `src/ai_scouting/rag/ingestion/` (pipeline offline:
domínio puro, serviço, parser de PDF, leitura do catálogo, CLI). Fora deles, a passada toca só: `pyproject.toml`
(dependências, script, import-linter, mypy), `uv.lock`, `.github/workflows/ci.yml` (job `qdrant`) e o `pack.py`, que
ganha a função de composição da CLI (R17). O `retrievers()` do pack **não** muda aqui: ligar o `ChunkIndex` ao
retriever é a 103 e a US5 da 101.

**Rationale**: o pack é uma distribuição; `pack.py` é a composition root dele (princípio XIII), então a composição do
processo offline também mora lá. Nenhuma outra spec muda.

**Alternatives considered**: um `ai_scouting/corpus.py` como segunda composition root (contraria a letra do princípio
XIII: "num pack, esse papel é do `pack.py`"); subcomando do `ai-core` (o core não conhece domínio — princípio I).

## R2 — Dependências da distribuição

**Decision**: dependências de runtime novas, todas comuns (sem extras): `qdrant-client>=1.19,<2` (cliente assíncrono,
modo local), `onnxruntime>=1.24.2` (o piso que o 3.14 exige), `tokenizers>=0.20,<1`, `numpy` (já transitiva; declarada
porque os adapters a usam), `snowballstemmer>=3,<4` (stemmer português, Python puro), `pypdfium2>=5,<6` e
`pyyaml>=6,<7`. Desenvolvimento: `fpdf2` (gera os PDFs sintéticos dos testes). Wheels conferidos em 2026-10-07: todos
têm `aarch64` e Python 3.12–3.14 (`qdrant-client` 1.19.1 e `pypdfium2` 5.14.0 são `py3-none`; `onnxruntime` 1.30.0 tem
`cp314` `manylinux_2_28_aarch64`; `tokenizers` 0.23.2 é `abi3`; `pyyaml` 6.0.3 tem `cp314`).

**Rationale**: a FR-001 da 101 ("depender apenas da distribuição de contratos") e a constituição ("packs dependem de
`ai-core-contracts` por faixa semver, nunca de `ai-core`") falam das distribuições **da plataforma**; bibliotecas de
infraestrutura em `adapters/` são o que a constituição prevê (stack: "Qdrant — adapter do índice do scouting") e o que
a Module Boundary da 102 declara ("base de vetores, modelo de embedding, armazenamento do texto original"). O SC-003 da
101 continua valendo: a suíte padrão roda sem o core. Extras (`ai-scouting[ingest]`) tirariam o parser de PDF da
imagem, mas obrigariam o `pack.py` a degradar por import ausente e o build da instalação a lembrar do extra — custo sem
ganho mensurável (o `pypdfium2` tem ~3 MB).

**Alternatives considered**: `fastembed` para denso e esparso (não traz o `multilingual-e5-small` no catálogo — só o
`-large` —, puxa `pillow`, `loguru`, `tqdm`, `requests` e um registro de modelos com download próprio; R10, R11);
`sentence-transformers` (torch: centenas de MB e lento em ARM sem GPU); `pypdf` (Python puro, mas extração de texto
pior em PDFs institucionais; o `pypdfium2` tem wheel para todas as plataformas-alvo).

## R3 — Catálogo do corpus (`corpus.yaml`)

**Decision** (clarificação 1, FR-011): YAML com `documents:` — uma lista, uma entrada por versão de documento. O adapter
(`adapters/catalog_yaml.py`) só lê o arquivo e devolve mapeamentos; a validação é pura (`domain/catalog.py`) e acumula
**todos** os problemas, cada um nomeando a entrada (índice e `document_id@version`, quando houver) e os campos
faltantes ou inválidos. Campos obrigatórios: `file`, `document_id`, `version`, `type`, `title`, `jurisdiction`,
`effective_date`. Opcionais: `branch` (ausente = documento geral), `publication_date`, `expiry_date`, `supersedes`
(versão anterior da mesma linhagem), `status` (só `rascunho` ou `revogado`; os demais são derivados — R4) e
`source_url` (link http/https do arquivo oficial; vai para o registro do documento e não entra na chave de conteúdo —
clarificação de 2026-10-08). Regras:
`document_id` em `^[a-z0-9]+(-[a-z0-9]+)*$`; `version` em `^[0-9a-z]+(\.[0-9a-z]+)*$` (sem hífen, para a chave
`document_id-version` ser inequívoca — R9); `type` na tabela fixa da FR-002; `branch` em `lobinho`, `escoteiro`,
`senior`, `pioneiro` (os ids da 101); datas ISO; `file` relativo ao diretório do catálogo, sem sair dele; par
(`document_id`, `version`) único; `revogado` exige `expiry_date`. Campo desconhecido é erro (erro de digitação não
some em silêncio). Formato completo em [contracts/corpus-catalog.md](contracts/corpus-catalog.md).

**Rationale**: o catálogo é a única fonte de metadados e da relação de substituição (clarificação 1); validar tudo
antes de tocar o índice é a falha fechada da FR-011. Os vocabulários de tipo e ramo são do modelo do índice (102),
porque são valores filtrados pela busca; a 101 produz os mesmos ids (conferido no léxico em 2026-10-07: tipos `manual`,
`programa_educativo`, `por`, `resolucao`, `estatuto`, `guia`; ramos `lobinho`, `escoteiro`, `senior`, `pioneiro`).

**Alternatives considered**: metadados no nome do arquivo ou extraídos do PDF (clarificação 1, rejeitadas);
`supersedes` apontando para outra linhagem (sem caso de uso na v1: revogação por documento de outra linhagem é
`status: revogado` com `expiry_date`); tolerar campos desconhecidos (um `expiry_dte` sumiria em silêncio).

## R4 — Vigência: status pela posição na linhagem, vigência numa data pelas datas

**Decision** (FR-007, FR-008, clarificação 4): a derivação é pura (`domain/lineage.py`), sobre o catálogo inteiro, e
não lê relógio. Por linhagem (`document_id`):

1. `status: rascunho` → `rascunho`; não substitui ninguém, mesmo com `supersedes`.
2. `status: revogado` → `revogado`, com o `expiry_date` declarado.
3. Versão com sucessor não rascunho (alguém declara `supersedes` = ela) → `substituido`, `superseded_by` = chave do
   sucessor, `expiry_date` = véspera do `effective_date` do sucessor (declarado e diferente disso → erro).
4. Demais → `vigente`.

Erros de linhagem (rejeitam a execução — R13): `supersedes` para versão inexistente; uma versão substituída por duas;
ciclo; sucessor com `effective_date` ≤ o do antecessor; **mais de uma `vigente`** (duas versões não rascunho sem elo de
substituição — "peça resolução ao curador"). Cada versão substituída guarda também `successor_expiry_date` (o fim de
vigência do sucessor, nulo se ele está em vigor), que a busca por `previous_version` usa (R5).

O status é a **posição na linhagem** (estrutural): no máximo uma `vigente` por linhagem, por construção (SC-003). Se a
versão estava **em vigor numa data** decide-se na busca, pelas datas (R5). Um sucessor publicado com vigência futura
fica `vigente` e o antecessor `substituido` desde a ingestão; até a data, a busca devolve o antecessor (em vigor pelas
datas), marcado `substituido` — a 104 avisa, o que é excesso de cautela, nunca omissão (princípio IX). Passada a data,
nada precisa ser reingerido.

**Rationale**: status calculado com o relógio da ingestão envelheceria à meia-noite da data de vigência e deixaria a
linhagem sem versão em vigor na busca default; e quebraria a avaliação com data de referência fixa no passado (ADR-013,
009): um item fixado em 2024 precisa recuperar a versão em vigor em 2024, mesmo que hoje ela seja `substituido`. Com
vigência por datas, qualquer data de referência dá o resultado certo, e o rótulo continua sendo o "status atual" que a
103 (US3) e a 104 pedem.

**Alternatives considered**: status relativo ao dia da ingestão (relógio na derivação; envelhece e quebra a avaliação);
status calculado na busca a partir da data de referência (exigiria a data de referência nos filtros mesmo em consulta
histórica — chave nova no contrato da 101 — sem ganho para o caso comum); vigência por artigo (fora do escopo,
clarificação 4).

## R5 — Semântica dos filtros (`IndexFilters`)

**Decision** (101 clarificação 4 e contrato de filtros; 103 US2, US3, US5): o `effective_on` único do design.md vira
intervalo, como a 101 já publica:

| Campo | Semântica no índice |
|---|---|
| `effective_from`, `effective_until` (datas, inclusivas) | versões **em vigor em algum dia** do intervalo: `effective_date ≤ until` e (`expiry_date` nulo ou `expiry_date ≥ from`) |
| `include_superseded=False` (default) | além disso, só versões ainda em vigor no fim do intervalo: `expiry_date` nulo ou `≥ until`. Com intervalo de um dia (o default da 101), é exatamente "vigente na data" |
| `include_superseded=True` | sem a restrição acima: entram as substituídas e revogadas que estiveram em vigor no intervalo |
| `previous_version=True` | troca o critério de datas por "a versão imediatamente substituída em relação a `until`": `superseded_by` presente, `expiry_date < until` e (`successor_expiry_date` nulo ou `≥ until`) |
| `branch` | o ramo **ou** documentos gerais (sem ramo) — o caso de borda da 103 |
| `document_types` | qualquer dos tipos; vazio = todos |
| rascunho | nunca entra na busca (US3 cen. 2) |

A semântica é uma função pura em `rag/index/domain/filters.py`: o adapter em memória a avalia diretamente, o adapter
Qdrant a traduz para `Filter`, e a suíte de conformidade prova que os dois concordam.

**Rationale**: as regras usam só datas e o vínculo de sucessão (R4), então valem para qualquer data de referência. O
`include_superseded=False` continua significando "nada que já tenha sido substituído ou revogado" — relativo ao fim
do intervalo, não ao relógio. `previous_version` precisa do índice porque "a versão anterior" é um fato da linhagem,
não uma faixa de datas; o campo denormalizado `successor_expiry_date` o resolve num filtro só, sem agrupar.

**Alternatives considered**: `include_superseded` filtrando pelo status gravado (quebra a avaliação com data passada e o
sucessor com vigência futura — R4); deixar `previous_version` para a 103 sem apoio do índice (exigiria duas buscas e
agrupamento por linhagem na aplicação); opção de incluir rascunhos (sem consumidor).

## R6 — Parser de PDF e texto original

**Decision**: `pypdfium2` atrás da porta `DocumentParser` (`adapters/pdfium.py`): lê os bytes, calcula o
`sha256` da fonte e devolve o texto de cada página (`get_textpage().get_text_range()`), sem limpeza. Documento sem
nenhum caractere extraível em nenhuma página → rejeitado como "sem camada de texto (OCR fora do escopo)"; páginas
vazias isoladas → aviso no relatório (capas e páginas de imagem existem em PDF com texto). O texto **bruto** de cada
página é o original preservado (FR-009, R15); a limpeza (R7) só alimenta o chunking.

**Rationale**: PDFium é o motor de extração mais robusto disponível com wheel para `aarch64` e todas as versões de
Python do projeto, sem dependência nativa extra. Guardar o bruto mantém o original fiel; o chunking é derivado e pode
ser refeito.

**Alternatives considered**: `pypdf` (R2); detecção de PDF escaneado por proporção de páginas vazias (um limiar
arbitrário — princípio X; a regra "nenhum texto em nenhuma página" é exata, e as páginas vazias aparecem no relatório
para o curador decidir).

## R7 — Limpeza e estrutura normativa

**Decision** (FR-002, FR-003; clarificação 3): funções puras em `ingestion/domain/`:

- **Limpeza** (`text.py`): linha só com número de página sai; linha idêntica no topo ou no rodapé de mais da metade das
  páginas (mínimo 3) sai como cabeçalho/rodapé corrido; palavra hifenizada na quebra de linha (`organiza-` + `ção`, com
  minúscula a seguir) é unida; espaços colapsados. Cada linha guarda a página de origem.
- **Marcadores normativos** (`structure.py`), por linha, sem distinguir caixa nem acento: `TÍTULO <romano>`,
  `CAPÍTULO <romano|número>`, `SEÇÃO <romano|número>`, `SUBSEÇÃO <romano|número>`, `Art. <n>[º°][-A]` (unidade),
  `Regra <n>` (unidade do POR, número com zeros à esquerda — "Regra 033"), `ANEXO <romano|número>`. Parágrafos
  (`§`, `Parágrafo único`), incisos (`I –`) e alíneas (`a)`) **não** cortam: ficam no chunk da unidade.
- **Unidade normativa** = do marcador da unidade até o próximo marcador de unidade, de agrupamento (título, capítulo,
  seção, subseção) ou de anexo. Texto antes da primeira unidade (preâmbulo, considerandos) e anexos viram janelas
  narrativas (R8) dentro do mesmo documento, com seção `preambulo` / `anexo-<n>`.
- **Prefixo** (FR-003): `[<título do catálogo> · Título II · Capítulo III · Seção I]`, com rótulo e número normalizados
  (o nome do agrupamento, como "Dos Associados", vai nos metadados `chapter`/`section`/`subsection`, não no prefixo).
  Narrativos também ganham prefixo (`[<título> · 4.2 Atividades]`), por consistência.
- Tipo normativo sem nenhuma unidade reconhecida → o documento inteiro vai para janelas, com aviso no relatório
  (clarificação 3).

**Rationale**: a estrutura é a unidade (design.md); a tabela de marcadores é dado do domínio e cresce com o corpus
real — o SC-005 é o momento de ajustá-la (o POR numera regras com três dígitos, "Regra 033", conferido em 2026-10-07).
O prefixo com o título do catálogo, e não do PDF, é estável e é o que a citação mostra.

**Alternatives considered**: detectar cabeçalhos por tamanho de fonte (exige layout do PDF; sem medição de que a
regex não basta); dividir artigos longos (contraria "um artigo = um chunk"; o modelo denso trunca em 512 tokens — o
esparso cobre o texto inteiro — e a 105 mede se isso pesa).

> Atualizado em 2026-10-08 (corpus real, SC-005 — [quickstart.md](quickstart.md) §5): a tabela cresceu com o que o
> POR 2025, o Estatuto 2024 e a Resolução CAN 08/2021 mostraram, cada ajuste com um caso sintético do mesmo formato.
> **Unidade pelo tipo** (`UNIT_BY_TYPE`): regra no `por`, artigo no `estatuto` e na `resolucao` — a resolução cita a
> nova redação das regras dentro do artigo. **Marcador partido** em duas linhas ("REGRA" / "001 DEFINIÇÃO…") é unido;
> o rótulo mantém o número como o documento escreve ("Regra 033"). **Título de unidade em maiúsculas** abre unidade e
> vira parágrafo próprio, mesmo sem pontuação na linha anterior (regras seguidas). **Página de índice** (3+ linhas com
> pontilhado, ≥ 30% da página) sai inteira do chunking. **Cabeçalho corrido** que muda por capítulo sai quando traz o
> número da própria página, de qualquer lado. **Crédito de foto** colado pela diagramação ("…Escotismo@ Nome")
> sai. **"ANEXOS"** sem número abre a seção de anexos. **Nome de agrupamento em duas linhas** é unido. Na chave fixa
> (preâmbulo, anexo), linha em maiúsculas é texto, não cabeçalho. Resultado: POR com 197 regras, Estatuto com 74
> artigos, Resolução com 7 — nenhum aviso de "normativo sem unidade".

## R8 — Janelas narrativas

**Decision** (FR-004, US4): `ingestion/domain/chunking.py`. Cabeçalhos narrativos: `CAPÍTULO <n>` e linhas curtas
numeradas (`4`, `4.2`, `4.2.1` seguidos de texto em maiúscula inicial, sem ponto final, até 80 caracteres); o
cabeçalho abre seção e força quebra de janela. Parágrafo termina em linha encerrada por `.`, `!`, `?`, `:` ou `;`
seguida de linha iniciada por maiúscula, número ou marcador de lista; frases são separadas por pontuação final
seguida de espaço e maiúscula, com uma lista curta de abreviações que não terminam frase (`Art.`, `art.`, `nº.`,
`Sr.`, `Sra.`, `p.`, `ex.`, `etc.`). Empacotamento guloso de parágrafos até o máximo; parágrafo maior que o máximo
divide-se em frases; frase maior que o máximo fica inteira (nunca se corta frase). Tamanho em **tokens estimados**
(`⌈caracteres/4⌉`, como a estimativa do core); defaults `300–600` (faixa do design.md); sem sobreposição. A janela que
fecha uma seção pode ficar abaixo do mínimo (fronteira semântica vence o tamanho). "Configurável" (FR-004) é pela
composição: o `pack.py` e o harness da 105 passam a `ChunkingPolicy`; a CLI usa os defaults, e o curador não ajusta
número sem medição (princípio X).

**Rationale**: "nenhum chunk corta frase" é verificável por construção; a estimativa por caracteres não acopla o
chunking ao tokenizador do modelo de embedding (que é adapter e pode mudar). Os números entram na identidade da
estratégia de chunking e, portanto, na versão do índice (R12): mudar é reindexar, e a 105 mede (princípio X).

**Alternatives considered**: contar tokens com o tokenizador do embedder (acopla domínio a adapter); sobreposição de
janelas (outro número sem medição; entra se a 105 mostrar ganho); janela fixa por caracteres (corta frase).

## R9 — Identificador de chunk

**Decision** (FR-005, design.md): `chunk_id = "<document_id>-<version>#<seção>@p<página inicial>"`, com sufixo
`~<k>` (k ≥ 2) quando (seção, página) se repete no mesmo documento — a k-ésima janela de uma seção que começa na mesma
página, ou um segundo "Art. 1" dentro de anexo. Seção: `art42`, `art42-a`, `regra33` (unidade normativa); numeração do
cabeçalho (`4.2.1`) ou `s<n>` (ordinal da seção sem número) nas narrativas; `preambulo`, `anexo-i`. Só ASCII minúsculo,
dígitos e `-._~#@`: nada de espaço nem colchete (o marcador `[[chunk_id]]` da 104). A chave do documento,
`<document_id>-<version>`, é inequívoca porque `version` não tem hífen (R3). No Qdrant, o id do ponto é
`uuid5(NAMESPACE_CHUNK, chunk_id)` (o Qdrant só aceita inteiro ou UUID); o `chunk_id` vai no payload.

**Rationale**: o formato do design.md (`man-pio-2026#4.2.1@p87`) com a regra de desempate que ele não previa;
determinístico dado (PDF, catálogo, estratégia de chunking), então reingerir dá os mesmos ids (SC-002).

**Alternatives considered**: hash do conteúdo (estável, mas ilegível na citação e no trace); ordinal global do chunk
(muda quando qualquer trecho anterior muda).

## R10 — Embedding denso: `multilingual-e5-small` em ONNX, adapter próprio

**Decision** (clarificação 2; princípio X): adapter `rag/index/adapters/e5.py` da porta `Embedder`, com
`onnxruntime` + `tokenizers`: tokenização com truncamento em 512, inferência, *mean pooling* com a máscara de atenção
e normalização L2 (é a configuração do modelo: `1_Pooling/config.json`, `mean_tokens`, dimensão 384); prefixos
`passage: ` na ingestão e `query: ` na pergunta (exigência do e5). A inferência roda em `asyncio.to_thread` para não
travar o laço do core. Arquivos fixados: repositório `intfloat/multilingual-e5-small`, revisão
`614241f622f53c4eeff9890bdc4f31cfecc418b3`, `onnx/model.onnx` (sha256 `ca456c06…a6bc8665`, 470 MB, fp32) e
`onnx/tokenizer.json` (sha256 `0b44a9d7…14ebdf4c39`). O adapter lê os dois de um diretório (`AI_SCOUTING_EMBEDDING_DIR`)
e **nunca baixa nada em runtime**; o subcomando `ai-scouting-corpus model fetch <dir>` baixa a revisão fixada por HTTPS
e confere os sha256. Identidade do modelo: nome + impressão digital = sha256 do `model.onnx` carregado (calculado uma
vez por processo) + dimensão.

**Rationale**: é a escolha provisória da clarificação 2; o adapter próprio tem ~60 linhas e duas dependências, contra
o registro de modelos e as dependências do `fastembed` (que nem traz o e5-small). A variante `qint8_avx512_vnni` do
repositório é específica de x86 — no ARM alvo vale o fp32. Fixar revisão e hash torna a impressão digital da FR-010
verificável e o build da instalação reproduzível.

**Alternatives considered**: `bge-m3` pelo Ollama (o próximo candidato da clarificação 2 — outro adapter de `Embedder`,
com reindexação); `fastembed` e `sentence-transformers` (R2); impressão digital pelo nome + revisão (confia no arquivo
em disco sem conferir).

## R11 — Representação esparsa: BM25 com stemmer português, IDF no Qdrant

**Decision**: adapter `rag/index/adapters/bm25.py` da porta `SparseEncoder`: texto dobrado (minúsculas, sem acento),
tokens alfanuméricos (números mantidos — "Art. 42" vira `art` e `42`), stopwords do português, `snowballstemmer`
português; id do termo = `crc32` do radical (estável entre processos, cabe no `u32` do Qdrant). Documento: peso BM25 de
frequência de termo, `tf·(k1+1)/(tf + k1·(1−b+b·len/avgdl))` com `k1=1.2`, `b=0.75`, `avgdl=256` fixos; pergunta: peso
1 por termo distinto. O IDF fica com o Qdrant (`SparseVectorParams(modifier=IDF)`, verificado — R12); o adapter em
memória o emula com a mesma fórmula. Identidade: `bm25-pt-v1;k1=1.2;b=0.75;avgdl=256`, gravada na versão do índice.

**Rationale**: a fusão nativa denso + esparso do design.md e da 103 US1 (o termo exato "Art. 42" vem do esparso); IDF
no servidor dispensa estatística de corpus no cliente. Os parâmetros são os padrões da literatura, provisórios e
gravados na versão do índice para a 105 medir (princípio X).

**Alternatives considered**: `fastembed` `Qdrant/bm25` (mesmo algoritmo, mas traz o pacote inteiro — R2); SPLADE
(modelos em inglês); esparso do `bge-m3` (vem junto com a troca de embedding, se a 105 a indicar).

## R12 — Layout no Qdrant (verificado)

**Decision**: um **build** do índice é uma coleção Qdrant; o nome configurado do índice (default `scouting`) é um
**alias** para o build publicado. Esse nome é a "coleção" da spec, a que o retriever declara (`NamedRetriever.collections`,
101) e a que o Assistant concede no grant; a coleção Qdrant de cada build é detalhe do adapter. Na coleção: vetores nomeados `dense` (cosseno, dimensão do embedder) e `sparse`
(`modifier=IDF`); `metadata` da coleção = a versão do índice (R14); pontos de **chunk** (com os dois vetores; payload =
todos os campos do `IndexedChunk` + `kind: "chunk"` + `doc_key`) e pontos de **documento** sem vetor (payload = o
registro do documento com as páginas originais + `kind: "document"`; R15). Índices de payload: `keyword` em `kind`,
`doc_key`, `document_id`, `status`, `branch`, `document_type`; `datetime` em `effective_date`, `expiry_date`,
`successor_expiry_date`. Busca: `query_points` com dois `prefetch` (denso e esparso, cada um com o filtro e o limite de
candidatos) e `FusionQuery(RRF)`; o resultado é reordenado por (`-score`, `chunk_id`) para empate determinístico.

Sonda de 2026-10-07 (servidor `v1.19.2` em container e modo local do `qdrant-client` 1.19.1, o mesmo script): metadados
de coleção gravados e lidos; pontos sem vetor numa coleção de vetores nomeados; filtro por `DatetimeRange` com campo
nulo (o `must_not` de `expiry_date < from` não exclui o nulo); RRF sobre os dois `prefetch`; alias trocado
atomicamente entre coleções; `set_payload` por filtro. Única diferença: a ordem entre empates de score (daí o
desempate no adapter).

**Rationale**: pontos de documento sem vetor nunca entram na busca (não têm os vetores consultados) e trocam junto com
os chunks no alias — um build é consistente por inteiro. O modo local roda o mesmo adapter sem servidor, então a suíte
de conformidade cobre o adapter real em qualquer máquina (R16).

**Alternatives considered**: coleção separada para documentos (duas trocas de alias, sem atomicidade entre elas);
versão do índice num ponto especial (a `metadata` de coleção existe para isso); Postgres para originais (o pack não
tem acesso ao pool do core — princípio II; seria outra infraestrutura só para o pack).

## R13 — Construção azul/verde: toda ingestão publica um build novo

**Decision** (FR-008, FR-010, US5): uma execução de `ingest` é **tudo ou nada**:

1. Lê e valida o catálogo (R3), deriva as linhagens (R4), analisa todos os PDFs (R6) e gera todos os chunks (R7–R9).
   Qualquer rejeição → relatório com todas, código de saída 1, **nada é escrito**.
2. Compara a versão do índice configurada (estratégia de chunking + embedder + codificador esparso) com a do build
   publicado. Diferente → `ingest` recusa e manda rodar `reindex` (não mistura vetores de modelos diferentes).
3. Cria um build novo e, para cada versão do catálogo: se o build publicado tem o mesmo documento com a mesma **chave
   de conteúdo** (`sha256` da fonte + tipo + título + identidade do parser), **copia** os chunks com os vetores e
   reescreve só o payload de documento (metadados e vigência); senão, codifica (denso e esparso) e grava.
4. Publica: troca o alias para o build novo, apaga o anterior e os builds órfãos de execuções interrompidas.

`reindex` é o mesmo processo sem reaproveitamento (versão nova: tudo é recodificado a partir dos PDFs). Documento que
sumiu do catálogo some do índice (o índice espelha o catálogo — clarificação 1). Nome do build:
`<índice>__<AAAAMMDDTHHMMSSZ>` pelo relógio da porta `Clock` (com `-<n>` se o nome já existe), que também dá o
`built_at` da versão. Um operador por
vez (sem trava distribuída na v1).

**Rationale**: quem busca nunca vê um estado parcial (o alias troca de uma vez), falha no meio não estraga o índice
publicado, reingerir é idempotente por construção (SC-002) e o caminho é um só para ingestão e reindexação. Copiar
milhares de pontos com vetores custa segundos; recodificar é o que custa minutos, e só o que mudou é recodificado.
Tudo ou nada é a falha fechada mais simples: o curador corrige o catálogo e roda de novo, sem estado intermediário.

**Alternatives considered**: atualizar no lugar (upsert + remoção dos chunks velhos — leitores veem duplicatas no meio,
e uma falha deixa o índice misturado); aplicar o que passou e pular o rejeitado (o índice deixa de espelhar o catálogo
e a linhagem rejeitada fica num estado que ninguém escolheu); `--force` para misturar versões (viola a FR-012).

## R14 — O seam `ChunkIndex` e o modelo publicado

**Decision**: `rag/index/api.py` publica `ValidityStatus` (`vigente`, `revogado`, `substituido`, `rascunho` — ids ASCII,
como os da 101; rótulos com acento em `STATUS_LABELS` para quem exibe), `DocumentType`, `NORMATIVE_TYPES`, `BRANCHES`,
`IndexedChunk`, `IndexFilters`, `EmbeddingModel`, `IndexVersion`, os erros `IndexUnavailable` e `IndexMismatch` e o
`Protocol` `ChunkIndex`. Ajustes à assinatura ilustrativa do design.md, todos antes de existir consumidor:

- `async def version(self) -> IndexVersion` (era síncrono): ler a versão é I/O, e o pack monta o índice num hook
  síncrono de carga — não há onde ler antes.
- `search` devolve `IndexedChunk` com `score` preenchido; `get` devolve com `score=None`.
- `IndexedChunk.to_chunk()` converte para o `Chunk` da 001: `document` = título do catálogo (o que a 104 mostra no
  aviso), `section` = a etiqueta mais específica (artigo/regra, senão subseção, seção, capítulo), `page` = página
  inicial, demais campos em `metadata`.

A cada busca o adapter lê a versão do build publicado (uma chamada leve) e a compara com a identidade do seu embedder e
do seu codificador esparso: diferente → `IndexMismatch`, nomeando os dois modelos (FR-012); alias inexistente ou
servidor fora → `IndexUnavailable` (a 103 FR-007 exige erro explícito, não vazio). Ler a cada busca faz uma reindexação
valer sem reiniciar o processo — e, se ela trocou o modelo, a busca recusa até o pack ser montado com o embedder novo.

**Rationale**: o seam é o modelo + a porta do design.md; os ajustes são de forma, feitos antes da primeira
implementação e sem consumidor (103 e 106 citam o seam pelo nome). Ficam anotados no design.md, como a 101 fez com as
linhas superadas pelas clarificações. Status em ASCII é o que a 104 já compara (dobrado), e evita acento em valor
filtrado.

**Alternatives considered**: ler a versão uma vez e guardar (uma reindexação exigiria reiniciar o core); seguir com
`search` só esparso quando o modelo diverge (falha silenciosa na qualidade — a FR-012 pede recusa).

## R15 — Texto original recuperável (FR-009)

**Decision**: o registro de cada documento (ponto sem vetor no build — R12) guarda as páginas **brutas** extraídas
(R6), o arquivo de origem e o `sha256` da fonte. A porta `DocumentStore` (leitura) responde
`original(chunk_id) → Original` (documento, versão, faixa de páginas e o texto delas); `ai-scouting-corpus original
<chunk_id>` a expõe ao curador. Nenhum consumidor de runtime pede o original na Fase 5, então ele **não** entra no
seam `ChunkIndex`.

**Rationale**: o original fica onde o índice está — acessível tanto da máquina do curador quanto do servidor — e troca
junto com os chunks no alias. O PDF continua na pasta do curador (fora do repositório, clarificação 5); o `sha256`
amarra o registro a ele.

**Alternatives considered**: disco (a ingestão pode rodar fora do servidor; o servidor não veria o arquivo);
Postgres (R12); guardar o PDF no Qdrant (binário de MBs no payload sem consumidor).

## R16 — Portas, adapters e estratégia de teste

**Decision**:

| Porta | Onde | Adapter real | Adapter em memória | Conformidade |
|---|---|---|---|---|
| `ChunkIndex` (seam) + `IndexWriter` + `DocumentStore` | `rag/index/api.py`, `rag/index/ports.py` | `QdrantIndex` (`adapters/qdrant.py`) | `MemoryIndex` (`adapters/memory.py`: filtros pela função pura, cosseno, IDF e RRF emulados) | uma suíte, três alvos: memória; Qdrant **modo local** (sempre); Qdrant servidor com `AI_SCOUTING_TEST_QDRANT_URL` (job `qdrant` da CI) |
| `Embedder` | `rag/index/ports.py` | `E5Embedder` (`adapters/e5.py`) | `HashingEmbedder` (determinístico, saco de palavras com hash) | suíte de forma (dimensão, norma 1, determinismo, prefixo pergunta ≠ passagem); contra o e5 real só com `AI_SCOUTING_EMBEDDING_DIR` |
| `SparseEncoder` | `rag/index/ports.py` | `Bm25Encoder` (`adapters/bm25.py`) | o próprio `Bm25Encoder` (puro, sem I/O) | suíte de forma (ids estáveis, números preservados, acentos dobrados) |
| `DocumentParser` | `rag/ingestion/ports.py` | `PdfiumParser` (`adapters/pdfium.py`) | `MemoryParser` (páginas dadas por caminho) | PDFs sintéticos gerados com `fpdf2` nos testes: texto por página, sha256, documento sem texto |
| `Clock` | `rag/ingestion/ports.py` | `SystemClock` (UTC) | `FixedClock` | suíte curta: UTC, nunca anda para trás, o fixo é fixo |

As portas de codificação e de escrita ficam em `rag/index/ports.py` (o design.md as listava em `ingestion/ports.py`):
o `ChunkIndex` codifica a pergunta com o mesmo embedder da ingestão, e escrita, leitura e originais são o mesmo
armazenamento — os mesmos adapters as implementam. O leitor do catálogo YAML não é porta: é a CLI (adapter primário)
que lê o arquivo e entrega mapeamentos ao serviço. Os testes de aceitação das US1–US5 rodam o serviço com adapters em
memória e texto sintético; a integração liga `PdfiumParser` + `QdrantIndex` (modo local) + `HashingEmbedder` sobre PDFs
gerados.

**Rationale**: constituição (toda porta com adapter em memória e suíte contra o real); o modo local do Qdrant dá
cobertura do adapter real sem infraestrutura, e o servidor fecha as diferenças que a sonda não pegou. O e5 real
(470 MB) não entra na CI padrão, como os providers pagos do core.

**Alternatives considered**: PDFs binários versionados como fixtures (opacos para revisão; gerar no teste documenta o
conteúdo); porta para o catálogo (o YAML é entrada da CLI, não infraestrutura que o serviço aciona).

## R17 — CLI `ai-scouting-corpus` e configuração

**Decision**: script `ai-scouting-corpus = "ai_scouting.pack:corpus_cli"`. `pack.py` compõe (imports pesados dentro da
função, para a carga do pack pelo core não pagar por eles); o parsing de argumentos e a impressão do relatório ficam em
`rag/ingestion/adapters/cli.py`. Subcomandos: `ingest <corpus.yaml>`, `reindex <corpus.yaml>`, `status`, `original
<chunk_id>`, `model fetch <dir>`. Configuração por ambiente: `AI_SCOUTING_QDRANT_URL` (default
`http://localhost:6333`), `AI_SCOUTING_QDRANT_API_KEY` (opcional, nunca impressa), `AI_SCOUTING_INDEX` (default
`scouting`), `AI_SCOUTING_EMBEDDING_DIR` (obrigatória para `ingest`/`reindex`). Saída: 0 sucesso; 1 rejeição (nada
aplicado); 2 erro de uso, configuração ou infraestrutura. O relatório traz documentos aceitos, chunks por documento
(reaproveitados/codificados), removidos, avisos, a versão do índice e a duração (para o SC-004). Contrato em
[contracts/ingestion-cli.md](contracts/ingestion-cli.md).

**Rationale**: a ingestão é offline (ADR-010) e roda onde o curador estiver — na máquina dele (o bge-m3 futuro usa a GPU
dele) ou dentro do container da instalação; nos dois casos fala com o mesmo Qdrant. Variáveis com o prefixo do pack
seguem o padrão `AI_CORE_*` do core sem se misturar a ele.

**Alternatives considered**: configuração pelo `packs.yaml` (a CLI roda fora do core; a configuração de runtime do
pack é decisão da US5 da 101); um arquivo de configuração próprio (sem caso que as variáveis não cubram).

## R18 — Fronteiras de import e tipagem

**Decision**: novos contratos no `pyproject.toml` do `ai-scouting`:

| Contrato | Regra |
|---|---|
| camadas do índice | `rag.index.adapters` → `rag.index.domain` → `rag.index.ports` → `rag.index.api` (o domínio usa os tipos das portas) |
| camadas da ingestão | `rag.ingestion.adapters` → `rag.ingestion.service` → (`rag.ingestion.ports` \| `rag.ingestion.domain`) |
| `api.py` do índice não importa o resto do índice nem a ingestão | `forbidden` |
| infraestrutura só em `adapters/` | `qdrant_client`, `onnxruntime`, `tokenizers`, `numpy`, `snowballstemmer`, `pypdfium2`, `yaml` proibidos em `rag.*.api`, `rag.*.domain`, `rag.*.ports`, `rag.ingestion.service` |
| os outros módulos do pack veem só o seam | `context`, `prompts`, `validators` (e, na Fase 5, `rag.retrieval`) não importam `rag.ingestion` nem `rag.index` além de `rag.index.api` |
| só o `pack.py` compõe | a camada existente ganha `ai_scouting.rag` abaixo de `ai_scouting.pack` |

mypy strict sobre `src`; `onnxruntime` e `pypdfium2` sem tipos completos ficam com `ignore_missing_imports`
restrito a eles, e só os adapters os tocam.

**Rationale**: princípio XIII e regra 7 do CLAUDE.md, aplicados dentro do pack como no core.

**Alternatives considered**: nenhum — é a regra.

## R19 — O corpus real (SC-005)

**Decision** (clarificação 5): na implementação, baixar do site oficial da UEB o POR consolidado, o estatuto, uma
resolução e um manual de ramo para uma pasta fora do repositório; escrever um `corpus.yaml` de rascunho com versões e
datas tiradas dos próprios documentos; o curador revisa; rodar `ingest` contra um Qdrant local. É verificação manual
(quickstart), não teste da CI — os testes automatizados usam documentos sintéticos. Ajustar a tabela de marcadores (R7)
ao que o corpus real mostrar faz parte da tarefa; nenhum PDF nem catálogo real entra no repositório do pack.

**Rationale**: os PDFs são públicos, mas o repositório do pack não é lugar de corpus; o SC-005 mede a ingestão real,
não a unidade.

**Alternatives considered**: versionar o corpus real nos testes (tamanho, direitos e mudança de versão sem controle).

> Atualizado em 2026-10-08 (clarificação de 2026-10-08): o catálogo revisado e os PDFs passaram a morar no repositório
> do `ai-scouting`, em `corpus/`, no git normal — ~33 MB, o maior arquivo com 24 MB, abaixo do limite de 100 MB por
> arquivo e da recomendação de 1 GB por repositório do GitHub. O catálogo é dado de domínio curado, como o léxico, e
> ganha histórico e revisão; os PDFs preservam o original mesmo se o site da UEB trocar o arquivo (princípio IX). Cada
> entrada traz `source_url`. Alternativas: Git LFS (clones leves, mas exige `git-lfs` e consome cota; migrar depois
> reescreve o histórico) e baixar pelo link conferindo o sha256 (não preserva o original). Testes seguem sintéticos.

## R20 — Efeitos fora desta passada (notas para consumidores)

**Decision**: registrar, sem implementar aqui: (a) a US5 da 101 monta o `QdrantIndex` no `retrievers()` com o
`E5Embedder` e o `Bm25Encoder`, lendo a mesma configuração; (b) a instalação (`agentic-deploy`, 002 US5) precisa do
modelo no runtime — `ai-scouting-corpus model fetch` no estágio `packs`, com o diretório copiado para o `runtime` — e de
um Qdrant ao lado do core; (c) o RRF devolve scores por posição (`Σ 1/(posição+2)`, posição contada a partir de 0, no Qdrant — verificado), o que o
portão de cobertura da 005 e o reforço da 103 precisam considerar.

**Rationale**: são decisões das specs donas (101, 103, 002/deploy, 005), que só precisam saber o que o índice entrega.

**Alternatives considered**: nenhum.

---

# Passada de 2026-10-21: o índice gerado no desenvolvimento ([ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md))

Decisões pré-aprovadas pelo ADR-043 (artefato, vetores por modelo, índice em memória, embedder remoto, Qdrant como
opção); o que segue é como elas chegam ao índice e à ingestão, sem re-pesquisa.

## R21 — O formato do artefato

**Decision**: `domain/artifact.py` (puro, só stdlib): `Manifest` (formato 1, índice, build, chunking, esparso,
`built_at`, sha256 de `chunks.jsonl` e `documents.jsonl`, e os `ModelVectors` — modelo, arquivo, sha256),
`vectors_file` (`vectors/<nome>-<12 da impressão digital>.f32`: dois pesos com o mesmo nome não dividem arquivo) e
`pack_vectors`/`unpack_vectors` (float32 little-endian, pelo `array`). Trechos e documentos usam o JSON do payload do
Qdrant (`points.py`), o trecho com o vetor esparso ao lado; trechos em ordem de `chunk_id`, documentos de `doc_key`,
uma linha cada — o diff no git é legível. No corpus real: 413 trechos, 2,5 MB com os vetores do e5.

**Rationale** (ADR-043, itens 1 e 2): o texto e o esparso uma vez só; o denso por modelo, em binário (o JSON dos
vetores do e5 passaria de 1,5 MB). float32 é a precisão em que os modelos produzem.

**Alternatives**: `.npy` (o domínio não importa o numpy); um artefato por modelo (rejeitado no ADR).

## R22 — `ArtifactIndex`

**Decision**: adapter que implementa `ChunkIndex`, `IndexWriter` e `DocumentStore` sobre o `MemoryIndex` (mesmas
fórmulas), com o `MemoryStorage` ganhando `put` e `export`. Lê o manifesto quando o carimbo do arquivo (mtime, tamanho)
muda e recarrega o build publicado (outra instância pode ter publicado); carrega os vetores do modelo da instância ou,
sem eles, os do primeiro conjunto (a busca então dá `IndexMismatch`). Builds em memória até `publish`, que grava num
diretório irmão e troca por `rename`, preservando os outros modelos (FR-014). `export` devolve o build com os vetores do
modelo, para o `copy_index`. Roda na suíte de conformidade como o alvo `artefato` (com `multi_model`: um leitor do
modelo antigo continua buscando com os próprios vetores preservados).

**Rationale** (ADR-043, item 4): reaproveitar o `MemoryIndex` é o que garante as mesmas fórmulas; confirmado no
corpus real — o eval da 105 dá os mesmos números que no Qdrant.

**Alternatives**: um índice em memória próprio (duplicaria cosseno, IDF e RRF).

## R23 — `OpenRouterEmbedder`

**Decision**: `adapters/openrouter.py`, só biblioteca padrão (`urllib`, em outra thread): `POST <base>/embeddings` com
`model`, `input` e `encoding_format: float`, lotes de 64, reordenação por `index`, normalização L2; `EmbeddingModel`
`openrouter/perplexity/pplx-embed-v1-0.6b`, impressão digital `perplexity/pplx-embed-v1-0.6b:1024:l2`, 1024 dimensões.
Sem a chave, a construção passa e a codificação levanta `EmbeddingUnavailable`; HTTP de erro, rede fora e resposta sem
os vetores certos também — sem a chave na mensagem.

**Rationale** (ADR-043, itens 2 e 5): o modelo remoto não tem arquivo para hashear; a impressão digital é o que precisa
ser igual na ingestão e na pergunta. Sem dependência nova.

**Alternatives**: o SDK da OpenAI (dependência a mais para uma chamada).

## R24 — A CLI e o `copy_index`

**Decision**: `ServiceOptions(needs_model, embedder, directory)` substitui o booleano da `Composition`, que ganha
`load_qdrant`; `--embedder` (`e5`/`pplx`) e `--dir` nos comandos do artefato; `load-qdrant` chama
`copy_index(source: IndexExport, writer)` do serviço da ingestão (porta `IndexExport` em `ports.py`). O `pack.py`
compõe o `ArtifactIndex` sobre `PACKAGED_INDEX` ou `--dir`, com uma instância do embedder para o índice e o serviço.
`ingest --embedder pplx` sem a chave é erro de configuração (2). O onnxruntime recebe `ORT_DISABLE_TELEMETRY=1` no
próprio adapter do e5 (era da imagem da instalação, que deixou de conhecer pack — 002 R66).

**Rationale** (ADR-043, item 4 e Consequências: a CLI passa a gerar o artefato).

**Alternatives**: um comando `export` separado (dois passos para o mesmo resultado).

## R25 — Determinismo e CI

**Decision**: o workflow `eval` reingere o corpus num diretório temporário e compara `chunks.jsonl` e `documents.jsonl`
com os commitados (`cmp`); sem Qdrant de serviço. Verificado localmente: reingerir dá os mesmos arquivos byte a byte,
inclusive os vetores do e5.

**Rationale**: o artefato commitado precisa ser o que o corpus produz; o CI pega um commit do corpus sem reingestão.

**Alternatives**: gerar o artefato no CI e publicar como asset (o ADR deixa para quando passar de dezenas de MB).

---

## Passada de 2026-10-27 (revisão do RAG; [relatório](../../docs/revisao-rag-scouting-2026-10.md))

## R26 — Ordem de leitura pela geometria

- **Decision**: `ParsedDocument` ganha `reading` (o texto de cada página na ordem de leitura) e `for_chunking`
  (`reading`, ou `pages` quando o parser não sabe a posição — o `MemoryParser`). O `PdfiumParser` separa o texto bruto
  nas quebras que o PDFium gera, dá a cada linha a caixa dos seus caracteres (`get_charbox`) e entrega as linhas a
  `domain/layout.py`, puro: tira a linha impressa duas vezes no mesmo lugar (±0,5 pt); decide "uma coluna" quando, entre
  as linhas com menos de 60% da largura da página, no máximo um grupo de sobreposição horizontal tem 5 linhas ou mais;
  então ordena por faixas de cima para baixo (sobreposição vertical de metade da altura da menor), com a ordem do
  parser dentro da faixa ("I -" antes do texto do inciso). A identidade do parser ganha `leitura-v1`, e com ela a chave
  de conteúdo de todo documento.
- **Rationale**: no *spike* nas pp. 58, 62, 116 e 118 do POR, os títulos das regras estão **acima** de cada corpo, na
  mesma coluna (não numa coluna lateral, como a revisão supôs), e são desenhados depois da página inteira; o Manual de
  Filhotes desenha o título da seção depois do texto e imprime o cabeçalho de margem duas vezes. A ordem vertical
  resolve os dois sem regra de documento; restringi-la a página de uma coluna evita misturar colunas.
- **Alternatives**: reancorar no domínio, pelo texto, o bloco "REGRA/NNN" do fim da página (frágil: o corpo de cada
  regra não se reconhece pelo texto); trocar de parser (sem evidência de necessidade — o PDFium dá as posições).

## R27 — Blocos corridos, hifenização do PDFium e número colado

- **Decision**: `_edges` olha até 4 linhas de cada borda (no máximo um terço das linhas da página); corrida é a linha
  (dígitos neutralizados) em ≥ 3 páginas e em mais da metade delas, em 80% das páginas entre a primeira e a última
  ocorrência, ou sempre com o número da própria página. O marcador sozinho ("REGRA", "Art.", com ou sem número) nunca
  é borda. U+FFFE antes de maiúscula vira quebra de linha; no fim da linha, U+FFFE e U+00AD viram `-` (e a regra do
  hífen de quebra se aplica); no meio, somem — a mesma política do `-` de quebra (compostos como "vice-presidente"
  perdem o hífen, como já acontecia). Número de 1 a 4 dígitos colado a um título todo em maiúsculas sai.
- **Rationale**: o cabeçalho do Manual de Filhotes é um bloco ("CAPÍTULO 3 / O Marco Simbólico", até em páginas do
  capítulo 6); o título de capítulo repete só nas páginas dele, longe da metade do documento. Medido no texto bruto:
  4.758 U+FFFE no meio da linha ("com" + U+FFFE + "põem") e 5 U+00AD no fim; 467 prefixos com o número colado.
- **Alternatives**: posição fixa na página como critério de linha corrida (precisaria da geometria na limpeza; a
  ordem de leitura já põe o bloco nas bordas).

## R28 — Nenhum trecho só com título; títulos completos; janelas v2

- **Decision**: corpo com menos de 40 letras e nenhuma linha terminada em `.!?:;` (`is_stub`) não vira trecho: no
  `narrative_chunks`, segue para o corpo da seção seguinte (no fim do texto, entra no último trecho; sem trecho nenhum,
  vira o único), e a janela final assim de uma seção longa junta-se à anterior; no `normative_chunks`, o texto solto
  assim entre um agrupamento e a unidade seguinte entra nela, como parágrafo depois do título. Nome de agrupamento que
  termina em preposição ou artigo ("Capítulo 15 – Segurança nas") continua na linha seguinte, também quando vem na
  linha do "CAPÍTULO". Linha logo depois
  de um título, antes de corpo, continua o título: o nome depois de "CAPÍTULO N" (`CAPÍTULO 3 – O Marco Simbólico`, no
  prefixo e no `chapter`) e as linhas seguintes de um título em maiúsculas. O prefixo normativo usa `Heading.metadata`
  (`Capítulo 8 – Ramo Filhotes`). `ChunkingPolicy` passa a `estrutural-v2;janela=250-450`; a frase maior que
  `window_max` é dividida em fatias de palavras inteiras.
- **Rationale**: a janela de 600 tokens estimados, mais o cabeçalho, passava de 512 tokens reais em 12,9% dos trechos
  (a razão real é ~3,9 caracteres por token); 450 dá p99 de 563. Listas de nomes sem pontuação nos relatórios anuais
  viravam "frases" de até 18 mil caracteres.
- **Alternatives**: medir as janelas com o tokenizador do embedder (acopla o chunking ao modelo, contra R8); reduzir
  mais a janela (calibração — a 105 decide com o conjunto curado).

## R29 — Medição e a reingestão

- **Decision**: preparo do corpus inteiro sem embeddings (38 s) antes e depois; reindexação com o e5 no artefato do
  pacote. Os vetores do `pplx` saem do artefato até um `reindex --embedder pplx` com a chave (a instalação usa o e5).
  Invariantes do artefato em `tests/rag/ingestion/test_artifact_quality.py`; sobram 2 trechos sem frase, que não são
  títulos — ruído de OCR numa ata e campos de formulário num guia (tolerância de 5). A primeira reindexação achou um
  defeito do `ArtifactIndex`: `_jsonl` separava as linhas com `str.splitlines()`, que quebra também em U+0085 e U+2028,
  e o JSON sem `ensure_ascii` os grava como estão (um relatório anual com fonte corrompida os traz); o artefato era
  gravado e não se lia de volta, e o `discard` do caminho de erro escondia a exceção original. O leitor separa só em
  `\n`. Quatro documentos com fonte sem mapeamento
  de caracteres (as três "recomendações" e a ata do FRJL SP 2021) ficam para a curadoria (derivado OCR).
  O passo de determinismo de R25 no CI deu lugar à conferência do artefato contra o catálogo (105 research R14): sem os
  PDFs no git, a reingestão byte a byte é de quem os tem.
  **Efeito na recuperação** (105, perfil `test`, e5): `scouting:fact_recall` 0,52 → 0,75 — o marco simbólico do
  Pioneiro, os lemas de Lobinho e Filhotes e a Regra 054 passam a chegar à geração (o lema de cada ramo, 0 → 0,6);
  agregados com os cinco ramos seguem em 0,2–0,4 e as faixas etárias em 0 (seleção, 103). Na semente, s01 apontava a
  Regra 159 — herança do defeito: o Sinal de Promessa é a **Regra 160**, e a semente foi corrigida. **Pendência**:
  s09 (os nós do Lobinho) perde a evidência porque o prefixo do trecho perdeu o capítulo — "O Sistema de Progressão
  Pessoal" vinha do cabeçalho corrido, e a abertura real "CAPÍTULO 9" sai junto, por ter o mesmo texto no topo da
  página; recuperá-lo como contexto da página pede a geometria (cabeçalho de margem × título de abertura). Também
  ficam nomes de capítulo de duas linhas cortados nos manuais ("Capítulo 8 – O Sistema de"). Linha de base da semente
  regravada (recall@5 0,7778 → 0,6667, MRR 0,5778 → 0,4352).
- **Rationale**: SC-006; o `fact_recall` da 105 mostra o efeito na recuperação.
- **Alternatives**: nenhum.

| Medida (593 documentos) | antes | depois |
|---|---:|---:|
| trechos | 16.742 | 15.504 |
| `fact_recall` (105, regressão) | 0,52 | 0,75 |
| só "O Marco Simbólico" | 175 | 0 |
| sem frase e com menos de 40 letras | — | 2 |
| corpo < 60 caracteres | 2.656 | 447 |
| corpo repetido | 2.222 | 971 |
| com U+FFFE | 1.113 | 0 |
| regras do POR sem corpo | 108/197 | 0/197 |
| > 512 tokens do e5 | 12,9% | 2,1% |
| tokens p50/p95/p99 | 145/578/684 | 218/468/563 |

## R30 — O Ramo Filhotes ([ADR-045](../../docs/adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md))

- **Decision**: `filhotes` em `BRANCHES`, primeiro (a ordem das idades); o catálogo aceita `branch: filhotes`, e os três
  documentos do Ramo Filhotes (Manual do Escotista, Começando uma Ninhada e Competências e Rotas de Aprendizagem) o
  declaram. A reingestão só muda metadados: os vetores são reaproveitados.
- **Rationale**: sem o id, os documentos de Filhotes eram gerais — entravam em toda busca filtrada por outro ramo — e
  uma pergunta sobre Filhotes não filtrava.
- **Alternatives**: nenhum.

## R31 — O catálogo de documentos como seam ([ADR-047](../../docs/adr/ADR-047-lista-de-documentos-do-acervo-no-scouting.md))

- **Decision**: `CatalogEntry` e `DocumentCatalog` no `api.py` do índice; `matches` (`domain/filters.py`) aceita o
  trecho ou a entrada, que têm os mesmos campos de vigência; `catalog_entry(StoredDocument)` em `domain/points.py`. A
  memória e o artefato filtram o registro de documento do build publicado; o Qdrant lê os pontos de documento (sem as
  páginas) e filtra com o mesmo predicado, em Python — são centenas de documentos. `catalog_entries(root)` lê
  `documents.jsonl` sob demanda para a métrica de fatos da 105, como `chunk_texts`.
- **Rationale**: o registro de documento já existe em todo adapter (`IndexWriter.documents`), mas é porta interna da
  ingestão; a 103 só vê o `api.py` (import-linter). Reusar `matches` garante a mesma vigência da busca, provada na
  suíte de conformidade contra os três alvos.
- **Alternatives**: expor `IndexWriter.documents` à 103 (abre a porta de escrita); um filtro do Qdrant para os pontos de
  documento (duplicaria a tradução de R5 para um conjunto pequeno).

## R32 — A hierarquia dos títulos (`estrutural-v3`)

- **Decision**: o chunker narrativo lê o documento antes de cortar e conta os títulos candidatos. Um título em
  maiúsculas que aparece 3 vezes ou mais (dígitos neutralizados) é **subtítulo** do último título que não se repete:
  "SUGESTÃO DE TEMAS" depois de "GASTRONOMIA" vira "GASTRONOMIA · SUGESTÃO DE TEMAS" no prefixo e em
  `chapter`/`section`. Um item numerado **não é título** quando o número aparece 3 vezes ou mais (a numeração recomeça:
  os requisitos de cada especialidade), quando é um ano ("2019. CRIS salienta…") ou quando a linha seguinte começa em
  minúscula (a frase continua). No normativo, a sobra curta antes de uma unidade entra **antes** dela quando a primeira
  linha da unidade é frase ("Art. 1º - A União…, fundada em 04 de novembro" / "de 1924"), e não depois dessa linha.
  Estratégia `estrutural-v3;janela=250-450`; reindexado com o e5: 13.973 trechos (eram 15.504).
- **Rationale**: no teste do mantenedor em 2026-10-27, a lista de especialidades do Pioneiro não chegou à geração, e o
  diagnóstico mostrou o defeito geral: 7.023 trechos com rótulo repetido sem o título-pai e 2.179 com um item numerado
  ou uma frase como capítulo (984 de 1.435 no guia de especialidades de Lobinho e Escoteiro), além do Art. 1 do
  Estatuto cortado pela sobra da capa. Medido no conjunto do acervo da 105 (R22), com 20 trechos: desenvolvimento
  0,852 → 0,898, **controle 0,841 → 0,865**, simples 0,917 → 1,0; regressão 0,991 → 1,0; semente: MRR 0,44 → 0,51,
  recall igual. Nenhum item piorou.
- **Alternatives**: limiar maior (5) para o recorrente (guias com poucas seções repetidas ficariam como antes); tirar o
  subtítulo recorrente do rótulo (perde "SUGESTÃO DE TEMAS", que diz o que o trecho é).

## R33 — A taxonomia do acervo e a reorganização do corpus ([ADR-048](../../docs/adr/ADR-048-arvore-de-unidades-e-enumeracao-no-scouting.md))

- **Decision**: `corpus/taxonomia.yaml` guarda o mapeamento semântico do mantenedor ("Mapeamento de documentos.csv",
  2026-10-27: categoria, subcategoria, nível, documento e tipo) e as linhas inferidas pelo mesmo padrão
  (`origem: inferido`): ofícios da Comissão Fiscal Regional e da Diretoria Regional, manifestações do CAN e, na Rede de
  Jovens Líderes, manuais, posicionamentos, editais, recomendações, boletins, apresentações e planejamento. Cada
  entrada é uma pasta `<categoria>/<subcategoria>/<nível>/` em ASCII (a subcategoria vazia vira o plural do tipo; o
  nível vazio ou "-" não vira pasta); o documento de uma região fica numa subpasta da entrada com o nome dela
  (`diretoria-regional/resolucoes/sao-paulo/`), e a cópia OCR repete o caminho sob `ocr/`. O corpus foi reorganizado
  assim em 2026-10-27: 656 arquivos movidos (599 originais, com as cinco duplicatas e a planilha da RNJL, e as 57 cópias
  OCR), em 15 pastas de categoria; `file`, `catalog_file`, `ocr_file`, `duplicate_of` e as notas do `fontes.yaml`, o
  `file` do `corpus.yaml` e o `source_file` do `documents.jsonl` do artefato acompanharam, e nada mais mudou (o
  `content_key` não depende do caminho). O PDF da Política de Relações Internacionais, renomeado no disco no mesmo dia,
  ficou com o nome novo ("internacionais"; o "institucionais" era o erro da URL oficial, que não mudou). O tipo
  semântico (17 valores) é mais fino que o `type` do contrato (seis) e vai para o registro do documento.
- **Rationale**: o `type` do catálogo não distingue ata de regulamento (`manual`), e por isso 17 normas eram cortadas em
  janelas (R34); a pasta, que já agrupava por órgão a maior parte do acervo, vira a fonte única da classificação, sem um
  campo novo em cada uma das 593 entradas. Com categoria e nível no registro, a lista "atas do CAN" que o ADR-047 deixou
  sem saída passa a ter onde casar.
- **Alternatives**: campos `category`/`semantic_type` em cada entrada do `corpus.yaml` (593 repetições, e a pasta
  desmentiria o campo); pastas com acento e espaço como os rótulos da planilha (frágeis em shell, URL e CI); a região
  antes da categoria (`sao-paulo/…`), como era (separa o mesmo órgão em duas árvores).

## R34 — A árvore de unidades e os perfis ([ADR-048](../../docs/adr/ADR-048-arvore-de-unidades-e-enumeracao-no-scouting.md))

- **Decision**: `corpus/estrutura.yaml` declara 18 tipos de unidade (com o plural que a pergunta usa), o vocabulário
  dos 4 eixos e 18 blocos (conferido no rodapé dos 4 guias de progressão e validado pelo mantenedor; "Paz e
  Compreensão" é sinônimo de "Paz e Desenvolvimento"), 11 perfis e `profile_by_type`; as exceções são os dois guias de
  especialidades (faixas de páginas de especialidades e grupos de insígnias, com ramos), os guias de progressão e os
  manuais do escotista (`progressao`), competências, "Primeiros meses", perfis de cargos e o FAQ. Resolvido contra o
  catálogo: `artigos` 281, `ata` 211, `comunicado` 29, `capitulos` 25, `secoes_numeradas` 15, `relatorio` 15,
  `progressao` 9, `apresentacao` 4, `especialidades` 2, `perguntas` 1, `regras` 1. As fontes do esqueleto, medidas nos
  593 PDFs: 33 têm página de sumário e 62 têm bookmarks (os manuais do escotista, 39 a 64); o rodapé corrido traz o eixo
  ("24 Habilidades para a Vida") e o grupo de insígnias com o ramo nos dois guias de especialidades, o eixo nos quatro
  guias de progressão e o capítulo nos manuais; os títulos de eixo das aberturas são imagem. O sumário confere as faixas:
  32 especialidades e 16 insígnias no Sênior/Pioneiro, 174 e 18 no Lobinho/Escoteiro. `shape` pela contagem de
  marcadores com itens de até 12 palavras em média (no artefato atual, ~160 trechos). Estratégia `estrutural-v4`.
- **Rationale**: medido sem reindexar (2026-10-27): um trecho de sumário na busca normal fica entre o 200º e o 800º,
  como a lista; restrita aos sumários, a busca põe o documento certo em 1º a 4º de 277, e restrita aos trechos `list`,
  a lista das especialidades em 1º ou 2º e o Art. 12 do Estatuto em 1º. O tipo de unidade torna a enumeração uma
  consulta de metadados, completa e com página. Os ramos por unidade fecham o vazamento dos guias de vários ramos, hoje
  sem `branch` e, portanto, gerais.
- **Alternatives**: perfil pelo `type` do catálogo (grosso demais); um trecho por capítulo (o e5 corta em 512 tokens;
  uma especialidade tem ~3 mil); indexar o sumário como trecho comum (perde da prosa, medido); faixas de páginas para
  todo documento (curadoria sem fim; o rodapé e o vocabulário cobrem os guias de progressão sem faixa).
- **Medido (2026-10-28)**, `estrutural-v4` reindexada com o e5: 14.140 trechos (eram 13.973; os 17 documentos de
  `artigos` catalogados como `manual` saíram das janelas — o Regulamento da RNJL com 129 artigos), 353 trechos `list`
  (a lista das especialidades e o Art. 12 do Estatuto entre eles); no Sênior/Pioneiro, 32 especialidades em 4 eixos e
  16 insígnias com o ramo do grupo; no Lobinho/Escoteiro, 174 e 18; 18 blocos no Horizonte; as reuniões dos "Primeiros
  meses" pelo ordinal do sumário. Duas correções saíram da conferência do artefato: o ordinal numa linha à parte no
  sumário ("1a" / "Reunião de Alcateia") e a ordem do sumário no empate de página; a faixa do grupo Lobinho foi para
  381-410. Trechos acima de 512 tokens: 2,52% (344 como antes, 6 artigos inteiros das normas novas, 7 janelas que o
  rótulo tipado empurrou), e o teto do invariante foi a 2,6%. `fact_recall`, nas condições do CI (20/20): semente igual;
  regressão 1,0 → 0,991 e acervo 0,882 → 0,871, dentro da tolerância — `etapas-cada-ramo` (as etapas do Pioneiro em 8º
  e 12º na faceta, que guarda 4), `tipos-de-risco` (o trecho em 26º) e `especialidades-pioneiro` (0,25 → 0) trocaram de
  posição com vizinhos pelo rótulo novo; nenhum perdeu por árvore errada. Sem a rota de enumeração da 103, a 102 não
  traz ganho de recuperação, e não se esperava. Achado à parte: na Política de Gestão de Riscos, os tipos de risco estão
  em prosa sob o título "5.4. Melhoria Contínua" — a hierarquia de títulos dessa política está errada desde antes.
- **Medido (2026-10-28, segunda passada: itens de pauta, FAQ e sumários)**: 14.706 trechos — 14.046 `prose`, 349
  `list`, 311 `outline` —; 476 itens de pauta em 64 das 211 atas (as que numeram, com a numeração crescente), as 11
  perguntas do FAQ, 51 reuniões. Duas correções do sumário saíram dos invariantes: a janela final curta junta-se à
  anterior (eram 145 trechos de uma ou duas linhas) e artigo e regra ficam fora dele (o sumário de uma resolução curta
  era "Art. 1, Art. 2…"; com isso, a resolução só com artigos fica sem sumário). Os invariantes passam.

## R35 — O tipo é o da taxonomia ([ADR-049](../../docs/adr/ADR-049-taxonomia-e-a-tipologia-do-acervo-no-scouting.md))

- **Decision**: o `type` sai do `corpus.yaml` (as 593 entradas e o contrato); o tipo é o `tipo` da entrada da taxonomia
  da pasta, como id (`taxonomy_id`); o índice grava também `bodies` (categoria e subcategoria) e `scope` (o nível, senão
  a jurisdição) e filtra por eles; a taxonomia passa a ser obrigatória (`MISSING_STRUCTURE`).
- **Rationale**: o `type` (6 valores) era grosso demais para filtrar — 10.722 dos 14.706 trechos eram `manual` — e
  divergia da taxonomia em 17 normas (10 resoluções regionais de SP e 7 regulamentos catalogados como `manual`); o perfil
  já saía da taxonomia desde o ADR-048.
- **Alternatives**: alargar o `type` para os 17 tipos (duplicaria a taxonomia em 593 entradas); comparar rótulos
  normalizando na busca (o Qdrant filtra por igualdade de payload).

## R36 — Colunas e títulos pela tipografia ([ADR-050](../../docs/adr/ADR-050-leitura-fiel-e-trecho-que-cabe-no-embedder-no-scouting.md))

- **Decision**: colunas de texto lidas uma a uma (`leitura-v2`), tabela alinhada na ordem do parser; o estilo de cada
  linha (tamanho efetivo pela matriz do texto, família, negrito; `tipografia-v1`) decide o título quando o documento tem
  estilo de título, com o nível pelos estilos estruturais; seção pequena junta-se à mãe ou à irmã anterior, sem engolir
  unidade com nome.
- **Rationale**: na p. 33 do Relatório Anual 2023 o PDF desenha a coluna da direita antes; com a leitura do parser e o
  nome em maiúsculas como título, o trecho do premiado do Prêmio Walter Dohme ("[… · CAIO FERREIRA BERNARDO]") seguia
  com o texto do Prêmio Aldo Chioratto, e o assistente trocou os prêmios (teste no dev, 2026-10-28). O `PdfiumParser`
  devolve tamanho 1,0 para tudo; o tamanho efetivo vem da escala da matriz (14 pt nos títulos, 10 no corpo). Os títulos
  mais finos picavam os guias (o de especialidades Lobinho/Escoteiro foi de 457 a 1.458 trechos); a junção os traz de
  volta a 250, sem perder nenhuma das 174 especialidades.
- **Alternatives**: ordenar toda página de colunas coluna a coluna (a tabela perderia a linha); só o tamanho, sem a
  família (o guia da Descoberta usa a mesma família, em 14 pt, nos blocos).

## R37 — O teto do trecho

- **Decision**: depois da árvore, todo trecho com mais de 512 tokens do tokenizador do e5 (`passage: ` e especiais
  incluídos) é dividido — a unidade normativa nas linhas do corpo, com "Art. N (parte i de n)", o caput curto repetido e
  as páginas de cada parte; a janela, nas linhas e frases —, para qualquer embedder; `teto=512:e5-tok:<sha>` na versão.
- **Rationale**: no artefato da `estrutural-v4`, 378 trechos passavam do que o e5 lê (82 normativos, o maior com 5.717
  tokens; 296 janelas, porque o texto real chega a 1,6 vez a estimativa por caracteres).
- **Alternatives**: janela em tokens reais (mudaria todo trecho); teto por embedder (o artefato tem um só conjunto de
  trechos para os dois modelos).

## R38 — Transcrição e ruído de OCR

- **Decision**: o digitalizado entra por `ocr/<caminho>.txt` (`transcricao-v1`), de partida pelo Tesseract 5 local e
  revisado pelo Codex (prompt e scripts em `scripts/`); nos documentos de `ocr/`, sai do trecho o carimbo com cara de
  carimbo, a linha e o rabo ilegíveis, pelo vocabulário dos nascidos digitais da mesma execução (22.856 palavras).
- **Rationale**: as 57 cópias OCR em PDF não tinham origem nem como revisar, e as 31 atas da Assembleia Regional de SP
  de 1994 a 2020 não têm camada de texto. Numa ata de 2005 com carimbo sobre o texto, o Tesseract erra o trecho sob o
  carimbo ("pagéstoNO «;"); um modelo de visão o recupera ("pagá-lo"), mas por API paga, que o mantenedor recusou. No
  calibrado sobre as 25.004 linhas OCR do acervo, o filtro tira 558 (carimbo, timbre e lixo) e não tira conteúdo
  legítimo que se repete ("RAMO LOBINHO" de um relatório escaneado), porque o carimbo precisa ter telefone, CEP, CNPJ ou
  palavras de cartório.
- **Alternatives**: vocabulário de dicionário externo (dependência e dado fora do acervo); filtro de carimbo só pela
  repetição (tirava 2.232 linhas, com conteúdo).

## R39 — Unidades declaradas

- **Decision**: `under` é fonte (o título logo abaixo do nome declarado); a exceção troca as fontes (`sources`) e limpa
  o título (`trim`); unidade do mesmo tipo dentro de outra é seção dela; a linha da borda colada ao número da página
  conta como corrida.
- **Rationale**: com a tipografia, os cargos são títulos de nível 3 sob "LINHA ESCOTISTA" e "LINHA DIRIGENTE" (o
  "Descritivos de Cargos" da declaração não existe no PDF), e o sumário do guia os cobria como capítulo; as competências
  são títulos de nível 2 sob "COMPETÊNCIAS ESSENCIAIS/ESPECÍFICAS", com o cabeçalho da tabela colado; as reuniões do Clã
  vêm sem ordinal; o eixo do Desafio Sênior está no rodapé girado e colado ao número da página ("100MEIO AMBIENTE"), em
  7 das 24 páginas do eixo. Saíram: 13 cargos, 6 a 10 competências por guia (o de Filhotes não usa essa estrutura), 16
  reuniões no Clã, 4 eixos e 16 blocos no Desafio Sênior, 4 eixos e 17 blocos na Descoberta.

## R40 — A codificação na GPU na ingestão offline

- **Decision**: o `E5Embedder` aceita `device="cuda"` (`AXON_SCOUTING_EMBEDDING_DEVICE=cuda` na CLI da ingestão), com o
  `CUDAExecutionProvider` na frente e a CPU de reserva, lotes de 64 e ordenados pelo tamanho; o `onnxruntime-gpu`
  (CUDA 13 e cuDNN 9 em wheels, carregados por `onnxruntime.preload_dlls`) mora num venv só da ingestão,
  `.cache/gpu-venv` (`scripts/gpu-venv.sh`). A carga do pack e a imagem de produção continuam na CPU.
- **Rationale**: a reindexação da `estrutural-v4` levou 22 min, quase todos codificando no e5 na CPU (~10 trechos/s).
  Na RTX 5060 da máquina do mantenedor: 251 trechos/s, e o cosseno entre o vetor da GPU e o da CPU é ≥ 0,9999998 em
  mil trechos — o índice é o mesmo, e as perguntas seguem codificadas na CPU.
- **Alternatives**: `onnxruntime-gpu` no venv do projeto (os dois pacotes ocupam o mesmo módulo e não convivem); a GPU
  também em produção (as VMs pequenas não têm).
