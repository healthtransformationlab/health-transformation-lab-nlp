"""Build the study datasets: training set, chart-review set, answer key.

One synthetic population, split by person:

  train      every visit of the training people. De-identified note text,
             labelled by the generator. This is what the AI model learns from.
  review     ONE visit per review person (independent charts), stratified so
             rare statuses are represented. Every evidence type for the visit,
             de-identified, packaged as Label Studio tasks. Reviewers stage
             these; nobody sees the generator's answer.
  answer key generator truth, each method's reading, the v0 algorithm. Kept
             apart from the tasks; used only after review to score everyone.

Raw notes with fake PHI are written under data/raw/ (gitignored), standing in
for the secure zone. Only de-identified text that passes the leak gate leaves.
"""

from __future__ import annotations

import datetime as dt
import json
import random
from pathlib import Path

import pandas as pd

from .clinical_notes import render_clinical_note
from .deid import deidentify, leak_check, residual_scan, score_deid
from .labels import PerioChart, Status, extent_of, grade_of, label_chart
from .medical_record import medical_records, people_from_visits
from .note_reader import read_note
from .periodx import visits_table as periodx_visits_table
from .phenotype import (
    DEFAULT_ABSENT_CODE,
    DX_CODE_METHODS,
    RULES_DESIGN,
    RULES_V0,
    agreement_matrix,
    coverage,
    phenotype,
    phenotype_v0,
    read_dx_code,
    with_absent_code,
)
from .phi import fake_person, fake_provider
from .radiograph import FEATURES as RAD_FEATURES
from .radiograph import features as rad_features
from .radiograph import read_radiograph, simulate_radiograph, to_json
from .radiograph import summary as rad_summary
from .sources import READERS, UNKNOWN, generate_sources
from .synthetic import draw_chart, draw_history, draw_pct_teeth_involved, draw_risk
from .telemetry import traced

REVIEW_STRATA = {  # target share of the review set; rare classes oversampled
    "healthy": 0.15, "gingivitis": 0.20, "periodontitis_stage_1": 0.17,
    "periodontitis_stage_2": 0.18, "periodontitis_stage_3": 0.18, "periodontitis_stage_4": 0.12,
}


@traced
def probing_chart_text(c: PerioChart) -> str:
    return (f"Max PD {c.max_probing_depth_mm:.0f} mm | BOP {c.bop_pct:.0f}% | "
            f"Max interproximal CAL {c.max_cal_mm:.0f} mm | RBL {c.rbl_pct:.0f}% | "
            f"Teeth lost to perio: {c.teeth_lost_perio}")


CHARTED_SHARE = 0.8         # visits with a full probing chart (Patel 2020: ~80%)
CLINICIAN_DISAGREES = 0.25   # share of visits where the written dx is one step off the chart


def _clinician_call(status: Status, rng: random.Random) -> Status:
    if rng.random() >= CLINICIAN_DISAGREES:
        return status
    order = list(Status)
    i = order.index(status)
    return order[min(max(i + rng.choice([-1, 1]), 0), len(order) - 1)]


N_CLINICS = 8
RECORD_ERROR_RATE = 0.02     # charted follow-up visits with a charting error (spec 005)


STRUCTURED_COLS = ["visit_id", "person_id", "clinic_id", "visit_seq", "visit_date", "age", "charted",
                   "treated_before", "cigarettes_per_day", "diabetes", "hba1c",
                   "rec_max_probing_depth_mm", "rec_bop_pct", "rec_max_cal_mm", "rec_rbl_pct",
                   "rec_teeth_lost_perio", "rec_pct_teeth_involved", "notes", *READERS, "probing_chart", "radiograph_ai",
                   "algorithm_v0", "algorithm_design", "in_review"]


@traced
def clinic_profiles(seed: int) -> pd.DataFrame:
    """Synthetic clinics: case mix (sicker or healthier patients) and charting habits."""
    rng = random.Random(seed * 31 + 7)
    return pd.DataFrame([{"clinic_id": c, "case_mix": round(rng.uniform(-0.08, 0.10), 3),
                          "charted_share": round(rng.uniform(0.6, 0.95), 2),
                          "patient_weight": rng.uniform(0.5, 1.5)} for c in range(1, N_CLINICS + 1)])


