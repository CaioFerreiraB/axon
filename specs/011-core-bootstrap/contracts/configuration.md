# Contrato — configuração do operador

O que o operador escreve para subir a plataforma. Três origens: variáveis de ambiente, `packs.yaml` (formato da 002)
e `assistants.yaml` (formato deste módulo até a 003 existir — [research.md](../research.md) R4).

## Variáveis de ambiente

| Variável | Default | Significado |
|---|---|---|
| `AI_CORE_PROFILE` | `memory` | perfil de adapters: `memory` ou `test` |
| `AI_CORE_PACKS_FILE` | — | caminho do `packs.yaml`; ausente = nenhum pack habilitado |
| `AI_CORE_ASSISTANTS_FILE` | — | caminho do `assistants.yaml`; ausente = nenhum Assistant |
| `AI_CORE_OLLAMA_BASE_URL` | `http://localhost:11434/v1` | camada compatível do provider local |
| `AI_CORE_TRACE_DIR` | — | **diretório** do trace (um arquivo por dia, formato da 009); ausente = trace em memória |
| `AI_CORE_HOST` | `127.0.0.1` | interface do `serve` |
| `AI_CORE_PORT` | `8000` | porta do `serve` |
| `AI_CORE_SHUTDOWN_GRACE_SECONDS` | `10` | espera pelas execuções em andamento no encerramento |

Valor inválido é recusado **antes** da primeira etapa, com erro que nomeia a variável (FR-001).

## `packs.yaml` — formato da 002

```yaml
packs:
  generic:
    enabled: true
```

O bootstrap escolhe o arquivo; o formato e a validação são da 002 (`contracts/packs-yaml.md`). Reimplementar a leitura
aqui faria a mensagem de erro divergir entre o boot e o `packs check` do módulo ([research.md](../research.md) R3).

## `assistants.yaml`

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
| `packs` | lista ordenada, composta pelo Pack Registry (002); pack indisponível torna **aquele** Assistant indisponível |
| `models` | ao menos `generation`; cada valor é `provider/modelo` |
| `allow` | padrões de allowlist; ausente = nenhuma restrição declarada |

Chave desconhecida, `models` sem `generation` ou referência de modelo sem `/` são recusadas nomeando o campo.

## Resolução do id de modelo

A API recebe `<assistant>` ou `<assistant>/<modelo>` e pede o grant.

| Caso | Resultado |
|---|---|
| Assistant desconhecido | `AssistantNotFound` → 404 (a existência de um privado não vaza) |
| Sem a parte do modelo | usa o `generation` declarado no Assistant |
| Com a parte do modelo | substitui **apenas** o papel `generation`; a allowlist do Assistant continua valendo |
| Modelo pedido fora da allowlist | o roteador (006) recusa — a requisição restringe, nunca amplia (princípio IV) |

## Suíte de conformidade

`packages/core/tests/bootstrap/unit/test_settings.py` e `test_grants.py`:

1. defaults aplicados quando nada é configurado;
2. perfil desconhecido, porta fora da faixa e prazo negativo são recusados nomeando a variável;
3. `assistants.yaml` válido vira Assistants resolvíveis;
4. `models` sem `generation`, referência sem `/` e chave desconhecida são recusados nomeando o campo;
5. `flow` fora dos nomes que o motor oferece é recusado nomeando o flow e os disponíveis;
6. id sem a parte do modelo usa o `generation` declarado;
7. id com a parte do modelo troca só o papel `generation` e preserva a allowlist;
8. Assistant desconhecido levanta o erro que a API traduz em 404;
9. Assistant cujo pack não está disponível fica indisponível, e os demais continuam resolvendo.

---

## Fase 2 (2026-09-30): variáveis novas (research R18)

| Variável | Default | Significado |
|---|---|---|
| `AI_CORE_PROFILE` | `memory` | agora `memory`, `persistent` ou `test` |
| `AI_CORE_DATABASE_URL` | — | **segredo**; obrigatória no `persistent`; nunca impressa |
| `AI_CORE_DEV_API_KEY` | — | **segredo**; chave de desenvolvimento do `memory` (`aic_<16 hex>_<segredo>`); recusada no `persistent` |
| `AI_CORE_OIDC_ISSUER` | — | emissor OIDC; sem ele, a superfície pública recusa toda credencial |
| `AI_CORE_OIDC_AUDIENCE` | — | obrigatória quando há emissor |
| `AI_CORE_OIDC_JWKS_URL` | — | opcional; sem ela, descoberta em `<emissor>/.well-known/openid-configuration` |
| `AI_CORE_OIDC_SUBJECT_CLAIM` | `sub` | claim que vira `user:<valor>` |
| `AI_CORE_OIDC_GROUPS_CLAIM` | `groups` | claim dos grupos |
| `AI_CORE_CONVERSATION_RETENTION_DAYS` | `180` | prazo de retenção de conversas sem atividade (008 FR-019) |
| `AI_CORE_CONVERSATION_EXPIRY_INTERVAL` | `3600` | segundos entre execuções da expiração |

O `assistants.yaml` é da 003 desde a Fase 2 (formato em `specs/003-core-assistants-access/contracts/assistants-yaml.md`);
a seção acima sobre ele descreve a Fase 1.

Conformidade (`tests/bootstrap/unit/test_settings.py`): cada variável nova com default e recusa nomeando a variável;
mensagens de erro de segredo nunca contêm o valor.
