"""
Runs the same four query patterns from the design doc (aggregation,
variance, trend, 2D pivot) against the SQLite database the ETL built,
to prove the pipeline produces a usable target model.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "analytics.db")


def show(title, cur, rows):
    print(f"\n=== {title} ===")
    cols = [d[0] for d in cur.description]
    print(" | ".join(cols))
    for r in rows:
        print(" | ".join(str(x) for x in r))


def main():
    con = sqlite3.connect(DB_PATH)
    con.create_function("json_extract_num", 2, lambda j, path: __import__("json").loads(j).get(path))

    # ---------------------------------------------------------------- 1) Aggregation
    # SUM population by continent, 2020
    q = """
        SELECT dm.display_value AS continent, SUM(f.sum_value) AS population
        FROM fact_observation f
        JOIN dimension_member dm ON dm.member_key = json_extract(f.dims, '$."2"')
        WHERE f.dataset_id = 1 AND f.measure_id = 1 AND f.time_id = 2020
        GROUP BY dm.display_value
        ORDER BY population DESC
    """
    cur = con.execute(q)
    show("1) Aggregation: population by continent, 2020", cur, cur.fetchall())

    # ---------------------------------------------------------------- 2) Variance
    # Variance of Birth Rate across countries, within each continent, 2020
    q = """
        SELECT dm.display_value AS continent,
               SUM(f.sum_square)/SUM(f.n) - POWER(SUM(f.sum_value)/SUM(f.n), 2) AS birth_rate_variance,
               COUNT(*) AS n_countries
        FROM fact_observation f
        JOIN dimension_member country ON country.member_key = json_extract(f.dims, '$."1"')
        JOIN dimension_member dm ON dm.member_key = country.parent_member_key
        WHERE f.dataset_id = 1 AND f.measure_id = 2 AND f.time_id = 2020
        GROUP BY dm.display_value
        ORDER BY birth_rate_variance DESC
    """
    cur = con.execute(q)
    show("2) Variance: birth rate variance across countries, by continent, 2020", cur, cur.fetchall())

    # ---------------------------------------------------------------- 3) Trend
    # Population YoY % change, USA, last 5 years on record
    q = """
        SELECT f.time_id AS year, f.sum_value AS population,
               ROUND(100.0 * (f.sum_value - LAG(f.sum_value) OVER (ORDER BY f.time_id))
                     / LAG(f.sum_value) OVER (ORDER BY f.time_id), 3) AS yoy_pct
        FROM fact_observation f
        JOIN dimension_member dm ON dm.member_key = json_extract(f.dims, '$."1"')
        WHERE f.dataset_id = 1 AND f.measure_id = 1 AND dm.natural_key = 'USA'
        ORDER BY f.time_id
    """
    cur = con.execute(q)
    rows = cur.fetchall()
    show("3) Trend: USA population YoY %", cur, rows[-6:])

    # ---------------------------------------------------------------- 4) 2D pivot
    # Population by continent over time (pivoted for a chart)
    q = """
        SELECT f.time_id AS year,
               SUM(CASE WHEN dm.display_value = 'Asia' THEN f.sum_value END) AS asia,
               SUM(CASE WHEN dm.display_value = 'Europe' THEN f.sum_value END) AS europe,
               SUM(CASE WHEN dm.display_value = 'Africa' THEN f.sum_value END) AS africa,
               SUM(CASE WHEN dm.display_value = 'North America' THEN f.sum_value END) AS north_america
        FROM fact_observation f
        JOIN dimension_member dm ON dm.member_key = json_extract(f.dims, '$."2"')
        WHERE f.dataset_id = 1 AND f.measure_id = 1
        GROUP BY f.time_id
        ORDER BY f.time_id
    """
    cur = con.execute(q)
    show("4) 2D pivot: population by continent over years", cur, cur.fetchall())

    # ---------------------------------------------------------------- bonus: grain-mismatch data
    # Variance of sampled birth years, by country x gender (from individuals.csv rollup)
    q = """
        SELECT country.display_value AS country, gender.display_value AS gender,
               f.n AS sample_size,
               ROUND(f.sum_value / f.n, 1) AS avg_birth_year,
               ROUND(f.sum_square/f.n - POWER(f.sum_value/f.n, 2), 1) AS birth_year_variance
        FROM fact_observation f
        JOIN dimension_member country ON country.member_key = json_extract(f.dims, '$."1"')
        JOIN dimension_member gender ON gender.member_key = json_extract(f.dims, '$."3"')
        WHERE f.dataset_id = 1 AND f.measure_id = 8
        ORDER BY country.display_value, gender.display_value
        LIMIT 8
    """
    cur = con.execute(q)
    show("bonus) individuals.csv rolled up (grain mismatch handled at ETL time)", cur, cur.fetchall())

    con.close()


if __name__ == "__main__":
    main()
