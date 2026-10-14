-- Sobreposições de Assistants de sistema (spec 003 US10, ADR-032; research R30): o conteúdo em JSON, a impressão
-- digital da seção do YAML de quando foi gravada e a versão otimista. O histórico guarda cada gravação e descarte.
-- Timestamps vêm da porta Clock (ADR-015).
CREATE TABLE assistants.system_overrides (
    assistant   text        NOT NULL,
    section     text        NOT NULL CHECK (section IN ('models', 'mcp')),
    payload     jsonb       NOT NULL,
    fingerprint text        NOT NULL,
    version     integer     NOT NULL,
    updated_by  text        NOT NULL,
    updated_at  timestamptz NOT NULL,
    PRIMARY KEY (assistant, section)
);

CREATE TABLE assistants.system_override_history (
    id          bigserial   PRIMARY KEY,
    assistant   text        NOT NULL,
    section     text        NOT NULL,
    action      text        NOT NULL CHECK (action IN ('saved', 'discarded')),
    payload     jsonb,
    version     integer     NOT NULL,
    actor       text        NOT NULL,
    at          timestamptz NOT NULL
);
CREATE INDEX system_override_history_assistant ON assistants.system_override_history (assistant, id DESC);
