# The competition's own verifier on this task set (November 10, 2026)

`swegemma_verification.csv` holds one row per task and patch source, from the Gemma 4 Developer Agent competition's
evaluator, `swegemma` 0.2.11: its `harness.verification.verify_task`, unmodified, in its subprocess sandbox. The
evaluator's wheel comes from the Kaggle dataset `metric/gemma-4-developer-agent-wheelhouse` and is not kept here.

| Patch | Tasks | Resolved |
|---|---|---|
| The reference patch | 113 | 93 |
| An empty patch | 113 | 0 |
| Gemma 4 E4B's saved patches (25 runs) | 25 | 2 |

**As published, the task set cannot be scored by the evaluator at all.** It puts the repository root on the import
path, and this repository's package is in `python/`, so every target test fails at import whatever the patch
(checked on three tasks with the evaluator's own command line and `--skip-agent-patch`). These rows were made on
copies of the version 3 snapshots with one file added at the root, a `conftest.py` that puts `python/` on the path.

**The 20 tasks the reference patch does not resolve:**

- 12 have tests that read `data/external/maccrobat/course/`, which the published snapshots withhold (PR 515). They
  cannot pass from a published snapshot under any verifier. `calib:oracle` resolved them because it ran from this
  repository's history, where the files exist.
- 6 have a test that starts `kaggle/prepare_kernel.py`, which imports a module beside it. The evaluator sets
  `PYTHONSAFEPATH=1`, which stops that. Our own harness does not set the flag (spec 035, "Known differences").
- 2 skip a required test here, the same two `calib:oracle` misses: one needs Postgres, one needs R.

**Agreement with our own harness (`htlnlp-harness-v1`):** the same verdict on 95 of 113 reference patches (the 18
differences are the first two groups above, always "ours yes, theirs no"), on all 113 empty patches, and on all 25
of Gemma's saved patches.

Since spec 028 US6 (#641) each snapshot carries that `conftest.py` itself (`task_graph.EVALUATOR_CONFTEST`), and the
published set holds only the tasks this table vouches for: the reference patch resolved, the empty patch not.

To repeat: install the evaluator's wheels and this repository's test dependencies (not the package itself) in one
environment, then `python kaggle/official_verify.py --tasks tasks.jsonl --snapshots-dir snapshots --submission-dir
<agent folder> --results-dir <dir> --patch oracle|null|file --out <file>` on the published files.
