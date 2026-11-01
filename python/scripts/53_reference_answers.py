"""Reference answers for the note reader's fields, one row per review visit (spec 004 US5, #130).

    python scripts/53_reference_answers.py

Reads data/datasets/answer_key/review_key.csv (the generator's truth, written by 10_build_study.py with
seed 42) and writes data/datasets/answer_key/reference_answers.csv: visit_id, status, grade, extent (the
fields llm_reader.parse_answer returns), the note's stated status, and the source. Deterministic: rerunning
10_build_study.py with the same seed and then this script gives the same file.

It is in answer_key/, which reviewers must not open. Synthetic truth, not a clinician's reading.
"""

import pandas as pd

from health_transformation_lab_nlp.paths import DATASETS_DIR
from health_transformation_lab_nlp.reference_answers import FIELDS, reference_answers

key = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")
ref = reference_answers(key)
out = DATASETS_DIR / "answer_key" / "reference_answers.csv"
ref.to_csv(out, index=False)
print(f"wrote {out}: {len(ref)} visits, fields {', '.join(FIELDS)}")
for f in FIELDS:
    print(f"  {f}: " + ", ".join(f"{k} {v}" for k, v in ref[f].value_counts().sort_index().items()))
