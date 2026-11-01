"""PerioBench as a Kaggle Benchmarks task (the `kaggle-benchmarks` SDK, `import kaggle_benchmarks as kbench`).

What the SDK adds over our own ladder: one `llm.prompt()` call for every model behind Kaggle's model
proxy, a run file per note that the Kaggle leaderboard reads, and a leaderboard Kaggle keeps up to date as
new models ship. What stays ours: the reader prompt (`llm_reader`), the quote gate (`parse_answer`), the
judge prompt and gate (`judge`), the six labels, and the metrics of `eval/score.py`.

Three tasks, smallest first:

- `read_note`: one note in, one JSON answer out, checked against the answer key (exact) and the quote gate.
- `judge_note`: the same note and answer shown to a second model, the judge, with our `judge.SYSTEM` prompt;
  passes when the judge says the note supports the answer and quotes it verbatim.
- `perio_bench`: `read_note` over the whole review set (optionally `judge_note` too), scored with the
  `eval/score.py` metrics. This is the task to push and `%choose` for the leaderboard.

Install with `pip install -e ".[kbench]"`. The SDK imports without credentials; `kbench.llm` only needs
them when prompted, so the tests below run on a scripted model.
"""

# No `from __future__ import annotations` here: the SDK reads each task's real return annotation
# (`-> dict`, `-> float`) to pick how the leaderboard scores it; a string annotation breaks that.
import hashlib
import json
from collections.abc import Callable
from typing import Any

import kaggle_benchmarks as kbench
import pandas as pd
import pydantic
from kaggle_benchmarks import actors
from kaggle_benchmarks.llm_messages import LLMMessage
from sklearn.metrics import f1_score

from . import judge as judge_rules
from . import llm_reader
from .labels import LABELS
from .paths import DATASETS_DIR
from .telemetry import traced

PERIO = {lab for lab in LABELS if lab.startswith("periodontitis")}
REVIEW_KEY = DATASETS_DIR / "answer_key" / "review_key.csv"
EVAL_COLUMNS = ["visit_id", "note_text", "truth_status", "difficulty"]
TASK_VERSION = 1


# ---------------------------------------------------------------- data
@traced
def eval_frame(path=REVIEW_KEY, n: int | None = None, seed: int = 0) -> pd.DataFrame:
    """The review set (240 synthetic charts, answer key included) as the SDK wants it: one row per
    evaluation, columns become the task's keyword arguments. `n` takes a seeded sample."""
    df = pd.read_csv(path)[EVAL_COLUMNS]
    if n is not None:
        df = df.sample(n=min(n, len(df)), random_state=seed)
    return df.reset_index(drop=True)


# ---------------------------------------------------------------- prompts
@traced
def reader_prompt(note_text: str, variant: str = llm_reader.DEFAULT_VARIANT) -> str:
    """Our reader's system and user messages as the single string `llm.prompt()` takes."""
    system, user = llm_reader.PROMPTS[variant], llm_reader.USER.format(note=note_text)
    return f"{system}\n\n{user}"


class JudgeVerdict(pydantic.BaseModel):
    """The judge's JSON (`judge.SYSTEM`), as the structured output the SDK asks the judge model for."""

    verdict: str
    supported_status: str | None = None
    quote: str = ""
    rationale: str = ""


@traced
def judge_prompt(criteria: Any, response_text: str) -> str:
    """`prompt_fn` for `assess_response_with_judge`: `criteria` carries the note (one item), `response_text`
    the predicted status. The SDK's default prompt is for free text; ours is the audited reader's rubric."""
    (note_text,) = tuple(criteria)
    return f"{judge_rules.SYSTEM}\n\n{judge_rules.USER.format(note=note_text, pred=response_text)}"


