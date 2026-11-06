-- Escopos da chave de API (spec 003 US14, ADR-057; research R50): conjunto fechado e não vazio. Anulável aqui: o passo
-- de preenchimento do `migrate` (postgres_schema.py) precisa do grupo de administração, que é configuração, dá a cada
-- chave existente `{inference}` — e `{inference, admin}` às do grupo — e então torna a coluna `NOT NULL`.
ALTER TABLE assistants.api_keys
    ADD COLUMN scopes text[]
    CHECK (scopes <@ '{inference,users,admin}'::text[] AND cardinality(scopes) > 0);
