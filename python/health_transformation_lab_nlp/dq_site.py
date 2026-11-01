"""The EHR DQ grader's data as one JSON file for the website's static page (#399, #401).

    python scripts/50_dq_site.py           # write docs/site/data-quality.json
    python scripts/50_dq_site.py --check   # exit 1 if it is stale

The grader (spec 019, `dashboards.dq_grader`) is organized by data-quality domain: completeness, accuracy and
consistency (Zozus), temporal plausibility (Kahn) and reliability (de Vet). This file has one section per grader
dataset, built from the same tables the grader reads (`grader_tables.dq_tables`), with the same definitions as its
SQL (`dashboards.DQ_SQL`), so the page and the dashboard show the same numbers. A last section adds how messy the
default synthetic Open Dental extract is (`open_dental.realism_profile`, spec 029 US6).

No server, no API: the page fetches this file. Synthetic data only, and the file says so.
"""

from __future__ import annotations

import pandas as pd

from . import grader_tables, open_dental
from .completeness import complete_cases
from .paths import DATASETS_DIR, REPO_ROOT
from .telemetry import traced

OUT = REPO_ROOT / "docs" / "site" / "data-quality.json"
SOURCES = {"exam_form": "Exam form", "proc_dx_completed": "Diagnosis codes, done",
           "proc_dx_planned": "Diagnosis codes, planned", "notes": "Chart note", "probing_chart": "Gum measurements",
           "algorithm_v0": "Rules, measurements first", "algorithm_design": "Rules, exam form first"}
METHODS = {**SOURCES, "truth_status": "Truth (synthetic)", "proc_codes_completed": "Procedure codes, done",
           "proc_codes_planned": "Procedure codes, planned", "radiograph_ai": "X-ray AI reading"}
STATUS = {"healthy_gingivitis": "Healthy or gingivitis", "periodontitis_stage_1": "Stage I",
          "periodontitis_stage_2": "Stage II", "periodontitis_stage_3": "Stage III",
          "periodontitis_stage_4": "Stage IV"}
COLUMNS = {"algorithm_design": "Rules, exam form first", "notes": "Chart note", "exam_form": "Exam form",
           "proc_dx_planned": "Diagnosis codes, planned", "probing_chart": "Gum measurements",
           "rec_max_cal_mm": "Attachment loss", "rec_bop_pct": "Bleeding", "rec_max_probing_depth_mm": "Pocket depth",
           "rec_teeth_lost_perio": "Teeth lost to gum disease"}
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


def _pct(x, d: int = 1):
    return None if pd.isna(x) else round(100 * float(x), d)


@traced
def flag_outliers(values: pd.Series, k: float = 2.0) -> pd.Series:
    """True where a clinic is more than k standard deviations from the mean of all clinics."""
    sd = values.std(ddof=1)
    return (values - values.mean()).abs() > k * sd if sd and not pd.isna(sd) else values * 0 != 0


def _accuracy(v: pd.DataFrame) -> list[dict]:
    rows = []
    for clinic, g in [("All", v), *sorted(v.groupby(v["clinic"].astype(str)), key=lambda x: int(x[0]))]:
        for col, label in SOURCES.items():
            ans = g[col] != "unknown"
            rows.append({"clinic": clinic, "source": col, "label": label, "visit_count": len(g),
                         "answered_pct": _pct(ans.mean()),
                         "agree_pct": _pct((g.loc[ans, col] == g.loc[ans, "truth_status"]).mean()) if ans.any()
                         else None})
    return rows


PERIO = ("periodontitis_stage_1", "periodontitis_stage_2", "periodontitis_stage_3", "periodontitis_stage_4")
FUNNEL = [("exam_form", "+ an exam form with a status"), ("proc_dx_completed", "+ a diagnosis code"),
          ("probing_chart", "+ a gum chart"), ("notes", "+ a chart note with a status")]


