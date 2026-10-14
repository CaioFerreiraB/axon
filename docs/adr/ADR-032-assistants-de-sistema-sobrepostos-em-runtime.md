# ADR-032 — Assistants de sistema podem ser sobrepostos em runtime, se o YAML permitir

- **Status:** Aceita · 2026-10-13
- **Specs afetadas:** [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md) (FR-013 substituída;
  contrato `assistants-yaml.md`: chave `overrides`), [008-core-http-api](../../specs/008-core-http-api/spec.md) (rotas de
  sobreposição), [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (saúde com os modelos efetivos; porta de
  armazenamento nova), [013-core-admin-console](../../specs/013-core-admin-console/spec.md)
- **Origem:** pedido do mantenedor (2026-10-13): trocar os modelos e os MCPs de cada Assistant pela console, sobrepondo
  o `assistants.yaml`, com uma flag por Assistant que diz se isso vale pela console ou só por novo deploy

## Contexto

A FR-013 da 003 diz que Assistants de sistema só mudam por novo deploy. O `AssistantsService` lê a configuração uma vez,
no boot, e a guarda imutável; a saúde lê os modelos declarados da mesma configuração. Não há caminho de sobreposição.

O operador quer duas coisas ao mesmo tempo: ajustar modelos e MCPs sem rebuild, e manter Assistants cuja configuração só
muda por deploy (por exemplo, os avaliados por um conjunto dourado, princípio X).

## Decisão

1. Cada Assistant de sistema pode declarar no YAML **o que a console pode sobrepor**:

   ```yaml
   geral:
     overrides: [models, mcp]
   ```

   O conjunto é fechado (`models`, `mcp`); ausente ou vazio, nada se sobrepõe — **o padrão é só por deploy**. Valor
   desconhecido é problema do Assistant, como os demais campos.
2. Uma sobreposição **substitui a seção inteira** e vive no armazenamento da 003 (schema `assistants`), com autor,
   versão e histórico:
   - `models`: os modelos por papel, **dentro do teto do YAML** — cada modelo casa a allowlist `models.allow`, e os
     papéis exigidos pelo flow continuam obrigatórios. A allowlist só muda por deploy;
   - `mcp`: os aliases e as entradas com namespace MCP de `allowed_tools` e `write_tools`. As entradas de pack não
     mudam. Tool de escrita em Assistant público continua proibida.
3. A sobreposição **só vale enquanto o YAML a permite**: se um deploy tira a seção de `overrides`, ela fica **inativa**,
   guardada e visível com o motivo, e o YAML volta a valer. (Se um deploy que muda a própria seção também desativa a
   sobreposição — a regra da impressão digital — fica para o `/speckit-clarify` da 003.)
4. A configuração **efetiva** (YAML + sobreposições ativas) passa pelas mesmas validações de hoje. Ao salvar, erro é 422
   nomeando o campo; na resolução, uma sobreposição que deixou de ser válida (um MCP apagado, por exemplo) torna o
   Assistant **indisponível com o motivo**, nunca degradado em silêncio (princípio VII).
5. Descoberta, resolução, validação e saúde usam a configuração efetiva. A troca vale na requisição seguinte, sem
   restart, num processo; o cache por processo segue a premissa já aceita para rate limit e fila.

## Alternativas rejeitadas

*Sobreposição livre, sem flag.* Tira do operador o controle sobre Assistants que só devem mudar por deploy, e uma edição
na tela invalidaria em silêncio uma linha de base de avaliação.

*Flag única, sem seções.* Não permite liberar MCP mantendo os modelos presos, que é o caso de um Assistant avaliado
contra um conjunto dourado com um modelo fixo.

*Sobreposição que pode ampliar a allowlist.* A allowlist é o teto que o operador fixou no deploy (princípio VIII); a
console escolhe dentro dele.

*Gravar a mudança no `assistants.yaml`.* O arquivo é do operador, montado somente leitura (ADR-029).

## Consequências

- A FR-013 da 003 passa a dizer: Assistants de sistema mudam por deploy e, nas seções que o YAML declara em
  `overrides`, pela administração; Assistants de usuário, só pelo dono.
- A 003 ganha a porta de armazenamento de sobreposições (memória e Postgres, com conformidade) e um seam de
  administração de Assistants de sistema, consumido pela 008.
- A saúde agregada (011) passa a ler os modelos efetivos.
- O `ai-core assistants validate` passa a validar também as sobreposições guardadas.
