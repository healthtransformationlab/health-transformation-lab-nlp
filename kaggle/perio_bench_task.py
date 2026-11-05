# %% [markdown]
# # PerioBench on Kaggle Benchmarks
#
# Finding gum disease in dental records (phenotyping): a model reads one synthetic dental note and names
# the periodontal status (2017 AAP/EFP) as JSON with a verbatim quote. Scored on the 223-note review set
# of the public `perio-bench-notes` dataset (CC BY 4.0, synthetic only) against its answer key, with a
# second model as judge. The logic lives in `health_transformation_lab_nlp.kbench`; this file is what
# `kaggle benchmarks tasks push` uploads and what the leaderboard runs.
#
# Push (from the repo root, after `kaggle b init -y`):
#
#     kaggle b t push perio-bench -f kaggle/perio_bench_task.py -d jcblearning/perio-bench-notes --wait
#     kaggle b t run perio-bench -m gemini-3.5-flash --wait
#
# Without Kaggle credentials this file still runs end to end on a scripted model and prints a
# SIMULATED result, which is never a number to report (AGENTS.md, "Label simulated output as simulated").

# %%
import json
import os
import subprocess
import sys
from pathlib import Path

import kaggle_benchmarks as kbench

# %%
# The package: already importable on a laptop (`pip install -e python[kbench]`); on Kaggle, cloned.
try:
    from health_transformation_lab_nlp import kbench as perio
except ImportError:  # pragma: no cover - the Kaggle kernel path
    PACKAGE = ("health-transformation-lab-nlp[kbench] @ git+https://github.com/healthtransformationlab/"
               "health-transformation-lab-nlp#subdirectory=python")
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", PACKAGE], check=True)
    from health_transformation_lab_nlp import kbench as perio

# %%
# The review set: the attached Kaggle dataset when there is one, else the repo's committed copy.
# `kaggle/publish.py` puts review_key.csv at the dataset root; Kaggle mounts it under the slug, or owner/slug.
candidates = [*Path("/kaggle/input").glob("**/perio-bench-notes/review_key.csv"), perio.REVIEW_KEY]
review_key = next(p for p in candidates if p.exists())
n = os.environ.get("PERIO_BENCH_N")
df = perio.eval_frame(review_key, n=int(n) if n else None)

# %%
# A dry run, without Kaggle credentials: scripted models stand in for `kbench.llm` and `kbench.judge_llm` and the
# result says SIMULATED. On Kaggle this cell does nothing.
if not kbench.kaggle.is_configured():
    kbench.llm = perio.ScriptedReader(perio.answer_key_script(df, wrong_every=5))
    kbench.judge_llm = perio.ScriptedReader(perio.judge_script(df), name="sim:scripted-judge")


# %%
# The task, in the form Kaggle's cookbook uses (#541, #547, #593): declared in this file, it calls the model it is
# given (`llm`) itself, and is run once on `kbench.llm` at the top level, so Kaggle can swap in each model added to
# the leaderboard. The judging and scoring are the package's (`perio.judge_and_score`), shared with the tests.
@kbench.task(name="perio-bench", version=perio.TASK_VERSION)
def perio_bench(llm, df, judge_llm=None) -> dict:
    """PerioBench: finding gum disease in dental records (phenotyping), scored against the answer key."""
    with kbench.client.enable_cache():
        runs = perio.read_note.evaluate(llm=[llm], evaluation_data=df, **perio.READ_OPTIONS)
    return perio.judge_and_score(llm, df, runs, judge_llm)


# %%
run = perio_bench.run(kbench.llm, df, judge_llm=kbench.judge_llm)
label = "SIMULATED (scripted model, not a result)" if run.result.get("is_simulated") else run.result["reader_name"]
print(f"PerioBench [{label}]")
print(json.dumps(run.result, indent=2))

# %%
# The leaderboard's main task. In jupytext's percent format a magic is written commented out; Kaggle's converter
# makes this line `%choose perio_bench` in the notebook.
# %choose perio_bench