@traced
def truth_row(v: pd.DataFrame, col: str) -> dict:
    """One source against the truth, where it answers: exact status agreement, and periodontitis yes/no
    sensitivity, specificity, PPV and NPV."""
    a = v[v[col] != "unknown"]
    p, t = a[col].isin(PERIO), a["truth_status"].isin(PERIO)
    tp, fp, fn, tn = int((p & t).sum()), int((p & ~t).sum()), int((~p & t).sum()), int((~p & ~t).sum())

    def r(x, y):
        return round(100 * x / y, 1) if y else None
    return {"source": col, "label": SOURCES.get(col, col), "answered_count": len(a),
            "agree_pct": r(int((a[col] == a["truth_status"]).sum()), len(a)),
            "sensitivity_pct": r(tp, tp + fn), "specificity_pct": r(tn, tn + fp),
            "ppv_pct": r(tp, tp + fp), "npv_pct": r(tn, tn + fn)}


def _monitor(v: pd.DataFrame, complete_ids: set) -> list[dict]:
    """Every clinic (and All) by every scale, for the page's filters."""
    scales = {"all_visits": lambda x: x, "complete_cases": lambda x: x[x["visit_id"].isin(complete_ids)],
              "reference_set": lambda x: x[x["in_review"].astype(bool)]}
    groups = [("All", v), *sorted(v.groupby(v["clinic"].astype(str)), key=lambda x: int(x[0]))]
    out = []
    for clinic, g in groups:
        for scale, pick in scales.items():
            x = pick(g)
            n = len(x)
            complete = ((x["exam_form"] != "unknown") & (x["proc_dx_completed"] != "unknown")
                        & (x["probing_chart"] != "unknown"))
            steps, keep = [{"label": "Visits", "visit_count": n}], pd.Series(True, index=x.index)
            for col, label in FUNNEL:
                keep &= x[col] != "unknown"
                steps.append({"label": label, "visit_count": int(keep.sum())})
            out.append({"clinic": clinic, "scale": scale, "visit_count": int(n),
                        "completeness_pct": _pct(complete.mean()) if n else None,
                        "accuracy_pct": _pct((x["algorithm_v0"] == x["truth_status"]).mean()) if n else None,
                        "accuracy_design_pct": _pct((x["algorithm_design"] == x["truth_status"]).mean()) if n else None,
                        "missing": [{"source": c, "label": SOURCES[c], "missing_pct": _pct((x[c] == "unknown").mean())}
                                    for c in ("notes", "exam_form", "proc_dx_completed", "proc_dx_planned",
                                              "probing_chart")] if n else [],
                        "funnel": steps,
                        "truth": [truth_row(x, c) for c in SOURCES] if n else []})
    return out


