# Data model — 011 Bootstrap (Fase 1)

Este módulo não publica seam Python. Os tipos abaixo são internos; o que o operador vê são os arquivos de
configuração e o comando.

## Configuração (`settings.py`)

### `Settings` — o que o operador escolheu

| Campo | Tipo | Regra |
|---|---|---|
| `profile` | `str` | `memory` ou `test`; outro valor invalida a configuração nomeando o campo |
| `packs_file` | `Path \| None` | `packs.yaml`; ausente = nenhum pack habilitado |
| `assistants_file` | `Path \| None` | `assistants.yaml`; ausente = nenhum Assistant, e toda resolução responde 404 |
| `ollama_base_url` | `str` | endereço da camada compatível do provider local |
| `trace_dir` | `Path \| None` | diretório do trace no perfil `memory` — a 009 grava um arquivo por dia; ausente = trace em memória |
| `host`, `port` | `str`, `int` | onde `serve` escuta; porta entre 1 e 65535 |
| `shutdown_grace_seconds` | `float` | prazo de espera pelas execuções em andamento no encerramento (FR-013) |

Validação pura: perfil desconhecido, porta fora da faixa e prazo negativo são recusados **antes** da primeira etapa,
com erro que nomeia o campo (FR-001).

### `ConfigSource` — porta

```python
class ConfigSource(Protocol):
    def load(self) -> Settings: ...
```

Adapters: `EnvConfigSource` (variáveis `AI_CORE_*`) e `InMemoryConfigSource` (testes).

## Perfil (`profiles.py`)

### Portas exigidas

A lista é **dado**: acrescentar uma porta numa fase futura é acrescentar uma linha, e o perfil que não a atender falha
nomeando-a (FR-004, [research.md](research.md) R6).

| Porta exigida | `memory` | `test` |
|---|---|---|
| relógio (005, 008, 009) | relógio do sistema | relógio fixo |
| trace (009) | arquivo JSONL, ou memória sem `trace_dir` | memória |
| provider de modelo (006) | Ollama na camada compatível | provider simulado |
| origem de packs (002) | entry points | entry points |
| autenticação (008) | anônimo de desenvolvimento | anônimo de desenvolvimento |
| identificador de requisição (008) | aleatório | sequencial |

Um **único** relógio atende as três portas de tempo, por tipagem estrutural (FR-008, ADR-013).

### `Profile`

| Campo | Significado |
|---|---|
| `name` | `memory` ou `test` |
| fábricas | uma por porta exigida; `validate(profile)` recusa perfil com fábrica faltando |

## Boot (`lifecycle.py`)

### `Stage` — uma etapa declarada

| Campo | Tipo | Significado |
|---|---|---|
| `name` | `str` | aparece no relatório de boot |
| `run` | callable | recebe o estado do boot e o avança |
| `critical` | `bool` | `True`: falha interrompe o boot; `False`: falha degrada e o boot segue (FR-003) |

### `StageOutcome` e `BootReport`

| Campo | Valores |
|---|---|
| `StageOutcome.status` | `ok` · `degraded` · `failed` |
| `StageOutcome.detail` | motivo, quando não é `ok` |
| `BootReport.stages` | resultados na ordem de execução |
| `BootReport.ok` | verdadeiro quando nenhuma etapa crítica falhou |
| `BootReport.degraded` | nomes das etapas degradadas — é o que o operador lê em menos de um minuto (SC-005) |

Etapas da Fase 1, nesta ordem: `configuration`, `adapters`, `packs`, `engine`, `api`. `mcp_registry` (007) e
`assistants` (003) entram nas fases deles, sem mudar a sequência.

### `Platform` — o que o boot entrega

| Campo | Origem |
|---|---|
| `settings`, `profile` | configuração validada |
| `packs` | `PackRuntime` (002), já carregado |
| `trace` | `TraceService` (009) |
| `engine` | `ExecutionService` (005), com os seams injetados |
| `app` | aplicação HTTP (008), montada |
| `report` | o `BootReport` |

`aclose()` libera os recursos na ordem inversa do boot (FR-013).

## Assistants (`grants.py`)

### `assistants.yaml`

```yaml
assistants:
  geral:
    flow: chat
    packs: [generic]
    models:
      generation: ollama/qwen3:1.7b
    allow: ["ollama/*"]
```

| Campo | Regra |
|---|---|
| `flow` | precisa estar entre os nomes que o motor oferece; ausente = `chat` |
| `packs` | lista ordenada; é composta pelo Pack Registry (002), que recusa pack indisponível |
| `models` | ao menos `generation`; cada valor é `provider/modelo` |
| `allow` | padrões de allowlist; ausente = nenhuma restrição declarada |

### Resolução de `<assistant>[/<modelo>]`

1. Assistant desconhecido → `AssistantNotFound` (a 008 responde 404).
2. Sem a parte do modelo → usa o `generation` declarado.
3. Com a parte do modelo → substitui **apenas** o papel `generation`; a allowlist do Assistant continua valendo, e um
   modelo fora dela é recusado pelo roteador (006). A requisição restringe, nunca amplia (princípio IV).

## Modos de falha

| Situação | Resultado |
|---|---|
| Perfil desconhecido, porta inválida, prazo negativo | erro nomeando o campo; o boot **não** começa (FR-001) |
| Perfil sem fábrica para uma porta exigida | erro nomeando a porta; o boot **não** começa (FR-004) |
| `packs.yaml` ou `assistants.yaml` malformado | erro nomeando arquivo e campo; o boot para na etapa de configuração |
| Pack em erro (002) | etapa `packs` fica **degradada**, com o pack nomeado; o boot segue e os demais packs atendem (SC-004) |
| Assistant que referencia pack indisponível | resolução daquele Assistant falha; os demais atendem |
| Falha em etapa crítica | boot interrompido; as etapas já concluídas são desfeitas na ordem inversa |
| Sinal de parada | a porta fecha, as execuções em andamento têm até `shutdown_grace_seconds`, e os recursos são liberados na ordem inversa |