# ---------------------------------------------------------------- tasks
@kbench.task(name="perio-bench-read-note", version=TASK_VERSION, store_task=False)
@traced
def read_note(llm, visit_id: int, note_text: str, truth_status: str, difficulty: str = "") -> dict:
    """Read one synthetic dental note and name its periodontal status (2017 AAP/EFP), as JSON with a
    verbatim quote. Exact check against the answer key; the quote gate must pass."""
    raw = llm.prompt(reader_prompt(note_text))
    out = llm_reader.parse_answer(raw if isinstance(raw, str) else json.dumps(raw), note_text)
    predicted = out["status"]
    kbench.assertions.assert_true(out["gate_ok"], expectation=f"quote gate: {out['error'] or 'ok'}")
    kbench.assertions.assert_equal(truth_status, predicted,
                                   expectation="status should match the answer key")
    return {
        "visit_id": int(visit_id),
        "difficulty": difficulty,
        "truth_status_code": truth_status,
        "predicted_status_code": predicted,
        "is_correct": predicted == truth_status,
        "is_gate_ok": bool(out["gate_ok"]),
        "is_perio_truth": truth_status in PERIO,
        "is_perio_predicted": predicted in PERIO,
        "error_text": out["error"],
    }


@kbench.task(name="perio-bench-judge-note", version=TASK_VERSION, store_task=False)
@traced
def judge_note(judge_llm, visit_id: int, note_text: str, predicted_status_code: str | None) -> dict:
    """Show the note and the predicted status to a judge model with our judge prompt. Passes when the
    verdict is `correct` and the judge's quote is in the note (our `judge.gate`)."""
    row = {"visit_id": int(visit_id), "verdict_code": "no_answer", "is_judge_ok": False,
           "is_judge_gate_ok": False}
    if predicted_status_code is None or pd.isna(predicted_status_code):
        return row
    report = kbench.assertions.assess_response_with_judge(
        criteria=[note_text], response_text=predicted_status_code, judge_llm=judge_llm,
        prompt_fn=judge_prompt, output_schema=JudgeVerdict)
    if report is None:
        kbench.assertions.assert_fail(expectation="judge should answer with the verdict JSON")
        return row | {"verdict_code": "no_judge_answer"}
    out = report.model_dump()
    gate_ok, reason = judge_rules.gate(note_text, out)
    verdict = out["verdict"] if gate_ok else "not_determinable"
    kbench.assertions.assert_true(gate_ok, expectation=f"judge quote gate: {reason or 'ok'}")
    kbench.assertions.assert_equal("correct", verdict, expectation="judge should support the answer")
    return row | {"verdict_code": verdict, "is_judge_ok": verdict == "correct", "is_judge_gate_ok": gate_ok}


@traced
def score_rows(rows: pd.DataFrame) -> dict:
    """The `eval/score.py` metrics on the per-note rows of `read_note` (parity test: `test_kbench.py`).
    Primary metric first: for screening, the miss is the costly error."""
    truth, pred = rows["truth_status_code"].tolist(), rows["predicted_status_code"].tolist()
    t, p = rows["is_perio_truth"].to_numpy(bool), rows["is_perio_predicted"].to_numpy(bool)
    tp, fn, tn, fp = int((t & p).sum()), int((t & ~p).sum()), int((~t & ~p).sum()), int((~t & p).sum())

    def ratio(a, b):
        return (a / b) if b else None

    out = {
        "sensitivity": ratio(tp, tp + fn),
        "specificity": ratio(tn, tn + fp),
        "ppv": ratio(tp, tp + fp),
        "npv": ratio(tn, tn + fn),
        "macro_f1": float(f1_score(truth, pred, labels=LABELS, average="macro", zero_division=0)),
        "accuracy": float(rows["is_correct"].mean()),
        "gate_ok_ratio": float(rows["is_gate_ok"].mean()),
        "n": len(rows),
    }
    if "is_judge_ok" in rows:
        out["judge_ok_ratio"] = float(rows["is_judge_ok"].mean())
    return out


