-- Assistants de usuário (spec 003, FR-009, FR-017): únicos por (dono, nome sem o "~"). O rascunho vai inteiro em JSON,
-- com "format" para permitir evolução sem migração de colunas. Timestamps vêm da porta Clock (ADR-015).
CREATE TABLE assistants.user_assistants (
    owner       text        NOT NULL,
    name        text        NOT NULL,
    definition  jsonb       NOT NULL,
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz NOT NULL,
    PRIMARY KEY (owner, name)
);
