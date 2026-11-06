# ADR-059 — O que fica de uma conta apagada é pseudonimizado (refina o item 6 do 058)

- **Status:** Aceita · 2026-11-04
- **Specs afetadas:**
  - [012-core-identity](../../specs/012-core-identity/spec.md): gera o pseudônimo e o passa aos apagadores (FR-038).
  - [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md): o Subject Erasure recebe o pseudônimo e
    troca o autor das sobreposições e do histórico.
  - [004-core-capabilities-gateway](../../specs/004-core-capabilities-gateway/spec.md): seam novo, que pseudonimiza a
    auditoria por subject.
  - [009-core-observability-eval](../../specs/009-core-observability-eval/spec.md): seam novo, que pseudonimiza os
    autores de preços e ajustes.
  - [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md): monta os apagadores da 004 e da 009.
- **Origem:** clarificação da 012 de 2026-11-04. O mantenedor manteve os registros da plataforma ("A") com a condição de
  que "não sejam mantidos dados que identifiquem a conta".

## Contexto

O ADR-058 (item 6) decidiu manter, depois do apagamento de uma conta, o que é registro da plataforma: a auditoria de
tools de escrita (004), o uso, o custo e o impacto (009), o trace em arquivo, e os autores em históricos "como texto". O
mesmo item pedia que a 012 o confirmasse ou revisse na clarificação. Na clarificação, o mantenedor manteve os registros,
mas sem nada que identifique a pessoa.

Onde a plataforma guarda, fora dos dados que o ADR-058 já apaga, uma citação da conta (o subject `user:<nome>` ou o nome
de usuário como autor):

| Módulo | Onde |
|---|---|
| 012 | `updated_by` de outras contas e dos ajustes de login |
| 003 | `updated_by` das sobreposições e `actor` do histórico delas |
| 004 | `principal` da auditoria de tools de escrita |
| 009 | `created_by` dos preços e `updated_by` dos ajustes de destino |

O uso, o custo, o impacto e o trace em arquivo não citam o subject. As conversas e os anexos (008), os Assistants de
usuário, as chaves (003) e os servidores MCP de usuário (007) já são apagados pelo ADR-058.

## Decisão

1. **Nada que identifique a conta fica na plataforma depois do apagamento concluído.** Cada citação da conta num
   registro que fica é trocada por um **pseudônimo**.
2. **O pseudônimo** tem a forma `deleted:<16 hexadecimais aleatórios>`.
   - É gerado pela 012 uma vez por apagamento e guardado na conta "em apagamento", para a retomada usar o mesmo.
   - É o mesmo em todos os módulos, para que a trilha continue ligando as ações daquela conta entre si.
   - O prefixo não é `user:` nem `svc:` e o separador `:` não cabe num nome de usuário, então ele nunca casa com um
     Principal nem é herdado por uma conta nova.
   - Não deriva do nome, por exemplo por hash, porque nomes são adivinháveis.
3. **A porta de apagamento da 012 passa o pseudônimo** a cada apagador, com o subject e o ator. Cada módulo troca as
   próprias citações no mesmo seam de apagamento (ADR-058, item 2), que ganha o parâmetro. A 004 e a 009 ganham esse
   seam, só com a troca. A troca é idempotente, porque repetir não encontra mais o subject. A 011 monta os apagadores
   na ordem 003 → 007 → 008 → 004 → 009.
4. **Fica fora, sob a retenção do operador:** o log de processo (FR-021 da 012, que registra o nome de usuário em
   logins e mudanças) e o que já saiu para destinos externos de observabilidade (Langfuse, com captura ligada). A
   documentação da instalação diz isso.

## Alternativas rejeitadas

- **Manter os autores e a auditoria como texto** (o item 6 original). O mantenedor recusou: o nome continuaria
  guardado.
- **Apagar a auditoria da conta.** Destruiria a trilha de segurança; a pseudonimização a mantém útil sem identificar.
- **Hash do nome como pseudônimo.** É reversível por força bruta, porque nomes de usuário são curtos e previsíveis.
- **Um pseudônimo por módulo.** Quebraria a ligação entre a auditoria e os históricos de uma mesma conta.

## Consequências

- O incremento 9.7 ganha passadas na 004 e na 009. A 003 ganha um ajuste no Subject Erasure, que passa a receber o
  pseudônimo (aditivo) e a trocar `updated_by`/`actor`. A tabela de seams em `specs/README.md` acompanha.
- A 012 guarda o pseudônimo na conta "em apagamento" (migração do estado) e troca as próprias citações.
- A prova ponta a ponta busca o nome e o subject apagados em todos os schemas e não encontra nada (SC-012 da 012).
