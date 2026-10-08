# Contrato — catálogo do corpus (`corpus.yaml`)

Arquivo do curador; a única fonte dos metadados e da relação de substituição (clarificação 1). Mora no repositório do
`ai-scouting`, em `corpus/corpus.yaml`, com os PDFs ao lado, referenciados por caminho relativo (clarificação de
2026-10-08). Decisões em
[research.md](../research.md) R3 e R4; tipos em [data-model.md](../data-model.md).

```yaml
documents:
  - file: por/por-2023.pdf
    source_url: https://www.escoteiros.org.br/wp-content/uploads/por-2023.pdf   # opcional: o link oficial do arquivo
    document_id: por
    version: "2023"
    type: por
    title: "Princípios, Organização e Regras (POR)"
    jurisdiction: nacional
    publication_date: 2023-03-01
    effective_date: 2023-03-01

  - file: por/por-2025.pdf
    document_id: por
    version: "2025"
    type: por
    title: "Princípios, Organização e Regras (POR)"
    jurisdiction: nacional
    effective_date: 2025-01-01
    supersedes: "2023"            # a 2023 vira substituido, com expiry_date 2024-12-31

  - file: manuais/pioneiro-2026.pdf
    document_id: manual-pioneiro
    version: "2026"
    type: manual
    title: "Manual do Ramo Pioneiro"
    branch: pioneiro
    jurisdiction: nacional
    effective_date: 2026-03-01

  - file: resolucoes/res-2024-03.pdf
    document_id: resolucao-2024-03
    version: "1"
    type: resolucao
    title: "Resolução 03/2024"
    jurisdiction: nacional
    effective_date: 2024-05-10
    status: revogado
    expiry_date: 2025-12-31
```

| Regra | Rejeição (lista todos os problemas; nada é aplicado) |
|---|---|
| raiz é um mapa com `documents` (lista não vazia) | "catálogo sem `documents`" |
| campo obrigatório ausente (`file`, `document_id`, `version`, `type`, `title`, `jurisdiction`, `effective_date`) | entrada N: campos faltantes `[...]` |
| campo desconhecido | entrada N: campo desconhecido `expiry_dte` |
| formato (`document_id`, `version`, datas, `type`, `branch`, `status`) | entrada N: campo inválido, com o valor e o esperado |
| `file` fora do diretório do catálogo ou inexistente | entrada N: arquivo |
| (`document_id`, `version`) repetido | as duas entradas |
| `status: revogado` sem `expiry_date` | entrada N |
| `source_url` que não é link `http(s)://` sem espaço | entrada N: campo inválido |
| linhagem (R4): `supersedes` inexistente, substituída por duas, ciclo, sucessor que não começa depois, `expiry_date` incoerente, mais de uma vigente | a linhagem, nomeando as versões |
| PDF sem texto em nenhuma página | entrada N: sem camada de texto (OCR fora do escopo) |

Versões são texto: no YAML, aspas evitam que `2023` vire número e `1.10` vire `1.1`. O status `vigente` e o
`substituido` nunca são escritos pelo curador — são derivados. Para tirar um documento do índice, tire-o do catálogo.
