# Contrato — perfis de adapters

Interno do módulo (`profiles.py`). Um perfil é o mapeamento porta → adapter de uma fase ou ambiente; trocar de perfil
**não** muda nenhum módulo (FR-005, SC-001).

## Portas exigidas

A lista é dado. Validar um perfil é conferir que nenhuma ficou sem fábrica — e isso acontece **antes** da primeira
etapa do boot (FR-004).

| Porta exigida | Dono | `memory` | `test` |
|---|---|---|---|
| `clock` | 005, 008, 009 | relógio do sistema | relógio fixo |
| `trace` | 009 | JSONL quando há diretório configurado; memória quando não há | memória |
| `providers` | 006 | Ollama na camada compatível | provider simulado |
| `pack_source` | 002 | entry points | entry points |
| `authenticator` | 008 | anônimo de desenvolvimento | anônimo de desenvolvimento |
| `request_ids` | 008 | aleatório | sequencial |

Um **único** adapter de relógio atende as três portas de tempo: os `Protocol` são estruturais, então uma
implementação satisfaz a porta que cada módulo declara (FR-008, ADR-013). É o que garante a mesma data de referência
em toda Turn View de uma execução.

## O perfil `test` é parte da distribuição

```python
from ai_core.bootstrap.wiring import platform

plataforma = platform(profile="test")          # packs, motor, trace, app — tudo em memória
```

Não fala com rede, não abre porta, não exige serviço externo (FR-014, SC-003). É o que permite à suíte de um **pack
externo** testar o pack contra a plataforma de verdade ([research.md](../research.md) R7), e o que substitui as
montagens manuais das suítes de 005 e 008.

O provider simulado responde com texto programável; o relógio fixo torna a data de referência e o campo `created` das
respostas verificáveis.

## Regras

| Regra | Origem | Verificada por |
|---|---|---|
| Perfil desconhecido é recusado nomeando o campo | FR-001 | conformidade |
| Perfil sem fábrica para uma porta exigida é recusado nomeando a porta | FR-004 | conformidade |
| O mesmo relógio é entregue a todos os módulos com porta de tempo | FR-008 | conformidade |
| O perfil `test` não instancia nenhum adapter que fale com rede | FR-014, SC-003 | conformidade |
| Trocar de perfil não muda nenhum módulo | FR-005, SC-001 | montar a plataforma nos dois perfis liga os mesmos módulos — construir o provider do Ollama não conecta, então a montagem roda sem rede; a conversa em si roda no `test`, e no `memory` só quando há Ollama |
| O relatório de boot avisa quando a autenticação é anônima | princípio VII | conformidade do comando |

## Suíte de conformidade

`packages/core/tests/bootstrap/unit/test_profiles.py`:

1. os dois perfis atendem todas as portas exigidas;
2. um perfil a que falte uma porta é recusado, com a porta nomeada;
3. perfil desconhecido é recusado, com o valor nomeado;
4. o relógio entregue ao motor, à API e ao trace é o **mesmo objeto**;
5. no perfil `test`, o provider é o simulado e o trace é o de memória;
6. no perfil `memory` sem diretório de trace configurado, o trace é o de memória; com diretório, é o de JSONL;
7. montar a plataforma nos dois perfis liga os mesmos módulos — é o que sustenta a SC-001 sem depender de rede.

## O aviso que o perfil `memory` precisa dar

Nesta fase, os dois perfis usam autenticação **anônima**: a real chega com a 003. O perfil `memory` é o que mais
parece produção, então o relatório de boot avisa em destaque que a plataforma está sem autenticação. É o tipo de
engano que sai caro e que uma linha impede.

---

## Fase 2 (2026-09-30): três perfis e autenticação real (research R12, R15)

