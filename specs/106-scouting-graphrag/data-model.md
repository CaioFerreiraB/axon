# Data Model — 106 Grafo de domínio

As decisões estão no [research.md](research.md). O seam está em
[contracts/domain-graph-seam.md](contracts/domain-graph-seam.md) e o arquivo em
[contracts/graph-jsonl-v2.md](contracts/graph-jsonl-v2.md).

## Entidade (`Entity`)

| Campo | Tipo | Regra |
|---|---|---|
| `id` | `str` | `<prefixo>:<slug>`. O prefixo é um de `tipo_inst`, `tipo_orgao`, `inst`, `orgao`, `cargo`, `ramo`, `secao`, `area`, `conceito` e `doc`, e o slug é `[a-z0-9_-]+`. Único |
| `type` | `str` | o prefixo |
| `name` | `str` | não vazio |
| `aliases` | `tuple[str, ...]` | normalizados pela 101 (`context/text.py`); podem ser vazios |
| `terms` | `tuple[str, ...]` | os nomes que a reconhecem numa pergunta: o nome e os apelidos, e para os tipos de órgão os nomes de cargo que dizem o nível (102 R43). Sem os apelidos ambíguos ("vice", "presidente") |
| `source` | `str` | resolvível (FR-002); `a verificar` não entra |
| `origin` | `Origin` | `curado`, `regra` ou `modelo_conferido` |
| `level` | `str \| None` | `mundial` … `local`, para os tipos e as instâncias |

**Fontes por prefixo:**
- `organizacao.yaml`: `tipo_inst`, `tipo_orgao`, `inst`, `orgao` e `cargo`;
- `dominio.yaml`: `ramo`, `secao`, `area` e `conceito`;
- o catálogo da 102: `doc`, com os apelidos do título e do número, a partir do G5.

## Nós do acervo

| Nó | Chave | Campos |
|---|---|---|
| `Version` | `doc_key` | `document_id`, `type` (`taxonomy_id`), `role`, `scope`, `status`, `date` (vigência) e `bodies` |
| `Unit` | `unit_id` (`<doc_key>#u/…`; o documento inteiro, `<doc_key>#documento`) | `doc_key`, `unit_kind`, `title`, `chunk_ids` (na ordem do documento), `branches`, `parent` e `ancestors` (as unidades acima e, no documento de um ramo, o documento inteiro; para o `todas`). Só entram as que alguma aresta usa e as dos tipos de unidade com nome do ADR-048, que `itens` lista (G6) |
| `Event` | `evento:<doc_key>#<n>` | `doc_key`, `date`, `type` (`reuniao`, `deliberacao` ou `eleicao`), `text` (o tema e a decisão da ficha) e `page` |

## Aresta (`Edge`)

| Campo | Tipo | Regra |
|---|---|---|
| `type` | `EdgeType` | `SOBRE`, `CONTEM`, `GERA`, `DE`, `INSTANCIA_DE`, `PARTE_DE`, `EMITIDO_POR`, `APLICA_SE_A`, `DE_AREA`, `REGE`, `DE_RAMO`, `E_UM` (a entidade específica → o termo genérico, curado: o escotista é um adulto; R19), `ATUA_EM`, `ALTERA`, `REVOGA`, `SUBSTITUI`, `CITA`, e os de governança (`ELEGE`, `COMPOE`, `INTEGRA`, `CONVOCA`, `FISCALIZA`, `APRECIA_RECURSO_DE`, `DIRIGE`) |
| `mode` | `Mode \| None` | só no `SOBRE`: `disciplina`, `orienta`, `registra` ou `comunica`, igual a `MODE_OF[role da versão da unidade]` |
| `from`, `to` | `str` | ids de nó ou de entidade existentes (nenhum órfão) |
| `source` | `str` | um `chunk_id`, um `unit_id`, `<doc_key>#<n>@p<página>`, `taxonomia:<categoria>`, `pasta:<caminho no corpus>` (G3: `APLICA_SE_A` e `EMITIDO_POR`, a pasta do arquivo sem o `ocr/`) ou `<arquivo>.yaml:<seção>/<id>` |
| `origin` | `Origin` | `curado`, `regra` ou `modelo_conferido` (este com `checked: true`) |
| `search` | `bool` | derivado do tipo: as de governança têm `False` (FR-007) |

