# Contrato — `assistants.yaml` (configuração de acesso do operador)

Arquivo versionado do operador, apontado por `AI_CORE_ASSISTANTS_FILE` (variável da 011). Nasceu na 011 (research R4
dela) e passa a ser desta spec: formato, validação e mensagens de erro são daqui; quem escolhe o arquivo é a
composition root. Lido pela porta `AssistantConfigSource` (adapter `adapters/assistants_yaml.py`), uma vez, no boot.
Nomes de domínio abaixo são ilustrativos.

## Exemplo completo

```yaml
assistants:

  geral:                                   # nome: [a-z0-9][a-z0-9._-]{0,63}, nunca começa com "~"
    description: Assistente de uso geral
    visibility: public
    auth:
      schemes: [oidc, api_key]
      allow: ["*"]
    flow: chat                             # opcional (regras abaixo)
    packs: [generic]
    models:
      generation: ollama/qwen3:1.7b        # provider/modelo, como na Fase 1
      allow: ["ollama/*"]                  # allowlist de modelos: obrigatória, não vazia
    limits:
      rpm: 20

  interno:
    visibility: private
    auth:
      schemes: [api_key]
      allow: ["user:caio", "group:operadores"]
    flow: chat
    packs: [generic]
    mcp: []                                # aliases MCP (007); vazio até a Fase 3
    collections: []                        # coleções (Fase 5)
    allowed_tools: [calculate]             # opcional: filtro final do catálogo (004)
    write_tools: []                        # opcional; proibido em Assistant público
    models:
      generation: ollama/qwen3:1.7b
      controller: ollama/qwen3:1.7b
      allow: ["ollama/*"]
    limits:
      rpm: 30
      max_iterations: 6
      max_context_tokens: 4000

user_assistants:                           # clarificação 1 (FR-014)
  policies:                                # em ordem; vale a primeira que casa
    - match: group:operadores
      packs: [generic]
      flows: [chat]
      collections: []
      models:
        allow: ["ollama/*"]
      limits: { rpm: 30, max_iterations: 6, max_context_tokens: 8000 }   # tetos
      write_tools: false
    - match: "*"
      packs: [generic]
      flows: [chat]
      models:
        allow: ["ollama/qwen3:1.7b"]
      limits: { rpm: 10, max_iterations: 3, max_context_tokens: 4000 }

api_keys:                                  # clarificação 2 (FR-015)
  admin_group: operadores                  # quem administra chaves pela superfície privada
```

## Topo do arquivo

| Chave | Obrigatória | Regra |
|---|---|---|
| `assistants` | não | mapeamento nome → Assistant; ausente = nenhum Assistant de sistema |
| `user_assistants.policies` | não | lista ordenada; ausente = ninguém cria Assistant de usuário |
| `api_keys.admin_group` | não | nome de grupo (sem `group:`); ausente = administração só pela CLI |

Arquivo ausente (variável não definida) é configuração válida: nenhum Assistant, nenhuma política.

## Assistant de sistema

| Campo | Obrig. | Regra |
|---|---|---|
| `description` | não | texto livre, até 500 caracteres |
| `visibility` | **sim** | `public` ou `private` |
| `auth.schemes` | **sim** | não vazio, ⊆ {`oidc`, `api_key`} |
| `auth.allow` | **sim** | não vazio; seletores `*`, `user:…`, `svc:…`, `group:…`; `*` em privado é inválido (FR-012) |
| `flow` | não | ∈ flows do motor. Ausente: com **um** pack, o `preferred_flow` dele ou `chat`; com **dois ou mais**, inválido (US1 cen. 4) |
| `packs` | não | lista ordenada; composta pelo Pack Registry (002) |
| `mcp` | não | aliases ⊆ `McpDirectory.aliases(owner=None)`; vazio até a Fase 3 (clarificação 3) |
| `collections` | não | ⊆ `CollectionCatalog.names()`; vazio até a Fase 5 |
| `allowed_tools` | não | lista de nomes de tool; ausente = sem filtro adicional |
| `write_tools` | não | lista de nomes; não vazia em `public` é inválido (FR-012) |
| `models.<papel>` | `generation` sim | papéis `controller`, `generation`, `rerank` (ADR-008); valor `provider/modelo`; cada um casa com `models.allow` |
| `models.allow` | **sim** | padrões `fnmatch` sobre `provider/modelo`; vazio é inválido (edge case) |
| `limits.rpm` | não | inteiro ≥ 1; default 60 (R9) |
| `limits.max_iterations`, `limits.max_context_tokens` | não | inteiros ≥ 1 |

## Política de Assistants de usuário

| Campo | Obrig. | Regra |
|---|---|---|
| `match` | **sim** | `*` ou `group:<nome>` |
| `packs`, `flows`, `collections` | não | o que o Assistant de usuário pode referenciar; ausente = nada |
| `models.allow` | **sim** | não vazio; vira a allowlist de todo Assistant criado sob esta política |
| `limits.rpm`, `limits.max_iterations`, `limits.max_context_tokens` | `rpm` sim | tetos; limite ausente no Assistant assume o teto |
| `write_tools` | não | `false` (default) proíbe tools de escrita nos Assistants de usuário desta política |

## Erros

**Erro de arquivo → o boot para** (`AssistantsConfigError`, nomeando o caminho do campo):

- YAML inválido, raiz que não é mapeamento, chave de topo desconhecida;
- `assistants` que não é mapeamento; política malformada (sem `match`, `match` fora da gramática, `models.allow` vazio,
  sem `limits.rpm`, chave desconhecida).

Uma política malformada para o boot porque pular uma política mudaria qual é a primeira que casa — e a seguinte pode
ser mais permissiva.

**Erro de um Assistant → só ele fica indisponível**, com os motivos no relatório de validação, no boot e em
`assistants validate` (FR-011, 011 FR-003):

- chave desconhecida no Assistant; `allow` na raiz do Assistant, com a mensagem *"`allow` saiu da raiz do Assistant: a
  allowlist de modelos vive em `models.allow`, e quem pode usar o Assistant, em `auth.allow`"* (R3);
- nome fora da gramática ou começando com `~` (FR-017); `visibility`, `auth` ou `models.allow` ausentes;
- `*` em privado; `write_tools` em público; modelo declarado fora da allowlist; referência de modelo sem `/`;
- flow ausente em composição; flow, pack, MCP ou coleção que não existe.

## Conformidade (`tests/assistants/unit/test_assistants_yaml.py`, `tests/assistants/contract/test_config_source.py`)

1. o exemplo acima carrega sem problemas e resolve como descrito;
2. cada erro de arquivo interrompe a carga nomeando o campo;
3. cada erro de Assistant deixa só aquele Assistant indisponível, com o motivo, e os demais carregam;
4. o arquivo da Fase 1 (com `allow` na raiz e sem `auth`) produz, para cada Assistant, os motivos que dizem o que mudar;
5. os adapters YAML e em memória produzem o mesmo `AssistantsConfig` para a mesma configuração.
