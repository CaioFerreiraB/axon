# Revisão do RAG do pack scouting — 2026-11-09: a Diretoria Regional

Em 08/11, uma conversa no Open WebUI de produção tratou da Diretoria Regional (prazos de gestão, composição, reeleição).
A pergunta central foi:

> "para a diretoria regional da região de são paulo, uma pessoa que foi diretor vice presidente em duas gestões
> seguidas, pode se candidatar a diretor presidente na gestão seguinte?"

O assistente respondeu pelo Regulamento da Região SP e não achou a regra. Ela só apareceu quando o mantenedor pediu
"olhe no estatuto nacional".

Este documento separa:
- o que foi **observado** em produção;
- o que foi **medido** localmente, com o mesmo índice;
- o que foi **corrigido** (ADR-061);
- o que fica **para decidir**: o grafo e a busca global.

## Como reproduzir

Código real do pack no `.venv` do `axon-scouting`: `ArtifactIndex` + `E5Embedder` + `Bm25Encoder` + `derive_context` +
`ScoutingRetriever`. Usa o e5 em `.cache/e5`, o índice do pacote 0.8.1 (642 documentos, 15.685 trechos), 20 candidatos
como na instalação e a data de referência de 2026-11-08. As sondagens estão no apêndice. O harness roda o mesmo
caminho:

```bash
cd axon-scouting
AXON_PROFILE=test AXON_PACKS_FILE=eval/packs.yaml AXON_ASSISTANTS_FILE=eval/assistants.yaml \
AXON_RAG_CANDIDATES=20 AXON_RAG_PASSAGES=20 AXON_TOOL_MAX_RESPONSE_BYTES=65536 \
  uv run --group platform axon eval run --golden eval/acervo.yaml --baseline eval/acervo-baseline.json
```

## 1. O que produção mostra

- **Langfuse**: três turnos, às 22:55, 22:56 e 22:57 UTC. Todos `rag_first`, cada um com `search_docs`,
  `list_documents`, `list_units` e uma geração do `glm-5.3-flash`.
- **Sem conteúdo**: a captura de conteúdo está desligada, então o trace não guarda a pergunta nem os trechos.
- **Sem segunda chance**: o Assistant `scouting` não tem `controller`, e `AXON_RAG_MIN_SCORE` não tem valor. O portão
  sempre dá "coberto" quando há trechos, e nada escala para o loop.

## 2. A resposta precisa de dois documentos

- **Estatuto da UEB, Art. 27**: "mandato de três anos… eleitos por chapa pela Assembleia Regional". O §3º diz: "É
  vedada a reeleição de membros da Diretoria Regional por mais de um mandato consecutivo, **para a mesma função**."
- **Regulamento da Região SP 2022, Art. 26**: mandato de três anos. Diretor-presidente e Diretor Vice-presidente são
  cargos distintos. O Regulamento não tem regra própria de reeleição para a DR: o Art. 42 trata dos distritos.

## 3. Causas medidas

| Causa | Evidência local | Peso |
|---|---|---|
| **Vocabulário.** A pergunta descreve um caso ("duas gestões seguidas", "se candidatar"); a norma fala em abstrato ("reeleição", "mandato consecutivo", "mesma função"). | Estatuto Art. 27: **448º** no denso (e5) e **1.273º** no BM25, de 14.872 trechos. Buscado com a redação do artigo, é o **1º**. Com cinco reescritas realistas, o Art. 27 fica entre o 1º e o 7º, e o Regulamento Art. 26, também. | Principal |
| **Proporção do corpus.** Atas são 36% dos trechos e relatórios, 10%; estatuto, regulamentos e POR, 5%. As atas de eleição falam a língua da pergunta. | Top 20: **15 atas**, 3 trechos do Regulamento SP (Arts. 29, 16 e 24, não o 26), 1 resolução e 1 relatório. O 2º é um trecho de ata com OCR corrompido (`sp-2021-ata-frjl-sp-1#s9@p8~3`). | Alto |
| **Os sinais da derivação não pesam.** O tipo e o órgão sugeridos só desempatam (ADR-046, ADR-049), e a fusão quase nunca empata. O tema saiu `gestao_do_grupo`. | `suggested_types: [por, resolucao, estatuto]` e `suggested_bodies: [diretoria_regional]` não mudaram a ordem. | Médio |
| **Sem segunda chance.** | Mesmo restrito a estatuto, regulamento, POR e resolução, o Art. 27 fica em **88º**. | Baixo, sozinha |

