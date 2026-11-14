"""Write a SIMULATED lab grader run (spec 019 US3): every number is made up, so the Lab grader dashboard and Genie
space have rows before any real run. Real runs commit data/datasets/grader/grader_*.csv, which Load results then
uses instead.

    python scripts/43_simulated_grader.py [--seed 2026]
"""

import argparse

from health_transformation_lab_nlp import grader_tables, telemetry
from health_transformation_lab_nlp.paths import DATASETS_DIR

telemetry.setup()
telemetry.start_script("43_simulated_grader", data_label="simulated")

ap = argparse.ArgumentParser()
ap.add_argument("--seed", type=int, default=2026)
a = ap.parse_args()

out = DATASETS_DIR / "grader"
out.mkdir(exist_ok=True)
FILES = {"dim_grader_question": "simulated_grader_questions.csv", "fact_grader_answer": "simulated_grader_answers.csv"}
for name, df in grader_tables.simulate_grader(seed=a.seed).items():
    df.to_csv(out / FILES[name], index=False)
    print(f"SIMULATED, not a result: {out / FILES[name]} ({len(df)} rows)")
