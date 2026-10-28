-- Analytical views. Standard SQL (window functions); sqrt() is registered by src/database.py for old SQLite builds.
-- NOTE: the final year (2026) is partial (Jan-Oct); use n_months to judge comparability.

-- Flat, analysis-ready join of the star schema (also the Tableau-friendly source).
CREATE VIEW vw_fuel_price_detail AS
SELECT f.record_id,
       c.country_code,
       c.country_name AS country,
       c.region,
       c.income_group,
       c.currency_local,
       d.full_date AS date,
       d.year,
       d.quarter,
       d.month,
       fu.fuel_type,
       f.price_usd_per_litre,
       f.price_before_tax_usd,
       f.tax_usd_per_litre,
       f.tax_rate_pct,
       f.tax_share_pct,
       f.subsidy_usd_per_litre,
       f.subsidy_ratio_pct,
       e.gdp_per_capita_usd,
       f.affordability_pct_daily_income,
       f.dq_flags,
       f.is_imputed
FROM fact_fuel_price f
JOIN dim_country c  ON c.country_id = f.country_id
JOIN dim_date d     ON d.date_id = f.date_id
JOIN dim_fuel fu    ON fu.fuel_id = f.fuel_id
JOIN fact_economy e ON e.country_id = f.country_id AND e.year = d.year;

-- Country x year x fuel summary. effective_tax_burden_pct and subsidy_to_price_pct are price-weighted ratios.
CREATE VIEW vw_country_year_fuel AS
SELECT country_code, country, region, income_group, year, fuel_type,
       COUNT(*)                                  AS n_months,
       AVG(price_usd_per_litre)                  AS avg_price,
       MIN(price_usd_per_litre)                  AS min_price,
       MAX(price_usd_per_litre)                  AS max_price,
       AVG(tax_usd_per_litre)                    AS avg_tax_usd,
       AVG(tax_rate_pct)                         AS avg_tax_rate_pct,
       SUM(tax_usd_per_litre) * 100.0 / SUM(price_usd_per_litre)      AS effective_tax_burden_pct,
       AVG(subsidy_usd_per_litre)                AS avg_subsidy_usd,
       SUM(subsidy_usd_per_litre) * 100.0 / SUM(price_usd_per_litre)  AS subsidy_to_price_pct,
       AVG(affordability_pct_daily_income)       AS avg_affordability_pct,
       AVG(gdp_per_capita_usd)                   AS gdp_per_capita_usd
FROM vw_fuel_price_detail
GROUP BY country_code, country, region, income_group, year, fuel_type;

-- Region x year x fuel: simple mean of country-level means (each country weighted equally).
CREATE VIEW vw_region_year_fuel AS
SELECT region, year, fuel_type,
       COUNT(DISTINCT country_code)  AS n_countries,
       AVG(avg_price)                AS avg_price,
       MIN(avg_price)                AS min_country_price,
       MAX(avg_price)                AS max_country_price,
       AVG(effective_tax_burden_pct) AS avg_tax_burden_pct,
       AVG(subsidy_to_price_pct)     AS avg_subsidy_to_price_pct,
       AVG(avg_affordability_pct)    AS avg_affordability_pct
FROM vw_country_year_fuel
GROUP BY region, year, fuel_type;

-- Year-over-year change of the annual average price.
CREATE VIEW vw_yoy_country_fuel AS
SELECT t.*,
       avg_price - prev_avg_price AS yoy_change_usd,
       CASE WHEN prev_avg_price > 0 THEN (avg_price / prev_avg_price - 1) * 100 END AS yoy_change_pct
FROM (SELECT country_code, country, region, fuel_type, year, n_months, avg_price,
             LAG(avg_price) OVER (PARTITION BY country_code, fuel_type ORDER BY year) AS prev_avg_price
      FROM vw_country_year_fuel) t;

-- Volatility of the monthly price level (sample std dev and coefficient of variation) per country and fuel.
CREATE VIEW vw_volatility_country_fuel AS
SELECT country_code, country, region, fuel_type, n_months, avg_price,
       CASE WHEN var_price > 0 THEN sqrt(var_price) ELSE 0 END AS std_price,
       CASE WHEN var_price > 0 THEN sqrt(var_price) / avg_price * 100 ELSE 0 END AS cv_pct
FROM (SELECT country_code, country, region, fuel_type,
             COUNT(*) AS n_months,
             AVG(price_usd_per_litre) AS avg_price,
             (AVG(price_usd_per_litre * price_usd_per_litre) - AVG(price_usd_per_litre) * AVG(price_usd_per_litre))
               * COUNT(*) / (COUNT(*) - 1.0) AS var_price
      FROM vw_fuel_price_detail
      GROUP BY country_code, country, region, fuel_type
      HAVING COUNT(*) > 1) v;

-- Rank of each country's annual average price within its region and globally (1 = most expensive).
CREATE VIEW vw_region_rank_country_year AS
SELECT country_code, country, region, fuel_type, year, avg_price,
       RANK() OVER (PARTITION BY region, fuel_type, year ORDER BY avg_price DESC) AS rank_in_region,
       RANK() OVER (PARTITION BY fuel_type, year ORDER BY avg_price DESC)         AS rank_global
FROM vw_country_year_fuel;
