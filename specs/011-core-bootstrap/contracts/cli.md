# Contrato — a raiz `axon` (Fase 2, US4; research R17)

```text
axon serve [--profile P]
axon packs list | check | prepare            # 002 (prepare: ADR-041)
axon assistants validate                     # 003
axon keys create --subject S [--group G]... [--label L] | list | revoke KEY_ID   # 003
axon health                                  # 011
```

Todos usam a mesma configuração (`AXON_*`) e os mesmos adapters do servidor; nenhum, além de `serve`, abre a porta
HTTP (FR-010, FR-011). `--profile` vale para todos os subcomandos.

| Comando | O que monta | Saída e código |
|---|---|---|
| `packs list` | configuração, adapters, packs | 002 `contracts/cli.md`: 0; 2 com `packs.yaml` malformado |
| `packs check` | idem | 0 sem pack em erro; 1 com; 2 com `packs.yaml` malformado |
| `packs prepare` | configuração e adapters; a 002 leva cada pack habilitado até a configuração validada, sem catálogo | 002 `contracts/cli.md`: 0; 1 nomeando o pack que falhou; 2 com `packs.yaml` malformado |
| `assistants validate` | a plataforma (sem servir) | 003 `contracts/cli.md`: 0; 1 com Assistant indisponível; 2 com `assistants.yaml` malformado |
| `keys create\|list\|revoke` | configuração, adapters; abre o armazenamento de chaves no próprio laço | 003 `contracts/cli.md`; aviso quando o perfil não é persistente |
| `health` | a plataforma (sem servir) | um item por linha; 0 `ok`, 1 `degraded`, 2 `down` |
| erro de configuração (`AXON_*`) | — | 1, nomeando a variável |

`axon --help` lista todos os subcomandos (US4 cen. 1). Acrescentar os comandos de um módulo novo é acrescentar uma
entrada à lista de registro da raiz, sem tocar nos outros (US4 cen. 3).

Conformidade (`tests/bootstrap/contract/test_cli_commands.py`): cada linha da tabela com `main(argv)`, saída capturada
e servidor injetado (que nunca é chamado fora do `serve`).

---

## Fase 3 (2026-10-02): `axon audit` (research R29)

```text
axon audit [--principal P] [--assistant A] [--tool T] [--since ISO] [--until ISO] [--limit N] [--results]
```

Formato da saída e códigos: os do contrato da 004 (`specs/004-core-capability-gateway/contracts/audit.md`) — 0; 2 para
filtro inválido. Boot que falha: 1. Sobe até `engine` (sem rede; o gateway precisa do Trace Sink) e monta a consulta da 004 sobre a sessão de
armazenamento, pela mesma fábrica do servidor. No `memory` e no `test`, a auditoria é do próprio processo: a listagem
sai vazia.

### Suíte de conformidade — acréscimos

- `axon --help` lista `audit`;
- `--since` fora do ISO 8601 → 2;
- perfil `test` → 0 e nenhuma linha;
- `persistent` com Postgres: um registro gravado pela auditoria da 004 aparece, sem o resultado; com `--results`,
  com ele.

## Fase 6 (2026-10-13): `axon eval run|compare` (009 research R25)

```text
axon eval run --golden <arquivo> [--assistant <nome>] [--judge <provider/modelo>] [--baseline <arquivo>]
                 [--update-baseline] [--force] [--report <arquivo>] [--principal <subject>] [--group <g>]…
                 [--annotate <texto>]…
axon eval compare <relatório> <relatório>…
```

`eval run` sobe a plataforma até a etapa `assistants`, sem a API, abre a sessão de armazenamento como o `audit` e compõe
o harness da 009 (motor, consulta de trace, resolução de grant da 003, métricas de domínio da 002 e, com `--judge`, o
juiz pelo Model Router). `--principal` é `user:<id>` ou `svc:<id>` (default `svc:eval`) e precisa ser admitido pela ACL
do Assistant. Saída: 0 sem regressão; 1 com regressão de métrica determinística além da tolerância; 2 para entrada
inválida (conjunto ilegível, Assistant inexistente, principal ou juiz inválidos, trace sem leitura). `eval compare` só
lê relatórios (0; 2 para relatório ilegível). Formatos em `specs/009-core-observability-evaluation/contracts/eval-harness.md`.


## Fase 9, incremento 9.5 (2026-10-20): o comando `axon` (US7; research R49)

A raiz se chama `axon` (era `ai-core`; ADR-037), com os mesmos subcomandos.

```text
axon --version        # axon-ai 0.7.0rc1
```

| Comando | O que monta | Saída e código |
|---|---|---|
| `--version` | nada (nem a configuração) | `axon-ai <versão>` dos metadados da distribuição, ou `axon-ai desconhecida`; 0 |
| qualquer subcomando com `AI_CORE_*` no ambiente | — | 1, com as linhas da recusa ([configuration.md](configuration.md)) |

Conformidade (`tests/bootstrap/contract/test_cli_commands.py`): `--version`, a recusa num subcomando e `prog` `axon` na
ajuda.
