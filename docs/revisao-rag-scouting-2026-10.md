# Revisão do RAG do pack scouting — 2026-10-27

Por que "Qual o marco simbólico dos 5 ramos?" recebeu, em produção, a formulação de um ramo só, embora as cinco estejam
no corpus — e o que isso diz do resto da recuperação. Este documento separa o que foi **observado** no código e nos
artefatos, o que foi **reproduzido** localmente, o que se **infere** de produção e o que **depende do trace** de
produção. As correções estão distribuídas pelas specs dos módulos (101, 102, 103 e 105), cada uma na própria fronteira;
a primeira etapa (a rede de segurança da 105, US6) já está feita.

## Como reproduzir

Código real do pack no `.venv` do `axon-scouting` — `ArtifactIndex` + `E5Embedder` + `Bm25Encoder` +
`ScoutingRetriever` + `MetadataReranker` + `derive_context` —, o e5 em `.cache/e5` e o índice do pacote. O corte do
gateway é o `render_within` do core (0.7.0rc4 no ambiente do pack; o caminho de recuperação, o rerank e o corte não
mudaram até a rc7). Data de referência 2026-10-27. Desde a 105 US6, o mesmo caminho roda pelo harness:

```bash
cd axon-scouting
AXON_PROFILE=test AXON_PACKS_FILE=eval/packs.yaml AXON_ASSISTANTS_FILE=eval/assistants.yaml \
  uv run --python 3.14 --group platform axon eval run --golden eval/regression.yaml \
  --baseline eval/regression-baseline.json
```

## 1. Fatos observados

**Produção usa o mesmo índice e o mesmo código.** O índice de `axon-cfblabs/packages/scouting-index/` é byte a byte o do
pack (build `scouting__20261026T133325Z`, 593 documentos, 16.742 trechos, vetores e5 e pplx), copiado sobre o pack no
commit `a17ebc3`. A instalação usa `embedder: e5`; o `compose.yml` não repassa `AXON_RAG_*` nem
`AXON_TOOL_MAX_RESPONSE_BYTES` (valem 20 candidatos, 5 trechos, sem limiar e 16.384 bytes); o Assistant `scouting` não
declara `limits` (sem teto de contexto) nem `controller` (sem escalada).

**As cinco formulações estão no texto indexado** — nos manuais de cada ramo e, juntas, no POR 2025 v2.1 (pp. 58, 62,
66, 72, 78). Nada está ausente, sem extração ou removido na limpeza: há fragmentação ruim e falha de recuperação e
seleção.

