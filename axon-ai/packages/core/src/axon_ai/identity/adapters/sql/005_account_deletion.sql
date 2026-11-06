-- Apagar conta em cascata (spec 012 US9, ADR-058; research R28): a conta "em apagamento" guarda o pseudônimo que
-- substitui as citações dela nos registros que ficam (ADR-059). Nulo nas contas que não estão sendo apagadas; a linha
-- some quando o apagamento conclui, e o nome e o e-mail ficam livres.
ALTER TABLE identity.accounts
    ADD COLUMN deletion_pseudonym text
    CHECK (deletion_pseudonym ~ '^deleted:[0-9a-f]{16}$');
