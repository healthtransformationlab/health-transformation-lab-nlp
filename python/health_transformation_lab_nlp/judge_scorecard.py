"""Judge-backed scorecard (spec 012): every README phenotyping metric against the truth and the judge.

On synthetic charts the truth is known; on real notes it isn't. An LLM judge can stand in for an
answer key only as far as it agrees with the truth where both exist, so every metric is computed
twice, once against each, and the gap is reported.

    answers = chart_answers(readme_results.load_inputs())   # every system x review chart
    queue = judge_queue(answers, key)                        # 1 status call per chart,
                                                             # 1 verdict call per distinct answer
    judgments = run_judge(queue, judge)                      # resumable; quote gate applied
    metrics = judge_metrics(...)                             # computed here, never by the LLM

Notes come from answer_key/review_key.csv: de-identified and leak-gated when the study was built
(constitution I). A *status* call shows the judge no answer, so its own status isn't anchored on
any system; a *verdict* call is the existing judge.py prompt.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import judge as jg
from . import readme_results as rr
from .cost_effectiveness import corrected_accuracy
from .harm import unsafe_rates
from .ladder_eval import STAGE4, grouped
from .phenotype import cohen_kappa
from .telemetry import traced

# Rough token counts for the cost estimate printed before a run (judge.SYSTEM is ~1,000 tokens).
SYSTEM_TOKENS = 1000
OUT_TOKENS = 100
CHARS_PER_TOKEN = 4
# databricks-meta-llama-3-3-70b-instruct pay-per-token list price: 7.143 / 21.429 DBU per 1M input / output
# tokens at US$0.07 per DBU (Databricks Foundation Model Serving pricing, checked 2026-10-27). Same as
# databricks.yml's judge_usd_per_million_in/out; a real run passes the endpoint's own price.
LIST_USD_PER_1M_IN = 0.50
LIST_USD_PER_1M_OUT = 1.50


@traced
def chart_answers(inp: dict) -> pd.DataFrame:
    """One row per (visit_id, system): the system's status on that review chart (NaN = none), the
    note's difficulty (L1/L2/L3) and the generator's truth (for the dashboard's drill-down). Same systems and answers as the README leaderboard."""
    truth, pred, level = rr.phenotype_predictions(inp)
    parts = [pd.DataFrame({"visit_id": p.index, "system": s, "answer": p.to_numpy(),
                           "difficulty": level.reindex(p.index).to_numpy(), "truth": truth.reindex(p.index).to_numpy()})
             for s, p in pred.items()]
    return pd.concat(parts, ignore_index=True)


@traced
def judge_queue(answers: pd.DataFrame, key: pd.DataFrame) -> pd.DataFrame:
    """kind='status': one per chart, no answer shown. kind='verdict': one per distinct (chart, answer),
    since a verdict depends only on the note and the answer, not on which system gave it."""
    charts = sorted(answers["visit_id"].unique())
    status = pd.DataFrame({"visit_id": charts, "kind": "status", "answer": None})
    verdict = (answers.dropna(subset=["answer"]).drop_duplicates(["visit_id", "answer"])
               [["visit_id", "answer"]].assign(kind="verdict"))
    q = pd.concat([status, verdict[["visit_id", "kind", "answer"]]], ignore_index=True)
    q["note_text"] = key["note_text"].reindex(q["visit_id"]).to_numpy()
    return q.sort_values(["visit_id", "kind", "answer"], na_position="first").reset_index(drop=True)


@traced
def estimate_cost(queue: pd.DataFrame, usd_per_1m_in: float, usd_per_1m_out: float,
                  system_tokens: int = SYSTEM_TOKENS, out_tokens: int = OUT_TOKENS) -> dict:
    """Tokens and US$ for judging the queue, printed (and checked against SC-005) before calling."""
    tok_in = float(sum(system_tokens + len(n) // CHARS_PER_TOKEN for n in queue["note_text"]))
    tok_out = float(out_tokens * len(queue))
    return {"calls": len(queue), "input_tokens": tok_in, "output_tokens": tok_out,
            "usd": tok_in / 1e6 * usd_per_1m_in + tok_out / 1e6 * usd_per_1m_out}


JUDGMENT_COLS = ["visit_id", "kind", "answer", "verdict", "judge_status", "quote", "gate_ok", "gate_reason",
                 "endpoint", "prompt_version", "prompt_tokens", "completion_tokens", "latency_s", "simulated",
                 "api_error"]


_JUDGMENT_DTYPES = {"visit_id": "int64", "gate_ok": "bool", "prompt_tokens": "int64", "completion_tokens": "int64",
                    "latency_s": "float64", "simulated": "bool", "api_error": "bool"}


@traced
def empty_judgments() -> pd.DataFrame:
    """A judgments table with no rows but typed columns (judge_endpoint=none)."""
    return pd.DataFrame({c: pd.Series(dtype=_JUDGMENT_DTYPES.get(c, "object")) for c in JUDGMENT_COLS})


def _spark_type(col: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(col):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(col):
        return "BIGINT"
    if pd.api.types.is_float_dtype(col):
        return "DOUBLE"
    vals = col.dropna()
    if len(vals) and all(isinstance(v, bool) for v in vals):
        return "BOOLEAN"
    if len(vals) and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in vals):
        return "DOUBLE" if any(isinstance(v, float) for v in vals) else "BIGINT"
    return "STRING"


@traced
def spark_ddl(pdf: pd.DataFrame) -> str:
    """Spark schema for a table, from pandas dtypes, so all-empty columns (no judge run) keep their type."""
    return ", ".join(f"`{c}` {_spark_type(pdf[c])}" for c in pdf.columns)


@traced
def spark_rows(pdf: pd.DataFrame) -> list[tuple]:
    """Rows as plain Python values, NaN as null."""
    return [tuple(None if pd.isna(v) else (v.item() if hasattr(v, "item") else v) for v in r)
            for r in pdf.itertuples(index=False, name=None)]


@traced
def reusable(done: pd.DataFrame | None, endpoint: str) -> pd.DataFrame | None:
    """Earlier judgments a rerun can keep: same endpoint, the current prompt for their kind, no endpoint error."""
    if done is None:
        return None
    current = done["kind"].map({"status": jg.STATUS_PROMPT_VERSION, "verdict": jg.PROMPT_VERSION})
    keep = (done["endpoint"] == endpoint) & (done["prompt_version"] == current) & ~done["api_error"].astype(bool)
    return done[keep]


def _key(r) -> tuple:
    return (int(r.visit_id), r.kind, "" if pd.isna(r.answer) else r.answer)


@traced
def run_judge(queue: pd.DataFrame, judge, endpoint: str, done: pd.DataFrame | None = None,
              trace=None) -> pd.DataFrame:
    """One judgment per queue row, in queue order. Rows already in `done` are kept, not re-asked, so a
    run cut short by rate limits resumes. A failed gate counts as not determinable (verdict) or no
    status; an endpoint error is kept with api_error=True and retried. `trace(row, verdict)` is called after each new call (MLflow on Databricks)."""
    done = reusable(done, endpoint)                   # an endpoint error isn't a judgment: ask again
    have = {_key(r): r._asdict() for r in (done.itertuples(index=False) if done is not None else [])}
    sim = bool(getattr(judge, "simulated", False))
    extra = (lambda r: {"visit_id": int(r.visit_id)}) if sim else (lambda r: {})
    rows = []
    for r in queue.itertuples(index=False):
        k = _key(r)
        if k in have:
            rows.append({c: have[k].get(c) for c in JUDGMENT_COLS})
            continue
        if r.kind == "status":
            v = judge.status(r.note_text, **extra(r))
            version = jg.STATUS_PROMPT_VERSION
        else:
            v = judge(r.note_text, r.answer, **extra(r))
            version = jg.PROMPT_VERSION
        ok = bool(v.quote_ok)
        api_error = bool(v.error) and not ok and v.input_tokens == 0   # judge.py's retry loop gave up
        rows.append({"visit_id": int(r.visit_id), "kind": r.kind, "answer": None if pd.isna(r.answer) else r.answer,
                     "verdict": None if r.kind == "status" else (v.verdict if ok else "not_determinable"),
                     "judge_status": (v.supported_status if ok else None) if r.kind == "status" else None,
                     "quote": v.quote, "gate_ok": ok, "gate_reason": v.error, "endpoint": endpoint,
                     "prompt_version": version, "prompt_tokens": int(v.input_tokens),
                     "completion_tokens": int(v.output_tokens), "latency_s": float(v.latency_s), "simulated": sim,
                     "api_error": api_error})
        if trace is not None:
            trace(r, v)
    return pd.DataFrame(rows, columns=JUDGMENT_COLS)


LEVELS = ("L1", "L2", "L3")
LEVEL_NAMES = {"L1": "easy", "L2": "medium", "L3": "hard"}   # the README's Easy / medium / hard

# The README's own column names (readme_results), so tables and the dashboard read like the README.
METRIC_LABELS = {"correct": "Correct", "incorrectly_assigned": rr.COL_ASSIGNED,
                 "incorrectly_ruled_out": rr.COL_NOT_ASSIGNED, "incorrect_stage": "Incorrect stage",
                 "no_answer": rr.COL_NO_ANSWER, "unsafe_rate": "Unsafe errors", "sensitivity": "Sensitivity",
                 "specificity": "Specificity", "ppv": "PPV", "npv": "NPV", "stage4_correct": "Stage 4 correct",
                 **{f"correct_{lv}": f"Correct: {n} note" for lv, n in LEVEL_NAMES.items()}}
STATUS_NAMES = {"healthy": "Healthy", "gingivitis": "Gingivitis", "periodontitis_stage_1": "Stage I",
                "periodontitis_stage_2": "Stage II", "periodontitis_stage_3": "Stage III",
                "periodontitis_stage_4": "Stage IV"}


def _point(ref: pd.Series, p: pd.Series, level: pd.Series, score) -> dict:
    """Every README phenotyping metric for one system against one reference, on ref's charts."""
    if ref.empty:                                    # no judge run: nothing to score against
        return dict.fromkeys(METRIC_LABELS, np.nan)
    p, level = p.reindex(ref.index), level.reindex(ref.index)
    ok = (p == ref)                                  # no status is wrong, as in the README
    s4 = ref == STAGE4
    bd = rr.breakdown(ref, p)                        # the README's five outcomes, adding to 1
    return {"correct": bd["correct"], "incorrectly_assigned": bd["dx_said_yes"],
            "incorrectly_ruled_out": bd["dx_said_no"], "incorrect_stage": bd["stage"], "no_answer": bd["no_answer"],
            "unsafe_rate": unsafe_rates(ref, p)["unsafe_rate"], **rr.yes_no(ref, p, score),
            "stage4_correct": ok[s4].mean() if s4.any() else np.nan,
            **{f"correct_{lv}": ok[level == lv].mean() if (level == lv).any() else np.nan for lv in LEVELS}}


def _judge_status(judgments: pd.DataFrame) -> pd.Series:
    st = judgments[(judgments["kind"] == "status") & judgments["gate_ok"].astype(bool)]
    # at the scoring grouping (spec 032 US8: five groups), as every answer and the truth are (rr.phenotype_predictions)
    return grouped(st.set_index("visit_id")["judge_status"].dropna())


@traced
def judge_metrics(inp: dict, answers: pd.DataFrame, judgments: pd.DataFrame, n_boot: int = 1000,
                  seed: int = 0) -> pd.DataFrame:
    """One row per (system, metric): vs_truth (the README number, all 240 charts), vs_truth_judged and
    vs_judge (the charts the judge gave a status for), difference = vs_judge - vs_truth_judged, and
    n_judged. `correct` rows also carry judge-corrected accuracy among answered charts
    (Rogan-Gladen from verdicts, judge calibrated on the same charts' truth) with a 95% range."""
    truth, pred, level = rr.phenotype_predictions(inp)
    js_ = _judge_status(judgments) if len(judgments) else pd.Series(dtype=object)
    judged = truth.index.intersection(js_.index)
    score = rr._shared_scorer()
    vd = judgments[judgments["kind"] == "verdict"].copy()
    vd["verdict"] = vd["verdict"].astype(object)
    vd["truly_correct"] = (vd["answer"].to_numpy() == truth.reindex(vd["visit_id"]).to_numpy())
    vd["gate_ok"] = vd["gate_ok"].astype(bool)
    by_pair = vd.set_index(["visit_id", "answer"])
    rows = []
    for s, p in pred.items():
        t_all = _point(truth, p, level, score)
        t_j = _point(truth.loc[judged], p, level, score)
        j = _point(js_.loc[judged], p, level, score)
        a = answers[(answers["system"] == s)].dropna(subset=["answer"])
        sample = by_pair.reindex(pd.MultiIndex.from_frame(a[["visit_id", "answer"]]))[["verdict", "gate_ok"]]
        ca = (corrected_accuracy(sample.reset_index(drop=True), vd.reset_index(drop=True), n_boot=n_boot, seed=seed)
              if len(sample) and len(vd) else {"accuracy_est": np.nan, "ci_low": np.nan, "ci_high": np.nan})
        # Rogan-Gladen assumes the judge errs at the same rate for every system; on synthetic charts we can
        # check it per system: of this system's right answers, the share called correct, and of its wrong
        # answers, the share called incorrect (judged verdicts only), and the raw share called correct.
        sv = sample.reset_index()
        has_verdict = (sv["verdict"].isin(["correct", "incorrect"]) & sv["gate_ok"].fillna(False).astype(bool)).to_numpy()
        right = (sv["answer"].to_numpy() == truth.reindex(sv["visit_id"]).to_numpy())
        said_ok = (sv["verdict"] == "correct").to_numpy()
        share = lambda x, m: float(x[m].mean()) if m.any() else np.nan
        check = {"judged_correct": share(said_ok, has_verdict),
                 "verdict_sensitivity": share(said_ok, has_verdict & right),
                 "verdict_specificity": share(~said_ok, has_verdict & ~right)}
        for k in t_all:
            rows.append({"system": s, "metric": k, "vs_truth": t_all[k], "vs_truth_judged": t_j[k],
                         "vs_judge": j[k], "difference": j[k] - t_j[k], "n_judged": len(judged),
                         **({"corrected_accuracy": ca["accuracy_est"], "ci_low": ca["ci_low"], "ci_high": ca["ci_high"],
                             **check} if k == "correct" else {})})
    out = pd.DataFrame(rows, columns=["system", "metric", "vs_truth", "vs_truth_judged", "vs_judge", "difference",
                                      "n_judged", "corrected_accuracy", "ci_low", "ci_high", "judged_correct",
                                      "verdict_sensitivity", "verdict_specificity"])
    out.insert(1, "group", out["system"].map(rr.phenotype_group))
    out.insert(3, "metric_label", out["metric"].map(METRIC_LABELS))
    return out


@traced
def judge_agreement(inp: dict, judgments: pd.DataFrame, n_boot: int = 1000, seed: int = 0) -> pd.DataFrame:
    """The judge's own status against the truth, overall and per truth status and note difficulty: n
    charts, coverage (share it gave a status for), agreement where it did (95% bootstrap range), kappa."""
    truth, _, level = rr.phenotype_predictions(inp)
    js_ = (_judge_status(judgments) if len(judgments) else pd.Series(dtype=object)).reindex(truth.index)
    rng = np.random.default_rng(seed)
    groups = [("all", "all", truth.index == truth.index)]
    groups += [("truth_status", v, (truth == v).to_numpy()) for v in sorted(truth.unique())]
    groups += [("difficulty", v, (level == v).to_numpy()) for v in LEVELS]
    rows = []
    for g, v, mask in groups:
        t, j = truth[mask], js_[mask]
        has = j.notna()
        ok = (j[has] == t[has]).to_numpy()
        boot = [ok[rng.integers(0, len(ok), len(ok))].mean() for _ in range(n_boot)] if len(ok) else []
        lo, hi = np.percentile(boot, [2.5, 97.5]) if boot else (np.nan, np.nan)
        label = ("All charts" if g == "all" else STATUS_NAMES.get(v, v) if g == "truth_status"
                 else f"{LEVEL_NAMES[v].capitalize()} note")
        rows.append({"group": g, "value": v, "label": label, "n": int(mask.sum()), "coverage": float(has.mean()),
                     "agreement": float(ok.mean()) if len(ok) else np.nan, "ci_low": float(lo), "ci_high": float(hi),
                     # within one true status the truth doesn't vary: kappa is undefined there, not 0
                     "kappa": cohen_kappa(t[has], j[has]) if len(ok) and g != "truth_status" else np.nan})
    return pd.DataFrame(rows)


@traced
def judge_run_summary(judgments: pd.DataFrame, usd_per_1m_in: float, usd_per_1m_out: float) -> pd.DataFrame:
    """What a judge run cost and how fast it was, per call type (status, verdict) and overall: calls,
    endpoint errors, quote-gate failures, tokens, US$ at the endpoint's list price (also per chart), and
    latency (mean, median, 95th percentile) over calls the endpoint answered."""
    rows = []
    for kind, g in [*judgments.groupby("kind", sort=True), ("all", judgments)]:
        err = g["api_error"].astype(bool)
        lat = g.loc[~err, "latency_s"].astype(float)
        tin, tout = float(g["prompt_tokens"].sum()), float(g["completion_tokens"].sum())
        usd = tin / 1e6 * usd_per_1m_in + tout / 1e6 * usd_per_1m_out
        charts = g["visit_id"].nunique()
        rows.append({"kind": kind, "calls": len(g), "charts": charts, "endpoint_errors": int(err.sum()),
                     "gate_failures": int((~g["gate_ok"].astype(bool) & ~err).sum()),
                     "prompt_tokens": tin, "completion_tokens": tout, "usd": usd,
                     "usd_per_chart": usd / charts if charts else np.nan,
                     "latency_mean_s": lat.mean() if len(lat) else np.nan,
                     "latency_p50_s": lat.quantile(0.5) if len(lat) else np.nan,
                     "latency_p95_s": lat.quantile(0.95) if len(lat) else np.nan})
    return pd.DataFrame(rows)
