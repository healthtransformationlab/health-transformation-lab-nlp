# Kaggle: free GPUs, public datasets

This folder runs the GPU work on Kaggle's free GPUs, for when Databricks Free Edition has none, and publishes
the synthetic data and results as Kaggle datasets. Everything is started from GitHub Actions, never from a
laptop, so each Kaggle run or version matches a commit. Everything on Kaggle is public: it holds synthetic
data only, and no token is ever stored in it.

## What's on Kaggle

| On Kaggle (user `jcblearning`) | What it is | Visibility; competition link | Made by (Actions tab) | Files here |
|---|---|---|---|---|
| Notebook `perio-bench-medgemma-reader` | MedGemma 1.5 4B reads the 223 review notes | public; none | *Run MedGemma on a free Kaggle GPU* | `medgemma_reader.ipynb`, `keras_to_hf.py`, `hf_config/`, `gemma3_chat_template.jinja` |
| Notebook `perio-bench-encoder-gpu` | Fine-tunes the large encoders (ModernBERT-large, Longformer, GatorTron) | public; none | *Fine-tune the GPU encoders on a free Kaggle GPU* | `encoder_gpu.ipynb` |
| Dataset `perio-bench-notes` | Synthetic notes, labels, structured visits, 223-note review set and answer key | public; datasets have no link | *Publish datasets (Kaggle and Hugging Face)* | `publish.py`, `cards/notes.md` |
| Dataset `perio-bench-results` | Every model's answers on the review set, the leaderboard, the judge scorecard | public; datasets have no link | *Publish datasets (Kaggle and Hugging Face)* | `publish.py`, `cards/results.md` |
| Notebook `perio-bench-quickstart` (spec 025) | Loads both datasets, trains a baseline on a CPU in about a minute, scores it beside the leaderboard | public; none | *Publish datasets (Kaggle and Hugging Face)* | `../notebooks/perio_bench_quickstart.ipynb`, `prepare_kernel.py --job quickstart` |
| Benchmark task `perio-bench` (Kaggle Benchmarks) | The reader task Kaggle's leaderboard runs: read a note, name the status, quote it; a judge checks it (`docs/kaggle_benchmarks.md`) | public; none | *Run PerioBench on Kaggle Benchmarks* | `perio_bench_task.py`, `../python/health_transformation_lab_nlp/kbench.py` |
| Notebook `new-benchmark-task-f9ca8` | The benchmark task's backing notebook, made by `kaggle b t publish` under Kaggle's default title; left as it is, so the task keeps its notebook (`new-benchmark-task-37c04`, private, is an earlier draft) | public; none | `kaggle b t publish perio-bench` (`docs/kaggle_benchmarks.md`) | `perio_bench_task.py` |
| Model `perio-bench-note-classifier` (spec 020 US3) | The top fine-tuned note classifier, ModernBERT-base class-weighted, in transformers format (Apache 2.0) | public; models have no link | *Fine-tune the GPU encoders on a free Kaggle GPU* with `save_model` | `publish_model.py`, `cards/model.md` |
| Dataset `health-transformation-lab-coding-agent-tasks` (spec 028) | 93 coding-agent tasks mined from this repository, in the Gemma 4 Developer Agent competition's layout, each verified with its evaluator | public; datasets have no link | *Publish the task set (Kaggle)* | `publish_tasks.py`, `cards/tasks.md` |
| Notebook `coding-agent-tasks-quickstart` (#535) | Loads the task set and walks through one task: its problem, fix and tests, its snapshot, its code graph and embeddings; cited in the Paper Track writeup | public; **Gemma 4 Developer Agent**, set by hand (below) | *Publish the task set (Kaggle)* | `../notebooks/agent_tasks_quickstart.ipynb`, `prepare_kernel.py --job tasks-quickstart` |
| Notebooks `htlnlp-run-*`, `htlnlp-offrun-*`; datasets `htlnlp-agent-*`, `htlnlp-official-*` | One per agent run (this repository's harness, and the competition's evaluator): the evidence behind the run tables in `data/tasks/` | private; none (an evaluator run attaches the competition's data instead) | a session: `../python/scripts/60_kaggle_agent.py`, `official_agent_run.py` | deleted after the Paper Track is judged (#720) |

**Linking a notebook to a competition.** On the notebook's page: **Settings → Competitions → Link to Competition**
(only competitions the account has joined are listed), then **Link** and **Save Changes**. It is done by hand: Kaggle's
API has no field for it (the save-kernel request in Kaggle CLI 2.2.5 sets competition *data sources*, which attach a
competition's files, not the link), so `kernels push` cannot set or keep it. Datasets and models have no competition
link. The column above is the record of which link each notebook should have; a notebook pushed under a new name
needs its link set again.

The notebook `dental-omop-medgemma-keras-test` was a one-off comparison (MedGemma through Keras vs converted to
transformers; the decision is in PR #99) and can be deleted.

**Renamed in spec 022.** Kaggle can't rename a notebook or dataset, so the next run of each workflow creates it
under the new name. Then delete the old ones on kaggle.com (each page's ⋮ menu → *Delete*): the notebooks
`health-transformation-lab-medgemma-reader` and `dental-omop-encoder-gpu`, the datasets
`synthetic-dental-perio-notes` and `dental-perio-benchmark-results`, and the collection "Dental OMOP NLP".

## One-time setup

1. Kaggle account with a **verified phone number** (needed for GPUs and internet).
2. Kaggle → Settings → API → **Generate New Token**. Save it as the secret `KAGGLE_API_TOKEN`, and your Kaggle
   username as the variable `KAGGLE_USERNAME`, in the GitHub environment **`dev`** (repo Settings → Environments).
   Delete the token on Kaggle when you no longer need it.

No Hugging Face token: MedGemma comes from Kaggle Models (`keras/medgemma`) and is converted on Kaggle; the
encoders are public.

## Running the GPU notebooks

Actions → pick the workflow → **Run workflow**:

- **`limit` 10** is a test (10 notes; encoders train 1 epoch). It takes 10-15 minutes and is never committed.
- **`limit` 0** is the full run: every review note, a few hours. With `open_pr` on, the workflow opens a pull
  request with `ai_predictions_<model>.csv` (and `llm_details_` for MedGemma). Once it's merged, the dev
  deploy's **Load results** job puts them in the Delta tables (spec 016).
- If it runs longer than the workflow can wait, run again with **`collect_only`** to fetch the outputs of the
  last Kaggle run.

The workflow prints the end of the Kaggle log (`show_log.py`) and keeps the outputs as an artifact.

## Publishing the datasets

Actions → *Publish datasets (Kaggle and Hugging Face)* → Run workflow, with `platform` `both` or `kaggle`
and `dataset` `both`, `notes` or `results`. With `both` datasets, it also pushes the quickstart notebook and
waits for its run on Kaggle (a minute or two), which proves it works there. The same datasets go to Hugging Face
from the same workflow ([huggingface/README.md](../huggingface/README.md)). The first run creates
each dataset, public and CC BY 4.0; later runs add a version that names the commit. `publish.py` lists
exactly which files go in. Nothing from `data/external/` (others' datasets) and no `simulated_*` file is ever
included. The cards in `cards/` become the dataset pages; edit them there, not on kaggle.com, or the next
version overwrites your edit.

Each dataset declares a semantic version and a changelog in `dataset_docs.yaml` (spec 039, #707). A test
(`python/tests/test_kaggle_dataset_docs.py`) hashes the files and columns each dataset publishes and fails when they
no longer match the declared `schema_sha256`. When it fails, bump `version`:

- MAJOR for a removed, renamed or retyped column or a removed file;
- MINOR for a new file or column;
- PATCH for values, rows or a fix with no schema change.

Add its line at the top of `changelog` (`"X.Y.Z — what changed"`) and set `schema_sha256` to the hash the failure
gives. The test catches only file and column changes; bump PATCH yourself when changed values matter to users.

Every build also writes `manifest.json` into the dataset (spec 039, #708): its slug and version, the commit it was
built from, when it was built, and each file's SHA-256, size and, for CSV and JSONL files, row count. The same
builder (`dataset_version.write_manifest`) serves Kaggle and Hugging Face, and the cards end by pointing to it.
A new version's note is its release string, `v<X.Y.Z> — <what changed> (<commit>)`, the same message the Hugging
Face commit carries, and the run tags it `data/<slug>-vX.Y.Z` in git (and on Hugging Face). A metadata-only refresh
makes no version and no tag, and tagging a version twice changes nothing.

Kaggle drops a `+` from an uploaded file's name (#695): `ai_predictions_modernbert-base+cw.csv` in the repository is
`ai_predictions_modernbert-basecw.csv` on Kaggle. `publish.kaggle_name` gives Kaggle's form; the metadata step
matches descriptions by it, and the card lists files by it, so load a file by the name the card gives.

Kaggle's server drops the column descriptions sent through its API ([Kaggle/kaggle-cli#1207](https://github.com/Kaggle/kaggle-cli/issues/1207), #694),
so each dataset's usability stays at 9.41 until they are typed into Kaggle's editor, which keeps them.
`python kaggle/column_descriptions.py --out build/column_descriptions.html` writes every one (495 across the three
datasets) by the file name Kaggle shows, with a Copy button each. When that issue closes, a metadata-only run sends
them and this step goes away.

## Publishing the note classifier

Actions → *Fine-tune the GPU encoders on a free Kaggle GPU* → Run workflow with **`rungs`** `modernbert-base+cw`,
**`lr_overrides`** empty, **`save_model`** `modernbert-base+cw` and **`limit`** `0`. The notebook keeps that rung's
fine-tuned weights (`/kaggle/working/model`), and after the full run the workflow publishes them with
`publish_model.py`: the model `perio-bench-note-classifier` public the first time, its transformers instance
`modernbert-base-cw`, then a new version per run. The card is `cards/model.md` plus the scores of that same run's
review-set predictions (the leaderboard's scoring); a test run (`limit` 10) is never published. The weights go to
Kaggle, not the workflow artifact. A full run takes hours: to collect it later, run the workflow again with
**`collect_only`** on and the same `save_model` and `limit` 0. The card names the commit the notebook trained.
Each instance version's note is the model's release string, from its `version` and `changelog` under `models:` in
`dataset_docs.yaml`, and the folder ships `manifest.json` with every file's SHA-256 (spec 039, #730).

## The collection

A Kaggle collection is a private list: kaggle.com offers no setting to make one public, and Kaggle's API can't
make collections. So the shared starting point is the table under [What's on Kaggle](#whats-on-kaggle), and every
item there is public on its own. For your own list, on kaggle.com: your profile → **Collections** → **New
collection** "Health Transformation Lab: Perio Bench", then add the three notebooks, the two datasets and the model
`perio-bench-note-classifier` (each page's ⋮ menu → *Add to collection*). It's optional (issue #270).

## GPU hours

Kaggle's free GPU allowance is about 30 hours a week; the exact number, and how much of it is used, is on
kaggle.com under **Settings**, or from the command line (#772):

```
KAGGLE_API_TOKEN=... python kaggle/gpu_quota.py
gpu_hours used 32.34 allowed 60.00 left 27.66 refresh 2026-11-21T00:00:00 UTC
```

The hours refresh weekly, on Saturday at 00:00 UTC. With a Colab subscription linked the account showed 60 hours
allowed (November 15). Read the quota before and after every run and record the difference: that is what a run costs,
and how the rest of the week is planned (AGENTS.md, "Failures, retries and reruns"). Measured on November 15: one
23-task development-set run on four L4 GPUs took 61 minutes and **2.00 quota hours**, so a four-GPU kernel counts
double (`data/tasks/official_agent_runs/README.md`, the PR 107 run). A kernel pushed with none left is refused: "Maximum weekly GPU quota of 30.00 hours
reached." Before a run is made smaller, put off or moved to another platform, check whether Kaggle itself gives
more (AGENTS.md, "Failures, retries and reruns"):

- **A linked Colab subscription adds hours.** A Colab Pro or Pro+ subscription linked to the Kaggle account adds
  15 or 30 GPU hours a week on Kaggle, on top of the free allowance
  ([Kaggle's announcement](https://www.kaggle.com/product-announcements/575468), read November 12, 2026).
- **To link one:** open any notebook in Kaggle's editor, **File → Link to Colab**, and sign in with the Google
  account that holds the subscription. The added hours show under Settings, sometimes after a delay.
- **It can change.** Kaggle describes it as an experimental feature, for one Kaggle account per subscription
  ([Kaggle's notebook docs](https://www.kaggle.com/docs/notebooks)). Read the number under Settings before
  planning a run on it.
- **Only the account's owner can link it.** An agent asks the owner, and the issue says what was checked.

Why this is written down: on November 11, 2026 the weekly allowance ran out before a planned rerun. The run moved
to Colab, with another Python, other package versions and a notebook opened by hand, and nobody had checked for
the link first (#698).

## When something fails

| Symptom | Cause and fix |
|---|---|
| "Kaggle rejected the credentials" | Regenerate the token; check `KAGGLE_USERNAME` is the name in kaggle.com/<username>, not your email |
| Run stops at "phone verification" or has no GPU | Verify your phone on Kaggle; GPU quota is about 30 hours a week |
| "Maximum weekly GPU quota ... reached" | The week's GPU hours are spent. Before another path, see [GPU hours](#gpu-hours): a linked Colab Pro or Pro+ subscription adds 15 or 30 a week |
| Status `error` | Read the log the workflow printed; the full log is in the run's artifact |
| Still running after the wait | Run again with `collect_only` |
| The results PR has no CI | PRs opened by the workflow token don't start CI: push any commit to the branch |

## Paper Track writeups: their main-leaderboard scores

`paper_track_scores.py` (#731) downloads the full public leaderboard of `gemma-4-developer-agent` and every published
writeup of `gemma-4-developer-agent-paper`. It matches each writeup to a leaderboard team by its authors' Kaggle
usernames: an exact match, not by display name. The best-ranked team wins when an author is on more than one. A writeup
with no matched team keeps empty score cells.

```bash
pip install "kaggle>=2.2"   # the CLI and kagglesdk, which lists the writeups
KAGGLE_API_TOKEN=... python kaggle/paper_track_scores.py --out paper_track_scores.csv
```

It writes one row per writeup:
- `writeup_id`, `title`, `kaggle_url`, `authors`, `author_usernames`;
- `main_lb_team`, `main_lb_rank`, `main_lb_score`, `main_lb_entries`, `main_lb_last_submission`;
- `matched_on`, `leaderboard_taken_at`.

The public leaderboard is scored on about half the test data, so the final standings can differ, and every row says
when it was taken. The CSV is about other people's entries, so it isn't committed.

To refresh the owner's Paper Track sheets:
1. Upload the CSV to Drive as a Google Sheet.
2. Replace each sheet's *Main leaderboard (live)* tab with it, keeping the tab's name.
3. The score, team and rank columns look writeups up in that tab by `writeup_id`, so they update on their own.

## Other files

- `prepare_kernel.py` fills a notebook's settings and writes `kernel-metadata.json` (GPU, internet, the
  MedGemma model source).
- `record_results.py` copies a full run's prediction files into `data/datasets/` and notes their source in
  `results_manifest.csv`.
- `show_log.py` prints a Kaggle log without the warnings.
- `colab_official_agent.ipynb`, `colab_official.py` and `colab_official_run.json` run the competition's evaluator
  loop (`official_agent_kernel.py`, the file the Kaggle kernels run) on a Colab GPU, for when Kaggle's weekly
  allowance is spent (spec 028 AI9, #687). The notebook reads the run list, makes each run the list names for its
  GPU, and sends the log and the output to a private dataset every eight minutes, so a session that drops goes on
  from its last upload. `official_agent_run.py --colab --collect --colab-results <dataset>/<version>
  --colab-session <start>` reads one session's upload and verifies its patches. The notebook takes the Kaggle
  token from Colab Secrets (`ops/secrets_register.yaml`), never from a cell. What was run this way, and how it
  differs from a Kaggle kernel: `data/tasks/official_agent_runs/README.md`.
  **What a later run must check first** (#691): (1) the network is still open to the agent's commands: nothing
  blocks it at the machine, so a run starts only when its entry in the run list says
  `"network_open_acknowledged": true`, written on the run's own branch after reading
  [ADR 0005](../docs/adr/0005-colab-runs-need-the-open-network-accepted.md). This item of #691 (item 6) is
  documented and guarded, not fixed. (2) Each entry names its `gpu`, and a run that goes on from a session that
  dropped names that session (`"resume_session"`, the id in the earlier upload's `session.json` and at the top of its
  log); without it a session resumes only its own upload. (3) The runner is called with `--colab --batch --label`,
  and collected with `--collect --colab --colab-session <start>`; it refuses any other mix. The other items of #691
  are fixed in the helper: a refused upload is not taken for sent, the stop button ends the kernel and the uploader,
  a failed status call stops the run, a bundle is checked file by file and size by size, an arm's output leaves the
  machine once it is on Kaggle, and the audit reads every tool call.

More: `docs/medgemma.md` (why Kaggle, how MedGemma is loaded), spec 016 (results into Delta), spec 020
(publishing).
