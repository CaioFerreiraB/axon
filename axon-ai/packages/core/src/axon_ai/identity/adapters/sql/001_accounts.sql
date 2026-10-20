-- Contas, grupos e membros (spec 012, FR-001, FR-010–FR-012). Contas nunca são apagadas, só desativadas: nome e e-mail
-- ficam únicos entre todas, sem diferenciar maiúsculas. A senha só como hash (FR-002). Timestamps vêm da porta Clock.
CREATE TABLE identity.accounts (
    id                  text        PRIMARY KEY,
    username            text        NOT NULL,
    email               text        NOT NULL,
    name                text        NOT NULL,
    active              boolean     NOT NULL,
    password_hash       text,
    temporary_password  boolean     NOT NULL,
    google_sub          text,
    created_at          timestamptz NOT NULL,
    updated_at          timestamptz NOT NULL,
    updated_by          text,
    last_login_at       timestamptz,
    version             integer     NOT NULL
);
CREATE UNIQUE INDEX accounts_username_key ON identity.accounts (lower(username));
CREATE UNIQUE INDEX accounts_email_key ON identity.accounts (lower(email));
CREATE UNIQUE INDEX accounts_google_sub_key ON identity.accounts (google_sub) WHERE google_sub IS NOT NULL;

CREATE TABLE identity.groups (
    name        text        PRIMARY KEY,
    created_at  timestamptz NOT NULL
);

-- Apagar um grupo remove as associações (FR-012).
CREATE TABLE identity.memberships (
    account_id  text NOT NULL REFERENCES identity.accounts (id),
    group_name  text NOT NULL REFERENCES identity.groups (name) ON DELETE CASCADE,
    PRIMARY KEY (account_id, group_name)
);
CREATE INDEX memberships_group ON identity.memberships (group_name);
