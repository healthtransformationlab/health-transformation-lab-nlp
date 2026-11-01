"""Build the training set, the chart-review set (Label Studio tasks) and the answer key.

    python scripts/10_build_study.py                       # 1200 people, 240 review charts
    python scripts/10_build_study.py --n-people 600 --review-n 120
    python scripts/10_build_study.py --deid-engine presidio   # needs presidio + Python <= 3.12
    python scripts/10_build_study.py --min-age 18 --start-date 2021-03-01   # which visits count (spec 032 US2)
"""

import argparse
import json

from health_transformation_lab_nlp.paths import DATASETS_DIR, RAW_DIR
from health_transformation_lab_nlp.study import build_study

ap = argparse.ArgumentParser()
ap.add_argument("--n-people", type=int, default=1200)
ap.add_argument("--review-n", type=int, default=240)
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--deid-engine", default="regex", choices=["regex", "presidio"])
ap.add_argument("--min-age", type=int, default=None, help="leave out visits of people younger (default: none)")
ap.add_argument("--start-date", default=None, help="ISO date: leave out visits before it (default: every year)")
a = ap.parse_args()
summary = build_study(DATASETS_DIR, RAW_DIR, a.n_people, a.review_n, a.seed, a.deid_engine, a.min_age, a.start_date)
(DATASETS_DIR / "build_summary.json").write_text(json.dumps(summary, indent=1, default=str))
print(json.dumps(summary, indent=1, default=str))
if summary["blocked_by_leak_gate"]:
    print(f"WARNING: {summary['blocked_by_leak_gate']} notes held back by the leak gate; see deid_report.csv")