| # | Módulo | Achado | Onde |
|---|---|---|---|
| F1 | 102 | 175 trechos cujo corpo é só "O Marco Simbólico" (163 no Manual de Filhotes). O rodapé é um bloco de várias linhas (`CAPÍTULO 3 / O Marco Simbólico / 60 / CAPÍTULO 3 / O Marco Simbólico`); a detecção de linha corrida só olha a primeira e a última linha da página, e o `CAPÍTULO 3` que sobra abre um capítulo a cada página. 2.656 trechos (16%) têm corpo com menos de 60 caracteres; 1.984 têm corpo repetido. | `rag/ingestion/domain/text.py` (`_edges`, `_running_lines`); `chunking.py` (`_CHAPTER`) |
| F2 | 102 | **POR: 108 das 197 regras (55%) só com o título.** Os títulos estão numa coluna lateral que o PDFium extrai no fim da página; o corpo cai em 32 janelas sem regra (54,5 KB) ou na regra vizinha (a `regra158` traz o sinal do Ramo Filhotes, que é da 159). Já existia no índice da Fase 5. | `documents.jsonl`, POR p. 58; `rag/ingestion/domain/structure.py` |
| F3 | 102 | 1.113 trechos com U+FFFE (hifenização do PDFium: "com￾põem"), 90 com hífen suave, 14 com U+FFFD. A palavra sai partida para o BM25 e para o e5. | `text.py` (`_join_hyphenated` só trata `-`) |
| F4 | 102 | 467 prefixos com o número da página colado ao título ("30IDENTIDADE E SÍMBOLOS"). | prefixo dos trechos |
| F5 | 102 | Com o tokenizador real do e5 e `passage: `, 12,9% dos trechos passam de 512 tokens (mediana 145, p95 578, máx. 5.717): a janela é caracteres/4 até 600, mais o cabeçalho. Só o vetor denso trunca; o texto e o BM25 ficam inteiros. | `e5.py` (`MAX_TOKENS`); `chunking.py` (`window_max`) |
| F6 | 102 | `Chunk.page = page_start`: em trecho de duas páginas a frase pode estar na segunda (Filhotes `cap3@p46~2` cita p. 46, frase na 47). | `rag/index/api.py` (`to_chunk`) |
| F7 | 101/102/103 | Filhotes não é ramo (`BRANCHES` e léxico têm 4); os documentos de Filhotes são "gerais" e entram em toda busca filtrada por outro ramo. | `rag/index/api.py`; `context/lexicon.py` |
| F8 | 101 | Pergunta com vários ramos ou "cada ramo" → nenhum filtro; não há noção de pergunta com várias facetas. | `context/derivation.py` (`_branch`) |
| F9 | curadoria | Os quatro "Competências e Rotas de Aprendizagem" de 2019 estão vigentes e trazem formulações diferentes do manual de 2026 e do POR (Escoteiro "Explorar novos territórios…", Pioneiro "Tenho um projeto para a minha vida"). *Corrigido em 2026-10-27:* "PRELIMINAR" neles é o nome de um nível de competência, não a marca de uma edição provisória; se o documento de 2019 foi substituído pelo manual é decisão de curadoria, que o catálogo já expressa (`supersedes`, datas) — não há precedência a criar em código (ADR-045). | `corpus.yaml` |
| F10 | 103 | **O reranker não lê a pergunta**: devolve a ordem da fusão com desempate por metadados. `rerank_gain` é 0 por construção. | `rag/retrieval/reranker.py`; `domain/ordering.py` |
| F11 | 103 | Densa e esparsa cortadas em `limit` antes do RRF; consulta sem termo esparso devolve vazio mesmo com a densa. | `rag/index/adapters/memory.py` |
| F12 | 004/005 | O `rag_first` pede 20 candidatos e o gateway os renderiza em 16.384 bytes: **20 viram 10–14** antes do rerank. Hoje não muda nada (o reranker mantém a ordem da fusão); passa a anular "mais candidatos" assim que houver um reranker que leia a pergunta. Os candidatos não vão ao modelo — só os entregues passam pela cerca. | `graph/adapters/langgraph/nodes/rag.py` (`retrieve`); `capabilities/service.py` (`_chunks_outcome`) |
| F13 | 005 | O portão mede presença e score; sem limiar em produção, e a similaridade do e5 é comprimida (0,82–0,88). Nada mede se as facetas pedidas foram cobertas. | `graph/domain/gate.py` |
| F14 | 005/101 | A consulta é só a última mensagem; pergunta de seguimento perde o contexto. | `graph/service.py`; `pack.py` |
| F15 | 101 | O prompt só trata "nenhum trecho chegou": nada sobre cobertura parcial, sobre não afirmar ausência no corpus a partir dos trechos, nem sobre conceitos vizinhos (marco simbólico × ênfase educativa × lema × símbolo × sinal). | `prompts/domain.py` |
| F16 | 105 | A semente citava um documento retirado (s08, s09); a baseline era do índice de 413 trechos; nenhum item multifaceta; o harness casa evidência por documento, não por conteúdo. | `eval/` *(corrigido na 105 US6)* |

## 2. Reprodução

F/L/E/S/P = trecho com a formulação de Filhotes, Lobinho, Escoteiro, Sênior, Pioneiro. "Entregues" é o que vai à
geração.

| # | Experimento | Parâmetros | Resultado |
|---|---|---|---|
| E1 | Pergunta original | 20 candidatos, 16 KB, 5 trechos | top-20: F L S · após o gateway, 10 trechos: L S · **entregues: só L** |
| E2 | Mais candidatos | 30, 16 KB, 5 | top-30: F L S P · entregues: L |
| E3 | Gateway maior | 30, 64 KB, 10 | entregues: L S |
| E4 | Tudo alto | 60, 256 KB, 20 | top-60: F L E S P (8 stubs) · entregues: F L S |
| E5 | Paráfrases | "cada ramo" / "cada um dos ramos" / nomeando os 5 | entregues: E / **S** / F S |
| E6 | 6 variantes mínimas | "cinco", sem acento, plural… | de 0 a 2 formulações; a Regra 158 em nenhuma |
| E7 | Uma pergunta por ramo | defaults | F L E S ✓, **P ✗** mesmo com filtro de ramo |
| E8 | Postos da evidência (pergunta original) | denso / BM25 | F 8/25 · L 12/0 · E 18/18 · S 6/10 · P 14/44; o POR no denso 496–1105 |
| E9 | Seleção alternativa | sem trechos curtos / 1 por documento / decomposição por ramo | só a decomposição ajuda: L → F L S |
| E10 | Subconsulta por ramo, com filtro | 3 moldes | a formulação entre os postos 0–8 de cada ramo |
| E11 | Tokens reais | 16.742 trechos | 12,9% acima de 512 |

