-- Rotação do segredo de chaves de API (spec 003 US12, ADR-040; research R38): o instante da última rotação. O hash é
-- trocado no lugar, e o `key_id` não muda. Nulo nas chaves que nunca rotacionaram.
ALTER TABLE assistants.api_keys ADD COLUMN rotated_at timestamptz;
