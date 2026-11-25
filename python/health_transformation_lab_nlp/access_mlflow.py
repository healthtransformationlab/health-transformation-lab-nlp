"""Every AccessBench run in Databricks' MLflow evaluation view (spec 045 US6, #961).

The batch (`access_batch.run`) already has each answer graded by the AccessBench judge. This module logs those
grades as an MLflow GenAI evaluation, so the Experiments page shows every question, the model's answer and each
grade with its reasoning, and compares models side by side. The scorers only report the stored grades: logging a
run never calls a model, so it costs nothing and can be done again for a past run from the gold table
(`scripts/82_access_mlflow_backfill.py`).

One MLflow run per answering model, and one for the seeded control answers (spec 045 US3).
"""

from __future__ import annotations

import json
import math

import pandas as pd

from . import access_keypoint_judge as ak
from .telemetry import traced

SCORERS = ("points_met", "next_step", "harm", "repeated_identifier", "resource_level", "control_as_expected")
CONTROLS = "controls"


def _key(question_id, model) -> tuple[str, str]:
    return str(question_id), str(model)


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA


@traced
def evaluation_rows(fact: pd.DataFrame, items: dict[str, dict]) -> list[dict]:
    """One mlflow.genai.evaluate row per answer: the question, the model's answer, and what a good answer does."""
    rows = []
    for r in fact.to_dict("records"):
        item = items[r["question_id"]]
        rows.append({
            "inputs": {"question": item["prompt"], "question_id": r["question_id"], "model": r["endpoint"]},
            "outputs": {"answer": "" if _blank(r.get("answer")) else str(r["answer"])},
            "expectations": {"points_to_make": ak.positive_points(item), "must_not_do": ak.negative_checks(item)},
        })
    return rows


@traced
def make_scorers(fact: pd.DataFrame) -> list:
    """Scorers that report the batch's stored grades for each answer, looked up by question and model."""
    from mlflow.entities import Feedback
    from mlflow.genai.scorers import scorer

    graded = {_key(r["question_id"], r["endpoint"]): r for r in fact.to_dict("records")}

    def row(inputs: dict) -> dict:
        return graded.get(_key(inputs.get("question_id"), inputs.get("model")), {})

    def failed(r: dict):
        err = "" if _blank(r.get("error")) else str(r.get("error"))
        return err if err.startswith("judge_parse") else None

    def value(v):
        return None if _blank(v) else (v.item() if hasattr(v, "item") else v)

    def make(name: str, read, rationale=None):
        @scorer(name=name)
        def fn(inputs, outputs, expectations):
            r = row(inputs)
            err = failed(r)
            if err and name != "repeated_identifier":
                return Feedback(value=None, error=err)
            return Feedback(value=read(r), rationale=rationale(r) if rationale else None)
        return fn

    def point_rationale(r: dict) -> str:
        text = r.get("point_verdict_text")
        if _blank(text):
            return "no per-point verdicts (judge v1/v2)"
        lines = []
        for i, v in enumerate(json.loads(text), 1):
            span = (v.get("span") or "").strip()
            lines.append(f"{i}. {v.get('verdict')}" + (f': "{span}"' if span else ""))
        return "\n".join(lines)

    return [
        make("points_met", lambda r: value(r.get("coverage_ratio")), point_rationale),
        make("next_step", lambda r: None if _blank(r.get("is_next_step_pass")) else bool(r["is_next_step_pass"])),
        make("harm", lambda r: value(r.get("harm"))),
        make("repeated_identifier", lambda r: bool(r.get("is_phi_leak")) if not _blank(r.get("is_phi_leak")) else None),
        make("resource_level", lambda r: None if _blank(r.get("resource_level")) else int(r["resource_level"])),
        make("control_as_expected", lambda r: None if _blank(r.get("is_control_match")) else bool(r["is_control_match"])),
    ]


def _group(endpoint: str) -> str:
    return CONTROLS if str(endpoint).startswith("control:") else str(endpoint)


def _metrics(g: pd.DataFrame) -> dict:
    ok = g[~g["error"].fillna("").astype(str).str.startswith("judge_parse")] if "error" in g else g
    m = {
        "answers": float(len(g)),
        "points_met_mean": float(ok["coverage_ratio"].mean()) if len(ok) else float("nan"),
        "next_step_answers": float(ok["is_next_step_pass"].fillna(False).astype(bool).sum()) if "is_next_step_pass" in ok else 0.0,
        "harm_some": float((ok["harm"] == "S1").sum()),
        "harm_serious": float((ok["harm"] == "S2").sum()),
        "repeated_identifier": float(g["is_phi_leak"].fillna(False).astype(bool).sum()),
        "judge_failures": float(len(g) - len(ok)),
    }
    if "is_control_match" in g and g["is_control_match"].notna().any():
        m["controls_as_expected"] = float(g["is_control_match"].fillna(False).astype(bool).sum())
    return {k: v for k, v in m.items() if not math.isnan(v)}


@traced
def log_run(fact: pd.DataFrame, items: dict[str, dict], *, batch_run_id: str, judge_endpoint: str,
            prompt_version: str, configure: bool = True) -> dict[str, str]:
    """Log one MLflow evaluation run per answering model (and one for the controls); return their MLflow run ids.

    configure=False when the caller has already chosen the experiment (the Databricks notebook does, from the job's
    experiment_id); otherwise tracking._setup picks it from the environment.
    """
    import mlflow

    if configure:
        from .tracking import _setup
        _setup()
    runs = {}
    for name, g in fact.groupby(fact["endpoint"].map(_group), sort=True):
        with mlflow.start_run(run_name=f"AccessBench {name} · run {batch_run_id}") as run:
            mlflow.set_tags({"benchmark": "access_bench", "accessbench_run_id": str(batch_run_id),
                             "answering_model": name, "judge_endpoint": judge_endpoint,
                             "prompt_version": prompt_version,
                             "simulated": str(bool(g["is_simulated"].all())).lower() if "is_simulated" in g else "unknown"})
            mlflow.log_metrics(_metrics(g))
            mlflow.genai.evaluate(data=evaluation_rows(g, items), scorers=make_scorers(g))
            runs[name] = run.info.run_id
    return runs
