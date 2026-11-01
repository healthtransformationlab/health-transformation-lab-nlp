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

Per-field accuracy (US6, #132): `field_accuracy` scores one reader run against this table, one row per field
with n, correct, accuracy and a 95% Wilson interval. `status` is the rung's answer (`pred`, after falling back to
note_rules), so it equals the run's headline accuracy. `grade` and `extent` are scored only on visits whose
reference is periodontitis, and only from answers that passed the gate: note_rules reads neither, so a fallback
row has no grade or extent and counts as wrong. r/R/17_spec004.R is the R twin; the parity test checks they agree.

Synthetic data only: the truth is the generator's, not a clinician's.
"""

from __future__ import annotations

import math

import pandas as pd

from .telemetry import traced

Z95 = 1.959963984540054
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


@traced
def wilson_ci(k: int, n: int, z: float = Z95) -> tuple[float | None, float | None]:
    """95% Wilson score interval for k of n; (None, None) when n is 0."""
    if n == 0:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


@traced
def field_accuracy(details: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Accuracy per reader field for one run (an llm_details file) against the reference answers."""
    ref = reference.set_index("visit_id")
    det = details.set_index("visit_id")
    missing = ref.index.difference(det.index)
    if len(missing):
        raise ValueError(f"{len(missing)} of {len(ref)} reference visits have no answer in this run "
                         "(a --limit run?); score complete runs only")
    det = det.reindex(ref.index)
    gate = det["gate_ok"].astype(str).str.lower().eq("true")
    perio = _applies(ref["status"])
    rows = []
    for f in FIELDS:
        if f == "status":
            pred, mask = det["pred"], pd.Series(True, index=ref.index)
        else:
            pred, mask = det[f].where(gate), perio
        ok = (pred.astype(object).where(pred.notna(), None) == ref[f].astype(object))[mask]
        n, k = int(mask.sum()), int(ok.sum())
        lo, hi = wilson_ci(k, n)
        rows.append({"field": f, "n": n, "correct": k, "accuracy": k / n if n else None, "ci_lo": lo, "ci_hi": hi})
    return pd.DataFrame(rows)


@traced
def field_metrics(table: pd.DataFrame) -> dict:
    """MLflow metrics for one run's field_accuracy table: field_accuracy_<field> and field_n_<field>."""
    t = table.set_index("field")
    return ({f"field_accuracy_{f}": t.loc[f, "accuracy"] for f in t.index}
            | {f"field_n_{f}": int(t.loc[f, "n"]) for f in t.index})
