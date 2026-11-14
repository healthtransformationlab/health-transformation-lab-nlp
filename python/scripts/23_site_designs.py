"""Compare three ways of storing site-level periodontal data in OMOP, on Postgres / Lakebase (spec 006).

    python scripts/23_site_designs.py --url "$DENTAL_DB_URL" [--n-visits 500]

Loads the same synthetic mouths (data/sites/, from 22_build_sites.py) into three
schemas (A post-coordinated SITE/SITE_EVENT, B pre-coordinated concepts, C site
columns), runs the same derived-measure query on each, checks every result
against Python's sites.derive(), and reports rows, storage, SQL size, joins and
query time. Writes data/sites/site_designs.csv.
"""

import argparse
import os

import pandas as pd
from sqlalchemy import create_engine, text

from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT
from health_transformation_lab_nlp.site_designs import (
    DESIGNS,
    load_design,
    run_derived,
    sql_stats,
    storage_bytes,
)

telemetry.setup()
telemetry.start_script("23_site_designs", data_label="synthetic")

ap = argparse.ArgumentParser()
ap.add_argument("--url", default=os.environ.get("DENTAL_DB_URL"))
ap.add_argument("--n-visits", type=int, default=500)
ap.add_argument("--keep", action="store_true", help="keep the schemas afterwards")
a = ap.parse_args()
if not a.url:
    raise SystemExit("set --url or DENTAL_DB_URL")
url = a.url.replace("postgresql://", "postgresql+psycopg://", 1) if a.url.startswith("postgresql://") else a.url

S = REPO_ROOT / "data" / "sites"
derived = pd.read_csv(S / "derived.csv")
keep = derived["visit_id"].head(a.n_visits)
sites = pd.read_parquet(S / "sites.parquet").query("visit_id in @keep")
teeth = pd.read_parquet(S / "teeth.parquet").query("visit_id in @keep")
teeth["missing_reason"] = teeth["missing_reason"].fillna("")
visits = pd.read_csv(DATASETS_DIR / "visits_structured.csv")[["visit_id", "person_id", "visit_date"]]
ref = derived[derived.visit_id.isin(keep)]

eng = create_engine(url)
rows = []
for design in DESIGNS:
    schema = f"site_design_{design[0]}"
    with eng.begin() as c:
        c.execute(text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
    n = load_design(eng, design, schema, sites, teeth, visits)
    got, secs = run_derived(eng, design, schema)
    m = ref.merge(got, on="visit_id", suffixes=("", "_db"))
    num = [c for c in got.columns if c not in ("visit_id", "cdc_aap_2012")]
    diff = max((m[c].astype(float) - m[f"{c}_db"].astype(float)).abs().max() for c in num)
    rows.append({"design": design, **n, "storage_mb": storage_bytes(eng, schema) / 1e6, **sql_stats(design),
                 "query_seconds": secs, "exams": len(got), "max_diff_vs_python": diff,
                 "cdc_mismatches": int((m["cdc_aap_2012"] != m["cdc_aap_2012_db"]).sum())})
    if not a.keep:
        with eng.begin() as c:
            c.execute(text(f"DROP SCHEMA {schema} CASCADE"))
t = pd.DataFrame(rows)
t.to_csv(S / "site_designs.csv", index=False)
print(f"SYNTHETIC: {len(ref)} exams, {len(sites):,} site rows, on {eng.dialect.name}")
print(t.round(3).to_string(index=False))
