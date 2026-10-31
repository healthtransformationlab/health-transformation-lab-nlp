"""The data-quality results as one JSON file for the website's static page (#399).

    python scripts/50_dq_site.py           # write docs/site/data-quality.json
    python scripts/50_dq_site.py --check   # exit 1 if it is stale

Read from committed results, nothing is re-run:
- the checks, overall and per clinic (spec 005 US4; data/datasets/data_quality/);
- how often each method's calls go backwards over time;
- how many planted charting errors the checks catch;
- how messy the default synthetic Open Dental extract is (`open_dental.realism_profile`, spec 029 US6).

No server, no API: the page fetches this file. Synthetic data only, and the file says so.
"""

from __future__ import annotations

import pandas as pd

from . import open_dental
from .paths import DATASETS_DIR, REPO_ROOT
from .telemetry import traced

OUT = REPO_ROOT / "docs" / "site" / "data-quality.json"
DQ = DATASETS_DIR / "data_quality"
CHECKS = {
    "conformance:probing_depth_range": "Pocket depths in a possible range",
    "conformance:cal_range": "Attachment loss in a possible range",
    "conformance:bop_range": "Bleeding share between 0 and 100%",
    "conformance:rbl_range": "X-ray bone loss between 0 and 100%",
    "conformance:teeth_lost_range": "Teeth lost between 0 and 32",
    "conformance:visit_not_future": "No visit dated in the future",
    "completeness:notes": "Visit has a clinical note",
    "completeness:exam_form": "Visit has an exam form",
    "completeness:proc_dx_completed": "Visit has a diagnosis code",
    "completeness:probing_chart": "Visit has a gum chart",
    "plausibility:age_range": "Age in a possible range",
    "plausibility:temporal_cal_drop": "Attachment loss never shrinks",
    "plausibility:temporal_rbl_drop": "X-ray bone loss never shrinks",
    "plausibility:temporal_teeth_regained": "Lost teeth never come back",
    "plausibility:temporal_perio_resolved": "Periodontitis never goes away",
    "plausibility:temporal_stage_drop": "Stage never goes down",
}
PARTS = {"notes": "Clinical note", "exam_form": "Exam form", "proc_dx_planned": "Diagnosis codes",
         "probing_chart": "Gum chart (probing)"}
METHODS = {"probing_chart": "Gum chart alone", "algorithm_v0": "Rules, gum measurements first",
           "exam_form": "Exam form alone", "proc_dx_completed": "Diagnosis codes alone",
           "notes": "Clinical note (keyword rules)", "algorithm_design": "Rules, exam form first"}
MESS = {"charted_visit_office_share": "Office visits with a perio chart",
        "charted_visit_site_share": "Mobile and nursing-home visits with a perio chart",
        "partial_chart_share": "Charts covering only some teeth",
        "buccal_only_chart_share": "Charts with cheek-side readings only",
        "no_margin_chart_share": "Charts without gum-margin readings (no attachment loss)",
        "no_bleeding_chart_share": "Charts without bleeding",
        "copied_chart_share": "Charts copied from the last visit",
        "uniform_chart_share": "Charts with one depth everywhere",
        "out_of_range_site_share": "Pocket readings over 15 mm",
        "charted_after_loss_chart_share": "Charts that include an extracted tooth",
        "radiograph_visit_share": "Visits with an X-ray",
        "unread_tooth_share": "Teeth on an X-ray with no bone-loss reading"}


def _pct(x: float, d: int = 1):
    return None if pd.isna(x) else round(100 * float(x), d)


@traced
def flag_outliers(values: pd.Series, k: float = 2.0) -> pd.Series:
    """True where a clinic is more than k standard deviations from the mean of all clinics."""
    sd = values.std(ddof=1)
    return (values - values.mean()).abs() > k * sd if sd and not pd.isna(sd) else values * 0 != 0


@traced
def build() -> dict:
    """The page's data."""
    overall = pd.read_csv(DQ / "dq_overall.csv")
    clinic = pd.read_csv(DQ / "dq_by_clinic.csv")
    comp = pd.read_csv(DQ / "completeness_columns.csv")
    temporal = pd.read_csv(DQ / "temporal_by_method.csv")
    injected = pd.read_csv(DQ / "injected_error_recall.csv").iloc[0]
    visits = pd.read_csv(DATASETS_DIR / "visits_structured.csv", usecols=["visit_id", "person_id"])

    checks = [{"check": r.check, "label": CHECKS.get(r.check, r.check), "category": r.category,
               "n_checked": int(r.n_checked), "n_fail": int(r.n_fail),
               "fail_pct": round(100 * r.n_fail / r.n_checked, 1), "status": r.status}
              for r in overall.itertuples()]
    by_clinic = []
    for check, g in clinic[clinic["category"] == "completeness"].groupby("check", sort=False):
        miss = 100 * g["n_fail"] / g["n_checked"]
        for (_, r), m, out in zip(g.iterrows(), miss, flag_outliers(miss)):
            by_clinic.append({"check": check, "label": CHECKS.get(check, check), "clinic": str(r["clinic_id"]),
                              "n_checked": int(r["n_checked"]), "missing_pct": round(float(m), 1),
                              "is_outlier": bool(out)})
    tables, _, readings = open_dental.build_with_readings(open_dental.Params(), seed=42)
    prof = open_dental.realism_profile(tables, readings)
    return {
        "title": "Data quality of a synthetic dental record",
        "is_synthetic": True,
        "note": ("Synthetic data: every record was generated, with mistakes added on purpose. The numbers show what "
                 "the checks find, not how good any real practice's records are."),
        "sources": ["data/datasets/data_quality/", "data/datasets/visits_structured.csv",
                    "open_dental.realism_profile (seed 42, default settings)"],
        "visit_count": len(visits), "patient_count": int(visits["person_id"].nunique()),
        "checks": checks,
        "completeness": [{"part": r.column, "label": PARTS[r.column], "n_rows": int(r.n_rows),
                          "missing_pct": round(float(r.pct_missing), 1)}
                         for r in comp.itertuples() if r.column in PARTS],
        "by_clinic": by_clinic,
        "temporal": [{"method": r.method, "label": METHODS.get(r.method, r.method), "n_later_visits": int(r.n_later_visits),
                      "perio_resolved_pct": _pct(r.perio_resolved), "stage_drop_pct": _pct(r.stage_drop)}
                     for r in temporal.itertuples()],
        "injected": {"injected_count": int(injected["injected_errors"]),
                     "caught_count": round(float(injected["caught_share"]) * int(injected["injected_errors"])),
                     "caught_pct": _pct(injected["caught_share"]),
                     "false_flag_pct": _pct(injected["flag_rate_without_error"], 2)},
        "open_dental": [{"metric": r.metric_name, "label": MESS.get(r.metric_name, r.metric_name),
                         "pct": _pct(r.value_ratio), "numerator": int(r.numerator_count),
                         "denominator": int(r.denominator_count)} for r in prof.itertuples()],
    }
