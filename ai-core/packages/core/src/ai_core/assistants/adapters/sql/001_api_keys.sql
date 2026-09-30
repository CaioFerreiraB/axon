-- Chaves de API (spec 003, FR-015): só o hash, nunca a chave. Timestamps vêm da porta Clock (ADR-015).
CREATE TABLE assistants.api_keys (
    key_id      text        PRIMARY KEY,
    key_hash    bytea       NOT NULL,
    subject     text        NOT NULL,
    groups      text[]      NOT NULL DEFAULT '{}',
    label       text,
    created_at  timestamptz NOT NULL,
    revoked_at  timestamptz
);
