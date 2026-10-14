-- Ajustes dos destinos do trace (spec 009 US6, US7; research R33): o segredo do Langfuse só selado com a subchave da
-- chave mestra (ADR-033). Uma linha só; campo nulo = vale o padrão.
CREATE TABLE observability.destination_settings (
    id                      integer     PRIMARY KEY CHECK (id = 1),
    langfuse_enabled        boolean,
    langfuse_host           text,
    langfuse_public_key     text,
    langfuse_secret_sealed  bytea,
    capture_content         boolean,
    version                 integer     NOT NULL,
    updated_by              text,
    updated_at              timestamptz
);
