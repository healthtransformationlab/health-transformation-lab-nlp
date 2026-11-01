"""Record-mismatch rules on every synthetic visit, scored against the generator's truth (spec 026, US2).

    python scripts/45_case_profiles.py

Each rule asks whether the recorded code fits the rest of the record (case_profile.py). Writes
data/datasets/case_profiles/: record_mismatch.csv (one row per visit and failed rule) and mismatch_rule_score.csv
(each rule, and any rule, overall and per clinic). Scores are over the visits a rule can check. A mismatch is a
record to recheck, usually a coding or charting gap. Synthetic data only. The case profiles themselves are built
when Load results runs (grader_tables), not written here.
"""

import pandas as pd

from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.case_profile import check_rules, record_mismatches, score_rules
from health_transformation_lab_nlp.paths import DATASETS_DIR

telemetry.setup()
telemetry.start_script("45_case_profiles", data_label="synthetic")
v = pd.read_csv(DATASETS_DIR / "visits_structured.csv")
truth = pd.read_csv(DATASETS_DIR / "answer_key" / "visits_truth.csv")
out = DATASETS_DIR / "case_profiles"
out.mkdir(exist_ok=True)

checks = check_rules(v)
scores = score_rules(checks, v, truth)
injected = truth.set_index("visit_id").record_error.fillna("").astype(str) != ""
failed = record_mismatches(checks, v, truth)
failed.to_csv(out / "record_mismatch.csv", index=False)
scores.to_csv(out / "mismatch_rule_score.csv", index=False)

temporal = pd.read_csv(DATASETS_DIR / "data_quality" / "injected_error_recall.csv").iloc[0]
overall = scores[scores.clinic == "All"].drop(columns=["rule_label", "clinic"])
print("SYNTHETIC records, scored against the generator's truth, over the visits each rule can check:")
print(overall.round(3).to_string(index=False))
a = overall.set_index("rule").loc["any_rule"]
print(f"\ninjected charting errors: the rules catch {int(a.injected_caught_count)} of the {int(a.injected_checkable_count)} "
      f"with a recorded code ({int(injected.sum())} injected in all); the temporal checks catch "
      f"{temporal.caught_share:.0%} of all {int(temporal.injected_errors)}")
