"""Load the synthetic OMOP tables into a database: Postgres / Lakebase, or Databricks SQL.

    pip install -e ".[db]"
    python scripts/05_load_omop_db.py --url "$DENTAL_DB_URL" --schema cdm

Lakebase is managed Postgres, so the Postgres path is the Lakebase path. A
Lakebase URL looks like
    postgresql://<user>:<oauth token>@<instance host>:5432/databricks_postgres?sslmode=require
(token from `databricks database generate-database-credential`, valid about an
hour). The large analytical copy belongs in Delta via Databricks SQL; Lakebase
suits dev/test and the operational tables (docs/results_storage.md).

DDL: OHDSI CommonDataModel v5.4.2 Postgres DDL (omop/ddl/postgresql/, Apache-2.0)
plus the dental extension (omop/ddl/dental_extension.sql). Primary keys and
indices are applied; foreign-key constraints are not, because they need the
full Athena vocabulary loaded first.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .paths import REPO_ROOT
from .telemetry import traced

DDL_DIR = REPO_ROOT / "omop" / "ddl"
PG_DDL = ["OMOPCDM_postgresql_5.4_ddl.sql", "OMOPCDM_postgresql_5.4_primary_keys.sql",
          "OMOPCDM_postgresql_5.4_indices.sql"]
EHR = 32817                 # Type concept: EHR
UTF8, ENGLISH = 32678, 4180186

# Required (NOT NULL) CDM 5.4 columns our build doesn't produce, with values for synthetic data.
# 0 = "No matching concept", the OMOP convention when nothing maps.
_DEFAULTS = {
    "person": {"race_concept_id": 0, "ethnicity_concept_id": 0},
    "visit_occurrence": {"visit_type_concept_id": EHR},
    "measurement": {"measurement_type_concept_id": EHR},
    "note": {"note_class_concept_id": 0, "encoding_concept_id": UTF8, "language_concept_id": ENGLISH},
}


@traced
def conform(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Add the required CDM columns that are missing."""
    out = {}
    for name, df in tables.items():
        df = df.copy()
        for col, val in _DEFAULTS.get(name, {}).items():
            if col not in df:
                df[col] = val
        if name == "visit_occurrence" and "visit_end_date" not in df:
            df["visit_end_date"] = df["visit_start_date"]
        out[name] = df
    return out


def _statements(sql: str, schema: str) -> list[str]:
    """The statements in a SQL file, `@cdmDatabaseSchema` filled in. Splits on `;` only outside single-quoted strings
    (with `''` escapes), double-quoted identifiers and comments, and drops `--` and `/* */` comments outside quotes,
    so a comment or literal that holds `--` or `;` stays whole (#624)."""
    sql = sql.replace("@cdmDatabaseSchema", schema)
    out, cur, i, n = [], [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch in "'\"":                                     # a literal or quoted identifier, to its closing quote
            j = i + 1
            while j < n:
                if sql[j] == ch:
                    if j + 1 < n and sql[j + 1] == ch:      # a doubled quote is an escaped one
                        j += 2
                        continue
                    break
                j += 1
            cur.append(sql[i:j + 1])
            i = j + 1
        elif sql.startswith("--", i):                      # a line comment: drop it, keep the line break
            j = sql.find("\n", i)
            i = n if j < 0 else j
        elif sql.startswith("/*", i):                      # a block comment
            j = sql.find("*/", i + 2)
            i = n if j < 0 else j + 2
        elif ch == ";":
            out.append("".join(cur))
            cur = []
            i += 1
        else:
            cur.append(ch)
            i += 1
    out.append("".join(cur))
    return [s.strip() for s in out if s.strip()]


@traced
def create_schema(engine, schema: str) -> None:
    from sqlalchemy import text
    with engine.begin() as c:
        c.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema}"))
        for f in PG_DDL:
            for s in _statements((DDL_DIR / "postgresql" / f).read_text(), schema):
                c.execute(text(s))
        c.execute(text(f"SET search_path TO {schema}"))
        for s in _statements((DDL_DIR / "dental_extension.sql").read_text(), schema):
            c.execute(text(s))


@traced
def local_concepts() -> pd.DataFrame:
    c = pd.read_csv(REPO_ROOT / "omop" / "vocab" / "local_concepts.csv", dtype={"standard_concept": "object"})
    for d in ("valid_start_date", "valid_end_date"):
        c[d] = pd.to_datetime(c[d]).dt.date
    return c


@traced
def load_omop(engine, omop_dir: Path, schema: str) -> dict[str, int]:
    """Create the CDM + dental extension in `schema` and load the synthetic tables."""
    create_schema(engine, schema)
    tables = conform({t: pd.read_parquet(Path(omop_dir) / f"{t}.parquet")
                      for t in ("person", "visit_occurrence", "measurement", "note")})
    tables["concept"] = local_concepts()
    counts = {}
    for name in ("concept", "person", "visit_occurrence", "measurement", "note"):
        df = tables[name]
        df.to_sql(name, engine, schema=schema, if_exists="append", index=False, method="multi", chunksize=2000)
        counts[name] = len(df)
    return counts


@traced
def perio_chart_from_db(engine, schema: str) -> pd.DataFrame:
    return pd.read_sql(f"SELECT * FROM {schema}.perio_chart", engine)
