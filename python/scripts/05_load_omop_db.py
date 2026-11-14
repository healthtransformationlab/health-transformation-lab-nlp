"""Load the synthetic OMOP CDM 5.4 tables + dental extension into Postgres / Lakebase.

    pip install -e ".[db]"
    python scripts/01_build_dataset.py
    python scripts/05_load_omop_db.py --url "postgresql+psycopg://user:token@host:5432/databricks_postgres?sslmode=require" --schema cdm_dev

Then `SELECT * FROM <schema>.perio_chart` gives one row per exam. Synthetic data only.
"""

import argparse
import os

import pandas as pd
from sqlalchemy import create_engine

from health_transformation_lab_nlp.db import load_omop, perio_chart_from_db
from health_transformation_lab_nlp.paths import REPO_ROOT
from health_transformation_lab_nlp import telemetry

telemetry.setup()
telemetry.start_script("05_load_omop_db", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--url", default=os.environ.get("DENTAL_DB_URL"), help="SQLAlchemy URL (or DENTAL_DB_URL)")
ap.add_argument("--schema", default="cdm_dev")
a = ap.parse_args()
if not a.url:
    raise SystemExit("set --url or DENTAL_DB_URL")
url = a.url.replace("postgresql://", "postgresql+psycopg://", 1) if a.url.startswith("postgresql://") else a.url
eng = create_engine(url)
counts = load_omop(eng, REPO_ROOT / "data" / "omop", a.schema)
print("loaded:", counts)
pc = perio_chart_from_db(eng, a.schema)
print(f"perio_chart view: {len(pc)} exams")
print(pd.DataFrame(pc).head(3).to_string(index=False))
