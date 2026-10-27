-- Spec 008, ADR-044 (research R60): as imagens de uma mensagem da conversa — as das tools e as do usuário —, presas a
-- ela. Somem com a mensagem, que some com a conversa (cascata e a mesma expiração; sem retenção própria).
CREATE TABLE http.attachments (
    conversation_id  text     NOT NULL,
    seq              integer  NOT NULL,
    position         integer  NOT NULL,
    id               text     NOT NULL,
    mime             text     NOT NULL,
    size_bytes       integer  NOT NULL,
    data             bytea    NOT NULL,
    PRIMARY KEY (conversation_id, seq, position),
    FOREIGN KEY (conversation_id, seq) REFERENCES http.messages (conversation_id, seq) ON DELETE CASCADE
);

CREATE INDEX attachments_by_id ON http.attachments (conversation_id, id);
