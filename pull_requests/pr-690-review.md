# PR 690 review: the experiment again on one Colab GPU, with a baseline (#687)

Reviewed against `.claude/review-rubric.md` and AGENTS.md. An independent reviewer read the range
`origin/main...64a3d1d` read-only (the helper against the evaluator's installed code, the five runs' collected
output, the tables), and each of its findings was then traced here before it was written down. The later commits
(the L4's second arm, the README section, `main` as the branch the notebook reads, the corrections below) were
checked against its numbers and re-tested.

| Check | Result |
|---|---|
| Branch `feat/687-028-colab-paired-run`, `Closes #687`; issue titled `028 AI9: ...` | ok |
| Spec: action item 9 of spec 028, with two addenda hashed on the issue before the runs they cover (`312041e8…2fc9` at 23:51 UTC on November 11, first task 02:04 UTC; `0532820a…f5cf` at 05:01 UTC on November 12, its arm at 06:06 UTC); `tasks.md` T028 | ok |
| Secrets scan over the whole diff, data files included: none. The nine 64-character strings are file hashes, each recomputed. The notebook reads the token from Colab Secrets and holds none; `ops/secrets_register.yaml` now lists that place | ok |
| Real data: none. Organisation claims and the wording rules: clean; the forbidden name is in no file but `CLAUDE.md`, no diff line and no commit message | ok |
| The counts, recomputed by the reviewer from the committed tables and not from the scripts' output: `colab-statement` 4, `colab-graph` 6, `colab-report` 4, `colab-statement-l4` 5, `colab-graph-l4` 8 of 93; in the core split 4, 6, 4, 5 and 7. Pairs: graph against statement 4, 0, 2, 87, p = 0.5; report against statement 3, 1, 1, 88, p = 1.0; the L4's 4, 1, 4, 84, p = 0.375. The three pairs files agree row by row | ok |
| No claim beyond the tests: both registered tests are above 0.05 and the README, the task entry and the issue say "no difference is claimed, and none is ruled out". The L4 pair is labelled unplanned and described; no count is added across machines | ok |
| The two-session deviation was recorded on the issue at 03:25 UTC with its rule, before any patch of either session was verified; each run was read from its own session's last upload by version and session start | ok |
| Test first: `gpu_name`, `is_for_this_gpu`, `listed_gpu`, the versioned collection, `--machine colab-l4`, `--arm report --machine colab`, the A100 price and the settings' network sentence each have a test that failed before the change | ok |
| Simulated is labelled simulated: nothing here is simulated; every count is a verified patch | ok |
| Prices: the A100's 1.87 USD an hour names its source and the day it was read (`ops/cost_settings.yaml`); the README says it is a rental estimate and that Colab is a paid subscription whose use was not read | ok |
| Configuration: no Databricks setting, job or table changes; the pull request says so | ok |
| Idempotent writes: the runner overwrites each run's tables; the helper's uploads are whole versions | ok |
| CI on `64a3d1d`: python, python-databricks-runtime, r-parity, postgres, bundle, azure-infra and the conventions check all green. Locally on the head: the whole suite at `64a3d1d` (2,488 passed, 4 skipped), then the changed tests after each later commit | ok |
| Ruff 0.17.3 on the changed Python files: the nine findings on lines this branch adds are cleared; the nine that remain are on lines `main` already has | ok |
| Merging starts no run and publishes nothing: the sessions were started by the owner and have ended, their datasets are private, the run list says stop, and the notebook and the helper now read `main` | ok |

## What the review found, and what was done

**Blocking, fixed here.** The helper, its test's description, the five runs' settings files, the README and a
comment on issue 687 all said the agent's commands had no way out: every proxy pointed at a port nothing listens
on, and pip had no index. That was set on the kernel's process. The evaluator starts each of the agent's commands
from its own short list of environment names (`_SAFE_ENV_KEYS` in `adk_eval_core`), and no proxy is on it. Traced
here: the list is PATH, LANG, LC_ALL, TERM, USER, LOGNAME, SYSTEMROOT, LD_LIBRARY_PATH, TMPDIR and TEST_TMPDIR,
and in the report arm an editable install fetched its build tools and ended with exit 0. So the network was open
to the agent's commands in all five runs. No credential is on the list either, so that half of the claim holds.

- The helper's description, the test's description and the runner's sentence (`COLAB_INTERNET`) now say what is
  so. The five settings files carry the corrected sentence and a note of the correction, and a test holds them.
- The README has a section on it, and issue 687 a correction.
- Whether it mattered was checked by reading every tool call of the five runs, 4,383 in all: three commands reach
  for the network, the three the registered audit already counted, all installs of the repository itself in two
  tasks no run resolved; nothing is downloaded or cloned; in the 27 task-runs that ended resolved no tool call of
  any kind holds a URL, a download tool, an installer or a network library. The paired tests without those pairs
  were already in the README: the same.

**A second deviation, now said.** Each finished run's output folder was set aside on the machine and not removed
(`working_before_<label>_<time>`), where addendum 2 says nothing of the first arm's is kept. Traced here in the
helper's `main` (`out.rename(...)`). No tool call of any run names a path under `/content`; the only absolute path any of the
687 commands names is `/workspace`, and none steps out of its workspace. The README says so.

**Should fix, not fixed here: issue 691.** A refused last upload reported as sent; a stop from the notebook's
button leaving the kernel going; a status call that fails read as "nothing to resume"; a bundle folder that is not
empty counting as complete; the audit being a list of words over commands alone; the runner not checking its Colab
options together. Each was reproduced by the reviewer with stand-ins. None touched these runs: no arm was
interrupted or resumed. They are defects in how the helper fails, and the helper is not to be used again before
they are closed; the run list on `main` says stop. Deferred because fixing eight failure paths with their tests is
a change of its own, and the paper this result goes into closes today.

Nothing blocking remains.

## Notes

- The network finding changes what the Colab runs are, not what they found: they are runs on a machine whose
  network the agent could have used and, by the reading of every call, did not use to fetch anything. The paper
  says the network was open. A later run that wants Kaggle's "internet off" has to block at the machine (issue 691,
  item 6).
- The registered audit's list of words was left as committed, since the addenda cite it; the wider reading is
  reported beside it and changes no test.
- `htlnlp_170` was resolved for the first time by any run, in the L4's graph arm, and `htlnlp_116` there is the
  one Colab fix outside the core split. Both are in the README. Neither is a claim.
- Two runs of the same baseline differ on three resolved tasks, and the two graph arms on two. Any later reading
  of a difference between arms on this set needs repeats before it means anything.