**Pelo harness (105 US6, linha de base `eval/regression-baseline.json`):** `scouting:fact_recall` 0,52 nos 20 itens.
Marco simbólico por ramo: 4 de 5 (Pioneiro 0); agregados 0,2–0,4; **lemas e faixas etárias** — que só o POR enuncia —
quase sempre 0; "O que diz a Regra 054?" 0. O problema não é da pergunta do exemplo: é da seleção e, no POR, da
ingestão. A semente também piorou com o corpus de 593 documentos (recall@5 0,89 → 0,78; s02 e s07 deixaram de achar a
evidência).

O embedder pplx não foi medido (precisa de chave; produção usa e5).

## 3. Inferências sobre produção

- Mesmo índice, mesmo código, e5 e os defaults: os mecanismos de E1–E11 valem lá. "Só Sênior" é o que a variação por
  redação produz (E5, E6).
- A Regra 158 nunca aparece no top-5 local. Em produção o conjunto entregue foi outro — outra redação, outra data, uma
  pergunta de seguimento (F14) —, ou o modelo a citou de memória, sem `[[id]]`, o que a 104 não barra. Se o trecho
  chegou, chegou corrompido (F2).
- "Os trechos não continham as demais formulações" era verdade sobre os cinco trechos entregues: a falha é entregar uma
  faceta de cinco e o prompt não separar "não veio nos trechos" de "não existe no corpus".

## 4. Pendente de trace e configuração de produção

1. O trace 009 da requisição: `retrieval` (candidatos, reordenados e entregues, com scores), `coverage_gate`,
   `tool_call` (`truncated`), avisos (`ContextTrimmed`, `RerankFailed`) e, com a captura ligada, `model_exchange`.
2. O texto exato, a data (`reference_time`) e se havia histórico.
3. O modelo de geração efetivo (a console pode ter sobreposto o `glm-5.3-flash`).
4. O ambiente real da stack (`AXON_RAG_*`, `AXON_TOOL_MAX_RESPONSE_BYTES`) e a imagem implantada (o build do índice no
   log do `install-scouting-index.py`).
5. Reexecução local com a mesma data e o mesmo texto, comparando os ids entregues com o trace; e o trace de 3 a 5
   perguntas reais recentes, para medir a frequência de `truncated` e o tamanho médio dos candidatos.

## 5. Diagnóstico

**Causas confirmadas**

1. **Seleção que não lê a pergunta** (F10): a fusão põe trechos *sobre* o marco simbólico acima dos que *contêm* a
   formulação. Afeta perguntas de um ramo (Pioneiro) e é sensível à redação.
2. **Pergunta multifaceta sem decomposição** (F8, F13): cinco trechos e nenhuma cota por faceta. Nem com 60 candidatos e
   20 trechos se chega a cinco de cinco.
3. **Ingestão** (F1, F2, F3): stubs ocupam vagas de candidato; o POR — que enuncia as cinco formulações, os lemas e as
   faixas etárias — fica longe nos postos e com corpos trocados. Afeta toda pergunta normativa.
4. **Prompt sem cobertura parcial** (F15): afirma ausência e preenche com conceitos vizinhos.

**Contribuintes**: Filhotes fora dos ramos (F7); precedência editorial ausente (F9); truncamento de 12,9% (F5); número
de página colado (F4); quase-duplicatas entre documentos.

**Latente**: o corte do gateway nos candidatos (F12).

**Hipóteses pendentes**: o conjunto entregue em produção (§4); página citada errada (F6); pergunta de seguimento (F14);
o pplx.

## 6. Correções, por módulo

