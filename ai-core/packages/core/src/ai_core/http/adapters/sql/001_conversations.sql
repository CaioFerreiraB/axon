-- Conversas no servidor (spec 008, US7; ADR-015): por (dono, id), mensagens em ordem, exclusão em cascata.
-- Timestamps vêm da porta Clock.
CREATE TABLE http.conversations (
    id                text        PRIMARY KEY,
    owner             text        NOT NULL,
    assistant         text        NOT NULL,
    model             text        NOT NULL,
    created_at        timestamptz NOT NULL,
    last_activity_at  timestamptz NOT NULL,
    message_count     integer     NOT NULL DEFAULT 0
);

CREATE INDEX conversations_owner_activity ON http.conversations (owner, last_activity_at DESC, id DESC);
CREATE INDEX conversations_activity ON http.conversations (last_activity_at);

CREATE TABLE http.messages (
    conversation_id  text        NOT NULL REFERENCES http.conversations (id) ON DELETE CASCADE,
    seq              integer     NOT NULL,
    role             text        NOT NULL,
    content          text        NOT NULL,
    at               timestamptz NOT NULL,
    request_id       text        NOT NULL,
    citations        jsonb       NOT NULL DEFAULT '[]',
    flags            text[]      NOT NULL DEFAULT '{}',
    PRIMARY KEY (conversation_id, seq)
);
