# Contrato — CLI `ai-scouting-corpus`

Script da distribuição (`[project.scripts] ai-scouting-corpus = "ai_scouting.pack:corpus_cli"`): o `pack.py` compõe os
adapters; `rag/ingestion/adapters/cli.py` faz argumentos e saída. Decisões em [research.md](../research.md) R10, R13,
R15, R17.

## Configuração (ambiente)

| Variável | Default | Uso |
|---|---|---|
| `AI_SCOUTING_QDRANT_URL` | `http://localhost:6333` | servidor Qdrant |
| `AI_SCOUTING_QDRANT_API_KEY` | — | opcional; nunca aparece em saída nem em erro |
| `AI_SCOUTING_INDEX` | `scouting` | nome do índice (alias) |
| `AI_SCOUTING_EMBEDDING_DIR` | — | diretório com `model.onnx` e `tokenizer.json`; obrigatório em `ingest` e `reindex` |

## Subcomandos

| Comando | Efeito | Saída |
|---|---|---|
| `ingest <corpus.yaml>` | valida tudo; com a versão do índice igual à publicada, monta um build novo reaproveitando o que não mudou e publica; sem índice, cria o primeiro | relatório (abaixo) |
| `reindex <corpus.yaml>` | como `ingest`, sem reaproveitar nada: recodifica tudo com a configuração atual e publica uma versão nova | relatório |
| `status` | versão publicada, contagem de documentos e chunks por linhagem e status, builds órfãos | tabela |
| `original <chunk_id>` | o texto original das páginas do chunk, com documento, versão, faixa de páginas e `sha256` da fonte | texto |
| `model fetch <dir>` | baixa `onnx/model.onnx` e `onnx/tokenizer.json` do `intfloat/multilingual-e5-small` na revisão fixada e confere os sha256; arquivo presente e íntegro não é baixado de novo | caminhos e hashes |

## Códigos de saída

| Código | Quando |
|---|---|
| 0 | sucesso |
| 1 | rejeição de catálogo, linhagem ou documento — nada foi escrito; `ingest` com versão diferente da publicada ("rode `reindex`") |
| 2 | uso, configuração (variável ausente, modelo com hash errado) ou infraestrutura (Qdrant fora) — nada foi escrito |

## Relatório de `ingest`/`reindex`

```text
índice scouting — build scouting__20261007T153000Z publicado
versão: estrutural-v1;janela=300-600 · intfloat/multilingual-e5-small (sha256 ca456c06…) · bm25-pt-v1;k1=1.2;b=0.75;avgdl=256

documento                 status       chunks  origem
por-2023                  substituido     194  reaproveitado
por-2025                  vigente         201  codificado
manual-pioneiro-2026      vigente          88  codificado
resolucao-2024-03-1       revogado          7  reaproveitado

removidos: estatuto-2019
avisos:
  manual-pioneiro-2026: página 1 sem texto
  resolucao-2024-03-1: unidade art3 com ~720 tokens estimados (o embedding denso trunca em 512)
duração: 4m12s
```

Com rejeição, o relatório lista só os problemas (todos), agrupados por entrada e por linhagem, e termina em
"nada foi aplicado".
