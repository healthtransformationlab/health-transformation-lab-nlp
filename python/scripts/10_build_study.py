"""Build the training set, the chart-review set (Label Studio tasks) and the answer key.

    python scripts/10_build_study.py                       # 1200 people, 240 review charts, adults from 2021-04-01
    python scripts/10_build_study.py --n-people 600 --review-n 120
    python scripts/10_build_study.py --deid-engine presidio   # needs presidio + Python <= 3.12
    python scripts/10_build_study.py --min-age 40 --start-date 2021-07-01   # which visits count (spec 032 US2)
    python scripts/10_build_study.py --all-visits          # every visit, as the build was before #467

The note set holds adults' visits from 2021-04-01 by default (spec 032 US8 defaults, preset repo_v2; #467), and
draws smoking and diabetes at published US shares (spec 033 US3, #486). Every number is SYNTHETIC.
"""

import argparse
import json

from health_transformation_lab_nlp.paths import DATASETS_DIR, RAW_DIR
from health_transformation_lab_nlp.study import ANALYSIS_MIN_AGE, ANALYSIS_START_DATE, build_study

ap = argparse.ArgumentParser()
ap.add_argument("--n-people", type=int, default=1200)
ap.add_argument("--review-n", type=int, default=240)
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--deid-engine", default="regex", choices=["regex", "presidio"])
ap.add_argument("--min-age", type=int, default=ANALYSIS_MIN_AGE,
                help=f"leave out visits of people younger (default: {ANALYSIS_MIN_AGE})")
ap.add_argument("--start-date", default=ANALYSIS_START_DATE,
                help=f"ISO date: leave out visits before it (default: {ANALYSIS_START_DATE})")
ap.add_argument("--all-visits", action="store_true", help="keep every visit (no age or date filter)")
a = ap.parse_args()
min_age, start_date = (None, None) if a.all_visits else (a.min_age, a.start_date)
summary = build_study(DATASETS_DIR, RAW_DIR, a.n_people, a.review_n, a.seed, a.deid_engine, min_age, start_date)
(DATASETS_DIR / "build_summary.json").write_text(json.dumps(summary, indent=1, default=str))
print(json.dumps(summary, indent=1, default=str))
if summary["blocked_by_leak_gate"]:
    print(f"WARNING: {summary['blocked_by_leak_gate']} notes held back by the leak gate; see deid_report.csv")
