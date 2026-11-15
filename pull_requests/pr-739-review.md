---
pr: 739
branch: docs/736-028-telemetry-design-decisions
title: "028 DOCS2: settle the telemetry-tasks design's three open questions"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-15
reviewer: the authoring session (each figure traced to its file or recomputed; no reviewer subagent run)
verdict: approve
---

# PR Review: 028 DOCS2: settle the telemetry-tasks design's three open questions

## Summary
One design document's "Open questions" section becomes "Decisions (2026-11-15)", on the owner's instruction to take
the recommended answers. 200 injected tasks with a pilot; the doctor's classification left for a later paper; the
injected tasks in a dataset of their own, the history tasks' telemetry statements beside the 93. No code, data or
settings change. Nothing blocking.

## Checks
| Check | Result |
|---|---|
| "disagree on 3, all among the 17 of the core split: 18%" | `official_agent_runs/README.md`, "Two runs of the same baseline": both resolved 3, the A100's alone 1 (`htlnlp_226`), the L4's alone 2 (`htlnlp_144`, `htlnlp_174`). "The core split": both runs resolved 0 of the other 76, so all three are in the 17. 3 / 17 = 17.6% |
| The power table and "17%, 24%, 30%", "12 points" | recomputed exactly (scratch script, not committed): disagreeing tasks Binomial(n, d); their split Binomial(D, (d + 0.10) / 2d); exact two-sided binomial test at 0.05. 150: 0.88, 0.75, 0.64, 0.56; 200: 0.96, 0.88, 0.79, 0.70; 250: 0.99, 0.94, 0.88, 0.80 at 15, 20, 25, 30% |
| "76 GPU-seconds a task", "1.87 USD an A100 hour" | the Colab cost table in `official_agent_runs/README.md` (`colab-statement`) and `ops/cost_settings.yaml` (`a100_usd_per_gpu_hour: 1.87`). 1,200 x 76 s = 25.3 h; x 1.87 = 47.4 USD |
| "21 kernels in 3.2 hours", "183 kernel-hours, six weeks" | `official_agent_runs/README.md`, "What it cost", and its 30-hour weekly allowance. 1,200 x 3.2 / 21 = 183 h; / 30 = 6.1 weeks |
| The card's sentence | `kaggle/cards/tasks.md`, quoted exactly; `tier_code` as `kaggle/dataset_docs.yaml` describes it |
| Consistent with the design | a fault no existing test catches is still dropped, not given a test; the headline is still the paired history comparison; the risks section is untouched |
| Wording, organisation names, benchmark order | `pytest -q tests/test_wording.py tests/test_no_org_references.py tests/test_bench_order.py`: 37 passed |
| Line length | no new line over 120 characters; one table row already over it on `main` is unchanged |
| Branch and issue | `docs/736-028-telemetry-design-decisions`, `Closes #736`; `pr_conventions.py` passes |

## Should fix
- Nothing before merge.
- For the spec that follows: the majority-of-three rule and the 24% threshold must be written into the
  pre-registration before the pilot runs, or they are not pre-registered.
- The 18% comes from two runs on two machines (an A100 and an L4), so it mixes run-to-run and machine-to-machine
  variation, as the README says. The pilot measures the real figure.

## Secrets, Real Data and Claims Scan
Secrets: none. Real data: none. Claims: no result is claimed; every figure is a committed one or a stated
calculation. Nothing is published and no compute runs.