As pontas válidas de cada tipo estão no design.md, seção 2.4. O build recusa uma aresta com pontas de tipo errado,
nomeando-a. O G3 (R20) acrescenta duas, que o design não listava:
- **`PARTE_DE` entre os tipos** (`tipo_orgao:` → `tipo_inst:`), do `instituicao` de cada tipo de órgão no
  `organizacao.yaml`, com o `instituido_em` como fonte quando ele está no acervo. É por ela que a instituição citada
  traz as partes do tipo: o que trata da assembleia de grupo trata do GE Inah;
- **`SOBRE` do documento inteiro → `inst:`**, quando o título do documento nomeia a instituição (o estatuto do GE, o
  Regulamento da Região SP), pelo `reconhecer` com os apelidos dela, como o regulamento que nomeia um órgão no ADR-063.

## Papel (`Role`) e modo

`Role = Literal["norma", "orientacao", "registro", "comunicacao"]`. `ROLES: Mapping[str, Role]` vai do `taxonomy_id`
ao papel (R3). `MODE_OF = {"norma": "disciplina", "orientacao": "orienta", "registro": "registra", "comunicacao":
"comunica"}`.

## Plano (`QueryPlan`, `QueryStep`)

| Campo | Tipo | Regra |
|---|---|---|
| `version` | `1` | outra → `PlanInvalid("version")` |
| `forma` | `simples \| para_cada \| intersecao` | padrão `simples` |
| `consultas` | `tuple[QueryStep, ...]` | até 4. Vazio = só a busca |
| `para_cada` | `tuple[str, ...]` | só com a forma `para_cada`, até 6 ids de entidade. Cada consulta tem um argumento `"$cada"` que o executor troca pelo id |
| `QueryStep.q` | nome de consulta | um de `sobre`, `aplicavel_a`, `documentos`, `itens`, `linha_do_tempo` e `ligados` |
| `QueryStep.args` | `Mapping` | só os parâmetros da assinatura, com os tipos do JSON Schema. Chave desconhecida → `PlanInvalid("consultas[i].args.<chave>")` |

O esquema completo está em [contracts/query-plan.schema.json](contracts/query-plan.schema.json).

## Evidência (`Evidence`) e frentes (`Frentes`)

| Campo | Tipo |
|---|---|
| `query` | o nome da consulta |
| `target` | o id da entidade ou do documento que a trouxe |
| `doc_key` | `str` |
| `unit_id` | `str \| None` (`None` = o documento inteiro, em `documentos`) |
| `chunk_ids` | `tuple[str, ...]`, todos os da unidade (R9) |
| `role`, `scope`, `date` | da versão ou do evento |
| `edge` | `EdgeRef(type, source, origin)` |
| `event` | `EventRef(type, text, page) \| None` |

`Frentes` é a evidência ordenada e agrupada por passo do plano e por entidade de `para_cada`. Em cada grupo há até 3
documentos (R9).

## Filtros novos (contrato 101 → 103)

| Chave | Tipo | Quem escreve | Regra |
|---|---|---|---|
| `entities` | lista de ids | 101 | ids que existem no grafo, na ordem da menção. Substitui `organs` |
| `plan` | objeto (`QueryPlan.to_json()`) | 101 | inválido → só a busca e um aviso (R8) |

## Validação no build (FR-019)

- toda `source` resolve;
- nenhum id órfão;
- todo `modelo_conferido` tem `checked`;
- todo `taxonomy_id` do catálogo tem papel;
- o `meta.chunking` é igual ao do manifesto do índice;
- as pontas de cada aresta têm tipo válido;
- nenhuma entidade tem `type` de pessoa.
