# PerioBench on Kaggle Benchmarks

Kaggle Benchmarks is Kaggle's framework and hosting for LLM evaluations: you write a task in Python with
their `kaggle-benchmarks` SDK, push it, and Kaggle runs it against the models behind its model proxy and
keeps a public leaderboard current as new models ship. This page says what maps to what in this repo, how
to push PerioBench there, and what the research grant asks for.

Plain words for the two terms that come up: a **benchmark** is a fixed set of test questions plus a scoring
rule, so models can be compared fairly; an **LLM judge** is a second model that grades a first model's
free-text answer against a rubric, used where no single right string exists.

## What maps to what

| Ours | Theirs | Where |
|---|---|---|
| The reader prompt (`llm_reader.PROMPTS`, `USER`) | the single string `llm.prompt()` takes | `kbench.reader_prompt` |
| The quote gate (`llm_reader.parse_answer`) | `assert_true` on `gate_ok` | `kbench.read_note` |
| Exact check against the answer key | `assert_equal(truth, predicted)` | `kbench.read_note` |
| The judge prompt and gate (`judge.SYSTEM`, `judge.gate`) | `assess_response_with_judge` with our `prompt_fn` and a pydantic schema | `kbench.judge_note` |
| 240-note review set, `review_key.csv` | `evaluation_data=` DataFrame, one row per run | `kbench.eval_frame` |
| `eval/score.py` metrics | the `dict` the top task returns (parity test to 1e-9) | `kbench.score_rows` |
| `models.yaml` model ids | `kbench.llm`, `kbench.judge_llm`, `kbench.llms[...]` from `.env` | `kaggle b init` |
| `data/results/*.csv` per run | `*.run.json` per note, read by the leaderboard | written by the SDK |
| Simulated readers (`sim:`) | `kbench.ScriptedReader`, flagged `is_simulated` | tests and dry runs |

The SDK's own `.run.json` is what their leaderboard reads, so the top-level task, `perio_bench`, returns
the metrics as a dict with the primary metric first (sensitivity: for screening, the miss is the costly
error). `perio_bench_sensitivity` returns that one number for a leaderboard that scores one value.

## Run it

```bash
cd python && pip install -e ".[dev,kbench]"
pytest -q tests/test_kbench.py                         # 15 tests, scripted models, no network
python ../kaggle/perio_bench_task.py                   # dry run: prints a SIMULATED result
```

A dry run is labelled `SIMULATED (scripted model, not a result)` and is never a number to report.

## Push it to Kaggle

Credentials come from `kaggle b init`, which writes short-lived `MODEL_PROXY_*` variables to `.env`
(re-run `kaggle b auth -y` when they expire). Their CLI docs: `kaggle benchmarks --help` and
[kaggle-cli/docs/benchmarks.md](https://github.com/Kaggle/kaggle-cli/blob/main/docs/benchmarks.md).

```bash
pip install -U kaggle kaggle-benchmarks
kaggle b init -y                                       # credentials + .env (gitignored)
set -a; . ./.env; set +a                               # the SDK only auto-loads a .env next to its own install
python kaggle/perio_bench_task.py                      # now a real model: validate before pushing
ls -1 *.run.json | head                                # run files prove the task recorded results
kaggle b t push perio-bench -f kaggle/perio_bench_task.py -d jcblearning/perio-bench-notes --wait
kaggle b t run  perio-bench -m gemini-3.5-flash --wait # repeat -m for more models; `kaggle b t models`
kaggle b t status perio-bench
kaggle b t download perio-bench -o results/kaggle-benchmarks
kaggle b t publish perio-bench                         # public task + backing notebook
```

Rules the SDK silently depends on (all checked by `tests/test_kbench.py`):

- the file starts with `# %%` cells and imports `kaggle_benchmarks as kbench`;
- the task slug `perio-bench` must match a `@kbench.task(name=...)` in the file;
- the file must call `.run(...)`: a push succeeds without it, and then nothing is recorded;
- repeat `-d jcblearning/perio-bench-notes` on every push, or the dataset is detached;
- one task per notebook feeds a leaderboard (`%choose perio_bench` as the notebook's last cell).

Per AGENTS.md ("Everything is started from GitHub Actions, never from a laptop") the same steps run from the
Actions tab: **Run PerioBench on Kaggle Benchmarks** (`.github/workflows/kaggle-benchmark.yml`), with the
`KAGGLE_USERNAME` variable and `KAGGLE_API_TOKEN` secret the publish workflow already uses. Pick `push`,
`push-and-run` (default; model slugs as an input), `run`, `status` or `publish`; with `validate` on it first runs
the task on 3 notes with the real default model and fails if no run file appears; with `wait` on it attaches the
finished runs' outputs to the workflow run. The Model Proxy credentials it fetches live only in the runner.

## Getting involved: three routes

1. **Publish the task** (free, no application). `kaggle b t publish perio-bench` after a clean run on two
   or three models. That puts PerioBench on kaggle.com/benchmarks with the dataset attached.
2. **Benchmarks Resource Grant** (compute, frontier-model access, Kaggle keeps the leaderboard updated,
   marketing). Application: the form linked from kaggle.com/research-grants. What it wants, and where we
   stand:
   - *a novel benchmark*: finding gum disease in dental records from notes with a verbatim-quote gate and
     an audited judge; no public benchmark covers it;
   - *a publishable dataset with ground truth*: `perio-bench-notes` is already public, synthetic, CC BY 4.0,
     240 reviewed charts with an answer key plus 3,484 training notes;
   - *reproducibility*: the task file, the tests, seeded data, the R parity test;
   - *why compute*: the judge doubles the calls (one read, one verdict per note), and the ladder in
     `models.yaml` is what we would want run across every proxy model.
3. **Competition grant** (hackathon or prediction competition) if the goal is a community working the
   problem rather than a standing leaderboard; the same dataset and answer key qualify.

## What their conventions give the healthtransformationlab repos

- **Sources-of-truth map in AGENTS.md.** Their AGENTS.md opens with a one-line mental model and a table of
  "this concern lives in this file". Ours now has the same section; the shared template is in
  `pipeline-doctor/AGENTS.md`.
- **Task, scoring and client stay separate.** `@kbench.task` functions prompt and assert; scoring is a
  pure function over a DataFrame of per-row dicts; the client is injected. `kbench.py` follows that split
  so the same tasks run on a scripted model, a Databricks endpoint, or Kaggle's proxy.
- **Return type decides the scoring.** `-> dict` for rich results, `-> float` for a single leaderboard
  number, `-> tuple[float, float]` for a value with its confidence interval: the annotation is the
  contract, which is why `kbench.py` does not use `from __future__ import annotations`.
- **Resilient batch evaluation.** `on_failure="continue"`, `max_attempts`, `enable_cache()`: failed
  rows are kept and retried, successes are cached; the same idea as the resumable judge queue in
  `judge_scorecard.run_judge`.
- **Skills for coding agents.** Kaggle ships `write-kaggle-benchmarks` (github.com/Kaggle/kaggle-skills)
  for Claude Code and similar; install it before editing the task file.
