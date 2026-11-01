"""The tables the two graders read (spec 019), one DataFrame per gold table, built from committed CSVs.

    lab_tables  the lab grader: questions and answers, real when committed, else a seeded SIMULATED sample
    dq_tables   the EHR DQ grader: data-quality checks, completeness, prevalence, temporal plausibility,
                transitions, concordance, per-visit evidence with its truth (statuses only, never note text),
                each visit's case profile, and the record-mismatch rules with their scores (spec 026)

Each dict is keyed by the gold table name; the frames keep their analysis column names, and the Load results job
renames them with gold_names.to_gold before writing (AGENTS.md "SQL and data names").

Every row carries `source_files` and `sha256` (of those files, together), so a table says which version of the
results it holds. The Load results job overwrites each table from these on every run.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from . import case_profile
from .telemetry import traced

STATUS_ORDER = ["healthy_gingivitis", "periodontitis_stage_1", "periodontitis_stage_2", "periodontitis_stage_3",
                "periodontitis_stage_4"]
# the evidence sources the DQ grader scores against the truth, in the study's terms (evidence_rules.md)
EVIDENCE = ["notes", "exam_form", "proc_dx_completed", "proc_dx_planned", "probing_chart", "algorithm_v0",
            "algorithm_design", "algorithm_patel2022"]
# spec 024 (FR-010): these come from periodx_visits.csv, not visits_structured.csv
PERIODX_EVIDENCE = ["algorithm_patel2022"]


def _with_provenance(df: pd.DataFrame, folder: Path, files: list[str]) -> pd.DataFrame:
    h = hashlib.sha256()
    for f in files:
        h.update((Path(folder) / f).read_bytes())
    return df.reset_index(drop=True).assign(source_files=",".join(files), sha256=h.hexdigest())


def _read(folder: Path, f: str) -> pd.DataFrame:
    return pd.read_csv(Path(folder) / f)


@traced
def dq_tables(datasets_dir: Path) -> dict[str, pd.DataFrame]:
    """Every dq_* table of spec 019 US1, from data/datasets/ (DATASETS_DIR)."""
    d = Path(datasets_dir)
    out = {}

    f = ["data_quality/dq_overall.csv", "data_quality/dq_by_clinic.csv"]
    overall = _read(d, f[0]).assign(clinic="All")
    by_clinic = _read(d, f[1]).assign(clinic=lambda x: x.clinic_id.astype(int).astype(str)).drop(columns="clinic_id")
    checks = pd.concat([overall, by_clinic], ignore_index=True).rename(columns={"check": "check_name"})
    out["dq_check"] = _with_provenance(checks, d, f)   # `check` and `column` are reserved words in SQL

    f = ["data_quality/completeness_columns.csv"]
    out["dq_column_missing"] = _with_provenance(_read(d, f[0]).rename(columns={"column": "evidence_column"}), d, f)

    f = ["prevalence/prevalence_by_clinic.csv", "data_quality/prevalence_by_scale.csv"]
    clinic = _read(d, f[0]).rename(columns={"n_people": "n"}).assign(
        level="clinic", group_name=lambda x: x.clinic_id.astype(int).astype(str))
    scale = _read(d, f[1]).rename(columns={"status_col": "method", "scale": "group_name", "n_known": "n"}).assign(
        level="scale")
    cols = ["method", "level", "group_name", "n", "periodontitis", "periodontitis_ci_low", "periodontitis_ci_high",
            "stage3_4"]
    out["dq_prevalence"] = _with_provenance(pd.concat([clinic, scale], ignore_index=True).reindex(columns=cols), d, f)

    f = ["data_quality/temporal_by_method.csv", "data_quality/transitions_by_method.csv"]
    out["dq_temporal_change"] = _with_provenance(_read(d, f[0]).merge(_read(d, f[1]), on="method", how="outer"), d, f)

    f = ["data_quality/transitions_algorithm_design.csv"]
    m = _read(d, f[0]).set_index("from_status")
    long = m.stack().rename("n").reset_index().rename(columns={"level_1": "to_status"})
    long["row_pct"] = 100 * long.n / long.groupby("from_status").n.transform("sum")
    rank = {s: i for i, s in enumerate(STATUS_ORDER)}
    step = long.to_status.map(rank) - long.from_status.map(rank)
    long["direction"] = step.map(lambda s: "worse" if s > 0 else "better" if s < 0 else "same")
    long.insert(0, "method", "algorithm_design")
    out["dq_stage_transition"] = _with_provenance(long, d, f)

    f = ["method_agreement.csv"]
    out["dq_source_concordance"] = _with_provenance(_read(d, f[0]), d, f)

    f = ["visits_structured.csv", "answer_key/visits_truth.csv", "periodx_visits.csv"]
    structured = [c for c in EVIDENCE if c not in PERIODX_EVIDENCE]
    v = _read(d, f[0])[["visit_id", "person_id", "clinic_id", "visit_date", "visit_seq", "in_review", *structured]]
    truth = _read(d, f[1])[["visit_id", "truth_status"]]
    v = v.merge(_read(d, f[2])[["visit_id", *PERIODX_EVIDENCE]], on="visit_id", validate="one_to_one")
    v = v.merge(truth, on="visit_id", validate="one_to_one").assign(
        clinic=lambda x: x.clinic_id.astype(str), visit_date=lambda x: pd.to_datetime(x.visit_date).dt.date)
    out["fact_visit_evidence"] = _with_provenance(v.drop(columns="clinic_id"), d, f)

    f = ["data_quality/injected_error_recall.csv"]
    out["dq_injected_error"] = _with_provenance(_read(d, f[0]), d, f)

    # spec 026 US1: one KEEPER-style profile per visit, built here from the committed visits (structured values
    # only), so the 100k-row long form isn't committed as a second copy of the same evidence
    f = ["visits_structured.csv"]
    out["fact_case_profile_item"] = _with_provenance(case_profile.build_profiles(_read(d, f[0])), d, f)

    # spec 026 US2: record mismatches (failed rules only) and each rule's scores, from scripts/45_case_profiles.py
    f = ["case_profiles/record_mismatch.csv"]
    m = _read(d, f[0]).assign(clinic=lambda x: x.clinic.astype(str), evidence=lambda x: x.evidence.fillna(""),
                              related_visit_id=lambda x: x.related_visit_id.astype("Int64"))
    out["fact_record_mismatch"] = _with_provenance(m, d, f)
    f = ["case_profiles/mismatch_rule_score.csv"]
    out["dq_mismatch_rule"] = _with_provenance(_read(d, f[0]).assign(clinic=lambda x: x.clinic.astype(str)), d, f)
    return out


# ---------------------------------------------------------------- the lab grader (spec 019 US3)

# Access to care first: the mission (docs/pitch/, slide 11). Five key points per question, as GlobalDentBench
# decomposes a case answer (docs/dentbench_methods.md).
CATEGORIES = ["Access to care", "Clinical cases", "Medical-dental integration", "Barriers to care",
              "Cost and coverage"]
KEY_POINTS = 5
SIM_MODELS = {"sim:model-a": 0.62, "sim:model-b": 0.55, "sim:model-c": 0.48}   # made-up base skill
SIM_JUDGE = "sim:judge-x"                                                      # a family no model shares
# made-up agent effect per category: the pitch expects little on clinical cases, more on access and the seam
SIM_AGENT_EFFECT = dict(zip(CATEGORIES, [0.12, 0.01, 0.08, 0.06, 0.05]))
SIM_LEVEL_EFFECT = {"L1": 0.10, "L2": 0.0, "L3": -0.15}
SIM_COST = {"sim:model-a": 0.020, "sim:model-b": 0.006, "sim:model-c": 0.002}   # US$ per answer, made up


@traced
def simulate_grader(seed: int = 2026, per_category: int = 25) -> dict[str, pd.DataFrame]:
    """A SIMULATED lab grader run: every number is made up, so the dashboard and Genie can be built and checked
    before any real run. Every row says simulated = true and every model is a sim: name."""
    import numpy as np
    rng = np.random.default_rng(seed)
    q = pd.DataFrame([{"question_id": f"q{i * per_category + j + 1:03d}", "category": c, "category_order": i + 1,
                       "level": rng.choice(["L1", "L2", "L3"], p=[0.3, 0.4, 0.3]), "n_key_points": KEY_POINTS,
                       "source": "simulated: no evidence attached"}
                      for i, c in enumerate(CATEGORIES) for j in range(per_category)]).assign(simulated=True)
    rows = []
    for r in q.itertuples():
        for model, skill in SIM_MODELS.items():
            for agent in (False, True):
                p = skill + SIM_LEVEL_EFFECT[r.level] + (SIM_AGENT_EFFECT[r.category] if agent else 0.0)
                covered = int(rng.binomial(KEY_POINTS, min(max(p, 0.02), 0.98)))
                # harm follows what was left out (most harmful errors are omissions); medicines raise S2
                missed = KEY_POINTS - covered
                s2 = 0.04 * missed * (2.0 if r.category == "Medical-dental integration" else 1.0)
                s1 = 0.08 * missed
                u = rng.random()
                harm = "S2" if u < s2 else "S1" if u < s2 + s1 else "S0"
                cost = SIM_COST[model] * (1.6 if agent else 1.0) * float(rng.uniform(0.8, 1.2))
                rows.append({"question_id": r.question_id, "model": model, "with_agent": agent,
                             "key_points_covered": covered, "score": covered / KEY_POINTS, "harm": harm,
                             "cost_usd": round(cost, 5), "judge": SIM_JUDGE, "run_id": f"sim-{seed}"})
    return {"dim_grader_question": q, "fact_grader_answer": pd.DataFrame(rows).assign(simulated=True)}


@traced
def lab_tables(datasets_dir: Path) -> dict[str, pd.DataFrame]:
    """dim_grader_question and fact_grader_answer, from grader/grader_questions.csv and grader_answers.csv when they
    exist, else the committed simulated sample there (simulated_grader_*.csv), else the seeded sample itself."""
    d = Path(datasets_dir)
    for prefix in ("", "simulated_"):
        files = {"dim_grader_question": f"grader/{prefix}grader_questions.csv",
                 "fact_grader_answer": f"grader/{prefix}grader_answers.csv"}
        if all((d / f).exists() for f in files.values()):
            return {n: _with_provenance(_read(d, f), d, [f]) for n, f in files.items()}
    sim = simulate_grader()
    return {n: df.assign(source_files="simulate_grader(seed=2026)",
                         sha256=hashlib.sha256(df.to_csv(index=False).encode()).hexdigest())
            for n, df in sim.items()}
