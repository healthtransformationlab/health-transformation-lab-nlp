"""Case profiles for the synthetic study's visits (spec 026, US1).

Every visit's structured evidence laid out the same way, grouped into the categories KEEPER uses for case
review (Schuemie, Ostropolets et al., npj Digit Med 2025; docs/rag_and_vocabulary.md, R6), adapted to
periodontal records. A reviewer, Genie or the chart review agent reads one profile instead of a dozen columns.

Structured values only, never note text: `notes` in visits_structured.csv is the note reader's status. A value
the record lacks reads "not recorded", never left out or filled in. Synthetic data only.

We find gum disease in records; we don't diagnose (AGENTS.md, "Words"). The recorded diagnosis codes here are
what the synthetic dentist recorded.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import plausibility
from .labels import LABELS
from .telemetry import traced

NOT_RECORDED = "not recorded"
NOT_TAKEN = "not taken"
NO_LATER_VISIT = "no later visit"
NEXT_CODE = "next visit's recorded code"
NEXT_FLAGS = "next visit's plausibility flags"

# (category, item, source column in visits_structured.csv or None when derived, unit), in display order
PROFILE_ITEMS: list[tuple[str, str, str | None, str]] = [
    ("Demographics", "age", "age", "years"),
    ("Demographics", "clinic", "clinic_id", ""),
    ("Presentation", "recorded diagnosis code, completed", "proc_dx_completed", ""),
    ("Presentation", "recorded diagnosis code, planned", "proc_dx_planned", ""),
    ("Presentation", "exam form", "exam_form", ""),
    ("Visit context", "visit number for the patient", "visit_seq", ""),   # shown from 1; visit_seq starts at 0
    ("Visit context", "probing chart taken", "charted", ""),
    ("Visit context", "treated before", "treated_before", ""),
    ("Measurements", "max probing depth", "rec_max_probing_depth_mm", "mm"),
    ("Measurements", "bleeding on probing", "rec_bop_pct", "%"),
    ("Measurements", "max attachment loss (CAL)", "rec_max_cal_mm", "mm"),
    ("Measurements", "bone loss", "rec_rbl_pct", "%"),
    ("Measurements", "teeth lost to periodontitis", "rec_teeth_lost_perio", "teeth"),
    ("Measurements", "teeth involved", "rec_pct_teeth_involved", "%"),
    ("Tests and imaging", "probing chart reading", "probing_chart", ""),
    ("Tests and imaging", "radiograph AI reading", "radiograph_ai", ""),
    ("Risk factors", "cigarettes per day", "cigarettes_per_day", ""),
    ("Risk factors", "diabetes", "diabetes", ""),
    ("Risk factors", "HbA1c", "hba1c", "%"),
    ("Treatment", "status from periodontal procedure codes, completed", "proc_codes_completed", ""),
    ("Treatment", "status from periodontal procedure codes, planned", "proc_codes_planned", ""),
    ("Other readings", "note reader", "notes", ""),
    ("Other readings", "rules, gum measurements first", "algorithm_v0", ""),
    ("Other readings", "rules in the study design's order", "algorithm_design", ""),
    ("After the visit", NEXT_CODE, None, ""),
    ("After the visit", NEXT_FLAGS, None, ""),
]
CATEGORIES = list(dict.fromkeys(cat for cat, *_ in PROFILE_ITEMS))


def _shown(value) -> str:
    """A value as the profile shows it: "not recorded" when missing or unknown, yes/no, numbers without trailing
    zeros, statuses as their code. Python, numpy and pandas scalars all show the same."""
    if not isinstance(value, str) and pd.isna(value):
        return NOT_RECORDED
    if value == "unknown":
        return NOT_RECORDED
    if isinstance(value, (bool, np.bool_)):
        return "yes" if value else "no"
    if isinstance(value, (int, float, np.number)):
        return f"{float(value):g}"
    return str(value)


@traced
def history_frame(visits: pd.DataFrame) -> pd.DataFrame:
    """The columns plausibility.check_history reads, from visits_structured.csv rows (as 20_data_quality does)."""
    return visits.rename(columns={"rec_max_cal_mm": "max_cal_mm", "rec_rbl_pct": "rbl_pct",
                                  "rec_teeth_lost_perio": "teeth_lost_perio"})


def _after(visits: pd.DataFrame) -> pd.DataFrame:
    """Per visit: the same patient's next visit's recorded code and the plausibility checks that visit fails."""
    flags = plausibility.check_history(history_frame(visits), "proc_dx_completed").set_index("visit_id")
    failed = flags[plausibility.FLAGS].apply(lambda r: ", ".join(f for f in plausibility.FLAGS if r[f]) or "none",
                                             axis=1)
    v = visits.sort_values(["person_id", "visit_date", "visit_id"])   # the order check_history uses
    nxt = v.groupby("person_id").visit_id.shift(-1)
    out = pd.DataFrame({"visit_id": v.visit_id.to_numpy(), "next_id": nxt.to_numpy()})
    code = visits.set_index("visit_id").proc_dx_completed
    has_next = out.next_id.notna()
    out[NEXT_CODE] = NO_LATER_VISIT
    out[NEXT_FLAGS] = NO_LATER_VISIT
    ids = out.loc[has_next, "next_id"].astype("int64")
    out.loc[has_next, NEXT_CODE] = [_shown(c) for c in code.loc[ids]]
    out.loc[has_next, NEXT_FLAGS] = failed.loc[ids].to_numpy()
    return out.set_index("visit_id")


@traced
def build_profiles(visits: pd.DataFrame) -> pd.DataFrame:
    """visits: visits_structured.csv rows. Returns the profiles in long form, one row per (visit, item):
    visit_id, category, category_order, item, item_order, value, unit."""
    after = _after(visits)
    order = {c: i + 1 for i, c in enumerate(CATEGORIES)}
    rows = []
    visits = visits.astype(object).where(visits.notna(), None)   # one scalar type, whatever the dtypes
    for r in visits.itertuples(index=False):
        rec = r._asdict()
        for i, (cat, item, col, unit) in enumerate(PROFILE_ITEMS, start=1):
            if col is None:
                value = after.at[r.visit_id, item]
            elif col == "probing_chart" and not rec["charted"]:
                value = NOT_TAKEN
            elif col == "visit_seq":
                value = _shown(rec[col] + 1)
            else:
                value = _shown(rec[col])
            rows.append({"visit_id": r.visit_id, "category": cat, "category_order": order[cat], "item": item,
                         "item_order": i, "value": value, "unit": unit if value not in
                         (NOT_RECORDED, NOT_TAKEN, NO_LATER_VISIT) else ""})
    return pd.DataFrame(rows, columns=["visit_id", "category", "category_order", "item", "item_order", "value",
                                       "unit"])


# ---------------------------------------------------------------- record-mismatch rules (spec 026, US2)
#
# Each rule asks whether the recorded code (the completed diagnosis code) fits the rest of the record. A failed rule
# is a record mismatch to recheck: usually a coding or charting gap, never a judgment that a dentist got it wrong.
# Outcomes: fail, pass, not_checkable (the evidence the rule needs is missing), no_code (no recorded code).

RANK = {s: i for i, s in enumerate(LABELS)}          # healthy 0, gingivitis 1, stage I-IV 2-5
STAGE_2, STAGE_3 = RANK["periodontitis_stage_2"], RANK["periodontitis_stage_3"]
PERIO = RANK["periodontitis_stage_1"]

HIGH_CODE_MAX_CAL_MM = 3.0    # 2017 AAP/EFP: CAL under 3 mm is stage I's attachment loss (1-2 mm) ...
HIGH_CODE_RBL_PCT = 15.0      # ... bone loss under 15% is stage I's ...
HIGH_CODE_MAX_PD_MM = 6.0     # ... and PD under 6 mm is below stage III's depth; with no tooth lost, nothing in the
                              # chart reaches stage III
LOW_CODE_CAL_MM = 3.0         # beyond stage I: CAL 3 mm or more or bone loss 15% or more is periodontitis, and
LOW_CODE_RBL_PCT = 15.0       # gingivitis has no attachment or bone loss
CHART_STEPS = 1               # code and chart reading may differ by one step on the ladder above

# (name, plain label), in the order they are reported
RULES = [
    ("code_vs_chart", "Code against the chart reading"),
    ("code_above_chart", "Code higher than the chart"),
    ("code_below_chart", "Code lower than the chart"),
    ("no_periodontal_care", "No periodontal care"),
    ("code_vs_radiograph", "Code against the radiograph"),
    ("stage_drop", "Stage drops"),
]
LABEL = dict(RULES)
ANY_RULE = "any_rule"


def _rank(status):
    return RANK.get(status) if isinstance(status, str) else None


def _num(value):
    return None if value is None or pd.isna(value) else float(value)


def _peaks(visits: pd.DataFrame) -> dict:
    """visit_id -> (rank, visit_id) of the highest periodontitis code the patient had at an earlier visit, ordered by
    date as plausibility.check_history orders them; absent when there was none."""
    out = {}
    v = visits.sort_values(["person_id", "visit_date", "visit_id"])
    for _, g in v.groupby("person_id", sort=False):
        best = None
        for vid, status in zip(g.visit_id, g.proc_dx_completed):
            if best is not None:
                out[vid] = best
            r = _rank(status)
            if r is not None and r >= PERIO and (best is None or r > best[0]):
                best = (r, vid)
    return out


def _check(rec: dict, peak) -> list[tuple[str, str, str, object]]:
    """One visit's (rule, outcome, evidence, related visit) for every rule."""
    code = _rank(rec["proc_dx_completed"])
    if code is None:
        return [(name, "no_code", "", None) for name, _ in RULES]
    charted = bool(rec["charted"])
    cal, rbl = _num(rec["rec_max_cal_mm"]), _num(rec["rec_rbl_pct"])
    pd_mm, lost = _num(rec["rec_max_probing_depth_mm"]), _num(rec["rec_teeth_lost_perio"])
    chart, rad = _rank(rec["probing_chart"]), _rank(rec["radiograph_ai"])
    shown = rec["proc_dx_completed"]
    out = []

    if not charted or chart is None:
        out.append(("code_vs_chart", "not_checkable", "", None))
    else:
        fail = abs(code - chart) > CHART_STEPS
        out.append(("code_vs_chart", "fail" if fail else "pass",
                    f"code {shown}, chart reading {rec['probing_chart']}" if fail else "", None))

    if not charted or None in (cal, rbl, pd_mm, lost):
        out.append(("code_above_chart", "not_checkable", "", None))
    else:
        fail = (code >= STAGE_3 and cal < HIGH_CODE_MAX_CAL_MM and rbl < HIGH_CODE_RBL_PCT and lost == 0
                and pd_mm < HIGH_CODE_MAX_PD_MM)
        out.append(("code_above_chart", "fail" if fail else "pass",
                    f"code {shown}, max CAL {cal:g} mm, bone loss {rbl:g}%, max probing depth {pd_mm:g} mm, "
                    f"no tooth lost" if fail else "", None))

    if not charted or None in (cal, rbl):
        out.append(("code_below_chart", "not_checkable", "", None))
    else:
        fail = code < PERIO and (cal >= LOW_CODE_CAL_MM or rbl >= LOW_CODE_RBL_PCT)
        out.append(("code_below_chart", "fail" if fail else "pass",
                    f"code {shown}, max CAL {cal:g} mm, bone loss {rbl:g}%" if fail else "", None))

    care = any((_rank(rec[c]) or 0) >= PERIO for c in ("proc_codes_completed", "proc_codes_planned"))
    fail = code >= PERIO and not care
    out.append(("no_periodontal_care", "fail" if fail else "pass",
                f"code {shown}, no periodontal procedure completed or planned" if fail else "", None))

    if rad is None:
        out.append(("code_vs_radiograph", "not_checkable", "", None))
    else:
        fail = code < PERIO and rad >= STAGE_2
        out.append(("code_vs_radiograph", "fail" if fail else "pass",
                    f"code {shown}, radiograph AI {rec['radiograph_ai']}" if fail else "", None))

    if peak is None:
        out.append(("stage_drop", "not_checkable", "", None))
    else:
        fail = code < peak[0]
        out.append(("stage_drop", "fail" if fail else "pass",
                    f"code {shown}, after {LABELS[peak[0]]} at visit {peak[1]}" if fail else "", peak[1]))
    return out


