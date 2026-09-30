# Design — 011 Bootstrap (composition root)

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: ADR-012 (decisão 7), ADR-013; arch-v1 §13, §14;
> [relatório de estilo arquitetural](../../docs/relatorio-estilo-arquitetural.md), lacuna G6.
>
> Esta é a **única spec autorizada a conhecer serviços, portas secundárias e adapters de outros módulos**
> (princípio XIII). As tabelas abaixo derivam da seção "Portas e adapters" de cada `design.md`; se divergirem,
> vale o `design.md` do módulo dono.

## Localização

```text
ai-core/packages/core/src/ai_core/bootstrap/
├── settings.py     # configuração do operador: packs.yaml, assistants.yaml, perfil, ambiente
├── profiles.py     # perfis de adapter: porta → adapter (memory, persistent, test)
├── wiring.py       # constrói serviços e adapters e injeta seams; único import de service.py/adapters/ de outros módulos
├── lifecycle.py    # ordem de boot e de encerramento, falha fechada por etapa
├── health.py       # health agregado
└── cli.py          # raiz do comando `ai-core`; registra os subcomandos contribuídos pelos módulos
```

```toml
# ai-core/packages/core/pyproject.toml
[project.scripts]
ai-core = "ai_core.bootstrap.cli:main"
```

## Ordem de boot

```mermaid
sequenceDiagram
    participant Root as Bootstrap (011)
    participant Reg as Pack Registry (002)
    participant MCP as MCP Registry (007)
    participant Eng as Execution Engine (005)
    participant Acc as Assistants & Access (003)
    participant Http as API HTTP (008)

    Root->>Root: carregar e validar configuração e perfil
    Root->>Root: instanciar adapters do perfil (relógio e segredos únicos)
    Root->>Reg: carregar packs
    Reg-->>Root: habilitados · desabilitados · com erro
    Root->>MCP: preparar registry
    Root->>Eng: construir motor com os seams injetados
    Eng-->>Root: nomes de flow
    Root->>Acc: validar assistants (packs, MCPs, coleções, flows)
    Acc-->>Root: disponíveis · indisponíveis com motivo
    Root->>Http: montar a app e abrir a porta
```

- Falha de configuração ou de adapter obrigatório: o boot para antes da etapa seguinte.
- Pack, MCP ou Assistant inválido: fica indisponível com motivo; o boot segue (princípio VII).
- Encerramento: fecha a porta HTTP, aguarda execuções até o prazo e libera recursos na ordem inversa.
- Tarefas periódicas declaradas pelos módulos (ex.: expiração de conversas da 008) são agendadas ao fim do boot e
  canceladas no encerramento.
- O motor é construído antes da validação de Assistants porque a 003 valida nomes de flow (seam da 005). A
  construção do motor não depende de Assistants: o grant só chega por execução.

## O que a 011 constrói e injeta

A 011 importa o `api.py`, o `service.py` e os `adapters/` de cada módulo. Nenhum outro módulo faz isso.

| Módulo | Recebe seams de | Recebe adapters para |
|---|---|---|
| 002 Pack Runtime | — | `PackSource`, `PackConfigSource` |
| 007 MCP | — | `McpServerStore`, `SecretResolver`, `McpTransport`, `DnsResolver`, `DiscoveryCache` |
| 006 LLM | 009 (Trace Sink) | adapters de `LLMProvider`, `SecretResolver` |
| 004 Capability Gateway | 002 (Pack Registry), 007 (cliente restrito), 009 (Trace Sink) | `AuditLog` |
| 005 Execution Engine | 002 (Pack Hooks), 004 (Catalog, Gateway), 006 (Model Router), 009 (Trace Sink) | `CheckpointStore`, `Clock` |
| 003 Assistants & Access | 002 (Pack Registry), 007 (MCP Registry), 005 (nomes de flow) | `AssistantStore`, `ApiKeyStore`, `OidcVerifier`, `RateCounterStore`, `Clock` |
| 008 API HTTP | 003, 005, 002, 007, 009 | `ConversationStore`, `HealthProvider` (o agregador desta spec), `Clock` |
| 009 Observability & Eval | 005 (Execution Engine, só o harness) | `TraceExporter`, `BaselineStore`, `Judge` |