@traced
def build() -> dict:
    """The page's data: one section per grader dataset, then the Open Dental profile."""
    t = grader_tables.dq_tables(DATASETS_DIR)
    v = t["fact_visit_evidence"]
    prev = t["dq_prevalence"]
    clin = prev.query("level == 'clinic' and method == 'algorithm_design'").copy()
    clin["is_outlier"] = flag_outliers(clin["periodontitis"])
    tc = t["dq_temporal_change"].set_index("method")
    complete = (v["exam_form"] != "unknown") & (v["proc_dx_completed"] != "unknown") & (v["probing_chart"] != "unknown")
    tables, _, readings = open_dental.build_with_readings(open_dental.Params(), seed=42)
    prof = open_dental.realism_profile(tables, readings)
    inj = t["dq_injected_error"].iloc[0]
    sections = {
        "tiles": {"completeness_pct": _pct(complete.mean()),
                  "accuracy_pct": _pct((v["algorithm_v0"] == v["truth_status"]).mean()),
                  "accuracy_design_pct": _pct((v["algorithm_design"] == v["truth_status"]).mean()),
                  "consistency_pts": _pct(clin["periodontitis"].max() - clin["periodontitis"].min()),
                  "implausible_pct": _pct(tc.loc["algorithm_design", "better"]),
                  "visit_count": len(v), "clinic_count": int(v["clinic"].nunique()),
                  "reliability_text": "Not assessed: needs real reviewers to label charts. Simulated reviewers are "
                                      "a dry run."},
        "missingness": [{"column": r.evidence_column, "label": COLUMNS.get(r.evidence_column, r.evidence_column),
                         "missing_pct": round(float(r.pct_missing), 1), "missing_count": int(r.n_missing),
                         "row_count": int(r.n_rows)}
                        for r in t["dq_column_missing"].sort_values("pct_missing", ascending=False).itertuples()],
        "checks": [{"clinic": r.clinic, "category": r.category, "check": r.check_name, "checked_count": int(r.n_checked),
                    "failed_count": int(r.n_fail), "pass_pct": round(100 * float(r.pass_rate), 2), "status": r.status}
                   for r in t["dq_check"].itertuples()],
        "accuracy": _accuracy(v),
        "concordance": [{"method_a": r.method_a, "method_b": r.method_b, "label_a": METHODS.get(r.method_a, r.method_a),
                         "label_b": METHODS.get(r.method_b, r.method_b), "agree_pct": round(float(r.pct_agree) * 100, 1),
                         "kappa": round(float(r.kappa), 2), "visit_count": int(r.n)}
                        for r in t["dq_source_concordance"].query("level == 'status'").itertuples()],
        "prevalence_clinic": [{"clinic": r.group_name, "people_count": int(r.n),
                               "periodontitis_pct": _pct(r.periodontitis), "ci_low_pct": _pct(r.periodontitis_ci_low),
                               "ci_high_pct": _pct(r.periodontitis_ci_high), "is_outlier": bool(r.is_outlier)}
                              for r in clin.itertuples()],
        "prevalence_scale": [{"method": r.method, "label": METHODS.get(r.method, r.method), "scale": r.group_name,
                              "visit_count": int(r.n), "periodontitis_pct": _pct(r.periodontitis),
                              "stage3_4_pct": _pct(r.stage3_4)} for r in prev.query("level == 'scale'").itertuples()],
        "transitions": [{"from_status": r.from_status, "to_status": r.to_status,
                         "from_label": STATUS.get(r.from_status, r.from_status),
                         "to_label": STATUS.get(r.to_status, r.to_status), "pair_count": int(r.n),
                         "row_pct": round(float(r.row_pct), 1), "direction": r.direction}
                        for r in t["dq_stage_transition"].itertuples()],
        "temporal": [{"method": m, "label": METHODS.get(m, m), "pair_count": int(r["pairs"]),
                      "improved_pct": _pct(r["better"]), "same_pct": _pct(r["same"]), "worse_pct": _pct(r["worse"]),
                      "resolved_pct": _pct(r["perio_resolved"]), "stage_drop_pct": _pct(r["stage_drop"])}
                     for m, r in tc.sort_values("better").iterrows()],
        "injected": {"injected_count": int(inj["injected_errors"]),
                     "caught_count": round(float(inj["caught_share"]) * int(inj["injected_errors"])),
                     "caught_pct": _pct(inj["caught_share"]), "false_flag_pct": _pct(inj["flag_rate_without_error"], 2)},
        "monitor": _monitor(v, set(complete_cases(pd.read_csv(DATASETS_DIR / "visits_structured.csv"))["visit_id"])),
        "open_dental": [{"metric": r.metric_name, "label": MESS.get(r.metric_name, r.metric_name),
                         "pct": _pct(r.value_ratio), "numerator": int(r.numerator_count),
                         "denominator": int(r.denominator_count)} for r in prof.itertuples()],
    }
    return {
        "title": "EHR DQ grader: is this dental record fit for finding gum disease?",
        "is_synthetic": True,
        "note": ("Synthetic data from the study's generator, scored against its own truth: not clinical performance, "
                 "and not how good any real practice's records are."),
        "design": "dashboards.dq_grader (spec 019): Zozus completeness, accuracy, consistency; Kahn temporal "
                  "plausibility; de Vet reliability",
        "sources": ["grader_tables.dq_tables(data/datasets/)",
                    "open_dental.realism_profile (seed 42, default settings)"],
        "sections": sections,
    }
