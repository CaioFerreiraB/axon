-- Chaves de assinatura (spec 012, FR-016): a privada só selada com a subchave da chave mestra (ADR-033).
CREATE TABLE identity.signing_keys (
    kid             text        PRIMARY KEY,
    public_jwk      jsonb       NOT NULL,
    private_sealed  bytea       NOT NULL,
    state           text        NOT NULL CHECK (state IN ('active', 'retiring', 'retired')),
    created_at      timestamptz NOT NULL,
    retiring_since  timestamptz
);
