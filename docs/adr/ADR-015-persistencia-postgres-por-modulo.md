# ADR-015 — Persistência em Postgres por módulo: psycopg 3, schema próprio, migrações no adapter

- **Status:** Aceita · 2026-09-30
- **Specs afetadas:** [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md) (primeira a aplicar),
  [008-core-http-api](../../specs/008-core-http-api/spec.md) (Fase 2),
  [004-core-capability-gateway](../../specs/004-core-capability-gateway/spec.md),
  [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md),
  [007-core-mcp-integration](../../specs/007-core-mcp-integration/spec.md) (Fase 3),
  [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (perfil persistente)
- **Origem:** plano da 003 ([research.md](../../specs/003-core-assistants-access/research.md) R8) — a primeira spec a
  trocar um adapter em memória por Postgres

## Contexto

A constituição fixa PostgreSQL como tecnologia dos adapters de armazenamento de cada módulo, e o roadmap troca cinco
portas de memória para Postgres entre as Fases 2 e 3 (`AssistantStore` e `ApiKeyStore` da 003, `ConversationStore` da
008, `AuditLog` da 004, `CheckpointStore` da 005, `McpServerStore` da 007). Nada fixa o driver, onde vivem as tabelas,
quem cria o schema nem quem abre as conexões. Se cada spec decidir sozinha, o processo único (ADR-012) termina com dois
drivers, pools concorrentes e tabelas de módulos diferentes misturadas no mesmo espaço de nomes — que é exatamente o
acoplamento por internals que o princípio II proíbe.

## Decisão

1. **Driver: psycopg 3**, API assíncrona, com `psycopg-pool`. O import-linter confina `psycopg` e `psycopg_pool` a
   `adapters/` de cada módulo.
2. **Um pool por processo**, construído pela composition root (011) a partir da configuração do perfil persistente e
   injetado em todos os adapters Postgres. Nenhum adapter abre conexão por conta própria.
3. **Um schema Postgres por módulo**, com o nome do pacote do módulo (`assistants`, `http`, `capabilities`, `graph`,
   `mcp`). Um adapter só lê e escreve no próprio schema; referência a tabela de outro módulo é violação do princípio II
   e aparece no SQL.
4. **Migrações no próprio adapter**: arquivos SQL numerados em `adapters/sql/`, só para a frente, aplicados em ordem
   por uma função `migrate(pool)` do módulo, sob trava consultiva, com a versão registrada numa tabela dentro do
   schema do módulo. A composition root chama o `migrate` de cada módulo na etapa de adapters do boot; migração que
   falha impede o boot, nomeando o módulo e o arquivo.
5. **Tempo vem da porta `Clock`**: timestamps são parâmetros das consultas, nunca `now()` no SQL (ADR-013).
6. **Conformidade contra Postgres real na CI**: a suíte de cada porta roda contra o adapter em memória e contra o
   Postgres, com a URL de teste em `AI_CORE_TEST_POSTGRES_DSN`; a CI do core oferece o serviço.

## Alternativas rejeitadas

*asyncpg.* Mais rápido e só assíncrono, mas com tipagem mais pobre e sem API síncrona para ferramentas de linha de
comando; o ganho de desempenho não aparece com o volume desta plataforma.

*SQLAlchemy + Alembic.* ORM e ferramenta de migração para um punhado de tabelas por módulo, com modelos declarativos
que tenderiam a vazar para fora de `adapters/`. Contraria o princípio XII.

*Tabelas com prefixo no schema `public`.* A fronteira entre módulos dependeria de convenção de nome; um schema por
módulo a torna um espaço de nomes.

*Migrações centralizadas na composition root.* A 011 passaria a conhecer o DDL de todos os módulos — internals que a
spec de cada um deve poder mudar sozinha.

## Consequências

- Trocar a porta de memória por Postgres é, em cada módulo, escrever o adapter e seus arquivos SQL; a 011 só acrescenta
  o módulo à lista de migrações do perfil persistente.
- Reescrever um módulo inclui reescrever o próprio schema, sem tocar nos outros.
- Uma instância Postgres só atende todos os módulos; separar um módulo em outra instância é configuração do pool.
- Custo: cada módulo mantém um executor de migração mínimo; se a repetição incomodar, ele sobe para uma biblioteca
  compartilhada de adapters, sem mudar esta decisão.