| Porta exigida | `memory` | `persistent` | `test` |
|---|---|---|---|
| `clock` | relógio do sistema | relógio do sistema | relógio fixo |
| `trace` | JSONL ou memória | JSONL ou memória | memória |
| `providers` | Ollama | Ollama | provider simulado |
| `pack_source` | entry points | entry points | entry points |
| `request_ids` | aleatório | aleatório | sequencial (`req-N`) |
| `conversation_ids` | aleatório | aleatório | sequencial (`t-N`) |
| `database` | — | pool Postgres (`AI_CORE_DATABASE_URL`), aberto no ciclo de vida da app | — |
| `api_keys` | memória + `AI_CORE_DEV_API_KEY` | Postgres (003) | memória + `TEST_API_KEY` |
| `oidc` | JWKS se configurado; senão recusa | JWKS se configurado; senão recusa | estático com `TEST_OIDC_TOKEN` |
| `user_assistants` | memória | Postgres (003) | memória |
| `conversations` | memória | Postgres (008) | memória |

As fábricas recebem a configuração e as partes já construídas (`database` antes das de armazenamento). O autenticador
anônimo sai dos perfis.

**Credenciais do perfil `test`** (exportadas por `ai_core.bootstrap.profiles`): `TEST_SUBJECT = "user:test"`,
`TEST_OIDC_TOKEN`, `TEST_API_KEY` (no grupo `TEST_ADMIN_GROUP = "admin"`). A suíte de um pack externo envia
`Authorization: Bearer <TEST_OIDC_TOKEN>` em `/v1` ou `Bearer <TEST_API_KEY>` em `/private/v1`.

**Regras novas**: nenhum perfil aceita requisição sem credencial (FR-015); `persistent` sem `AI_CORE_DATABASE_URL` é
configuração inválida; `AI_CORE_DEV_API_KEY` no `persistent` é recusada; o relatório de boot avisa quando o `memory`
não tem chave de desenvolvimento nem OIDC.

Conformidade (`tests/bootstrap/unit/test_profiles.py`): os três perfis atendem todas as portas exigidas; as fábricas do
`persistent` constroem o pool fechado e os adapters Postgres sem conectar; o `test` não instancia nada que fale com
rede.

---

## Fase 3 (2026-10-02): portas da 007 e da 004; trocas de porta (research R22, R31)

| Porta exigida | Dono | `memory` | `persistent` | `test` |
|---|---|---|---|---|
| `mcp_store` | 007 | memória | Postgres (schema `mcp`) | memória |
| `mcp_dns` | 007 | DNS do sistema | DNS do sistema | resolvedor fixo, vazio |
| `mcp_transports` | 007 | `http`, `sse` (política de rede da 007, com `mcp_dns`) | `http`, `sse`, `stdio` | `http`, `sse`, `stdio`: um transporte programado, sem servidores |
| `mcp_secrets` | 007 | ambiente (`AI_CORE_MCP_SECRET_<REF>`) | ambiente | memória, vazio |
| `mcp_cache` | 007 | memória, com TTL | memória, com TTL | memória, com TTL |
| `audit` | 004 | memória | Postgres (schema `capabilities`) | memória |

No `test`, o provider simulado responde `{"action": "answer"}` em chamada sem streaming: um Assistant `agentic` funciona
ponta a ponta sem configuração extra — o controller responde direto.

### Trocas de porta

```python
from ai_core.bootstrap.wiring import platform

plataforma = platform(
    profile="test",
    config=minha_config,
    overrides={
        "providers": {"ollama": provider_da_suite, "ctrl": controller_programado},
        "mcp_transports": {"http": transporte_programado, "sse": transporte_programado},
    },
)
```

| Regra | Verificada por |
|---|---|
| A troca substitui o adapter da porta; as fábricas seguintes enxergam o valor trocado | `unit/test_profile_overrides.py` |
| Porta desconhecida → `ConfigurationError` nomeando a porta | idem |
| `database` ou porta de armazenamento → `ConfigurationError` (a sessão de armazenamento reconstruiria a porta e ignoraria a troca) | idem |
| Nenhuma variável de ambiente nem arquivo expõe trocas | revisão de `settings.py` |
