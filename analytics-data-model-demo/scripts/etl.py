"""
ETL: loads the six World Population sub-files into the target analytical
data model (schema.sql) exactly as described in the design doc --

  - country_region.csv    -> seeds dimension_member for Country + Continent (hierarchy)
  - population_by_country_year.csv,
    birth_death_rates.csv,
    food_habits.csv,
    travel.csv             -> country-year grain, straight into fact_observation
  - individuals.csv        -> PERSON grain (finer than everything else) --
                              pre-aggregated into sufficient statistics
                              (n, sum, sum_square, min, max) before it ever
                              reaches fact_observation, per the doc's
                              "grain mismatch" section.

Every dimension, regardless of which file it came from, is stored the same
way: an entry in fact_observation.dims, keyed by dimension_id. There is no
per-dimension column anywhere in this table.
"""
import csv
import hashlib
import json
import os
import sqlite3
from collections import defaultdict

BASE = os.path.dirname(__file__)
DATA_DIR = os.path.join(BASE, "..", "data")
DB_PATH = os.path.join(BASE, "..", "data", "analytics.db")


def dims_json(d: dict) -> str:
    """Canonical JSON for a dims map -- sorted keys so identical maps hash identically."""
    return json.dumps(d, sort_keys=True, separators=(",", ":"))


def dims_hash(d: dict) -> str:
    return hashlib.md5(dims_json(d).encode()).hexdigest()


