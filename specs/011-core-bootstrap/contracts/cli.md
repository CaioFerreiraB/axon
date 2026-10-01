# Contrato — a raiz `ai-core` (Fase 2, US4; research R17)

```text
ai-core serve [--profile P]
ai-core packs list | check                      # 002
ai-core assistants validate                     # 003
ai-core keys create --subject S [--group G]... [--label L] | list | revoke KEY_ID   # 003
ai-core health                                  # 011
```

Todos usam a mesma configuração (`AI_CORE_*`) e os mesmos adapters do servidor; nenhum, além de `serve`, abre a porta
HTTP (FR-010, FR-011). `--profile` vale para todos os subcomandos.

| Comando | O que monta | Saída e código |
|---|---|---|
| `packs list` | configuração, adapters, packs | 002 `contracts/cli.md`: 0; 2 com `packs.yaml` malformado |
| `packs check` | idem | 0 sem pack em erro; 1 com; 2 com `packs.yaml` malformado |
| `assistants validate` | a plataforma (sem servir) | 003 `contracts/cli.md`: 0; 1 com Assistant indisponível; 2 com `assistants.yaml` malformado |
| `keys create\|list\|revoke` | configuração, adapters; abre o armazenamento de chaves no próprio laço | 003 `contracts/cli.md`; aviso quando o perfil não é persistente |
| `health` | a plataforma (sem servir) | um item por linha; 0 `ok`, 1 `degraded`, 2 `down` |
| erro de configuração (`AI_CORE_*`) | — | 1, nomeando a variável |

`ai-core --help` lista todos os subcomandos (US4 cen. 1). Acrescentar os comandos de um módulo novo é acrescentar uma
entrada à lista de registro da raiz, sem tocar nos outros (US4 cen. 3).

Conformidade (`tests/bootstrap/contract/test_cli_commands.py`): cada linha da tabela com `main(argv)`, saída capturada
e servidor injetado (que nunca é chamado fora do `serve`).
