-- Uso por chamada de modelo e por execução (spec 009 US5, ADR-034; research R30). Sem texto nenhum: tokens, tempos e
-- de onde veio. O dia é calculado na consulta, no fuso pedido — mudar o fuso não exige migração.
CREATE TABLE observability.model_calls (
    id              bigserial   PRIMARY KEY,
    request_id      text        NOT NULL,
    at              timestamptz NOT NULL,
    origin          text        NOT NULL CHECK (origin IN ('production', 'evaluation')),
    assistant       text,
    provider        text        NOT NULL,
    model           text        NOT NULL,
    role            text        NOT NULL,
    input_tokens    integer     NOT NULL,
    output_tokens   integer     NOT NULL,
    duration_ms     double precision NOT NULL,
    failed          boolean     NOT NULL
);
CREATE INDEX model_calls_at ON observability.model_calls (at);
CREATE INDEX model_calls_model_at ON observability.model_calls (provider, model, at);

CREATE TABLE observability.executions (
    request_id      text        PRIMARY KEY,
    started_at      timestamptz NOT NULL,
    finished_at     timestamptz,
    origin          text        NOT NULL CHECK (origin IN ('production', 'evaluation')),
    assistant       text        NOT NULL,
    flow            text        NOT NULL,
    ok              boolean,
    duration_ms     double precision
);
CREATE INDEX executions_started_at ON observability.executions (started_at);
