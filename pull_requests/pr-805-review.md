---
pr: 805
branch: feat/804-028-modal-gpu-path
title: "028 AI15: add Modal as a GPU path for agent runs, started from GitHub Actions"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-15
reviewer: a read-only reviewer subagent over c37c30e (rubric step 3), which installed modal 1.6.4 and read its source and that of kaggle 2.2.5; each finding then checked by the authoring session against the code before acting on it (step 4)
verdict: approve (after the second commit; the first had one blocking finding)
---

# PR Review: 028 AI15: add Modal as a GPU path for agent runs, started from GitHub Actions

## Summary
`kaggle/modal_official.py` and `.github/workflows/modal-agent.yml` run a sealed batch on a Modal GPU, through the Colab
helper's `run_one`. The reviewer found:

- **one blocking finding:** the machine had no `git`, which the evaluator diffs with;
- **eight Should-fix findings and five nits.**

While checking them, the authoring session found one more: a Modal entry in Colab's run list would be started by
Colab sessions too.

Each finding was checked against the code. Most are fixed in the second commit, each with a test that fails without
the fix. The rest are either for the owner or come later, with the trial (#804). Nothing blocking remains. Merging
starts no run.

## Scans
- **Secrets:** none. Credentials are referenced by name only, and none is written to a file or echoed.
- **PHI / real data:** none.
- **Organization claims:** none. Modal is described from its published prices, with sources.

## Findings and what was done
| # | Severity | Finding | Checked by | Outcome |
|---|---|---|---|---|
| 1 | 🔴 Blocking | The image (`debian_slim`) had no `git`, no `pkill` and no CUDA toolkit. Every task would fail at the evaluator's `git diff` after the GPU had paid for the model load. | The competition's patch extraction is `git add -N . && git diff --binary HEAD` (gemma-developer-agent `docs/rulebook-notes.md`). The helper calls `pkill` (`colab_official.py:856`). Modal's `debian_slim` installs only compilers. | Fixed. The base is now `nvidia/cuda:12.8.1-devel-ubuntu22.04` with Python 3.13, plus `apt_install("git", "procps")`. `check_machine` runs on a CPU before any GPU starts. It checks git, pkill, unshare, nvcc, Python 3.13, the packages, and the user-namespace probe the Kaggle workflow uses. Tests cover the image steps, the machine check and the order (a lack stops the run before `run_on_gpu`). |
| 2 | 🟡 Should fix | "A run stopped at the limit resumes where it stopped" was false. A new container is a new session, and `restore()` refuses another session's unfinished upload. | `session_id` (`colab_official.py:552`), `restore` (`:632`), `UPLOAD_EVERY_SECONDS = 480` | Fixed in the docstring and README. A stopped run loses up to 8 minutes and its final log; to carry on, its entry names the session in `resume_session`. |
| 3 | 🟡 Should fix | The `KAGGLE_KEY` fallback copied a legacy key into `KAGGLE_API_TOKEN`. kaggle 2.2.5 reads that name only as an access token. | the reviewer's reading of kaggle 2.2.5 | Fixed. Each Kaggle credential reaches the machine under its own name (`kaggle_secret_names`). Test. |
| 4 | 🟡 Should fix | Three checks happened only on the GPU: whether Kaggle accepts the credentials, the label's form, and the entry's `gpu` (a mismatch makes `run_one` return 0, so the run goes green with nothing done). | `run_one` (`colab_official.py:803-806, 819-820`) | Fixed. A step makes one cheap Kaggle call (`kaggle kernels list --mine --page-size 1`, as `kaggle-agent.yml` does). `plan` checks the label with the helper's `results_ref(base_label(...))`. An entry that names a `gpu` is refused, since the workflow chooses it. Tests. |
| 5 | 🟡 Should fix | The CPU and memory beside the GPU were billed with no limit. vLLM's RAM could add a third or more to the hour. | Modal's `cpu`/`memory` request-and-limit tuples (`app.py:950-956`) | Fixed. `cpu=(2, 6)` cores and `memory=(16 GiB, 32 GiB)`, priced into the cap at their limits. Modal's CPU and memory prices are in `ops/cost_settings.yaml` with a source and date. A $5 L4 run gets about 3.7 hours. Test. |
| 6 | 🟡 Should fix | (a) A second dispatch could run beside a detached run still going. (b) Cancelling the job leaves the run going. (c) Anyone with write access, or an agent's token, can start a paid run. | `modal app list` output fields (`cli/app.py:118-170`) | (a) Fixed: the `busy` step refuses while an earlier run of this app is going. Test. (b) Fixed in the workflow comment and README: `modal app stop <id>`. (c) For the owner (see Should fix). The workflow and README say an agent does not start it on its own. |
| 7 | 🟡 Should fix | `expires: unknown` is a finding by the register's own rule. AGENTS.md's credentials table has no Modal row. | `modal token info` prints "Expires at" (`cli/token.py:70`) | Partly fixed. The workflow prints the expiry without the workspace or user lines, and the register says to write it there after the first run and names `modal token new --expires-in`. The AGENTS.md row would change the rules, so it is left for the owner. |
| 8 | 🟡 Should fix | The collector records every Colab-style run as "Colab, one GPU" (`official_agent_run.py:472`), so a Modal run's rows would say Colab. | read | Documented in the README. The collector is fixed with the first Modal run's rows, which #804 already places after the trial. |
| 9 | 🟡 Should fix | "Colab is the default on cost; Modal is for speed" was a new decision stated outside `docs/adr/`. | AGENTS.md "Decisions and action items" | Fixed. The README and workflow now say ADR 0007 stands, and that when Modal is used is decided in the ADR after the trial (#804's "Done when"). |
| 10 | 🟡 Should fix (authoring session) | A Modal entry in `colab_official_run.json` would also be started by any Colab session following that list. | `follow` (`colab_official.py:419-441`) starts every listed run not yet done | Fixed. Modal has its own list, `kaggle/modal_official_run.json`, and `point_at_checkout` answers the helper's request for the Colab list with it. A test puts a different entry under the same label in a Colab list and shows Modal's is read. |
| 11 | 🔵 Nit | The Modal block never ran in the tests, and with modal installed and no Kaggle names set, importing the module raised. | the reviewer, with modal 1.6.4 installed | Fixed. Three tests load the module against a stand-in `modal` package (image, function settings, check order, `run_one`'s arguments). The offline fixture hides a real `modal`. With the real modal 1.6.4, the module imports with and without Kaggle names, and `modal run ... --help` lists `--label`, `--gpu` and `--max-usd`. |
| 12 | 🔵 Nit | `--max-usd nan` or `inf` ended in a traceback. | ran | Fixed: refused by name. Test. |
| 13 | 🔵 Nit | The 20-minute floor was no more than the kernel's own 20-minute wait for its model server. | `official_agent_kernel.py` | Fixed: the floor is 30 minutes. |
| 14 | 🔵 Nit | `kernel_url` was still fetched from the network, and `kernel_dataset` was not required. | `fetch` (`colab_official.py:684-688`) | Fixed. The entry needs a `kernel_dataset` (a sealed batch's kernel holds its key), and `run_one` gets no URL. Test (a plan carrying a URL still passes none). |
| 15 | 🔵 Nit | A secret holding a newline could add lines to `GITHUB_ENV`. | read | Fixed. Credentials come from the job's `env:` and none is written to `GITHUB_ENV`. Test. |

Mutation check: each of these eight changes makes at least one test fail:

- leaving `git` out of the image;
- `retries=1`;
- reading Colab's list;
- skipping the machine check;
- treating a detached run as stopped;
- pricing the CPU at its request;
- accepting an entry with a `gpu`;
- passing the entry's `kernel_url`.

## Residual risk
- **Whether vLLM, the evaluator's sandbox and the CUDA image run on Modal's machines** is only known from a run. The
  CPU check finds a missing tool or a sandbox that cannot start, for a fraction of a cent. A failure that needs the
  GPU shows in the two-task trial, inside the cap.
- **The prices** come from third-party pages; modal.com could not be read from the session. The cap is only as good
  as them, so check Modal's page before budgeting.
- **A run stopped at the time limit** loses its last upload interval. The kernel's own deadline is not tied to the
  limit.
- **32 GiB of memory** is a guess from the model's size. A run that runs out says so, and the limit (and so the
  hourly price) is raised in one constant.

## Compliance
| Rule | Result |
|---|---|
| Test first | Each fix in the second commit has a test that fails without it (the mutations above). |
| Settings and credentials checked before work | Credentials, entry, label and cap; one cheap call each to Kaggle and Modal; the machine on a CPU; all before the GPU. |
| Every credential in the register | Modal token; its expiry is printed by the first run. |
| Settings change by PR, naming environments | No setting changes in any environment. |
| A quota is raised before it is worked around | Modal adds paid GPU time beside Colab; Kaggle's pool is untouched. |
| Decisions in ADRs | No new decision is stated. The ADR follows the trial (#804). |
| Wording, benchmark order, organization names | Their tests pass. |

## Checks
- `tests/test_modal_official.py`: 19 passed.
- The whole suite is run before the push (see the PR thread).
- `ruff check` on both changed Python files: clean.
- With modal 1.6.4: the module imports, and `modal run --help` lists the three options.

## Should fix
- **For the owner, before relying on the workflow for paid runs:** limit who can start it. GitHub's way is an
  environment with a required reviewer (for example, a `modal` environment holding the two Modal secrets, with the
  owner as its reviewer). Or keep the Modal secrets only while a batch is planned.
- **For the owner:** add a Modal row to AGENTS.md's credentials table (this changes the rules), and write the token's
  expiry in the register after the first run.

## Secrets, Real Data and Claims Scan
Secrets: none. Real data: none. Claims: none.
