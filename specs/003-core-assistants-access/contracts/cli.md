# Contrato — comandos de linha de comando da 003

Implementados em `axon_ai/assistants/adapters/cli.py` como funções — `validate_command`, `keys_create_command`,
`keys_list_command` e `keys_revoke_command`, assíncronas, e `validate_config_error`, síncrona — que recebem o serviço
já montado, os argumentos e a saída, e devolvem o código de saída. **Quem os registra** na raiz `axon` é a
composition root (011 US4): o framework de linha de comando é decisão dela ([research.md](../research.md) R14). Rodam
com a mesma configuração e os mesmos adapters do servidor, sem abrir a API (011 FR-010, FR-011).

## `axon assistants validate`

Valida todos os Assistants contra packs, flows, MCPs, coleções e modelos (FR-011).

```text
$ axon assistants validate
geral        system  ok
interno      system  indisponível  packs: pack 'financeiro' não está habilitado
~meu-rag     user    ok            (dono user:ana)
1 de 3 Assistants indisponível
```

| Situação | Código de saída |
|---|---|
| todos disponíveis (última linha: `N Assistants disponíveis`) | 0 |
| algum indisponível | 1 |
| erro de arquivo no `assistants.yaml` | 2, com a mensagem que nomeia o campo |

Assistants de usuário aparecem com as referências conferidas; a conformidade com a política depende dos grupos do
Principal e só é verificável na resolução (R14).

## `axon keys create --subject <user:…|svc:…> [--group <g>]... [--label <texto>]`

Emite uma chave com a autoridade do operador. A chave em claro aparece **uma vez**, na saída padrão, sozinha na última
linha — para que um script possa capturá-la —, e nunca em log.

```text
$ axon keys create --subject user:caio --group operadores --label "notebook"
key_id: 3f9a1c2e7b604d18
subject: user:caio  groups: operadores
axn_3f9a1c2e7b604d18_Jd8…
```

## `axon keys list`

Lista `key_id`, subject, grupos, rótulo, emissão e revogação. Nunca mostra hash nem chave.

## `axon keys revoke <key_id>`

Revoga; a próxima requisição com a chave é recusada. `key_id` inexistente sai com código 1 e mensagem explícita.

## `axon keys rotate <key_id>` (Fase 9, 2026-10-21; ADR-040)

Gera um segredo novo para a chave e a mostra **uma vez**, sozinha na última linha, como `keys create`. O `key_id`, o
subject, os grupos e o rótulo não mudam; o segredo anterior é recusado a partir da requisição seguinte, sem janela.
`key_id` inexistente ou chave revogada sai com código 1 e mensagem explícita.

```text
$ axon keys rotate 3f9a1c2e7b604d18
key_id: 3f9a1c2e7b604d18 (rotacionada)
subject: svc:relatorios  groups: -
axn_3f9a1c2e7b604d18_Qp7…
```

`keys create --subject svc:<nome>` exige `nome` no padrão dos nomes de Assistant (minúsculas, dígitos, `.`, `_`, `-`;
até 64). A CLI é o único caminho que concede o grupo de administração a uma chave.

## Observações

- No perfil em memória, cada processo tem o próprio armazenamento: chaves emitidas pela CLI só valem no perfil
  persistente. O comando avisa quando roda num perfil sem armazenamento persistente.
- Conformidade em `tests/assistants/integration/test_cli.py`: saída e código de saída de cada comando com o serviço em
  memória; `create` seguido de `authenticate` com a chave impressa; `revoke` seguido de recusa.
