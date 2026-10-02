# ADR-020 — Segredos: uma fonte por perfil, uma porta por módulo; credencial ausente degrada, não derruba

- **Status:** Aceita · 2026-10-02
- **Specs afetadas:** [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (FR-009 e o caso de borda "referência
  de segredo ausente" — refinados), [006-core-llm-providers](../../specs/006-core-llm-providers/spec.md) (FR-011, porta
  `SecretResolver`), [007-core-mcp-integration](../../specs/007-core-mcp-integration/spec.md) (porta `SecretResolver` e prefixo
  `AI_CORE_MCP_SECRET_`, sem mudança)
- **Origem:** análise de 2026-10-02 da passada da Fase 3 da 006 (achado I1); clarificação 2 de 2026-10-02 da 006

## Contexto

A FR-009 da 011 diz que "um único adapter de segredos DEVE atender todos os módulos que declaram porta de segredos", e o
caso de borda da 011 diz que, com uma referência ausente, "o adapter que precisa dela falha na inicialização com erro
que nomeia a referência". As duas frases foram escritas antes de existir qualquer porta de segredos.

Na Fase 3 surgiram duas, com necessidades diferentes:

- a **007** resolve referências que vêm de configuração e da API privada (`credential: financeiro_token`). O adapter de
  ambiente prefixa `AI_CORE_MCP_SECRET_` — e esse prefixo é controle de segurança (007 R7): sem ele, quem cadastra um
  servidor global apontaria a referência para `AI_CORE_DATABASE_URL` e a mandaria para um endpoint externo. A 011 já o
  registrou como `mcp_secrets` e trata a credencial ausente **degradando** a etapa `mcp_registry`, sem parar o boot;
- a **006** precisa de duas credenciais de nome fixo, `AI_CORE_OPENAI_API_KEY` e `AI_CORE_OPENROUTER_API_KEY`
  (clarificação 2), e a spec dela decidiu que provider sem credencial fica registrado, indisponível na saúde, com erro
  explícito antes da rede — sem derrubar o boot (FR-011).

Um adapter único não serve aos dois: com o prefixo da 007, as variáveis da 006 virariam `AI_CORE_MCP_SECRET_…`; sem
ele, a 007 perderia o controle de segurança. E "falha na inicialização" lida como "o boot para" contradiz a 007 já
implementada e a 006.

## Decisão

1. **Uma fonte de segredos por perfil**: o ambiente do processo em `memory` e `persistent`, memória em `test`. Trocar a
   fonte (por exemplo, por um secret store do operador) é trocar, na 011, os adapters de **todas** as portas de segredo
   do perfil juntos. É isso que a FR-009 da 011 passa a significar.
2. **Uma porta por módulo, com a regra de nomes do módulo**: a 007 resolve referências pelo prefixo
   `AI_CORE_MCP_SECRET_<REF>` e pela gramática dela; a 006 resolve só os seus dois nomes fixos. Nenhum módulo resolve
   nome arbitrário vindo de entrada. Cada porta tem a sua fábrica no perfil (`mcp_secrets`, `llm_secrets`).
3. **Credencial ausente degrada, não derruba**: a peça que depende dela é montada em estado de falha que nomeia a
   referência — nunca o valor — e o boot continua. Servidor MCP: etapa `mcp_registry` degradada (011 R23). Provider de
   modelo: indisponível no item `model:<provider/modelo>` da saúde e erro explícito na chamada, sem rede (006 FR-011); um
   provider sem credencial que nenhum Assistant declara não aparece em lugar nenhum, porque não é problema. É isso que o
   caso de borda da 011 passa a significar.
4. Inalterado: valor de segredo nunca em configuração versionada, log, relatório, erro ou trace.

## Alternativas rejeitadas

*Um adapter único para todas as portas.* Obrigaria um esquema de nomes comum: ou a 006 adota o prefixo da 007
(variáveis com "MCP" no nome para credenciais de modelo, contra a clarificação da 006), ou a 007 perde o prefixo (falha
de segurança).

*Parar o boot quando falta uma credencial.* Um provider sem uso — a plataforma registra OpenAI e OpenRouter em todo
perfil `memory` — impediria subir sem chaves que ninguém usa; contradiz a FR-009 da 006 (saúde nunca bloqueia o boot) e
o tratamento que a 011 já dá ao MCP.

*Degradar o boot quando falta a credencial de um provider.* Mesmo problema em menor grau: o relatório de boot ficaria
degradado em toda instalação local sem chaves de nuvem. A saúde agregada já mostra a falta onde ela importa (modelo
declarado por Assistant de sistema).

## Consequências

- A spec da 011 ganha uma nota na FR-009 e no caso de borda apontando para este ADR, como a 006 fez com o ADR-016.
- O perfil da 011 tem duas portas de segredo (`mcp_secrets`, `llm_secrets`); um módulo novo com segredos acrescenta a
  sua, com a sua regra de nomes, e o adapter da mesma fonte.
- Um secret store do operador, quando vier, é um adapter por porta sobre o mesmo cliente do store — não um adapter
  genérico de nomes livres.
