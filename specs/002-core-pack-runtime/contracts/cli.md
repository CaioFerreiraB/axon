# Contrato — `packs list`, `packs check` e `packs prepare` (Fase 2, US4; `prepare` desde 2026-10-21, ADR-041)

Funções em `axon_ai/packs/adapters/cli.py` que recebem o `PackRegistry` já carregado pela composition root — com os
mesmos adapters do servidor, sem abrir a API — e a saída, e devolvem o código de saída ([research.md](../research.md)
R15). **Quem as registra** na raiz `axon` é a 011 (US4). Síncronas, como a carga do registry.

```python
def list_command(registry: PackRegistry, out: TextIO) -> int: ...
def check_command(registry: PackRegistry, out: TextIO) -> int: ...
def config_error_command(error: PackConfigError, err: TextIO) -> int: ...
def prepare_command(preparation: PackDataPreparation, out: TextIO, err: TextIO) -> int: ...   # ADR-041
```

## `axon packs list`

Uma linha por pack instalado ou citado na configuração, na ordem de `entries()`: nome, versão, versão de contrato,
status e, se em erro, a mensagem (US4 cen. 1). Campo ausente aparece como `-`.

```text
$ axon packs list
financeiro  1.2.0  0.2  error     requer axon-ai-contracts>=0.2,<0.3, instalado 0.1.0
generic     0.2.0  0.2  enabled
scouting    -      -    error     não instalado
```

Sai com 0 mesmo havendo packs em erro — listar não é validar.

## `axon packs check`

Reprova exatamente o que o boot marcaria como erro (R16), inclusive pack instalado e desabilitado. Imprime as entradas
em erro e um resumo.

```text
$ axon packs check
financeiro  1.2.0  0.2  error     requer axon-ai-contracts>=0.2,<0.3, instalado 0.1.0
1 de 2 packs em erro
```

## `axon packs prepare` (ADR-041)

Roda no build da instalação, antes do `packs check`. Para cada pack habilitado: leva o pack até a configuração validada,
cria `<AXON_PACKS_DATA_DIR>/<nome>` e chama o `prepare` dele ([pack-runtime-api.md](pack-runtime-api.md), "Preparo de
dados"). Uma linha por pack — nome, `ok` ou `error`, e o diretório ou a causa — e um resumo. Sem raiz de dados, o
diretório aparece como `-` e o hook recebe `data_dir=None`.

```text
$ AXON_PACKS_DATA_DIR=/opt/axon-data axon packs prepare
generic   ok     /opt/axon-data/generic
scouting  error  prepare levantou ConnectionError: falha ao baixar o modelo
1 de 2 packs falharam no preparo
```

Com todos bons, o resumo é `M packs preparados`. Nenhum pack habilitado: `0 packs preparados`, código 0.

## Códigos de saída

| Situação | `list` | `check` | `prepare` |
|---|---|---|---|
| nenhum pack em erro | 0 | 0 (`M packs ok`) | 0 (`M packs preparados`) |
| algum pack em erro | 0 | 1, nomeando pack e causa | 1, nomeando pack e causa, depois de tentar os demais |
| `packs.yaml` malformado (`PackConfigError`) | 2 | 2, com a mensagem que nomeia o campo | 2, idem |

São os códigos do `assistants validate` (003), para que o build trate os dois comandos do mesmo jeito.

## Conformidade (`tests/packs/integration/test_packs_cli.py`)

1. `list` mostra nome, versão, versão de contrato e status de cada pack, com `-` onde não há valor, e sai com 0;
2. `check` com todos os packs bons sai com 0 e o resumo `M packs ok`;
3. `check` com um pack incompatível **desabilitado** sai com 1 e nomeia a incompatibilidade (US4 cen. 2);
4. `check` com pack citado e não instalado, e com configuração fora do schema, sai com 1 nomeando cada um;
5. `config_error_command` sai com 2 e repete a mensagem de `PackConfigError`;
6. a carga usada pelos comandos é a real — distribuições falsas e `packs.yaml` em `tmp_path`, como na suíte de
   integração da Fase 1.
7. `prepare` com dois packs bons e a raiz em `tmp_path` sai com 0, cria os dois diretórios e imprime cada um (US4 cen. 3);
8. `prepare` com um pack cujo hook levanta sai com 1, nomeia o pack e a exceção, e prepara o outro (US4 cen. 4).
