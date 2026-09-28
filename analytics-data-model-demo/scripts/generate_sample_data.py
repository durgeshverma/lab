"""
Generates synthetic-but-plausible sample data for the World Population
dataset's sub-files, as described in the analytics data model doc:

  population_by_country_year.csv   country x year
  country_region.csv               country reference (continent/region, static)
  birth_death_rates.csv            country x year
  food_habits.csv                  country x year
  travel.csv                       country x year
  individuals.csv                  person-grain sample (finer grain than the rest)

Numbers are seeded and roughly realistic in shape (growth curves, regional
patterns) but are NOT official statistics -- this is fixture data for
building and testing the ETL pipeline, not for analysis.
"""
import csv
import random
import os

random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
os.makedirs(OUT_DIR, exist_ok=True)

YEARS = list(range(2010, 2025))  # 15 years

# country_iso, country_name, continent, region, base_population_2010(millions), annual_growth_pct
COUNTRIES = [
    ("USA", "United States", "North America", "Northern America", 309.3, 0.6),
    ("CAN", "Canada", "North America", "Northern America", 34.0, 0.9),
    ("MEX", "Mexico", "North America", "Central America", 117.3, 1.2),
    ("BRA", "Brazil", "South America", "South America", 195.7, 0.8),
    ("ARG", "Argentina", "South America", "South America", 41.2, 1.0),
    ("COL", "Colombia", "South America", "South America", 45.5, 1.1),
    ("GBR", "United Kingdom", "Europe", "Northern Europe", 62.8, 0.6),
    ("DEU", "Germany", "Europe", "Western Europe", 81.8, 0.1),
    ("FRA", "France", "Europe", "Western Europe", 64.6, 0.4),
    ("ITA", "Italy", "Europe", "Southern Europe", 59.2, 0.1),
    ("ESP", "Spain", "Europe", "Southern Europe", 46.6, 0.2),
    ("POL", "Poland", "Europe", "Eastern Europe", 38.0, -0.1),
    ("SWE", "Sweden", "Europe", "Northern Europe", 9.4, 0.7),
    ("CHN", "China", "Asia", "Eastern Asia", 1337.7, 0.4),
    ("IND", "India", "Asia", "Southern Asia", 1234.3, 1.3),
    ("JPN", "Japan", "Asia", "Eastern Asia", 128.1, -0.2),
    ("KOR", "South Korea", "Asia", "Eastern Asia", 49.6, 0.4),
    ("IDN", "Indonesia", "Asia", "South-Eastern Asia", 242.5, 1.1),
    ("PAK", "Pakistan", "Asia", "Southern Asia", 179.4, 2.0),
    ("BGD", "Bangladesh", "Asia", "Southern Asia", 148.4, 1.1),
    ("VNM", "Vietnam", "Asia", "South-Eastern Asia", 87.4, 1.0),
    ("THA", "Thailand", "Asia", "South-Eastern Asia", 67.1, 0.4),
    ("PHL", "Philippines", "Asia", "South-Eastern Asia", 93.3, 1.6),
    ("NGA", "Nigeria", "Africa", "Western Africa", 160.9, 2.6),
    ("EGY", "Egypt", "Africa", "Northern Africa", 84.5, 2.0),
    ("ZAF", "South Africa", "Africa", "Southern Africa", 51.2, 1.3),
    ("KEN", "Kenya", "Africa", "Eastern Africa", 41.5, 2.5),
    ("ETH", "Ethiopia", "Africa", "Eastern Africa", 87.6, 2.7),
    ("DZA", "Algeria", "Africa", "Northern Africa", 36.0, 1.9),
    ("AUS", "Australia", "Oceania", "Australia and New Zealand", 22.2, 1.4),
    ("NZL", "New Zealand", "Oceania", "Australia and New Zealand", 4.4, 1.0),
]

