# Contrato — catálogo do corpus (`corpus.yaml`)

Arquivo do curador; a única fonte dos metadados e da relação de substituição (clarificação 1). Mora no repositório do
`axon-scouting`, em `corpus/corpus.yaml`, com os PDFs ao lado, referenciados por caminho relativo (clarificação de
2026-10-08). Decisões em
[research.md](../research.md) R3 e R4; tipos em [data-model.md](../data-model.md). Desde o
[ADR-049](../../../docs/adr/ADR-049-taxonomia-e-a-tipologia-do-acervo-no-scouting.md) o catálogo **não tem `type`**: o
tipo do documento é o da taxonomia, pela pasta do arquivo (abaixo). Um documento digitalizado aponta para a transcrição
em `ocr/<caminho do original>.txt` (ADR-050).

```yaml
documents:
  - file: por/por-2023.pdf
    source_url: https://www.escoteiros.org.br/wp-content/uploads/por-2023.pdf   # opcional: o link oficial do arquivo
    document_id: por
    version: "2023"
    title: "Princípios, Organização e Regras (POR)"
    jurisdiction: nacional
    publication_date: 2023-03-01
    effective_date: 2023-03-01

  - file: por/por-2025.pdf
    document_id: por
    version: "2025"
    title: "Princípios, Organização e Regras (POR)"
    jurisdiction: nacional
    effective_date: 2025-01-01
    supersedes: "2023"            # a 2023 vira substituido, com expiry_date 2024-12-31

  - file: manuais/pioneiro-2026.pdf
    document_id: manual-pioneiro
    version: "2026"
    title: "Manual do Ramo Pioneiro"
    branch: pioneiro
    jurisdiction: nacional
    effective_date: 2026-03-01

  - file: resolucoes/res-2024-03.pdf
    document_id: resolucao-2024-03
    version: "1"
    title: "Resolução 03/2024"
    jurisdiction: nacional
    effective_date: 2024-05-10
    status: revogado
    expiry_date: 2025-12-31
```

| Regra | Rejeição (lista todos os problemas; nada é aplicado) |
|---|---|
| raiz é um mapa com `documents` (lista não vazia) | "catálogo sem `documents`" |
| campo obrigatório ausente (`file`, `document_id`, `version`, `title`, `jurisdiction`, `effective_date`) | entrada N: campos faltantes `[...]` |
| campo `type` presente (ADR-049) | entrada N: o campo saiu do catálogo; o tipo é o da taxonomia |
| campo desconhecido | entrada N: campo desconhecido `expiry_dte` |
| formato (`document_id`, `version`, datas, `branch`, `status`) | entrada N: campo inválido, com o valor e o esperado |
| `file` fora do diretório do catálogo ou inexistente | entrada N: arquivo |
| (`document_id`, `version`) repetido | as duas entradas |
| `status: revogado` sem `expiry_date` | entrada N |
| `source_url` que não é link `http(s)://` sem espaço | entrada N: campo inválido |
| linhagem (R4): `supersedes` inexistente, substituída por duas, ciclo, sucessor que não começa depois, `expiry_date` incoerente, mais de uma vigente | a linhagem, nomeando as versões |
| PDF sem texto em nenhuma página | entrada N: sem camada de texto — transcreva em `ocr/<caminho>.txt` (ADR-050) |
| sem `taxonomia.yaml` e `estrutura.yaml` ao lado do catálogo | a execução inteira (ADR-049) |
| `file` fora de uma pasta de entrada da taxonomia (nem numa subpasta de região ou UEL dela) | entrada N: pasta fora da taxonomia |

Versões são texto: no YAML, aspas evitam que `2023` vire número e `1.10` vire `1.1`. O status `vigente` e o
`substituido` nunca são escritos pelo curador — são derivados. Para tirar um documento do índice, tire-o do catálogo.

## Taxonomia e estrutura ([ADR-048](../../../docs/adr/ADR-048-arvore-de-unidades-e-enumeracao-no-scouting.md))

Dois arquivos do curador ao lado do catálogo, lidos e validados com ele (research R33, R34):

```yaml
# corpus/taxonomia.yaml — cada entrada é uma pasta; o arquivo mora nela (região ou UEL como subpasta)
version: 1
entries:
  - {categoria: Conselho de Administração Nacional, subcategoria: Atas, tipo: Ata,
     pasta: conselho-de-administracao-nacional/atas, documento: Atas do CAN}
  - {categoria: Diretoria Regional, subcategoria: Resoluções, tipo: Resolução, pasta: diretoria-regional/resolucoes,
     documento: Resolução da DR}            # arquivos em diretoria-regional/resolucoes/sao-paulo/
  - {categoria: Comissão Fiscal, subcategoria: Ofícios, nivel: Regional, tipo: Ofício,
     pasta: comissao-fiscal/oficios/regional, documento: Ofícios da Comissão Fiscal Regional, origem: inferido}

# corpus/estrutura.yaml — como cada documento se organiza por dentro
version: 1
unit_kinds: {especialidade: {label: Especialidade, plural: especialidades}, …}
vocabulary: {eixo: {Meio Ambiente: [Consumo Responsável, …], …}, aliases: {Paz e Compreensão: Paz e Desenvolvimento}}
profiles: {artigos: {sources: [marcadores], units: [capitulo, secao, artigo, paragrafo], fallback: títulos}, …}
profile_by_type: {Ata: ata, Regulamento: artigos, Resolução: artigos, Manual: capitulos, …}
documents:                                   # exceções, em ordem; a primeira que casa vence
  - match: [guia-especialidades-insignias-senior-pioneiro]
    profile: especialidades
    branches: [senior, pioneiro]
    units:
      - {kind: especialidade, pages: 24-221, source: sumário, parent: eixo}
      - {kind: grupo_de_insignias, pages: 247-256, name: Insígnias de Interesse Especial — Ramo Pioneiro, branches: [pioneiro]}
  - folder: [programa-educativo/guias-de-jovens, programa-educativo/manuais-de-escotistas]
    profile: progressao
```

| Regra | Rejeição |
|---|---|
| `pasta` repetida ou fora de `corpus/` | a entrada da taxonomia |
| tipo da taxonomia sem perfil em `profile_by_type` | o tipo |
| perfil, tipo de unidade, eixo ou bloco não declarados | a regra que o usa |
| faixa de páginas que não casa com o sumário do documento (entrada fora, faixa vazia) | o documento e a faixa |
| `branches` com ramo fora de `BRANCHES` | a regra |
