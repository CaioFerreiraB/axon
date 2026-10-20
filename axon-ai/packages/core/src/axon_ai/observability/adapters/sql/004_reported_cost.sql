-- Custo informado pelo provider em cada chamada (ADR-035). Nulo quando o provider não informa — inclusive nas linhas
-- de antes desta migração: essas continuam pela tabela de preços.
ALTER TABLE observability.model_calls ADD COLUMN reported_cost_usd numeric;
