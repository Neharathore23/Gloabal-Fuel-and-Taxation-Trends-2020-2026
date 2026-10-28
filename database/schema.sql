-- Star schema (SQLite default; written to be PostgreSQL-compatible).
-- Grain of fact_fuel_price : one row per country x month x fuel type.
-- Grain of fact_economy    : one row per country x year (kept separate: different grain).

DROP VIEW IF EXISTS vw_region_rank_country_year;
DROP VIEW IF EXISTS vw_volatility_country_fuel;
DROP VIEW IF EXISTS vw_yoy_country_fuel;
DROP VIEW IF EXISTS vw_region_year_fuel;
DROP VIEW IF EXISTS vw_country_year_fuel;
DROP VIEW IF EXISTS vw_fuel_price_detail;
DROP TABLE IF EXISTS fact_fuel_price;
DROP TABLE IF EXISTS fact_economy;
DROP TABLE IF EXISTS dim_fuel;
DROP TABLE IF EXISTS dim_date;
DROP TABLE IF EXISTS dim_country;
DROP TABLE IF EXISTS etl_run;

CREATE TABLE dim_country (
    country_id     INTEGER PRIMARY KEY,
    country_code   VARCHAR(3)  NOT NULL UNIQUE,
    country_name   VARCHAR(80) NOT NULL,
    region         VARCHAR(40) NOT NULL,
    income_group   VARCHAR(20) NOT NULL CHECK (income_group IN ('Low', 'Lower-middle', 'Upper-middle', 'High')),
    currency_local VARCHAR(3)
);

CREATE TABLE dim_date (
    date_id    INTEGER PRIMARY KEY,              -- YYYYMM
    full_date  DATE        NOT NULL UNIQUE,      -- first day of the month
    year       INTEGER     NOT NULL,
    quarter    INTEGER     NOT NULL CHECK (quarter BETWEEN 1 AND 4),
    month      INTEGER     NOT NULL CHECK (month BETWEEN 1 AND 12),
    month_name VARCHAR(10) NOT NULL
);

CREATE TABLE dim_fuel (
    fuel_id   INTEGER PRIMARY KEY,
    fuel_type VARCHAR(10) NOT NULL UNIQUE,
    unit      VARCHAR(40) NOT NULL
);

CREATE TABLE fact_economy (
    country_id         INTEGER NOT NULL REFERENCES dim_country (country_id),
    year               INTEGER NOT NULL,
    gdp_per_capita_usd NUMERIC NOT NULL CHECK (gdp_per_capita_usd > 0),
    PRIMARY KEY (country_id, year)
);

CREATE TABLE fact_fuel_price (
    record_id                      INTEGER PRIMARY KEY,
    country_id                     INTEGER NOT NULL REFERENCES dim_country (country_id),
    date_id                        INTEGER NOT NULL REFERENCES dim_date (date_id),
    fuel_id                        INTEGER NOT NULL REFERENCES dim_fuel (fuel_id),
    price_usd_per_litre            NUMERIC NOT NULL CHECK (price_usd_per_litre > 0),
    price_before_tax_usd           NUMERIC NOT NULL,
    tax_usd_per_litre              NUMERIC NOT NULL CHECK (tax_usd_per_litre >= 0),
    tax_rate_pct                   NUMERIC NOT NULL CHECK (tax_rate_pct >= 0 AND tax_rate_pct <= 500),
    tax_share_pct                  NUMERIC NOT NULL CHECK (tax_share_pct >= 0 AND tax_share_pct < 100),
    subsidy_usd_per_litre          NUMERIC NOT NULL CHECK (subsidy_usd_per_litre >= 0),
    subsidy_ratio_pct              NUMERIC NOT NULL CHECK (subsidy_ratio_pct >= 0),
    affordability_pct_daily_income NUMERIC NOT NULL CHECK (affordability_pct_daily_income > 0),
    dq_flags                       VARCHAR(200) NOT NULL DEFAULT '',
    is_imputed                     INTEGER NOT NULL DEFAULT 0 CHECK (is_imputed IN (0, 1)),
    UNIQUE (country_id, date_id, fuel_id)
);

CREATE INDEX ix_fact_date    ON fact_fuel_price (date_id);
CREATE INDEX ix_fact_fuel    ON fact_fuel_price (fuel_id);
CREATE INDEX ix_fact_country ON fact_fuel_price (country_id, fuel_id, date_id);
CREATE INDEX ix_country_region ON dim_country (region, income_group);

CREATE TABLE etl_run (
    run_id           INTEGER PRIMARY KEY,
    loaded_at        VARCHAR(40) NOT NULL,
    data_origin      VARCHAR(200),
    source_records   INTEGER,
    cleaned_records  INTEGER,
    inserted_records INTEGER NOT NULL
);
