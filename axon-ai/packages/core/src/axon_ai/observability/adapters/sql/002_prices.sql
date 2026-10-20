-- Tabela de preços com vigência (spec 009 US5, research R31): USD por milhão de tokens. O custo é calculado na
-- consulta, então um preço lançado depois corrige o histórico.
CREATE TABLE observability.prices (
    provider            text            NOT NULL,
    model               text            NOT NULL,
    effective_from      date            NOT NULL,
    usd_per_mtok_in     numeric(12, 6)  NOT NULL CHECK (usd_per_mtok_in >= 0),
    usd_per_mtok_out    numeric(12, 6)  NOT NULL CHECK (usd_per_mtok_out >= 0),
    created_by          text            NOT NULL,
    created_at          timestamptz     NOT NULL,
    PRIMARY KEY (provider, model, effective_from)
);
