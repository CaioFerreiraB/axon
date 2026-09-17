# Contrato — configuração de packs do operador (`packs.yaml`)

Formato é da 002; caminho do arquivo e escolha do adapter são da 011 (research R6). Lido uma vez, no boot; mudar exige
restart (FR-003).

```yaml
packs:
  generic:
    enabled: true
  scouting:
    enabled: true
    config:
      collection: scouting_docs
  financial:
    enabled: false          # instalado, desligado
```

## Regras

| Regra | Violação |
|---|---|
| o arquivo existe e é YAML válido | `PackConfigError` — boot para (011) |
| raiz é um mapeamento com a chave `packs` (pode ser vazia) | `PackConfigError` — boot para (011) |
| cada pack é um mapeamento com, no máximo, `enabled` e `config` | `PackConfigError` nomeando `packs.<nome>.<chave>` |
| `enabled` é booleano; ausente = `false` | `PackConfigError` |
| `config` é mapeamento JSON; ausente = `{}` | `PackConfigError` |
| pack habilitado na configuração e não instalado | não para o boot: entrada `error: não instalado` |
| `config` de pack habilitado não conforma ao `config_schema` do pack | não para o boot: pack `error` nomeando o campo (`configuração inválida em 'collection': ...`) — US1 cenário 3 |

Validação do `config` contra o schema do pack: `jsonschema`, dialeto de `$schema` (padrão Draft 2020-12), sem `$ref`
remoto; o erro usa o caminho absoluto do campo (`collection`, `limits.top_k`).