| Módulo | Correção | Contrato / ADR |
|---|---|---|
| **105** *(feito)* | Métrica `scouting:fact_recall`, conjunto de regressão (`eval/regression.yaml`) com linha de base, semente corrigida, CI sem os PDFs. | nenhum |
| **102** *(feito)* | Blocos corridos de várias linhas (k linhas nas bordas, limiar por faixa de páginas); "CAPÍTULO N" + título como um cabeçalho; nenhum trecho sem corpo (o curto se funde ao seguinte); ordem de leitura pela posição das linhas no PDFium (o *spike* nas pp. 58, 62, 116 e 118 do POR mostrou os títulos acima de cada corpo, desenhados depois da página); U+FFFE e hífen suave; número de página colado; janela calibrada para p99 ≤ 512 tokens do e5 (`estrutural-v2`); relatório da ingestão com stubs, regras sem corpo, U+FFFE e truncados por modelo. | interno; nova versão do índice |
| **101** | Filhotes como ramo no léxico e no catálogo; `branches` na derivação quando a pergunta cita vários ramos ou "cada/todos os/N ramos"; prompt com cobertura parcial ("não veio nos trechos", nunca "não existe"), o conceito pedido sem trocar por vizinho, e preliminar subordinado ao definitivo. | ADR do pack (abaixo) |
| **103** | Decomposição por faceta no retriever (uma subbusca por ramo, cota por faceta no top-N); reranker v2/v3 que lê a pergunta, escolhido por medição (RAM, latência, ganho); colapso de quase-duplicatas; precedência editorial como desempate; densa mesmo sem termo esparso. | ADR do pack; ADR da escolha do reranker |
| **Core** *(condicional)* | Candidatos do `rag_first` fora do limite de resposta do gateway (o corte e a cerca só nos entregues); `AXON_RAG_PASSAGES` 8–10 se a medição pedir. Portão inalterado: suficiência por faceta é domínio. | ADR novo (seam 004 → 005), só se o reranker provar ganho com mais candidatos |

**ADR do pack** — [ADR-045](adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md), "Ramo Filhotes e pergunta sobre
vários ramos no scouting": `BRANCHES` e o catálogo (102), `retrieval_filters` com `branches` (101 → 103, com
`contracts/retrieval-filters.md`). A precedência editorial saiu: o F9 era uma leitura errada. O contrato 001 não muda; opcionais, cada um com ADR próprio:
`EvalChunk.text` para os entregues e página final no `Chunk` (F6). Nenhum ADR aceito é editado.

## 7. Ordem, dependências e aceite

1. **105 — rede de segurança** *(feita)*. Linha de base: `fact_recall` 0,52.
2. **102 — ingestão** *(feita, 102 US6)*. 0 stubs; 0 regras do POR sem corpo, com o corpo certo; 0 U+FFFE; 2,1%
   acima de 512 tokens (unidades normativas inteiras e tabelas de relatório — a meta de 1% pediria calibração);
   marcos por ramo 5/5 e lemas por ramo 3/3; `fact_recall` 0,52 → 0,75. O *spike* corrigiu a hipótese: os títulos das
   regras não ficam numa coluna lateral, mas acima de cada corpo, desenhados depois da página. A semente achou o
   próprio erro — o Sinal de Promessa é a Regra 160, não a 159 — e perdeu s09, cujo trecho perdeu o capítulo que vinha
   do cabeçalho corrido (pendência da 102, R29).
3. **ADR do pack + 101/103 — Filhotes e facetas** *(feita, [ADR-045](adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md))*.
   Um trecho de cada ramo nos primeiros entregues, com os 5 trechos do default; `fact_recall` 0,75 → 0,81, "dos 5
   ramos" e "dos cinco ramos" 0,8 (≥ 4/5), lema de cada ramo 0,8, perguntas de um ramo sem piora, semente sem
   regressão. Abaixo do aceite: "de cada ramo" e os cinco nomeados (0,4) e as faixas etárias (0) — dentro da faceta, a
   fusão põe em primeiro a definição genérica, e as faixas etárias estão no POR, que é geral. Precedência editorial saiu
   do escopo (F9 corrigido).
4. **103 — reranker** (depois de 1–3). Aceite: agregados 5/5, `rerank_gain` > 0, latência e RAM no orçamento da VM.
5. **Core** (só se 4 mostrar ganho com mais candidatos).
6. **101 — prompt** (em paralelo a 2). Aceite, nas rodadas manuais com modelo real e juiz: nenhuma afirmação de
   ausência no corpus com recuperação parcial; nenhuma troca de lema por marco simbólico.
7. **Curadoria**: precedência e `branch: filhotes` no catálogo; marcar os "Competências… PRELIMINAR".

Depois de 2–4: um artefato novo do índice na instalação (`axon-cfblabs/packages/scouting-index` e `PACKS`), com o deploy
só sob permissão explícita do mantenedor; e, em produção, as variantes de E6 pelo Open WebUI com o trace confirmando as
cinco facetas entregues.