@kbench.task(name="perio-bench", version=TASK_VERSION)
@traced
def perio_bench(llm, df: pd.DataFrame, judge_llm=None, n_jobs: int = 2, timeout: float = 180) -> dict:
    """PerioBench: finding gum disease in dental records (phenotyping). `read_note` over the review set,
    `judge_note` on each answer when a judge is given, then the `eval/score.py` metrics."""
    with kbench.client.enable_cache():
        runs = read_note.evaluate(llm=[llm], evaluation_data=df, n_jobs=n_jobs, timeout=timeout,
                                  on_failure="continue", max_attempts=2, retry_delay=5)
    rows = pd.DataFrame(list(runs.completed_runs.as_dataframe()["result"]))
    if judge_llm is not None and len(rows):
        with kbench.client.enable_cache():
            judged = judge_note.evaluate(
                judge_llm=[judge_llm], n_jobs=n_jobs, timeout=timeout, on_failure="continue",
                evaluation_data=rows.merge(df[["visit_id", "note_text"]], on="visit_id")
                                    [["visit_id", "note_text", "predicted_status_code"]])
        verdicts = pd.DataFrame(list(judged.completed_runs.as_dataframe()["result"]))
        rows = rows.merge(verdicts, on="visit_id", how="left")
        rows["is_judge_ok"] = rows["is_judge_ok"].fillna(False).astype(bool)
    out = score_rows(rows)
    out["errored_count"] = len(runs.errored_runs)
    out["reader_name"] = getattr(llm, "name", "")
    out["is_simulated"] = isinstance(llm, ScriptedReader)
    return out


@kbench.task(name="perio-bench-sensitivity", version=TASK_VERSION)
@traced
def perio_bench_sensitivity(llm, df: pd.DataFrame) -> float:
    """PerioBench's primary metric alone, for a leaderboard that scores one number."""
    return float(perio_bench(llm, df)["sensitivity"] or 0.0)


# ---------------------------------------------------------------- dry runs (simulated, never a result)
class ScriptedReader(actors.LLMChat):
    """A stand-in model for tests and dry runs: answers come from `script(prompt_text)`.
    Named `sim:...` and flagged `is_simulated`, as AGENTS.md asks of every simulated output."""

    def __init__(self, script: Callable[[str], str], name: str = "sim:scripted-reader", **kw):
        super().__init__(name=name, **kw)
        self.script, self.prompts = script, []

    @traced
    def invoke(self, messages, tools=None, **kwargs):
        text = "\n".join(str(getattr(m, "content", m)) for m in messages)
        self.prompts.append(text)
        return LLMMessage(sender=self, content=self.script(text))


@traced
def answer_key_script(df: pd.DataFrame, wrong_every: int = 0, seed: int = 0) -> Callable[[str], str]:
    """A script that answers from the answer key (every `wrong_every`-th note one stage off), quoting
    the note's own decisive line, for dry runs of the whole task without a model."""
    by_note = {r.note_text: r.truth_status for r in df.itertuples()}
    stage = {lab: i for i, lab in enumerate(LABELS)}

    def script(prompt_text: str) -> str:
        note = prompt_text.rsplit("<<<\n", 1)[1].split("\n>>>", 1)[0]
        status = by_note.get(note, LABELS[0])
        digest = int(hashlib.sha256(f"{seed}:{note}".encode()).hexdigest()[:8], 16)
        if wrong_every and digest % wrong_every == 0:
            status = LABELS[(stage[status] + 1) % len(LABELS)]
        return llm_reader.target_answer(note, status)

    return script


@traced
def judge_script(df: pd.DataFrame) -> Callable[[str], str]:
    """A scripted judge for dry runs: `correct` when the shown status matches the answer key."""
    by_note = {r.note_text: r.truth_status for r in df.itertuples()}

    def script(prompt_text: str) -> str:
        note = prompt_text.rsplit("<<<\n", 1)[1].split("\n>>>", 1)[0]
        pred = prompt_text.rsplit("Predicted status: ", 1)[1].split("\n", 1)[0].strip()
        truth = by_note.get(note)
        quote = next((ln for ln in note.splitlines() if ln.strip()), "")
        return json.dumps({"verdict": "correct" if pred == truth else "incorrect",
                           "supported_status": truth, "quote": quote, "rationale": "simulated"})

    return script