**Por que o segundo turno deu certo**: "estatuto" vira filtro de tipo, e o universo cai para os 141 trechos do
Estatuto, onde o Art. 27 vence. O mantenedor fez à mão o que a recuperação deveria ter feito.

**Granularidade.** O §3º sozinho tem similaridade 0,876 com a pergunta, e o artigo inteiro, 0,872; o corte do top 20
denso é 0,887. Descer o índice até parágrafo serve à citação e ao grafo, não ao vocabulário.

## 4. Defeitos achados no caminho, corrigidos (ADR-061, `axon-scouting` 0.9.0)

1. **Órgão como filtro zerava a busca.**
   - Com tipo citado, o órgão nomeado virava `bodies`, mas o `bodies` de um documento é a pasta da taxonomia: o
     Regulamento SP está em `gestao_institucional_e_governanca`.
   - "diretoria **regional**" ainda virava `scopes: [regional]`, o que excluía o Estatuto, que é nacional.
   - Agora o órgão só filtra quando é o **emissor** ("resoluções **da** diretoria regional"). O órgão-assunto só
     desempata, e o nome dele não é abrangência.
   - A busca filtrada que volta vazia é refeita sem órgão e abrangência, com a marca `relaxed`.
2. **Seguimento perdia o assunto.**
   - A busca do `rag_first` usa só a última mensagem.
   - Agora a pergunta sem assunto próprio, curta ou com marcador de retomada, herda o assunto da última pergunta do
     usuário que tem um (`anchor`). O retriever busca com a âncora e com a pergunta sozinha e junta os achados pela
     melhor posição.
3. **Hierarquia das normas no prompt.** Numa pergunta sobre um órgão ou sobre estatutos e regulamentos, a resposta põe
   primeiro a regra do nível de cima e depois o que o de baixo acrescenta.

**Antes e depois** (posição no top 20; "—" = fora):

| Pergunta | Antes | Depois |
|---|---|---|
| "O que diz o regulamento regional sobre a diretoria regional? Prazo de gestão e composição" | **0 trechos** | Regulamento Art. 26 em 6º |
| "Segundo o estatuto, qual o mandato da diretoria regional?" | **0 trechos** | Estatuto Art. 27 em 1º |
| "e no estatuto nacional?" (depois da pergunta de 08/11) | — | Art. 27 em 9º |
| "olhe no estatuto nacional" (idem) | — | Art. 27 em 1º |
| "Qual o prazo de gestão?" (depois de "Como funciona a diretoria regional?") | — | Art. 27 em 3º, Art. 26 em 12º |
| "e quem pode ser reeleito?" (idem) | — | Art. 27 em 2º, Art. 26 em 10º |
| A pergunta de 08/11 | — | — (é o vocabulário: Fase 2) |

**Avaliação**:
- `golden`, regressão (0,9768) e acervo (0,8915) ficaram idênticos.
- O acervo ganhou três itens: os dois primeiros da tabela, com `fact_recall` 1,0 (antes seriam 0), e a pergunta de
  08/11 como controle, com 0.
- A nova linha de base do acervo, com 46 itens, é 0,8768 = (0,8915 × 43 + 2) / 46. Nenhum item antigo mudou.

## 5. Avaliações pedidas pelo mantenedor

- **GraphRAG da Microsoft × grafo com esquema fixo.**
  - O da Microsoft extrai entidades de esquema livre por LLM de todo o corpus, inclusive das atas, e responde por
    resumos de comunidades, sem `chunk_id` nem vigência.
  - Aqui serve um GraphRAG de **esquema fixo**: a organização curada, a árvore e as citações por regra, e as relações
    que exigem entender o texto extraídas offline por LLM, só nas normas vigentes, com a fonte conferida. Na hora da
    pergunta não há modelo.
- **Custo da recuperação ancorada no órgão.** Desprezível em dinheiro e latência: é uma consulta em memória, e dentro
  dos 20 trechos não acrescenta tokens. O custo real é a vaga tomada, limitada a 3 trechos por documento e a nenhum na
  pergunta histórica.
