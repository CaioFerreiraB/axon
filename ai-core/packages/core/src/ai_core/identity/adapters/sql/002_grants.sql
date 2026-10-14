-- Pedidos pendentes, sessões, códigos e renovação (spec 012, FR-006, FR-007, FR-014). Todo segredo de protocolo só como
-- hash (FR-020). Apagar uma sessão apaga a renovação dela; códigos sobrevivem à sessão por um tempo, para que o reuso
-- ainda revogue a família.
CREATE TABLE identity.pending_authorizations (
    id_hash             text        PRIMARY KEY,
    csrf_hash           text        NOT NULL,
    client_id           text,
    redirect_uri        text,
    scope               text        NOT NULL,
    state               text,
    nonce               text,
    code_challenge      text,
    account_id          text,
    google_state_hash   text        UNIQUE,
    google_nonce        text,
    google_verifier     text,
    created_at          timestamptz NOT NULL,
    expires_at          timestamptz NOT NULL
);

CREATE TABLE identity.sessions (
    id_hash     text        PRIMARY KEY,
    account_id  text        NOT NULL REFERENCES identity.accounts (id),
    auth_time   timestamptz NOT NULL,
    amr         text        NOT NULL,
    created_at  timestamptz NOT NULL,
    expires_at  timestamptz NOT NULL,
    revoked_at  timestamptz
);
CREATE INDEX sessions_account ON identity.sessions (account_id);

CREATE TABLE identity.authorization_codes (
    hash            text        PRIMARY KEY,
    client_id       text        NOT NULL,
    session_id      text        NOT NULL,
    account_id      text        NOT NULL,
    family_id       text        NOT NULL,
    redirect_uri    text        NOT NULL,
    scope           text        NOT NULL,
    nonce           text,
    code_challenge  text,
    auth_time       timestamptz NOT NULL,
    amr             text        NOT NULL,
    expires_at      timestamptz NOT NULL,
    used_at         timestamptz
);

CREATE TABLE identity.refresh_tokens (
    hash        text        PRIMARY KEY,
    family_id   text        NOT NULL,
    session_id  text        NOT NULL REFERENCES identity.sessions (id_hash) ON DELETE CASCADE,
    client_id   text        NOT NULL,
    account_id  text        NOT NULL,
    scope       text        NOT NULL,
    status      text        NOT NULL CHECK (status IN ('active', 'rotated', 'revoked')),
    created_at  timestamptz NOT NULL,
    rotated_to  text
);
CREATE INDEX refresh_tokens_family ON identity.refresh_tokens (family_id);
CREATE INDEX refresh_tokens_session ON identity.refresh_tokens (session_id);
