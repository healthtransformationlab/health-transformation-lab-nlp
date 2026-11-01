# %% [markdown]
# # PerioBench on Kaggle Benchmarks
#
# Finding gum disease in dental records (phenotyping): a model reads one synthetic dental note and names
# the periodontal status (2017 AAP/EFP) as JSON with a verbatim quote. Scored on the 240-note review set
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
if kbench.kaggle.is_configured():
    llm, judge_llm = kbench.llm, kbench.judge_llm
else:
    llm = perio.ScriptedReader(perio.answer_key_script(df, wrong_every=5))
    judge_llm = perio.ScriptedReader(perio.judge_script(df), name="sim:scripted-judge")

# %%
run = perio.perio_bench.run(llm, df, judge_llm=judge_llm)
label = "SIMULATED (scripted model, not a result)" if run.result.get("is_simulated") else run.result["reader_name"]
print(f"PerioBench [{label}]")
print(json.dumps(run.result, indent=2))
run  # noqa: B018 - the SDK renders the run object in a notebook cell
