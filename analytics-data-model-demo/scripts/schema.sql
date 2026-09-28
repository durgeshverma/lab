-- Target analytical data model, exactly as designed in the doc:
-- dataset-agnostic metadata layer + one fact table with a uniform JSONB-style
-- dimension map. SQLite here (json1 + generated columns, both built in since
-- SQLite 3.31 / 3.38) for a zero-install demo; the same shapes carry over to
-- Postgres (JSONB instead of TEXT-as-JSON) or a columnar warehouse unchanged.

PRAGMA foreign_keys = ON;

CREATE TABLE dataset (
  dataset_id          INTEGER PRIMARY KEY,
  dataset_name        TEXT NOT NULL,
  domain              TEXT,
  source_system       TEXT,
  default_time_grain  TEXT,
  description         TEXT
);

CREATE TABLE dimension (
  dimension_id    INTEGER PRIMARY KEY,   -- this id IS the key used inside fact_observation.dims
  dataset_id      INTEGER REFERENCES dataset,
  dimension_name  TEXT NOT NULL,
  data_type       TEXT,
  is_hierarchical INTEGER DEFAULT 0,
  UNIQUE (dataset_id, dimension_name)
);

CREATE TABLE dimension_member (
  member_key        INTEGER PRIMARY KEY,
  dimension_id      INTEGER REFERENCES dimension,
  natural_key       TEXT NOT NULL,
  display_value     TEXT,
  parent_member_key INTEGER REFERENCES dimension_member,
  attributes        TEXT,     -- JSON
  UNIQUE (dimension_id, natural_key)
);

CREATE TABLE measure (
  measure_id            INTEGER PRIMARY KEY,
  dataset_id            INTEGER REFERENCES dataset,
  measure_name          TEXT NOT NULL,
  unit                  TEXT,
  default_aggregation   TEXT NOT NULL,   -- SUM | AVG | LAST | MIN | MAX
  is_additive           INTEGER DEFAULT 1,
  UNIQUE (dataset_id, measure_name)
);

CREATE TABLE metric_definition (
  metric_id        INTEGER PRIMARY KEY,
  dataset_id       INTEGER REFERENCES dataset,
  metric_name      TEXT NOT NULL,
  base_measure_id  INTEGER REFERENCES measure,
  calculation_type TEXT NOT NULL  -- YOY | MOM | CAGR | MOVING_AVG | VARIANCE
);

CREATE TABLE time_dim (
  time_id  INTEGER PRIMARY KEY,   -- YYYY for year grain, YYYYMMDD for day grain
  date     TEXT NOT NULL,
  year     INTEGER,
  month    INTEGER,
  day      INTEGER,
  grain    TEXT NOT NULL
);

CREATE TABLE source_file (
  file_id      INTEGER PRIMARY KEY,
  dataset_id   INTEGER REFERENCES dataset,
  file_name    TEXT NOT NULL,
  grain        TEXT NOT NULL,
  description  TEXT
);

CREATE TABLE source_field_map (
  file_id        INTEGER REFERENCES source_file,
  source_column  TEXT NOT NULL,
  maps_to        TEXT NOT NULL,   -- dimension | measure | time | entity_key
  target_id      INTEGER,
  transform_rule TEXT
);

-- The fact table: one uniform "dims" map for every dimension, on every
-- dataset. No dedicated columns per dimension, no cap on how many exist.
CREATE TABLE fact_observation (
  dataset_id     INTEGER NOT NULL REFERENCES dataset,
  time_id        INTEGER NOT NULL REFERENCES time_dim,
  dims           TEXT NOT NULL DEFAULT '{}',   -- JSON: {"<dimension_id>": <member_key>, ...}
  dims_hash      TEXT,                          -- stable fingerprint of dims, computed by the loader (see etl.py)
  measure_id     INTEGER NOT NULL REFERENCES measure,
  n              INTEGER NOT NULL DEFAULT 1,
  sum_value      REAL,
  sum_square     REAL,
  min_value      REAL,
  max_value      REAL,
  last_value     REAL,
  source_file_id INTEGER REFERENCES source_file,
  PRIMARY KEY (dataset_id, time_id, dims_hash, measure_id)
);

CREATE INDEX idx_fact_dataset_time ON fact_observation(dataset_id, time_id);
-- Optional, added later per hot dimension -- never a table/column change:
-- CREATE INDEX idx_fact_dims_1 ON fact_observation(json_extract(dims, '$."1"'));
