"""Clinic-level periodontitis prevalence with confidence intervals (spec 005, US3).

Person-level: each person counts once, using their latest visit with a known
status. Reported per group (clinic) and overall: share with any periodontitis
and share with stage III-IV, each with a 95% Wilson score interval (better than
the normal approximation for small clinics and rare stages).

Published comparison: NHANES 2009-2014 (Eke et al. 2018, via NIDCR). Caveats,
which matter more than the numbers: NHANES used the CDC/AAP surveillance case
definitions, not 2017 staging, in a full-mouth exam of a national sample of
dentate adults 30+. A clinic population is not a national sample, and "severe"
(CDC/AAP) is not the same as stage III-IV.

r/R/06_validation.R has the R twin; the parity test checks they agree.
"""

from __future__ import annotations

import math

import pandas as pd

from .labels import GROUPINGS, LABELS, group_status
from .telemetry import traced

Z95 = 1.959963984540054
_PERIO = {"periodontitis_stage_1", "periodontitis_stage_2", "periodontitis_stage_3", "periodontitis_stage_4"}
_SEVERE = {"periodontitis_stage_3", "periodontitis_stage_4"}
_KNOWN = set(LABELS) | {"healthy_gingivitis"}

# NIDCR, "Periodontal Disease in Adults (Age 30 or Older)", from Eke PI et al., JADA 2018;149(7):576-588.
NHANES_2009_2014 = pd.DataFrame([
    {"group": "All adults 30+", "total_pct": 42.2, "nonsevere_pct": 34.4, "severe_pct": 7.8},
    {"group": "Ages 30-44", "total_pct": 29.5, "nonsevere_pct": 25.3, "severe_pct": 4.1},
    {"group": "Ages 45-64", "total_pct": 46.0, "nonsevere_pct": 35.6, "severe_pct": 10.4},
    {"group": "Ages 65+", "total_pct": 59.8, "nonsevere_pct": 50.7, "severe_pct": 9.0},
    {"group": "Current smokers", "total_pct": 62.4, "nonsevere_pct": 45.4, "severe_pct": 16.9},
    {"group": "Nonsmokers", "total_pct": 34.4, "nonsevere_pct": 29.5, "severe_pct": 4.9},
])


@traced
def wilson_ci(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


@traced
def latest_known(visits: pd.DataFrame, status_col: str) -> pd.DataFrame:
    v = visits.sort_values(["person_id", "visit_date"])
    known = v[v[status_col].isin(_KNOWN)]
    return known.groupby("person_id").tail(1)


@traced
def prevalence_by(visits: pd.DataFrame, status_col: str, by: str | None = None) -> pd.DataFrame:
    """visits: person_id, visit_date, <status_col>, and <by> if given."""
    people = visits.drop_duplicates("person_id")
    last = latest_known(visits, status_col)
    groups = [("all", people, last)] if by is None else [
        (g, people[people[by] == g], last[last[by] == g]) for g in sorted(people[by].unique())]
    rows = []
    for g, ppl, lk in groups:
        n = len(lk)
        k1 = int(lk[status_col].isin(_PERIO).sum())
        k2 = int(lk[status_col].isin(_SEVERE).sum())
        l1, h1 = wilson_ci(k1, n)
        l2, h2 = wilson_ci(k2, n)
        rows.append({by or "group": g, "n_people": n, "n_unknown": len(ppl) - n,
                     "periodontitis": k1 / n if n else float("nan"), "periodontitis_ci_low": l1,
                     "periodontitis_ci_high": h1, "stage3_4": k2 / n if n else float("nan"),
                     "stage3_4_ci_low": l2, "stage3_4_ci_high": h2})
    return pd.DataFrame(rows)


@traced
def prevalence_by_group(visits: pd.DataFrame, status_col: str, grouping: str = "six", by: str | None = None
                        ) -> pd.DataFrame:
    """Spec 032 US1: person-level share in each status group of `grouping` (labels.GROUPINGS), with a 95% Wilson
    interval; long format, one row per group (and per <by> value when given). Same people as prevalence_by: the
    latest visit with a known status. At `six`, a source that says only "healthy or gingivitis" counts as known but
    falls in neither group; `five` and `three` merge it."""
    groups = GROUPINGS[grouping]
    people = visits.drop_duplicates("person_id")
    last = latest_known(visits, status_col)
    grouped = last[status_col].map(lambda s: group_status(s, grouping))
    parts = [("all", people, grouped)] if by is None else [
        (g, people[people[by] == g], grouped[last[by] == g]) for g in sorted(people[by].unique())]
    rows = []
    for g, ppl, gs in parts:
        n = len(gs)
        for grp in groups:
            k = int((gs == grp).sum())
            lo, hi = wilson_ci(k, n)
            rows.append({by or "group": g, "grouping": grouping, "status_group": grp, "n_people": n,
                         "n_unknown": len(ppl) - n, "n_in_group": k, "share": k / n if n else float("nan"),
                         "share_ci_low": lo, "share_ci_high": hi})
    return pd.DataFrame(rows)