O `AgentContext` continua interno da 005: o `service.py` do motor o monta por execução, a partir do grant, com os
seams recebidos aqui (ADR-012).

## Perfis de adapters

| Porta (módulo dono) | `memory` — Fase 1 | `persistent` — Fase 2+ | `test` |
|---|---|---|---|
| `AssistantStore` de sistema (003) | YAML | YAML | fixture |
| `AssistantStore` de usuário (003) | memória | Postgres (Fase 2) | memória |
| `ApiKeyStore` (003) | memória | Postgres (Fase 2 — plano da 003, ADR-015) | memória |
| `OidcVerifier` (003) | provedor OIDC | provedor OIDC | verificador de teste |
| `RateCounterStore` (003) | memória | memória (processo único) | memória |
| `PackSource` (002) | entry points | entry points + declarativo | packs de teste |
| `AuditLog` (004) | memória | Postgres (Fase 3) | memória |
| `CheckpointStore` (005) | memória | Postgres (Fase 3) | memória |
| `LLMProvider` (001/006) | Ollama | Ollama · OpenAI · OpenRouter | provider simulado |
| `McpServerStore` (007) | memória | Postgres (Fase 3) | memória |
| `McpTransport` (007) | http/sse | http/sse · stdio (só global) | MCP de teste em processo |
| `ConversationStore` (008) | memória | Postgres (Fase 2) | memória |
| `TraceExporter` (009) | arquivo | a decidir no plano da 009 | memória |
| `Clock` (003, 005, 008) | relógio do sistema | relógio do sistema | relógio fixo |
| `SecretResolver` (006, 007) | variáveis de ambiente | a decidir no plano da 007 | dicionário |

Um único adapter atende todas as portas de mesmo papel (`Clock`, `SecretResolver`): os `Protocol` são estruturais, então
uma implementação satisfaz a porta declarada por cada módulo.

## Linha de comando

```bash
ai-core serve                  # boot completo + API
ai-core packs list             # 002 — adapters/cli.py do módulo
ai-core packs check            # 002 — roda no build da imagem (ADR-009)
ai-core assistants validate    # 003 — adapters/cli.py do módulo
ai-core eval run               # 009 — harness em processo; único caminho que fixa a data de referência (008 FR-012)
ai-core health                 # 011 — saúde agregada
```

Cada módulo contribui seus subcomandos pelo próprio `adapters/cli.py`; a 011 só os registra. Subcomandos de validação
executam o boot até a etapa necessária (sem abrir a API) e saem com código não zero em caso de erro.

## Health agregado

| Item | Fonte |
|---|---|
| Packs (habilitados, desabilitados, com erro) | Pack Registry (002) |
| Providers e modelos configurados | Model Router (006, FR-009) |
| Servidores MCP | MCP Registry (007, FR-011) |
| Armazenamentos persistentes | cada adapter persistente (verificação de conexão) |

Exposto em `GET /private/v1/health` (008) e em `ai-core health`. A 008 declara a porta `HealthProvider`; a 011 entrega o
agregador como adapter dessa porta ao montar a app — assim a 008 não importa a 011.

## Portas e adapters

| Porta | Tipo | Adapters por fase | Teste |
|---|---|---|---|
| `ConfigSource` | secundária | arquivos montados (`packs.yaml`, `assistants.yaml`) + variáveis de ambiente | configuração em memória |
| Pontos de entrada (`ai-core`, `serve`) | primária (processo) | CLI | teste ponta a ponta no perfil `test` |

## Fronteira verificada

```toml
# esboço — sintaxe exata no plano
[[tool.importlinter.contracts]]
name = "só a composition root importa service/adapters de outros módulos"
type = "forbidden"
source_modules = ["ai_core.packs", "ai_core.assistants", "ai_core.capabilities", "ai_core.graph",
                  "ai_core.llm", "ai_core.mcp", "ai_core.http", "ai_core.observability", "ai_core.eval"]
forbidden_modules = ["ai_core.bootstrap"]
```

A regra inversa (um módulo não importa `service.py`/`adapters/` de outro) é um contrato por módulo, gerado a partir da
lista de módulos; a forma exata fica para o plano.
