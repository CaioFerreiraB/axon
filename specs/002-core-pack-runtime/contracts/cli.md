# Contrato — `packs list` e `packs check` (Fase 2, US4)

Funções em `ai_core/packs/adapters/cli.py` que recebem o `PackRegistry` já carregado pela composition root — com os
mesmos adapters do servidor, sem abrir a API — e a saída, e devolvem o código de saída ([research.md](../research.md)
R15). **Quem as registra** na raiz `ai-core` é a 011 (US4). Síncronas, como a carga do registry.

```python
def list_command(registry: PackRegistry, out: TextIO) -> int: ...
def check_command(registry: PackRegistry, out: TextIO) -> int: ...
def config_error_command(error: PackConfigError, err: TextIO) -> int: ...
```

## `ai-core packs list`

Uma linha por pack instalado ou citado na configuração, na ordem de `entries()`: nome, versão, versão de contrato,
status e, se em erro, a mensagem (US4 cen. 1). Campo ausente aparece como `-`.

```text
$ ai-core packs list
financeiro  1.2.0  0.2  error     requer ai-core-contracts>=0.2,<0.3, instalado 0.1.0
generic     0.1.0  0.1  enabled
scouting    -      -    error     não instalado
```

Sai com 0 mesmo havendo packs em erro — listar não é validar.

## `ai-core packs check`

Reprova exatamente o que o boot marcaria como erro (R16), inclusive pack instalado e desabilitado. Imprime as entradas
em erro e um resumo.

```text
$ ai-core packs check
financeiro  1.2.0  0.2  error     requer ai-core-contracts>=0.2,<0.3, instalado 0.1.0
1 de 2 packs em erro
```

## Códigos de saída

| Situação | `list` | `check` |
|---|---|---|
| nenhum pack em erro | 0 | 0 (`M packs ok`) |
| algum pack em erro | 0 | 1, nomeando pack e causa |
| `packs.yaml` malformado (`PackConfigError`) | 2 | 2, com a mensagem que nomeia o campo |

São os códigos do `assistants validate` (003), para que o build trate os dois comandos do mesmo jeito.

## Conformidade (`tests/packs/integration/test_packs_cli.py`)

1. `list` mostra nome, versão, versão de contrato e status de cada pack, com `-` onde não há valor, e sai com 0;
2. `check` com todos os packs bons sai com 0 e o resumo `M packs ok`;
3. `check` com um pack incompatível **desabilitado** sai com 1 e nomeia a incompatibilidade (US4 cen. 2);
4. `check` com pack citado e não instalado, e com configuração fora do schema, sai com 1 nomeando cada um;
5. `config_error_command` sai com 2 e repete a mensagem de `PackConfigError`;
6. a carga usada pelos comandos é a real — distribuições falsas e `packs.yaml` em `tmp_path`, como na suíte de
   integração da Fase 1.
