# World Population dataset -- reference ETL implementation

Companion code for the analytics data model doc. Loads the six sample
files into the target model (one fact table, uniform `dims` JSON map,
no per-dimension columns) and runs the four canonical query patterns.

## Files

- `data/*.csv` -- synthetic sample data (31 countries, 2010-2024):
  `population_by_country_year.csv`, `country_region.csv` (reference),
  `birth_death_rates.csv`, `food_habits.csv`, `travel.csv` (all country-year
  grain), and `individuals.csv` (person grain -- finer than the rest).
- `scripts/generate_sample_data.py` -- regenerates the CSVs (seeded, so output is reproducible).
- `scripts/schema.sql` -- the target model's DDL (SQLite here; same shapes carry over to
  Postgres/JSONB or a columnar warehouse -- swap `TEXT` for `JSONB` and generated-column
  syntax as needed).
- `scripts/etl.py` -- loads all six files into `data/analytics.db`. `individuals.csv`
  is pre-aggregated into sufficient statistics (n, sum, sum_square, min, max) per
  (country, gender) *before* it reaches the fact table -- the "grain mismatch" handling
  from the doc, not one fact row per person.
- `scripts/demo_queries.py` -- runs aggregation, variance, trend and 2D-pivot queries
  against the loaded data to prove the model works end to end.

## Run it

```
python3 scripts/generate_sample_data.py   # (re)generate the CSVs
python3 scripts/etl.py                    # build data/analytics.db from them
python3 scripts/demo_queries.py           # run the four query patterns
```

## Where to look for each idea from the doc

- **Uniform dims, no per-dimension columns**: `fact_observation.dims` in `schema.sql`,
  built as `dims_json({...})` in `etl.py` -- Population rows carry Country *and*
  Continent keys (denormalized on purpose); the individuals rollup carries Country
  and Gender.
- **Conformed dimensions**: `country_region.csv` seeds `dimension_member` once; every
  other file's rows resolve to the *same* Country member_key, which is what lets you
  join population against birth rate against food habits by country+year.
- **Grain mismatch**: `etl.py`'s individuals-loading block -- groups person rows by
  (country, gender), computes sufficient statistics, and only those rollup rows reach
  `fact_observation`.
- **Sufficient statistics / variance**: `demo_queries.py` query 2 and the bonus query
  compute variance straight from `sum_value`/`sum_square`/`n`, no stored variance column.