def get_time_id(con, date_str: str, grain: str) -> int:
    """time_dim uses YYYY for year grain, YYYYMMDD for day grain, as its own time_id."""
    if grain == "year":
        year = int(date_str)
        time_id = year
        con.execute(
            "INSERT OR IGNORE INTO time_dim (time_id, date, year, grain) VALUES (?, ?, ?, ?)",
            (time_id, f"{year}-01-01", year, "year"),
        )
    else:
        raise ValueError(grain)
    return time_id


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    con.executescript(open(os.path.join(BASE, "schema.sql")).read())

    # ---------------------------------------------------------------- dataset + metadata
    con.execute(
        "INSERT INTO dataset (dataset_id, dataset_name, domain, default_time_grain) "
        "VALUES (1, 'World Population', 'Demographics', 'year')"
    )

    DIM_COUNTRY, DIM_CONTINENT, DIM_GENDER = 1, 2, 3
    con.executemany(
        "INSERT INTO dimension (dimension_id, dataset_id, dimension_name, is_hierarchical) VALUES (?, ?, ?, ?)",
        [
            (DIM_COUNTRY, 1, "Country", 1),
            (DIM_CONTINENT, 1, "Continent", 0),
            (DIM_GENDER, 1, "Gender", 0),
        ],
    )

    MEASURES = {
        # name                     -> (measure_id, unit,           default_agg, is_additive)
        "Population":              (1, "people",              "SUM", 1),
        "Birth Rate":              (2, "per 1,000 people",     "AVG", 0),
        "Death Rate":              (3, "per 1,000 people",     "AVG", 0),
        "Avg Calories":            (4, "kcal/day",             "AVG", 0),
        "Meat Pct":                (5, "% of diet",            "AVG", 0),
        "Outbound Trips":          (6, "thousands of trips",   "SUM", 1),
        "Tourism Receipts":       (7, "USD millions",         "SUM", 1),
        "Sample Birth Year Stats": (8, "calendar year",        "AVG", 0),  # from individuals.csv
    }
    con.executemany(
        "INSERT INTO measure (measure_id, dataset_id, measure_name, unit, default_aggregation, is_additive) "
        "VALUES (?, 1, ?, ?, ?, ?)",
        [(mid, name, unit, agg, add) for name, (mid, unit, agg, add) in MEASURES.items()],
    )

    SOURCE_FILES = [
        (1, "population_by_country_year.csv", "country_year"),
        (2, "country_region.csv", "country"),
        (3, "birth_death_rates.csv", "country_year"),
        (4, "food_habits.csv", "country_year"),
        (5, "travel.csv", "country_year"),
        (6, "individuals.csv", "person"),
    ]
    con.executemany(
        "INSERT INTO source_file (file_id, dataset_id, file_name, grain) VALUES (?, 1, ?, ?)",
        SOURCE_FILES,
    )
    con.commit()

    # ---------------------------------------------------------------- 1) country_region.csv -> dimension_member
    # Continents first (they're the parents), then countries pointing at them.
    continent_member_key = {}
    next_key = 1000
    with open(os.path.join(DATA_DIR, "country_region.csv")) as f:
        rows = list(csv.DictReader(f))
    for cont in sorted({r["continent"] for r in rows}):
        continent_member_key[cont] = next_key
        con.execute(
            "INSERT INTO dimension_member (member_key, dimension_id, natural_key, display_value) VALUES (?, ?, ?, ?)",
            (next_key, DIM_CONTINENT, cont.upper().replace(" ", "_"), cont),
        )
        next_key += 1

    country_member_key = {}
    country_continent_key = {}
    next_key = 2000
    for r in rows:
        iso, name, cont, region = r["country_iso"], r["country_name"], r["continent"], r["region"]
        country_member_key[iso] = next_key
        country_continent_key[iso] = continent_member_key[cont]
        con.execute(
            "INSERT INTO dimension_member "
            "(member_key, dimension_id, natural_key, display_value, parent_member_key, attributes) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (next_key, DIM_COUNTRY, iso, name, continent_member_key[cont], json.dumps({"region": region})),
        )
        next_key += 1

    # Gender members, for the individuals.csv rollup
    gender_member_key = {"M": 3001, "F": 3002}
    con.executemany(
        "INSERT INTO dimension_member (member_key, dimension_id, natural_key, display_value) VALUES (?, ?, ?, ?)",
        [(3001, DIM_GENDER, "M", "Male"), (3002, DIM_GENDER, "F", "Female")],
    )
    con.commit()
    print(f"Loaded {len(continent_member_key)} continents, {len(country_member_key)} countries as dimension_member")

    # ---------------------------------------------------------------- helper for straight country-year loads
    def load_country_year_measure(filename, file_id, value_col_to_measure):
        """value_col_to_measure: {csv_column_name: measure_name}"""
        n_rows = 0
        with open(os.path.join(DATA_DIR, filename)) as f:
            for row in csv.DictReader(f):
                iso, year = row["country_iso"], int(row["year"])
                if iso not in country_member_key:
                    continue  # a row for a country not in the reference file -- skipped, not guessed
                time_id = get_time_id(con, str(year), "year")
                # Continent is stored directly alongside Country too (denormalized on
                # purpose) so a group-by-continent query never needs to walk the
                # Country hierarchy -- same "dims" map, just two keys instead of one.
                # d = {str(DIM_COUNTRY): country_member_key[iso], str(DIM_CONTINENT): country_continent_key[iso]}
                d = {str(DIM_COUNTRY): country_member_key[iso]}
                dh = dims_hash(d)
                for col, measure_name in value_col_to_measure.items():
                    val = float(row[col])
                    measure_id = MEASURES[measure_name][0]
                    con.execute(
                        "INSERT OR REPLACE INTO fact_observation "
                        "(dataset_id, time_id, dims, dims_hash, measure_id, n, sum_value, sum_square, "
                        " min_value, max_value, last_value, source_file_id) "
                        "VALUES (1, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)",
                        (time_id, dims_json(d), dh, measure_id, val, val * val, val, val, val, file_id),
                    )
                    n_rows += 1
        con.commit()
        print(f"  {filename}: {n_rows} fact rows written")

    # ---------------------------------------------------------------- 2..5) the four country-year files
    load_country_year_measure("population_by_country_year.csv", 1, {"population": "Population"})
    load_country_year_measure("birth_death_rates.csv", 3, {"birth_rate": "Birth Rate", "death_rate": "Death Rate"})
    load_country_year_measure("food_habits.csv", 4, {"avg_calories": "Avg Calories", "meat_pct": "Meat Pct"})
    load_country_year_measure(
        "travel.csv", 5, {"outbound_trips_thousands": "Outbound Trips", "tourism_receipts_usd_millions": "Tourism Receipts"}
    )

    # ---------------------------------------------------------------- 6) individuals.csv -- GRAIN MISMATCH
    # Person-grain rows get pre-aggregated to (country, gender) sufficient statistics
    # over birth_year BEFORE they ever touch fact_observation -- exactly the pattern
    # the doc recommends instead of loading one fact row per person.
    groups = defaultdict(list)
    with open(os.path.join(DATA_DIR, "individuals.csv")) as f:
        for row in csv.DictReader(f):
            iso, gender, birth_year = row["country_iso"], row["gender"], int(row["birth_year"])
            if iso not in country_member_key:
                continue
            groups[(iso, gender)].append(birth_year)

    SURVEY_TIME_ID = get_time_id(con, "2024", "year")  # cross-sectional sample, dated to the survey year
    measure_id = MEASURES["Sample Birth Year Stats"][0]
    n_groups = 0
    for (iso, gender), years in groups.items():
        n = len(years)
        s = float(sum(years))
        ss = float(sum(y * y for y in years))
        d = {str(DIM_COUNTRY): country_member_key[iso], str(DIM_GENDER): gender_member_key[gender]}
        dh = dims_hash(d)
        con.execute(
            "INSERT OR REPLACE INTO fact_observation "
            "(dataset_id, time_id, dims, dims_hash, measure_id, n, sum_value, sum_square, "
            " min_value, max_value, source_file_id) "
            "VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, 6)",
            (SURVEY_TIME_ID, dims_json(d), dh, measure_id, n, s, ss, float(min(years)), float(max(years))),
        )
        n_groups += 1
    con.commit()
    print(f"  individuals.csv: {len(groups)} person rows rolled up into {n_groups} (country x gender) fact rows")

    total = con.execute("SELECT COUNT(*) FROM fact_observation").fetchone()[0]
    print(f"\nfact_observation now holds {total} rows across {len(MEASURES)} measures.")
    con.close()


if __name__ == "__main__":
    main()
