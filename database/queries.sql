-- Named, reusable queries. Run with: database.run_named("<name>", **params)  or  python -m src.database query <name>
-- Format: "-- name:" starts a query, "-- params:" gives default bind parameters.

-- name: country_comparison
-- params: year=2025 fuel=Petrol
SELECT country, region, income_group, avg_price, effective_tax_burden_pct, subsidy_to_price_pct, avg_affordability_pct
FROM vw_country_year_fuel
WHERE year = :year AND fuel_type = :fuel
ORDER BY avg_price DESC;

-- name: regional_averages
-- params: fuel=Diesel
SELECT region, year, n_countries, avg_price, avg_tax_burden_pct, avg_subsidy_to_price_pct, avg_affordability_pct
FROM vw_region_year_fuel
WHERE fuel_type = :fuel
ORDER BY region, year;

-- name: tax_burden_top
-- params: year=2025 fuel=Petrol limit=10
SELECT country, region, avg_price, avg_tax_rate_pct, effective_tax_burden_pct
FROM vw_country_year_fuel
WHERE year = :year AND fuel_type = :fuel
ORDER BY effective_tax_burden_pct DESC
LIMIT :limit;

-- name: subsidy_effect
-- params: year=2025 fuel=Diesel
-- Compares subsidised (>= 10% of retail price) and unsubsidised countries. Association only, not causation.
SELECT CASE WHEN subsidy_to_price_pct >= 10 THEN 'Subsidised (>=10% of price)' ELSE 'Little/no subsidy' END AS group_label,
       COUNT(*) AS n_countries,
       AVG(avg_price) AS avg_price,
       AVG(avg_affordability_pct) AS avg_affordability_pct,
       AVG(gdp_per_capita_usd) AS avg_gdp_per_capita
FROM vw_country_year_fuel
WHERE year = :year AND fuel_type = :fuel
GROUP BY CASE WHEN subsidy_to_price_pct >= 10 THEN 'Subsidised (>=10% of price)' ELSE 'Little/no subsidy' END;

-- name: yoy_changes
-- params: year=2022 fuel=Petrol limit=10
SELECT country, region, avg_price, prev_avg_price, yoy_change_usd, yoy_change_pct
FROM vw_yoy_country_fuel
WHERE year = :year AND fuel_type = :fuel AND prev_avg_price IS NOT NULL
ORDER BY yoy_change_pct DESC
LIMIT :limit;

-- name: volatility_ranking
-- params: fuel=Petrol limit=10
SELECT country, region, n_months, avg_price, std_price, cv_pct
FROM vw_volatility_country_fuel
WHERE fuel_type = :fuel
ORDER BY cv_pct DESC
LIMIT :limit;

-- name: regional_rank
-- params: region=Europe_&_Central_Asia year=2025 fuel=Petrol
SELECT country, avg_price, rank_in_region, rank_global
FROM vw_region_rank_country_year
WHERE region = :region AND year = :year AND fuel_type = :fuel
ORDER BY rank_in_region;

-- name: median_price_by_region
-- params: year=2025 fuel=Petrol
-- Median via window functions (SQLite and PostgreSQL both lack a portable MEDIAN aggregate).
SELECT region, AVG(avg_price) AS median_price
FROM (SELECT region, avg_price,
             ROW_NUMBER() OVER (PARTITION BY region ORDER BY avg_price) AS rn,
             COUNT(*) OVER (PARTITION BY region) AS cnt
      FROM vw_country_year_fuel
      WHERE year = :year AND fuel_type = :fuel) t
WHERE rn IN ((cnt + 1) / 2, (cnt + 2) / 2)
GROUP BY region
ORDER BY region;

-- name: validation_duplicates
-- Natural-key duplicates in the fact table (expected: 0).
SELECT COUNT(*) AS violations
FROM (SELECT country_id, date_id, fuel_id FROM fact_fuel_price GROUP BY country_id, date_id, fuel_id HAVING COUNT(*) > 1) d;

-- name: validation_nulls
-- Null values in required fact columns (expected: 0).
SELECT COUNT(*) AS violations FROM fact_fuel_price
WHERE price_usd_per_litre IS NULL OR tax_usd_per_litre IS NULL OR tax_rate_pct IS NULL
   OR subsidy_usd_per_litre IS NULL OR affordability_pct_daily_income IS NULL;

-- name: validation_ranges
-- Out-of-range values (expected: 0).
SELECT COUNT(*) AS violations FROM fact_fuel_price
WHERE price_usd_per_litre <= 0 OR tax_usd_per_litre < 0 OR tax_rate_pct < 0 OR tax_rate_pct > 500
   OR subsidy_usd_per_litre < 0 OR tax_usd_per_litre >= price_usd_per_litre;

-- name: validation_orphans
-- Fact rows without a dimension or economy match (expected: 0).
SELECT COUNT(*) AS violations FROM fact_fuel_price f
LEFT JOIN dim_country c ON c.country_id = f.country_id
LEFT JOIN dim_date d ON d.date_id = f.date_id
LEFT JOIN dim_fuel fu ON fu.fuel_id = f.fuel_id
LEFT JOIN fact_economy e ON e.country_id = f.country_id AND e.year = d.year
WHERE c.country_id IS NULL OR d.date_id IS NULL OR fu.fuel_id IS NULL OR e.country_id IS NULL;

-- name: db_row_counts
SELECT 'dim_country' AS table_name, COUNT(*) AS n_rows FROM dim_country
UNION ALL SELECT 'dim_date', COUNT(*) FROM dim_date
UNION ALL SELECT 'dim_fuel', COUNT(*) FROM dim_fuel
UNION ALL SELECT 'fact_economy', COUNT(*) FROM fact_economy
UNION ALL SELECT 'fact_fuel_price', COUNT(*) FROM fact_fuel_price;