@traced
def check_rules(visits: pd.DataFrame) -> pd.DataFrame:
    """visits: visits_structured.csv rows. One row per (visit, rule): visit_id, rule, outcome, evidence, and
    related_visit_id (stage drops: the earlier visit with the higher code)."""
    peaks = _peaks(visits)
    v = visits.astype(object).where(visits.notna(), None)
    rows = [{"visit_id": rec["visit_id"], "rule": rule, "outcome": outcome, "evidence": evidence,
             "related_visit_id": related}
            for rec in (r._asdict() for r in v.itertuples(index=False))
            for rule, outcome, evidence, related in _check(rec, peaks.get(rec["visit_id"]))]
    out = pd.DataFrame(rows, columns=["visit_id", "rule", "outcome", "evidence", "related_visit_id"])
    out["visit_id"] = out.visit_id.astype("int64")
    out["related_visit_id"] = out.related_visit_id.astype("Int64")
    return out


@traced
def record_mismatches(checks: pd.DataFrame, visits: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    """The failed rules only, one row per (visit, rule), with how many rules the visit fails (so the visits failing
    most sort first), its clinic and whether it carries an injected charting error (synthetic answer key)."""
    failed = checks[checks.outcome == "fail"].drop(columns="outcome")
    clinic = visits.set_index("visit_id").clinic_id.astype("int64").astype(str)
    injected = truth.set_index("visit_id").record_error.fillna("").astype(str) != ""
    out = failed.assign(rule_label=failed.rule.map(LABEL),
                        failed_rule_count=failed.visit_id.map(failed.visit_id.value_counts()).astype("int64"),
                        clinic=failed.visit_id.map(clinic),
                        injected_error=failed.visit_id.map(injected).fillna(False).astype(bool))
    return out[["visit_id", "rule", "rule_label", "evidence", "related_visit_id", "failed_rule_count", "clinic",
                "injected_error"]].reset_index(drop=True)


def _scores(g: pd.DataFrame) -> dict:
    checkable = g.outcome.isin(["fail", "pass"])
    flagged = g.outcome == "fail"
    true = flagged & g.wrong
    n_flag, n_wrong = int(flagged.sum()), int((checkable & g.wrong).sum())
    return {"checkable_count": int(checkable.sum()), "not_checkable_count": int((g.outcome == "not_checkable").sum()),
            "flagged_count": n_flag, "code_truth_mismatch_count": n_wrong, "true_flag_count": int(true.sum()),
            "precision": true.sum() / n_flag if n_flag else float("nan"),
            "recall": true.sum() / n_wrong if n_wrong else float("nan"),
            "only_rule_count": int((flagged & (g.n_failed == 1)).sum()),
            "injected_checkable_count": int((checkable & g.injected).sum()),
            "injected_caught_count": int((flagged & g.injected).sum())}


@traced
def score_rules(checks: pd.DataFrame, visits: pd.DataFrame, truth: pd.DataFrame) -> pd.DataFrame:
    """Each rule, and any rule, scored against the generator's truth over the visits it can check: overall
    (clinic "All") and per clinic. A visit's code is wrong when it differs from truth_status; a stage drop is also
    true when the earlier visit's code is the wrong one. Synthetic data only."""
    t = truth.set_index("visit_id")
    code = visits.set_index("visit_id").proc_dx_completed
    own_wrong = (code != t.truth_status.reindex(code.index)) & (code != "unknown")
    injected = t.record_error.reindex(code.index).fillna("").astype(str) != ""
    clinic = visits.set_index("visit_id").clinic_id.astype("int64").astype(str)

    c = checks.copy()
    c["wrong"] = c.visit_id.map(own_wrong)
    related = c.related_visit_id.notna() & (c.rule == "stage_drop")
    c.loc[related, "wrong"] = c.loc[related, "wrong"] | c.loc[related, "related_visit_id"].astype("int64").map(own_wrong)
    c["injected"] = c.visit_id.map(injected)
    c["clinic"] = c.visit_id.map(clinic)
    c["n_failed"] = c.visit_id.map((c.outcome == "fail").groupby(c.visit_id).sum())

    per_visit = c.groupby("visit_id").agg(n_failed=("n_failed", "first"), coded=("outcome", lambda o: (o != "no_code").all()),
                                          injected=("injected", "first"), clinic=("clinic", "first"))
    anyr = per_visit.assign(visit_id=per_visit.index, rule=ANY_RULE, wrong=per_visit.index.map(own_wrong),
                            outcome=lambda x: (x.n_failed > 0).map({True: "fail", False: "pass"}).where(x.coded, "no_code"))
    rows = []
    for rule in [r for r, _ in RULES] + [ANY_RULE]:
        g = anyr if rule == ANY_RULE else c[c.rule == rule]
        for name, part in [("All", g)] + sorted(g.groupby("clinic"), key=lambda kv: int(kv[0])):
            rows.append({"rule": rule, "rule_label": LABEL.get(rule, "Any rule"), "clinic": name, **_scores(part)})
    return pd.DataFrame(rows)
