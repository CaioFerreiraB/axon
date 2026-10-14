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

---

## Fase 3 (2026-10-02): registry MCP e gateway de tools (research R23, R27)

| Variável | Default | Significado |
|---|---|---|
| `AI_CORE_MCP_FILE` | — | caminho do arquivo de servidores MCP do operador, no formato da 007 (`specs/007-core-mcp-integration/contracts/mcp-yaml.md`); ausente = nenhum servidor do operador |
| `AI_CORE_MCP_DISCOVERY_TTL` | `300` | segundos de validade do catálogo descoberto de um servidor |
| `AI_CORE_TOOL_TIMEOUT_MS` | `30000` | prazo do gateway por chamada de tool (1 000–300 000) |
| `AI_CORE_TOOL_MAX_RESPONSE_BYTES` | `16384` | tamanho máximo do resultado de tool entregue ao modelo (1 024–1 048 576) |
| `AI_CORE_MCP_SECRET_<REF>` | — | valor de uma credencial de MCP referenciada no arquivo por `<ref>`; lido só ao montar a operação, nunca impresso |

O arquivo é lido na etapa `configuration`: ilegível ou malformado para o boot nomeando o arquivo; entrada com problema
fica indisponível e degrada a etapa `mcp_registry`.

## Fase 5 (2026-10-09): `rag_first` (005 research R44)

| Variável | Default | Significado |
|---|---|---|
| `AI_CORE_RAG_CANDIDATES` | `20` | `top_k` pedido a cada tool de recuperação no `rag_first` (inteiro ≥ 1) |
| `AI_CORE_RAG_PASSAGES` | `5` | trechos que o rerank leva à geração (inteiro ≥ 1) |
| `AI_CORE_RAG_MIN_SCORE` | — | limiar do portão de cobertura sobre o melhor score, em `[0, 1]`; ausente ou vazia = sem limiar (só a ausência de resultado escala) até a 105 calibrar |

Valor inválido impede o boot nomeando a variável. Os três chegam ao motor como `RagSettings` (005), na etapa `engine`.

### Suíte de conformidade — acréscimos

10. defaults das quatro variáveis; recusa nomeando a variável para TTL `≤ 0`, prazo e tamanho fora da faixa;
11. `AI_CORE_MCP_FILE` apontando para arquivo malformado para o boot em `configuration`;
12. nenhum valor de `AI_CORE_MCP_SECRET_*` aparece em `repr(Settings)`, no relatório de boot ou em mensagem de erro.

## Fase 7 (2026-10-13): admissão da API (008 FR-016, FR-017; 008 research R36)

| Variável | Default | Significado |
|---|---|---|
| `AI_CORE_MAX_EXECUTIONS` | `2` | execuções simultâneas da API, por processo (inteiro de 1 a 64) |
| `AI_CORE_QUEUE_SIZE` | `8` | pedidos que esperam vaga (inteiro de 0 a 1000; `0` = sem fila — vagas cheias recusam na hora) |
| `AI_CORE_QUEUE_WAIT_MS` | `60000` | espera máxima na fila, em milissegundos (1 a 600 000); esgotada, 503 sem streaming ou fim com erro em streaming |

Os defaults são provisórios, medidos no hardware alvo (008 quickstart, "Fase 7"). A etapa `api` monta
`AdmissionLimits` e a passa a `create_app(admission=…)`; valor fora da faixa falha a etapa `configuration` nomeando a
variável. O harness de avaliação (009) não passa pela API e não entra na fila.

## Fase 9 (2026-10-14): identidade, administração e destinos do trace (research R36)

| Variável | Padrão | Regra |
|---|---|---|
| `AI_CORE_IDENTITY_ENABLED` | `false` | liga o provedor de identidade (012) |
| `AI_CORE_PUBLIC_URL` | — | obrigatório com a identidade; é o emissor; `https` exceto `localhost` |
| `AI_CORE_IDENTITY_CLIENTS_FILE` | — | obrigatório com a identidade; formato da 012 (`identity.yaml`) |
| `AI_CORE_MASTER_KEY` | — | 32 bytes em base64; obrigatória no `persistent` com a identidade ligada ou segredo gravado; aleatória no `memory`, fixa no `test`; nunca em log |
| `AI_CORE_DISPLAY_NAME` | `Agentic` | nome da instalação nas páginas e na console |
| `AI_CORE_LOGO_FILE` | — | SVG ou PNG montado; servido pela 012 |
| `AI_CORE_TRUSTED_PROXIES` | — | IPs ou redes (CIDR), separados por vírgula |
| `AI_CORE_COOKIE_SECURE` | ligado com `https` | cookie de sessão da 012 |
| `AI_CORE_LANGFUSE_HOST`, `_PUBLIC_KEY`, `_SECRET_KEY` | — | tudo ou nada; definidas, prevalecem sobre a console (ADR-033) |
| `AI_CORE_LANGFUSE_CAPTURE_CONTENT` | — | `true`/`false`; definida, prevalece |
| `AI_CORE_USAGE_TIMEZONE` | `UTC` | fuso IANA padrão do relatório de uso |
| `AI_CORE_USAGE_RETENTION_DAYS` | `400` | inteiro ≥ 30 |
| `AI_CORE_GOOGLE_*`, `AI_CORE_GOOGLE_LOGIN`, `AI_CORE_BOOTSTRAP_ADMIN_*`, `AI_CORE_IDENTITY_SECRET_<REF>` | — | lidas pelas portas de segredo da 012 (ADR-020) |

Erros que param o boot: identidade com `AI_CORE_OIDC_ISSUER`; identidade sem `AI_CORE_PUBLIC_URL` ou sem o arquivo de
clientes; `persistent` com identidade sem chave mestra; chave mestra malformada; grupo do Langfuse incompleto; fuso
desconhecido.
