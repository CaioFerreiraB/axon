-- Seção `auth` nas sobreposições de Assistants de sistema (spec 003 US13, ADR-040; research R41): a restrição da 003,
-- anônima, recebe do Postgres o nome `system_overrides_section_check`; é trocada pela que aceita `auth`.
ALTER TABLE assistants.system_overrides DROP CONSTRAINT system_overrides_section_check;
ALTER TABLE assistants.system_overrides
    ADD CONSTRAINT system_overrides_section_check CHECK (section IN ('models', 'mcp', 'auth'));
