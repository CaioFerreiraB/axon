-- Spec 007 (ADR-015): servidores MCP criados pela API. Os do arquivo do operador não passam por aqui.
-- Só a REFERÊNCIA da credencial é gravada (FR-003); o valor mora no ambiente (AXON_MCP_SECRET_<REF>).
CREATE TABLE mcp.servers (
    owner           text,                 -- NULL = global; senão o subject do dono
    alias           text        NOT NULL,
    definition      jsonb       NOT NULL, -- o rascunho validado, formato 1 (registry_postgres.py)
    created_at      timestamptz NOT NULL,
    updated_at      timestamptz NOT NULL
);

-- FR-015: alias global único entre os globais; de usuário, único por dono.
CREATE UNIQUE INDEX servers_global_alias ON mcp.servers (alias) WHERE owner IS NULL;
CREATE UNIQUE INDEX servers_user_alias ON mcp.servers (owner, alias) WHERE owner IS NOT NULL;
