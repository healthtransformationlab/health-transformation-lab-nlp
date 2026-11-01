"""Completeness after the NIH Collaboratory data-quality framework (Zozus et al. 2014; spec 013 G7).

    data element   are the tables and columns the source system defines in the extract?
                   (compare the extract with the vendor's published schema)
    column value   share of missing values in each column a phenotype needs
                   ('unknown', '' and null count as missing)
    row value      share of rows with every input a calculation needs (the chart algorithm needs
                   CAL, BOP, PD and teeth lost on the same charted visit)

Ascertainment completeness (people missing from the extract) is not computed: it needs the source
population. Results are reported on three scales, as the framework asks for accuracy to be judged
as close to the truth as possible: all visits, complete cases (every evidence type present), and
the reviewed reference set.
"""

from __future__ import annotations

import pandas as pd

from .sources import UNKNOWN
from .telemetry import traced

CHART_INPUTS = ["rec_max_cal_mm", "rec_bop_pct", "rec_max_probing_depth_mm", "rec_teeth_lost_perio"]
SCALES = ["all_visits", "complete_cases", "reference_set"]
PERIO = ["periodontitis_stage_1", "periodontitis_stage_2", "periodontitis_stage_3", "periodontitis_stage_4"]


def _missing(s: pd.Series) -> pd.Series:
    return s.isna() | s.astype(str).isin([UNKNOWN, ""])


@traced
def element_completeness(expected: dict[str, list[str]], actual: dict[str, list[str]]) -> pd.DataFrame:
    """expected / actual: table -> columns. One row per expected column, present True/False."""
    rows = [{"table": t, "column": c, "present": c in actual.get(t, [])}
            for t, cols in expected.items() for c in cols]
    return pd.DataFrame(rows, columns=["table", "column", "present"])


@traced
def column_completeness(v: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame([{"column": c, "n_rows": len(v), "n_missing": int(_missing(v[c]).sum()),
                          "pct_missing": 100.0 * float(_missing(v[c]).mean()) if len(v) else float("nan")}
                         for c in columns])


@traced
def row_completeness(v: pd.DataFrame, inputs: list[str], where: str = "charted") -> dict:
    """Among rows where `where` is true (visits with a chart), the share with every input present."""
    rows = v[v[where].astype(bool)] if where else v
    ok = ~pd.concat([_missing(rows[c]) for c in inputs], axis=1).any(axis=1)
    n = len(rows)
    return {"n_rows": n, "n_complete": int(ok.sum()), "pct_complete": 100.0 * ok.sum() / n if n else float("nan")}


@traced
def complete_cases(v: pd.DataFrame) -> pd.DataFrame:
    """Visits where every evidence type can be compared: an exam-form status, a treatment plan
    (planned procedure codes, with or without a diagnosis), a complete probing chart and a note."""
    chart_ok = v["charted"].astype(bool) & ~pd.concat([_missing(v[c]) for c in CHART_INPUTS], axis=1).any(axis=1)
    keep = ~_missing(v["exam_form"]) & ~_missing(v["proc_codes_planned"]) & chart_ok & ~_missing(v["notes"])
    return v[keep]


@traced
def prevalence_by_scale(v: pd.DataFrame, status_col: str) -> pd.DataFrame:
    """Visit-level share with periodontitis and with stage III-IV on each scale (known calls only)."""
    scales = {"all_visits": v, "complete_cases": complete_cases(v), "reference_set": v[v["in_review"].astype(bool)]}
    rows = []
    for name in SCALES:
        s = scales[name][status_col]
        known = s[~_missing(s)]
        n = len(known)
        rows.append({"scale": name, "status_col": status_col, "n_visits": len(s), "n_known": n,
                     "periodontitis": float(known.isin(PERIO).mean()) if n else float("nan"),
                     "stage3_4": float(known.isin(PERIO[2:]).mean()) if n else float("nan")})
    return pd.DataFrame(rows)


@traced
def section_completeness(v: pd.DataFrame, sections: dict[str, list[str]], merged: str, decided_by: str) -> pd.DataFrame:
    """Completeness per section before merging, and of the merged result, as Patel et al. 2022 Fig. 1 reports it
    (spec 024 FR-005). sections: name -> columns read in order (a value in any counts). One row per section, then
    'merged': n_visits, n_with_value / pct_with_value (before merging), n_decided / pct_decided (the visits that
    section decides once merged)."""
    n = len(v)

    def pct(k):
        return 100.0 * k / n if n else float("nan")

    rows = []
    for name, cols in sections.items():
        has = ~pd.concat([_missing(v[c]) for c in cols], axis=1).all(axis=1)
        k, d = int(has.sum()), int((v[decided_by] == name).sum())
        rows.append({"section": name, "n_visits": n, "n_with_value": k, "pct_with_value": pct(k),
                     "n_decided": d, "pct_decided": pct(d)})
    k = int((~_missing(v[merged])).sum())
    rows.append({"section": "merged", "n_visits": n, "n_with_value": k, "pct_with_value": pct(k),
                 "n_decided": k, "pct_decided": pct(k)})
    return pd.DataFrame(rows)
