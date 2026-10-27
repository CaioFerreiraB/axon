-- Spec 004, ADR-044 (research R13): id, tipo e tamanho das imagens do resultado — nunca os bytes.
ALTER TABLE capabilities.audit ADD COLUMN attachments jsonb NOT NULL DEFAULT '[]'::jsonb;
