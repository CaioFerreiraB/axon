-- Impacto ambiental de cada chamada de modelo, estimado pelo EcoLogits no esvaziamento do destino de uso (spec 009
-- US9, ADR-056; research R47). Mínimo e máximo de energia (kWh), GWP (kgCO2eq), ADPe (kgSbeq), PE (MJ) e água (L), e
-- de GWP, ADPe e PE por fase (uso e fabricação), com o modelo da base usado, o casamento, a zona e a versão.
-- `impact_match` nulo = nunca tentada; `none` = tentada, sem par na base. Mesma retenção das linhas de uso.
ALTER TABLE observability.model_calls
    ADD COLUMN impact_model      text,
    ADD COLUMN impact_match      text CHECK (impact_match IN ('exact', 'approximate', 'none')),
    ADD COLUMN impact_zone       text,
    ADD COLUMN ecologits_version text,
    ADD COLUMN impact_warnings   text[],
    ADD COLUMN energy_kwh_min       double precision,
    ADD COLUMN energy_kwh_max       double precision,
    ADD COLUMN gwp_kgco2eq_min      double precision,
    ADD COLUMN gwp_kgco2eq_max      double precision,
    ADD COLUMN adpe_kgsbeq_min      double precision,
    ADD COLUMN adpe_kgsbeq_max      double precision,
    ADD COLUMN pe_mj_min            double precision,
    ADD COLUMN pe_mj_max            double precision,
    ADD COLUMN wcf_l_min            double precision,
    ADD COLUMN wcf_l_max            double precision,
    ADD COLUMN gwp_usage_min        double precision,
    ADD COLUMN gwp_usage_max        double precision,
    ADD COLUMN gwp_embodied_min     double precision,
    ADD COLUMN gwp_embodied_max     double precision,
    ADD COLUMN adpe_usage_min       double precision,
    ADD COLUMN adpe_usage_max       double precision,
    ADD COLUMN adpe_embodied_min    double precision,
    ADD COLUMN adpe_embodied_max    double precision,
    ADD COLUMN pe_usage_min         double precision,
    ADD COLUMN pe_usage_max         double precision,
    ADD COLUMN pe_embodied_min      double precision,
    ADD COLUMN pe_embodied_max      double precision;

-- O preenchimento (`axon usage impact-backfill`) só procura as elegíveis nunca tentadas.
CREATE INDEX model_calls_unestimated ON observability.model_calls (id)
    WHERE impact_match IS NULL AND NOT failed AND output_tokens > 0;