- **`controller`.** Não é problema, mas sozinho não muda o `rag_first`, que só o usa para escalar sem cobertura. O que
  resolve o vocabulário é uma etapa de reescrita da consulta no core (005), com uma chamada a mais por turno.
- **Atas por último, nunca fora.** Faixas de autoridade com reserva: estatuto, regulamento e POR → resolução e
  política → manuais → atas e relatórios, cada faixa com mínimo garantido. A pergunta histórica inverte a ordem.
- **Busca global.** Fichas estruturadas por ata, extraídas offline, com página conferida por código, e a linha do tempo
  por órgão e ano montada a partir delas. Só a pergunta de síntese as recebe, e ela continua com uma chamada.

## 6. O grafo proposto

- O desenho aprovado está em `axon-scouting/corpus/Organização Escoteira.revisado.json` (arrows.app). O original do
  mantenedor fica intacto, ao lado.
- Ele tem três camadas:
  - **organização**: tipos de instituição, de órgão e cargos;
  - **normas**: documento, unidade e trecho;
  - **ponte**: `DISCIPLINA`, `EMITIDO_POR`, `APLICA_SE_A`.
- A busca global acrescenta ficha de reunião, deliberação, eleição, linha do tempo e resumo de norma.
- O rascunho da camada de organização é `axon-scouting/corpus/organizacao.yaml`: 49 fontes conferidas no texto do
  artefato e 9 marcadas "a verificar". Entre elas está "CAN nomeia DEN", do desenho original: o Estatuto, Art. 18, §1º
  só diz que os membros da DEN "podem ser escolhidos" entre os conselheiros.
- **Armazenamento**:
  - o grafo fica em memória, dentro do pack, como o índice (ADR-043): arquivos no artefato, carregados pelo
    `ArtifactIndex`;
  - nenhum serviço nem banco novo;
  - um banco de grafos só valeria para exploração ad hoc, no computador do mantenedor.

## 7. Fase G feita: a busca global pelos resumos das atas (ADR-062, `axon-scouting` 0.10.0)

- **O conjunto de síntese** (`eval/sintese.yaml`): 13 perguntas cuja resposta está espalhada pelas atas da Assembleia
  Regional e do Conselho Consultivo Regional de SP, em quatro grupos (eleições, números, pauta, locais), com itens de
  desenvolvimento e de controle em cada um. Foi escrito **antes** da mudança: linha de base 0,4551.
- **As fichas**: o `gpt-4.1-mini` extrai offline uma ficha estruturada por ata (`scripts/fichas.py extract`):
  - tipo, data e local da reunião;
  - deliberações nas palavras da ata, eleições e números;
  - a página de cada item.

  Cada item é conferido por código contra a página.
  - Piloto nas 58 atas regionais: 1.796 de 1.902 itens conferidos (94,4%), por US$ 0,36.
  - As 256 atas: 5.298 de 5.677 (93,3%), por cerca de US$ 1,30.
- **Os resumos**, montados sem modelo (`build`): a ficha da reunião e a linha do tempo por órgão e ano, em
  `summaries.jsonl` ao lado do índice, sem vetores.
- **A pergunta de síntese**:
  - a derivação publica `synthesis` (anos, abrangência, órgãos);
  - a tool `scouting.search_summaries` entrega até 10 resumos à frente dos trechos;
  - as perguntas pontuais não mudam: nenhuma das 84 dos outros conjuntos pede síntese.

| Item de síntese | Sem resumos | Piloto (58 atas) | As 256 atas |
|---|---|---|---|
| presidentes regionais desde 2016 | 0,33 | 1,00 | 1,00 |
| mandatos das três últimas Diretorias | 0,00 | 0,67 | 0,33 |
| delegados credenciados 2019–2025 | 0,67 | 1,00 | 1,00 |
| delegados à Assembleia Nacional | 0,00 | 0,33 | 0,33 |
| novo Regulamento nos anos 2000 (controle) | 0,00 | 1,00 | 1,00 |
| quórum para reformar o Regulamento (controle) | 0,00 | 1,00 | 1,00 |
| Conselho Consultivo 2014–2015 (controle) | 0,33 | 1,00 | 1,00 |
| Conselho Consultivo 2017–2019 / 2023–2024 | 0,75 / 0,50 | 1,00 / 1,00 | 1,00 / 1,00 |
| **média dos 13** | **0,4551** | **0,8718** | **0,8462** |