# ---------------------------------------------------------------- country_region.csv
with open(os.path.join(OUT_DIR, "country_region.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["country_iso", "country_name", "continent", "region"])
    for iso, name, cont, region, _, _ in COUNTRIES:
        w.writerow([iso, name, cont, region])

# ---------------------------------------------------------------- population_by_country_year.csv
pop_rows = []
pop_by_country_year = {}
for iso, name, cont, region, base_m, growth in COUNTRIES:
    pop = base_m * 1_000_000
    for year in YEARS:
        noise = random.uniform(-0.15, 0.15)  # +/- 0.15pp yearly wobble
        pop = pop * (1 + (growth + noise) / 100.0)
        pop_val = int(pop)
        pop_by_country_year[(iso, year)] = pop_val
        pop_rows.append([iso, year, pop_val])

with open(os.path.join(OUT_DIR, "population_by_country_year.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["country_iso", "year", "population"])
    w.writerows(pop_rows)

# ---------------------------------------------------------------- birth_death_rates.csv
# regional baseline birth/death rates per 1,000 population, with a mild downward
# birth-rate trend over time (a common real pattern) plus noise
REGION_RATES = {
    "North America": (13.0, 8.0), "South America": (16.0, 6.5),
    "Europe": (10.5, 10.5), "Asia": (16.0, 7.5), "Africa": (32.0, 8.0),
    "Oceania": (13.5, 6.5),
}
bd_rows = []
for iso, name, cont, region, _, _ in COUNTRIES:
    base_birth, base_death = REGION_RATES[cont]
    for i, year in enumerate(YEARS):
        birth = max(6.0, base_birth - i * 0.15 + random.uniform(-0.6, 0.6))
        death = max(4.0, base_death + random.uniform(-0.4, 0.4))
        bd_rows.append([iso, year, round(birth, 1), round(death, 1)])

with open(os.path.join(OUT_DIR, "birth_death_rates.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["country_iso", "year", "birth_rate", "death_rate"])
    w.writerows(bd_rows)

# ---------------------------------------------------------------- food_habits.csv
REGION_DIET = {
    "North America": (3600, 28.0), "South America": (3100, 20.0),
    "Europe": (3400, 22.0), "Asia": (2900, 12.0), "Africa": (2500, 8.0),
    "Oceania": (3300, 24.0),
}
food_rows = []
for iso, name, cont, region, _, _ in COUNTRIES:
    base_cal, base_meat = REGION_DIET[cont]
    for i, year in enumerate(YEARS):
        cal = base_cal + i * random.uniform(2, 8) + random.uniform(-40, 40)
        meat = max(3.0, base_meat + i * 0.1 + random.uniform(-1.5, 1.5))
        food_rows.append([iso, year, round(cal, 0), round(meat, 1)])

with open(os.path.join(OUT_DIR, "food_habits.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["country_iso", "year", "avg_calories", "meat_pct"])
    w.writerows(food_rows)

# ---------------------------------------------------------------- travel.csv
REGION_TRAVEL = {
    "North America": (25000, 900), "South America": (6000, 150),
    "Europe": (30000, 1200), "Asia": (12000, 400), "Africa": (2500, 80),
    "Oceania": (9000, 300),
}
travel_rows = []
for iso, name, cont, region, base_pop_m, _ in COUNTRIES:
    base_trips, base_receipts = REGION_TRAVEL[cont]
    scale = base_pop_m / 50.0  # bigger countries -> more absolute trips
    for i, year in enumerate(YEARS):
        dip = 0.35 if year in (2020, 2021) else 1.0  # pandemic-style dip, for realism
        trips = base_trips * scale * dip * (1 + i * 0.02) * random.uniform(0.9, 1.1)
        receipts = base_receipts * scale * dip * (1 + i * 0.03) * random.uniform(0.9, 1.1)
        travel_rows.append([iso, year, round(trips, 0), round(receipts, 1)])

with open(os.path.join(OUT_DIR, "travel.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["country_iso", "year", "outbound_trips_thousands", "tourism_receipts_usd_millions"])
    w.writerows(travel_rows)

# ---------------------------------------------------------------- individuals.csv
# Finer grain than everything else: one row per sampled person. This is what
# the doc's "grain mismatch" section talks about -- these get pre-aggregated
# by the ETL (count, sufficient stats) rather than loaded one row per person.
indiv_rows = []
person_id = 1
GENDERS = ["M", "F"]
for iso, name, cont, region, base_pop_m, _ in COUNTRIES:
    # sample size roughly proportional to country population (a small survey, not a census)
    n_people = max(40, int(base_pop_m * 1.2))
    for _ in range(n_people):
        birth_year = random.randint(1945, 2023)
        gender = random.choice(GENDERS)
        indiv_rows.append([person_id, iso, birth_year, gender])
        person_id += 1

with open(os.path.join(OUT_DIR, "individuals.csv"), "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["person_id", "country_iso", "birth_year", "gender"])
    w.writerows(indiv_rows)

print("Wrote files to", os.path.abspath(OUT_DIR))
for fn in ["country_region.csv", "population_by_country_year.csv", "birth_death_rates.csv",
           "food_habits.csv", "travel.csv", "individuals.csv"]:
    path = os.path.join(OUT_DIR, fn)
    with open(path) as f:
        n = sum(1 for _ in f) - 1
    print(f"  {fn}: {n} rows")