def _study_visits(n_people: int, rng: random.Random, clinics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pid in range(1, n_people + 1):
        birth = dt.date(1940, 1, 1) + dt.timedelta(days=rng.randint(0, 365 * 63))
        first = dt.date(2021, 1, 1) + dt.timedelta(days=rng.randint(0, 180))
        clinic = rng.choices(list(clinics.clinic_id), weights=list(clinics.patient_weight))[0]
        for k in range(rng.randint(1, 6)):   # 1-6 recall visits about 6 months apart
            d = first + dt.timedelta(days=182 * k + rng.randint(-20, 20))
            rows.append(dict(person_id=pid, clinic_id=clinic, visit_seq=k, birth_date=birth, visit_date=d,
                             age=(d - birth).days // 365))
    return pd.DataFrame(rows)


def _record_error(chart: PerioChart, age: int, rng: random.Random) -> tuple[PerioChart, str]:
    """A charting error in the record (truth unchanged): another patient's chart, or a decimal slip."""
    if rng.random() < 0.5:
        return draw_chart(age, rng), "wrong_patient_chart"
    return PerioChart(chart.max_probing_depth_mm, chart.bop_pct, round(chart.max_cal_mm / 10, 2),
                      round(chart.rbl_pct / 10, 1), chart.teeth_lost_perio), "decimal_slip"


@traced
def generate_visits(n_people: int, seed: int) -> pd.DataFrame:
    rng = random.Random(seed)
    clinics = clinic_profiles(seed).set_index("clinic_id")
    visits = _study_visits(n_people, rng, clinics.reset_index()).sort_values(
        ["person_id", "visit_date"]).reset_index(drop=True)
    people = {pid: (fake_person(rng, g.iloc[0]["birth_date"]), draw_risk(rng))
              for pid, g in visits.groupby("person_id")}
    histories = {pid: draw_history(int(g.iloc[0]["age"]), len(g), people[pid][1], rng,
                                   case_mix=float(clinics.loc[g.iloc[0]["clinic_id"], "case_mix"]))
                 for pid, g in visits.groupby("person_id")}
    rows, prev = [], {}
    for i, v in enumerate(visits.itertuples(), start=1):
        person, risk = people[v.person_id]
        hv = histories[v.person_id][v.visit_seq]
        chart, status = hv.chart, hv.status
        diabetic = risk.hba1c is not None and risk.hba1c >= 6.5   # notes call 5.8-6.4 pre-diabetic
        grade = grade_of(status, chart.rbl_pct, int(v.age), risk.cigarettes_per_day, risk.hba1c, diabetes=diabetic)
        pct_involved = draw_pct_teeth_involved(chart, rng)
        extent = extent_of(status, pct_involved)
        # Radiograph AI output (spec 003) on its own random stream, so adding it
        # doesn't change any other source.
        rad = simulate_radiograph(chart, pct_involved, random.Random(seed * 7919 + i))
        stated = _clinician_call(status, rng)
        text, phi, meta = render_clinical_note(chart, status, grade, extent, risk, person,
                                               fake_provider(rng), v.visit_date, rng, prev.get(v.person_id),
                                               stated_status=stated)
        prev[v.person_id] = v.visit_date
        charted = rng.random() < float(clinics.loc[v.clinic_id, "charted_share"])
        recorded, error = chart, ""
        if charted and v.visit_seq > 0 and rng.random() < RECORD_ERROR_RATE:
            recorded, error = _record_error(chart, int(v.age), rng)
        rows.append(dict(visit_id=i, person_id=v.person_id, clinic_id=int(v.clinic_id), visit_seq=int(v.visit_seq),
                         visit_date=v.visit_date, age=int(v.age),
                         note_raw=text, phi_spans=json.dumps(phi), **meta,
                         charted=charted, treated_before=hv.treated_before, record_error=error,
                         probing_chart_text=probing_chart_text(recorded) if charted else "(not charted at this visit)",
                         probing_chart_status=label_chart(recorded).value if charted else UNKNOWN,
                         truth_status=status.value, truth_grade=grade, truth_extent=extent,
                         cigarettes_per_day=risk.cigarettes_per_day,
                         diabetes=diabetic, hba1c=risk.hba1c,
                         **{k: getattr(chart, k) for k in ("max_probing_depth_mm", "bop_pct", "max_cal_mm",
                                                           "rbl_pct", "teeth_lost_perio")},
                         rec_pct_teeth_involved=pct_involved if charted else None,
                         **{f"rec_{k}": getattr(recorded, k) if charted else None
                            for k in ("max_probing_depth_mm", "bop_pct", "max_cal_mm", "rbl_pct", "teeth_lost_perio")},
                         radiograph_json=to_json(rad), radiograph_summary=rad_summary(rad),
                         radiograph_ai=read_radiograph(rad), **rad_features(rad),
                         **generate_sources(status, extent, rng)))
    return pd.DataFrame(rows)


# Spec 032 US8 (#448): which visits count when results are scored. The benchmark note set (build_study: the review
# set, the answer key, train.csv) keeps every visit, because committed model runs were scored on those exact notes; the
# scoring scripts leave out the rest (scripts/28_ladder_vs_truth.py, 19_prevalence.py, 40_classify_status.py).
ANALYSIS_MIN_AGE = 18
ANALYSIS_START_DATE = "2021-04-01"    # synthetic stand-in for the date a newer classification was adopted


def _visit_masks(df: pd.DataFrame, min_age: int | None, start_date: str | None) -> tuple[pd.Series, pd.Series]:
    young = df["age"] < min_age if min_age is not None else pd.Series(False, index=df.index)
    on = pd.to_datetime(df["visit_date"])
    early = ~young & (on < pd.Timestamp(start_date)) if start_date is not None else pd.Series(False, index=df.index)
    return young, early


@traced
def visits_in_study(df: pd.DataFrame, min_age: int | None = ANALYSIS_MIN_AGE,
                    start_date: str | None = ANALYSIS_START_DATE) -> pd.DataFrame:
    """The visits that count (spec 032 US2): aged at least `min_age` at the visit when one is set, and on or after
    `start_date` (an ISO date) when one is set. The defaults (spec 032 US8) are adults from ANALYSIS_START_DATE; None
    for both keeps every visit (as build_study does for the benchmark note set)."""
    if min_age is None and start_date is None:
        return df
    young, early = _visit_masks(df, min_age, start_date)
    return df[~young & ~early]


@traced
def visit_exclusions(df: pd.DataFrame, min_age: int | None = ANALYSIS_MIN_AGE,
                     start_date: str | None = ANALYSIS_START_DATE) -> dict[str, int]:
    """How many visits `visits_in_study` leaves out, by reason, in the order it applies them (each visit counted
    once, under the first reason), and how many it keeps."""
    young, early = _visit_masks(df, min_age, start_date)
    return {"under_min_age_count": int(young.sum()), "before_start_date_count": int(early.sum()),
            "eligible_count": int((~young & ~early).sum())}


@traced
def apply_deid(df: pd.DataFrame, engine: str = "regex") -> tuple[pd.DataFrame, pd.DataFrame]:
    out, report = [], []
    for r in df.itertuples():
        phi = json.loads(r.phi_spans)
        text, found = deidentify(r.note_raw, engine)
        leaks = leak_check(text, phi)
        s = score_deid(r.note_raw, phi, found)
        report.append({"visit_id": r.visit_id, **s, "leaked_values": len(leaks),
                       "residual_flags": len(residual_scan(text.replace("[", "").replace("]", "")))})
        out.append({"visit_id": r.visit_id, "note_text": text, "deid_passed": not leaks})
    return df.merge(pd.DataFrame(out), on="visit_id"), pd.DataFrame(report)


@traced
def read_methods(df: pd.DataFrame, absent_code: str = DEFAULT_ABSENT_CODE) -> pd.DataFrame:
    """Every method's reading per visit, and the phenotypes built from them. `absent_code` (spec 032 US3,
    phenotype.ABSENT_CODE_RULES) is how the diagnosis-code source reads a visit with no gum-disease code."""
    df = df.copy()
    df["notes"] = [read_note(t) for t in df["note_text"]]
    for col, reader in READERS.items():
        df[col] = [reader(v) for v in df[col + "_raw"]]
    df = with_absent_code(df, absent_code)
    # The chart is the measured evidence, when it was done (Patel 2020: ~80% charted;
    # here it varies by clinic). Read from the RECORDED chart, which carries the
    # injected charting errors, and staged from that visit's chart alone.
    df["probing_chart"] = df["probing_chart_status"]
    df["difficulty"] = [difficulty(d, s, c, cf) for d, s, c, cf in
                        zip(df["dx_pattern"], df["stated_status"], df["truth_status"], df["copy_forward"])]
    pa = [phenotype_v0(r) for _, r in df.iterrows()]
    df["algorithm_v0"] = [p[0] for p in pa]
    df["algorithm_v0_decided_by"] = [p[1] for p in pa]
    pd_ = [phenotype(r, RULES_DESIGN) for _, r in df.iterrows()]   # spec 005: study-design order
    df["algorithm_design"] = [p[0] for p in pd_]
    df["algorithm_design_decided_by"] = [p[1] for p in pd_]
    return df


@traced
def pick_review(df: pd.DataFrame, n: int, seed: int) -> pd.DataFrame:
    """One visit per person (latest), stratified by truth status."""
    last = df.sort_values("visit_date").groupby("person_id").tail(1)
    picks = []
    for status, share in REVIEW_STRATA.items():
        pool = last[last["truth_status"] == status]
        picks.append(pool.sample(min(len(pool), round(n * share)), random_state=seed))
    return pd.concat(picks).sample(frac=1, random_state=seed)


@traced
def label_studio_tasks(review: pd.DataFrame) -> list[dict]:
    return [{"data": {
        "visit_id": int(r.visit_id),
        "note": r.note_text,
        "exam_form": r.exam_form_raw or "(none)",
        "proc_codes_completed": r.proc_codes_completed_raw or "(none)",
        "proc_codes_planned": r.proc_codes_planned_raw or "(none)",
        "proc_dx_completed": r.proc_dx_completed_raw or "(none)",
        "proc_dx_planned": r.proc_dx_planned_raw or "(none)",
        "probing_chart": r.probing_chart_text,
        "radiograph": r.radiograph_summary,
        "age": int(r.age),
    }} for r in review.itertuples()]


@traced
def build_study(out_dir: Path, raw_dir: Path, n_people: int = 1200, review_n: int = 240,
                seed: int = 42, engine: str = "regex", min_age: int | None = None,
                start_date: str | None = None, absent_code: str = "no_answer") -> dict:
    """Build the study files (module docstring). `min_age` and `start_date` (spec 032 US2, default None: every
    visit) choose which visits count; the summary then reports those left out, by reason. These and `absent_code`
    keep their pre-US8 defaults here: this builds the benchmark note set (review set, answer key) that committed model
    runs were scored on, so the scoring scripts apply the spec 032 US8 defaults instead (ANALYSIS_MIN_AGE)."""
    df = generate_visits(n_people, seed)
    filtered = min_age is not None or start_date is not None
    left_out = visit_exclusions(df, min_age, start_date)
    df = visits_in_study(df, min_age, start_date)
    # Spec 023: the synthetic medical record, on its own random stream after every study draw, so no other file changes.
    medical = medical_records(people_from_visits(df), seed)
    for c in READERS:
        df = df.rename(columns={c: c + "_raw"})
    raw_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(raw_dir / "visits_with_fake_phi.parquet")

    df, deid_report = apply_deid(df, engine)
    blocked = df[~df["deid_passed"]]
    df = df[df["deid_passed"]].drop(columns=["note_raw", "phi_spans"])  # nothing with PHI past here
    df = read_methods(df, absent_code)

    review = pick_review(df, review_n, seed)
    train = df[~df["person_id"].isin(review["person_id"])]
    df["in_review"] = df["visit_id"].isin(review["visit_id"])

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "answer_key").mkdir(exist_ok=True)
    train[["visit_id", "person_id", "note_text", "truth_status", "truth_grade", "truth_extent", "stated_status",
           *RAD_FEATURES]] \
        .rename(columns={"truth_status": "label", "truth_grade": "grade", "truth_extent": "extent"}) \
        .assign(label_source="generator").to_csv(out_dir / "train.csv", index=False)
    (out_dir / "review_tasks.json").write_text(json.dumps(label_studio_tasks(review), indent=1))
    key_cols = ["visit_id", "person_id", "age", "truth_status", "truth_grade", "truth_extent",
                "style", "numeric", "dx_scheme", "dx_pattern", "difficulty", "copy_forward", "stated_status", "notes", *READERS, "probing_chart", "radiograph_ai", "radiograph_summary",
                *RAD_FEATURES,
                "algorithm_v0", "algorithm_v0_decided_by", "algorithm_design", "algorithm_design_decided_by",
                "clinic_id", "note_text"]
    review[key_cols].to_csv(out_dir / "answer_key" / "review_key.csv", index=False)
    # Spec 005: every visit's structured data and source readings (no note text, no truth),
    # for longitudinal checks, clinic prevalence and prediction; truth kept in the answer key.
    df[STRUCTURED_COLS].to_csv(out_dir / "visits_structured.csv", index=False)
    df[["visit_id", "person_id", "truth_status", "truth_grade", "truth_extent", "record_error",
        "max_cal_mm", "rbl_pct", "teeth_lost_perio"]].to_csv(out_dir / "answer_key" / "visits_truth.csv", index=False)
    clinic_profiles(seed).to_csv(out_dir / "answer_key" / "clinic_profiles.csv", index=False)
    medical.to_csv(out_dir / "medical_record.csv", index=False)
    # Spec 024 (FR-010): the PerioDx readings and the Patel et al. 2022 stepwise phenotype, statuses only (no note
    # text), in their own file so every file above stays byte-identical.
    periodx_visits_table(df).to_csv(out_dir / "periodx_visits.csv", index=False)
    methods =["notes", *READERS, "probing_chart", "radiograph_ai"]
    agree = pd.concat([agreement_matrix(df, methods, "status").assign(level="status"),
                       agreement_matrix(df, methods, "perio").assign(level="perio")])
    agree.to_csv(out_dir / "method_agreement.csv", index=False)
    coverage(df, methods).rename("coverage").to_csv(out_dir / "method_coverage.csv")
    deid_report.to_csv(out_dir / "deid_report.csv", index=False)

    tot = deid_report[["phi_chars", "phi_chars_removed", "non_phi_chars_removed"]].sum()
    summary = {"visits": len(df) + len(blocked), "blocked_by_leak_gate": len(blocked),
            "train_visits": len(train), "train_people": train["person_id"].nunique(),
            "review_visits": len(review), "deid_engine": engine,
            "deid_char_recall": round(tot.phi_chars_removed / tot.phi_chars, 4),
            "deid_non_phi_chars_removed": int(tot.non_phi_chars_removed),
            "algorithm": RULES_V0["version"], "algorithm_design": RULES_DESIGN["version"],
            "record_errors_injected": int((df["record_error"] != "").sum()),
            "review_status_mix": review["truth_status"].value_counts().to_dict()}
    if filtered:      # only then, so the default summary (data/datasets/build_summary.json) is unchanged
        summary["visits_left_out"] = {"min_age": min_age, "start_date": start_date, **left_out}
    return summary


@traced
def build_corpus_sample(n_people: int, seed: int, engine: str = "regex") -> pd.DataFrame:
    """A de-identified stand-in for the full corpus, for timing and judging.

    Returns visit_id, note_text and (for simulated judging ONLY) truth_status.
    A real corpus has no truth column; nothing downstream may use it except
    the simulated judge backend.
    """
    df = generate_visits(n_people, seed)
    for c in READERS:
        df = df.rename(columns={c: c + "_raw"})
    df, _ = apply_deid(df, engine)
    df = df[df["deid_passed"]]
    return df[["visit_id", "person_id", "note_text", "truth_status", *RAD_FEATURES]].reset_index(drop=True)


TRANSLATE_PATTERNS = {"pre2017_severity", "legacy_old"}


@traced
def difficulty(dx_pattern: str, stated_status: str, chart_status: str, copy_forward: bool) -> str:
    """Difficulty level per chart (spec 002), adapted from GlobalDentBench's
    L1 recall / L2 routine reasoning / L3 individualized reasoning:

        L1  the note states the diagnosis in 2017 terms and it matches the chart
        L2  the diagnosis must be translated (pre-2017 terms) or copied-forward
            text must be ignored
        L3  no diagnosis is written, or the written one disagrees with the chart,
            so the status must be inferred from findings or a conflict resolved
    """
    if dx_pattern == "none" or stated_status != chart_status:
        return "L3"
    if dx_pattern in TRANSLATE_PATTERNS or bool(copy_forward):
        return "L2"
    return "L1"


# ---------- spec 032 US8 (#448): scoring under the defaults without rebuilding the benchmark note set ----------
BUILD_N_PEOPLE, BUILD_SEED = 1200, 42        # scripts/10_build_study.py's defaults: the committed build


@traced
def reread_absent_code(frame: pd.DataFrame, absent_code: str = DEFAULT_ABSENT_CODE, n_people: int = BUILD_N_PEOPLE,
                       seed: int = BUILD_SEED) -> pd.DataFrame:
    """`frame` (committed visits with `visit_id` and every method's reading: the answer key or visits_structured.csv)
    with the diagnosis-code readings and the two rule phenotypes read again under `absent_code`. The raw codes come
    from generate_visits with the build's people and seed (no note text is used); a frame those don't reproduce under
    "no_answer" fails at once, so a build with other settings can't be re-read by mistake."""
    raw = generate_visits(n_people, seed).set_index("visit_id")
    ids = frame["visit_id"]
    missing = ids[~ids.isin(raw.index)]
    if len(missing):
        raise ValueError(f"{len(missing)} visits are not in the build of {n_people} people, seed {seed}")
    raw = raw.loc[ids, [*DX_CODE_METHODS, "proc_codes_planned"]]
    out = frame.copy()
    for m in DX_CODE_METHODS:
        as_built = [READERS[m](v) for v in raw[m]]
        if list(as_built) != list(frame[m]):
            raise ValueError(f"{m}: the regenerated codes don't give the committed readings; was the build made "
                             f"with {n_people} people and seed {seed}?")
        out[m] = [read_dx_code(d, p, absent_code) for d, p in zip(raw[m], raw["proc_codes_planned"])]
    pa = [phenotype_v0(r) for _, r in out.iterrows()]
    out["algorithm_v0"], out["algorithm_v0_decided_by"] = [p[0] for p in pa], [p[1] for p in pa]
    pd_ = [phenotype(r, RULES_DESIGN) for _, r in out.iterrows()]
    out["algorithm_design"], out["algorithm_design_decided_by"] = [p[0] for p in pd_], [p[1] for p in pd_]
    return out


@traced
def scored_review(key: pd.DataFrame, visits: pd.DataFrame, min_age: int | None = ANALYSIS_MIN_AGE,
                  start_date: str | None = ANALYSIS_START_DATE,
                  absent_code: str = DEFAULT_ABSENT_CODE) -> pd.DataFrame:
    """The review charts results are scored on (spec 032 US8): the answer key's visits that count (visits_in_study,
    with each visit's date from visits_structured.csv), their codes and rule phenotypes read under `absent_code`."""
    dated = key.merge(visits[["visit_id", "visit_date"]], on="visit_id", how="left")
    return reread_absent_code(visits_in_study(dated, min_age, start_date), absent_code).reset_index(drop=True)
