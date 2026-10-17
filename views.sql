-- Analytics layer built on top of indicators_long.

DROP VIEW IF EXISTS kenya_yearly;
CREATE VIEW kenya_yearly AS
SELECT
    year,
    MAX(CASE WHEN indicator_name = 'population'            THEN value END) AS population,
    MAX(CASE WHEN indicator_name = 'gdp_usd'               THEN value END) AS gdp_usd,
    MAX(CASE WHEN indicator_name = 'unemployment_pct'      THEN value END) AS unemployment_pct,
    MAX(CASE WHEN indicator_name = 'primary_enrolment_pct' THEN value END) AS primary_enrolment_pct
FROM indicators_long
GROUP BY year;

DROP VIEW IF EXISTS kenya_growth;
CREATE VIEW kenya_growth AS
SELECT
    year,
    population,
    gdp_usd,
    gdp_usd / population AS gdp_per_capita_usd,
    ROUND(100.0 * (population - LAG(population) OVER (ORDER BY year))
          / LAG(population) OVER (ORDER BY year), 2) AS population_growth_pct,
    ROUND(100.0 * (gdp_usd - LAG(gdp_usd) OVER (ORDER BY year))
          / LAG(gdp_usd) OVER (ORDER BY year), 2) AS gdp_growth_pct
FROM kenya_yearly
WHERE population IS NOT NULL AND gdp_usd IS NOT NULL;
