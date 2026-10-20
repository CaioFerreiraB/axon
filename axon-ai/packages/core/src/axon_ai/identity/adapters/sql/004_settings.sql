-- Ajustes de login de runtime (spec 012, FR-009). Uma linha só; `google_enabled` nulo = padrão.
CREATE TABLE identity.settings (
    id              integer     PRIMARY KEY CHECK (id = 1),
    google_enabled  boolean,
    version         integer     NOT NULL,
    updated_by      text,
    updated_at      timestamptz
);
