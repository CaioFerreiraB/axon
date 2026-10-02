-- Spec 004 (ADR-015): auditoria de tools de escrita. Só inserção e o fechamento do próprio registro.
CREATE TABLE capabilities.audit (
    id          bigserial   PRIMARY KEY,
    request_id  text        NOT NULL,
    principal   text        NOT NULL,
    assistant   text        NOT NULL,
    tool        text        NOT NULL,   -- nome com namespace
    kind        text        NOT NULL,
    arguments   jsonb       NOT NULL,   -- inteiros (clarificação 4)
    status      text        NOT NULL CHECK (status IN ('started', 'ok', 'error', 'timeout')),
    result      text,                   -- o texto como o modelo recebeu: cercado e cortado
    started_at  timestamptz NOT NULL,
    finished_at timestamptz
);

CREATE INDEX audit_started_at ON capabilities.audit (started_at DESC, id DESC);
CREATE INDEX audit_principal ON capabilities.audit (principal);
CREATE INDEX audit_assistant ON capabilities.audit (assistant);
CREATE INDEX audit_tool ON capabilities.audit (tool);
