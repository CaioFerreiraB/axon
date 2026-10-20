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

Adapters: `EnvConfigSource` (variáveis `AXON_*`) e `InMemoryConfigSource` (testes).

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

---

## Fase 2 (2026-09-30)

- **Profile** ganha o terceiro perfil (`persistent`) e as portas novas (contracts/profiles.md); as fábricas recebem
  as partes já construídas.
- **Settings** ganha as variáveis de contracts/configuration.md, "Fase 2"; segredos (`database_url`, `dev_api_key`)
  nunca entram em `repr`, log ou mensagem de erro.
- **Health Report** (Key Entity da spec): `HealthReport(items)` da 008, com `HealthItem(name, ok, critical, detail)` e
  `status` = `ok` | `degraded` | `down` (contracts/health.md).
- **Platform** ganha `assistants`, `access`, `routing`, `conversations` e o ciclo de vida da app (pool e tarefas).

## Fase 3 (2026-10-02): registry MCP, gateway de tools e `agentic` ([research.md](research.md) R21–R33)

### `Settings` — campos novos

| Campo | Variável | Default | Regra |
|---|---|---|---|
| `mcp_file` | `AXON_MCP_FILE` | `None` | caminho do arquivo do operador (formato da 007) |
| `mcp_discovery_ttl` | `AXON_MCP_DISCOVERY_TTL` | `300.0` | segundos, `> 0` |
| `tool_timeout_ms` | `AXON_TOOL_TIMEOUT_MS` | `30000` | inteiro, 1 000–300 000 |
| `tool_max_response_bytes` | `AXON_TOOL_MAX_RESPONSE_BYTES` | `16384` | inteiro, 1 024–1 048 576 |

Fora da regra → `ConfigurationError` nomeando a variável. Credenciais de MCP (`AXON_MCP_SECRET_<REF>`) não passam por
`Settings` (R27).

### Portas exigidas — acréscimos

`REQUIRED_PORTS` ganha, ao fim e nesta ordem: `mcp_store`, `mcp_dns`, `mcp_transports`, `mcp_secrets`, `mcp_cache`,
`audit`.
`STORAGE_PORTS` ganha `mcp_store` e `audit`. Adapters por perfil em [contracts/profiles.md](contracts/profiles.md).

### Partes novas do boot

| Parte | Produzida por | O quê |
|---|---|---|
| `mcp_config` | `configuration` | o `McpConfig` da 007 (arquivo lido ou vazio) |
| `mcp` | `mcp_registry` | o `McpService` da plataforma (registry, catálogo de aliases, clientes restritos) |
| `capabilities` | `engine` | o `CapabilityService` da plataforma |

### `Platform` — campos novos

`mcp: McpService | None` e `capabilities: CapabilityService | None` — vazios quando a etapa não rodou. É por
`Platform.mcp` que a 008 vai ligar as rotas de MCP.

### `platform()` — parâmetro novo

`overrides: Mapping[str, Any] | None = None` — porta → adapter que substitui a fábrica do perfil (R31). Nome fora de
`REQUIRED_PORTS`, `database` ou porta de `STORAGE_PORTS` → `ConfigurationError` nomeando a porta, na etapa de adapters.

### Itens de saúde novos

| Item | Crítico | `ok` / `detail` |
|---|---|---|
| `mcp:<alias>` (um por servidor global) | não | `ServerHealth.ok` / motivo, ou as tools pedidas e não anunciadas |
| `mcp` (só quando a listagem dos globais falha) | não | `false` / o motivo |

### Modos de falha — acréscimos

| Situação | Resultado |
|---|---|
| `mcp.yaml` ilegível ou malformado | o boot para na etapa `configuration`, nomeando o arquivo |
| Entrada do `mcp.yaml` com problema | etapa `mcp_registry` degradada, nomeando alias e motivo; o servidor fica indisponível e o resto sobe |
| Referência de credencial de servidor global sem `AXON_MCP_SECRET_<REF>` | etapa `mcp_registry` degradada, nomeando alias e referência — nunca valor |
| Entrada `stdio` num perfil sem transporte `stdio` (`memory`) | servidor indisponível na descoberta ("transporte 'stdio' não configurado") |
| Migração de `mcp` ou `capabilities` quebrada | o boot para na etapa `adapters`, nomeando o schema |
| Servidor MCP global fora do ar | nada no boot; item `mcp:<alias>` não saudável, saúde `degraded` (200) |
| Banco fora do ar depois do boot | item `database` crítico, saúde `down` (503); requisições com 503 `storage_unavailable` (008) |

## Fase 9, incremento 9.5 (2026-10-20): identidade Axon (US7)

Nenhuma entidade nova nem campo novo. Mudam só nomes e defaults:

- **Settings**: lidas de `AXON_*` (`PREFIX = "AXON_"`); `display_name` tem default `"Axon"`. A carga recusa o ambiente
  com algum `AI_CORE_*` (`LEGACY_PREFIX`), antes de construir a `Settings` (research R48).
- **Pool** do `persistent`: nome `axon`.
- **Credenciais do perfil `test`**: as mesmas, exportadas por `axon_ai.bootstrap.profiles`.