- **Mesmos fatos dos dois lados**: as três colunas usam os mesmos fatos, com alternativas essenciais (a cidade, o
  período), e o "sem resumos" reproduz a linha de base.
- **Da coluna do piloto para a das 256 atas**: com todas as atas, outros órgãos regionais passaram a concorrer. A
  seleção ganhou o filtro por órgão nomeado e a melhor parte de cada ano antes da segunda.
- **Linha de base**: é a das 256 atas, gravada com `--force`. O harness a recusava por comparar com a do piloto, que
  nunca foi commitada.
- **Outros conjuntos**: `golden`, regressão (0,9768) e acervo (0,8768) ficaram iguais.

## 8. Próximos passos (para decidir)

1. **Fase 2, o grafo.**
   - Parágrafo e inciso na árvore (`estrutural-v6`).
   - `organizacao.yaml` revisado.
   - Camadas de normas e ponte por regra, mais a extração offline por LLM nas normas vigentes.
   - Seam `NormGraph`.
   - Recuperação guiada: o órgão e o cargo da pergunta → `DISCIPLINA` → `INSTANCIA_DE` → `SUBORDINA_SE_A`, nos níveis
     da pergunta e acima.
   - É o que resolve a pergunta de 08/11 e garante a hierarquia.
2. **Fase G**: feita (seção 7). Falta a revisão humana por amostra das fichas (`corpus/resumos/atas/`, ~10%) e as
   perguntas de síntese das atas nacionais.
3. **Se ainda faltar**: as faixas de autoridade e a reescrita da consulta pelo `controller` (core).
4. **Sem código**: ligar a captura de conteúdo do `scouting` na console, para o próximo caso trazer a pergunta e os
   trechos no Langfuse.

## Apêndice — sondagem

O caminho real da derivação até o retriever, com o artefato do pacote (rode de `axon-scouting/`, com
`XDG_DATA_HOME=$HOME/.local/share uv run --offline python -I sonda.py`):

```python
import asyncio
from datetime import date
from pathlib import Path

from axon_scouting.context.derivation import derive_context, to_slice
from axon_scouting.rag.index.adapters.artifact import ArtifactIndex
from axon_scouting.rag.index.adapters.bm25 import Bm25Encoder
from axon_scouting.rag.index.adapters.e5 import E5Embedder
from axon_scouting.rag.retrieval.retriever import ScoutingRetriever

P = ("para a diretoria regional da região de são paulo, uma pessoa que foi diretor vice presidente em duas gestões "
     "seguidas, pode se candidatar a diretor presidente na gestão seguinte?")
D = "Como funciona a diretoria regional?"
CASOS = [
    ("O que diz o regulamento regional sobre a diretoria regional? Prazo de gestão e composição", ()),
    ("Segundo o estatuto, qual o mandato da diretoria regional?", ()),
    (P, ()),
    ("e no estatuto nacional?", (P,)),
    ("olhe no estatuto nacional", (P,)),
    ("Qual o prazo de gestão?", (D,)),
    ("e quem pode ser reeleito?", (D,)),
]
ALVOS = {"estatuto-2024#art27@p19": "Est27", "regulamento-regional-sp-2022#art26@p9": "Reg26"}


async def main() -> None:
    raiz = Path("src/axon_scouting/data/index")
    retriever = ScoutingRetriever(ArtifactIndex(raiz, E5Embedder(Path(".cache/e5")), Bm25Encoder()))
    for pergunta, anteriores in CASOS:
        filtros = to_slice(derive_context(pergunta, date(2026, 11, 8), previous=anteriores))["retrieval_filters"]
        ids = [c.chunk_id for c in await retriever.search(pergunta, top_k=20, filters=filtros)]
        print(pergunta[:60], {nome: ids.index(i) + 1 if i in ids else "—" for i, nome in ALVOS.items()})


asyncio.run(main())
```

As posições "só no denso" e "só no BM25" saem do `MemoryIndex` (`cosine` e `sparse_score` de
`rag/index/domain/scoring.py`) sobre os mesmos candidatos filtrados.
