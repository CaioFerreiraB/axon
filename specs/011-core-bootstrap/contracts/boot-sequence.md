# Contrato — sequência de boot e encerramento

Interno do módulo (`lifecycle.py`), mas é **requisito observável**: a ordem e a política de falha de cada etapa são o
que o operador enxerga quando algo dá errado (FR-002, FR-003, SC-002, SC-004, SC-005).

## As etapas

| # | Etapa | Faz | Política |
|---|---|---|---|
| 1 | `configuration` | carrega e valida a configuração do operador e os arquivos citados | **crítica** |
| 2 | `adapters` | valida o perfil e instancia os adapters de cada porta | **crítica** |
| 3 | `packs` | carrega os packs (002) | degradável |
| 4 | `engine` | constrói o motor (005) com os seams injetados | **crítica** |
| 5 | `api` | monta a aplicação HTTP (008) | **crítica** |

Etapas de outras fases — `mcp_registry` (007) e `assistants` (003) — entram na lista sem tocar no código que a
executa ([research.md](../research.md) R1). O motor vem **antes** da validação de Assistants porque a 003 valida nomes
de flow, que são seam do motor.

## Regras

| Regra | Origem | Verificada por |
|---|---|---|
| As etapas rodam na ordem declarada | FR-002 | conformidade, com etapas de teste |
| Falha de etapa crítica interrompe o boot; as seguintes não rodam | FR-003 | conformidade |
| Falha de etapa degradável registra o motivo e o boot segue | FR-003, princípio VII | conformidade |
| A API só aceita requisição depois da última etapa | FR-002, SC-002 | conformidade |
| Nenhum adapter é instanciado durante uma execução | US1 cen. 5 | conformidade (a plataforma é montada uma vez) |
| O relatório nomeia a etapa que falhou e o motivo | SC-005 | conformidade |
| O encerramento libera os recursos na ordem inversa | FR-013, US1 cen. 4 | conformidade |

## Relatório de boot

```text
configuration  ok
adapters       ok
packs          degraded  — pack 'quebrado': contrato incompatível
engine         ok
api            ok
```

`BootReport.ok` é verdadeiro: nenhuma etapa crítica falhou. `BootReport.degraded` traz `["packs"]` — é o que responde
"qual item falhou e por quê" sem ler log (SC-005).

## Encerramento

1. a porta para de aceitar requisições (o servidor ASGI faz isso ao receber o sinal);
2. as execuções em andamento têm até `shutdown_grace_seconds` para terminar;
3. os recursos registrados por cada etapa são liberados na **ordem inversa** do boot.

Na Fase 1 os adapters são todos de memória ou de arquivo, então há pouco a liberar — mas o mecanismo existe e é
testado, porque é ele que a Fase 2 usa quando houver conexões de banco.

## Suíte de conformidade

`packages/core/tests/bootstrap/contract/test_boot_sequence.py`, com **etapas de teste** (sem plataforma):

1. as etapas rodam na ordem declarada, e o relatório as traz nessa ordem;
2. falha em etapa crítica interrompe: as seguintes não rodam e `BootReport.ok` é falso;
3. falha em etapa degradável não interrompe: as seguintes rodam e `ok` continua verdadeiro;
4. o relatório nomeia a etapa e o motivo em ambos os casos;
5. o encerramento libera os recursos na ordem inversa do registro;
6. uma etapa crítica que falha desfaz as etapas já concluídas, também na ordem inversa;
7. acrescentar uma etapa à lista não exige mudança no executor — uma lista com etapa nova roda sem alteração de
   código.

E `packages/core/tests/bootstrap/contract/test_cli_serve.py`, para o comando:

1. `serve` monta a plataforma e entrega a app e o endereço ao servidor injetado;
2. o relatório sai com as cinco etapas da fase;
3. o relatório avisa que a autenticação é anônima;
4. configuração inválida faz o comando sair com código não zero **sem** chamar o servidor;
5. a ajuda lista o subcomando.

---

## Fase 2 (2026-09-30)

Etapas registradas: `configuration` → `adapters` → `packs` → `engine` → `assistants` (validação de Assistants, 003;
degradável) → `api`. No perfil `persistent`, a etapa `adapters` (crítica) confere a conexão com o banco e roda as
migrações de `assistants` e `http` num pool temporário; falha para o boot nomeando a porta `database`, o adapter e,
numa migração, o módulo e o arquivo — nunca a URL.

**Ciclo de vida da app** (research R14): no início, abre o pool de serviço e agenda as tarefas periódicas (expiração
de conversas); no fim, cancela as tarefas e fecha o pool. O encerramento do processo continua liberando os recursos do
boot na ordem inversa (FR-013).
