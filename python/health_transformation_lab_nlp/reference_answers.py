"""Reference answers for the note reader's fields (spec 004 US5, #130).

MedGemma's reader (`llm_reader.parse_answer`) returns three fields per note: `status` (healthy, gingivitis,
periodontitis stage I-IV), `grade` (A/B/C) and `extent` (localized/generalized/molar_incisor), plus a verbatim
quote that the gate checks against the note. To score each field we need the correct answer for it on every
review visit. The synthetic study already has it: the generator decides each visit's status, grade and extent
before writing the note (`study.build_study`, seed 42), and writes them to `answer_key/review_key.csv`. That is
option 1 of #130 (structured truth, no manual review).

The reference follows the generator's truth, not the note: when the note's stated status differs from the truth
(a copied-forward or miscoded record, injected on purpose), the reference keeps the truth and
`note_stated_status` shows what the note says, so a reader error can be told apart from a record mismatch.

Grade and extent apply only to periodontitis; elsewhere the reference is "NA", the reader's own value for
"not applicable". The reader returns no pocket depths, bleeding or attachment levels, so the table has no
columns for them (the generator records them per visit, but there is nothing to score them against).

Synthetic data only: the truth is the generator's, not a clinician's.
"""

from __future__ import annotations

import pandas as pd

from .telemetry import traced

FIELDS = ("status", "grade", "extent")
NA = "NA"
SOURCE = ("generator truth: answer_key/review_key.csv from 10_build_study.py (seed 42); "
          "synthetic, not a clinician's reading")


def _applies(status: pd.Series) -> pd.Series:
    return status.astype(str).str.startswith("periodontitis")


@traced
def reference_answers(key: pd.DataFrame) -> pd.DataFrame:
    """One row per review visit, one column per reader field, from the answer key's truth columns."""
    perio = _applies(key["truth_status"])

    def field(col: str) -> pd.Series:
        return key[col].where(perio & key[col].notna(), NA).astype(str)

    out = pd.DataFrame({
        "visit_id": key["visit_id"].astype(int),
        "status": key["truth_status"].astype(str),
        "grade": field("truth_grade"),
        "extent": field("truth_extent"),
        "note_stated_status": key["stated_status"].astype(str),
        "source": SOURCE,
    })
    return out.sort_values("visit_id").reset_index(drop=True)
