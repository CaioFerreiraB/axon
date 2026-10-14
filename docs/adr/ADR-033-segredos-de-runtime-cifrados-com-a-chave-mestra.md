# ADR-033 — Segredos configurados em runtime ficam cifrados com a chave mestra da instalação

- **Status:** Aceita · 2026-10-13
- **Specs afetadas:** [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (`AI_CORE_MASTER_KEY`; precedência
  entre instalação e runtime), [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md)
  (chaves do Langfuse), [012-core-identity](../../specs/012-core-identity/spec.md) (chaves de assinatura);
  refina o item 1 do [ADR-020](ADR-020-segredos-uma-fonte-por-perfil-uma-porta-por-modulo.md)
- **Origem:** decisão do mantenedor (2026-10-13): com a console instalada, as chaves do Langfuse ficam na console; sem
  ela, na instalação. E o provedor de identidade (ADR-030) precisa guardar a própria chave de assinatura

## Contexto

O ADR-020 fixou **uma fonte de segredos por perfil**: o ambiente em `memory` e `persistent`, a memória em `test`. Cada
módulo tem a sua porta, com a sua regra de nomes, e nenhum valor de segredo vai para configuração versionada, log,
erro ou trace.

Dois segredos novos não cabem nisso: as chaves do Langfuse, que a console precisa gravar sem deploy, e a chave privada
de assinatura do provedor de identidade, que a plataforma gera e precisa guardar entre restarts.

## Decisão

1. Um segredo **configurável em runtime** é gravado **cifrado** no armazenamento do módulo dono, com AES-GCM e uma
   subchave derivada (HKDF) de `AI_CORE_MASTER_KEY` com o nome do módulo. Cada módulo que grava segredo declara a
   própria porta de cifra; nenhum módulo decifra o segredo de outro.
2. **Precedência: instalação > runtime > padrão.** Um valor definido no ambiente vence e aparece na administração como
   "definido na instalação", somente leitura. Assim o core não precisa saber se há console: a instalação com console
   simplesmente não define as variáveis; a sem console as define.
3. Segredo é **só de escrita** na API: a administração informa se há valor e de onde ele vem, nunca o valor.
4. `AI_CORE_MASTER_KEY` (32 bytes em base64) é **obrigatória no perfil `persistent`** quando há o que cifrar (identidade
   ligada ou segredo gravado); sem ela, gravar um segredo é 409 com a explicação, e a identidade não sobe. No `memory`,
   uma chave aleatória por processo; no `test`, uma fixa.
5. Os segredos de nome fixo da instalação (credenciais dos providers, do Google, dos clientes OIDC, referências de MCP)
   continuam pela regra do ADR-020: ambiente e porta por módulo.

## Alternativas rejeitadas

*Segredos em claro no banco.* Um dump do banco entregaria as chaves do Langfuse e a chave de assinatura — com ela,
qualquer um emite tokens de admin.

*Só a instalação, sempre.* Contraria a decisão do mantenedor para a instalação com console.

*Um cofre externo (Vault, secret manager da nuvem).* Um serviço a mais no hardware alvo, sem caso de uso além destes
dois segredos; continua possível depois, como adapter da porta de cifra.

## Consequências

- O item 1 do ADR-020 passa a ler: uma fonte de segredos **de instalação** por perfil; segredos de runtime, cifrados
  no módulo dono com a chave mestra.
- Perder a chave mestra torna ilegíveis os segredos gravados: a recuperação é rotacionar a chave de assinatura (todas as
  sessões caem) e redigitar as chaves do Langfuse. A instalação documenta isso.
- O perfil `persistent` ganha uma variável obrigatória condicional, verificada na etapa `configuration`.
