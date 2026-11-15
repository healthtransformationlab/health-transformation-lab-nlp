---
pr: 800
branch: docs/755-040-runs-on-colab
title: "Spec 040: run its GPU work on Colab first, to save the Kaggle hours"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-15
reviewer: the authoring session (docs only; each name and figure checked against main)
verdict: approve
---

# PR Review: Spec 040: run its GPU work on Colab first, to save the Kaggle hours

## Summary
Docs only. Spec 040's plan, spec and tasks now send its GPU runs to Colab first, as the owner asked on November 15,
2026 and as `AGENTS.md` ("The Kaggle GPU hours are rationed") already requires for a question that does not depend
on the competition's hardware. Nothing runs. Nothing blocking.

## Checks
| Check | Result |
|---|---|
| The runner's flags | `kaggle/official_agent_run.py` defines `--colab`, `--batch` and `--label` (lines 940-957 on `main`) |
| The Colab path | `kaggle/official_agent_bundle.py`, `kaggle/colab_official.py` and `kaggle/colab_official_agent.ipynb` exist on `main`; the helper's docstring says it runs the same kernel from a sealed bundle |
| ADR 0005 | `docs/adr/0005-colab-runs-need-the-open-network-accepted.md`: a run starts only with `"network_open_acknowledged": true` on its own branch |
| L4 cost | 140 GPU-seconds a task (`colab-statement-l4`, `official_agent_runs/README.md`); 0.83 USD an hour (`ops/cost_settings.yaml`, `l4_usd_per_gpu_hour`); (1,800 + 60 + 270) x 140 s = 82.8 h; x 0.83 = 68.7 USD |
| Pilot | 60 task-runs x 140 s = 2.3 L4 GPU-hours; x 76 s = 1.3 A100 GPU-hours |
| Consistent with the rules | `AGENTS.md`: Colab for a question about why or whether, Kaggle's four L4s only where the competition's hardware matters, each Kaggle GPU run on the owner's yes; pull request 798 (ADR 0007, waiting for the owner) says the same |
| Wording, names, order | `test_wording`, `test_no_org_references`, `test_bench_order`: 37 passed |
| Line length, conventions | no prose line over 120 characters; `pr_conventions.py` passes with `Refs #755` |

## Should fix
- Nothing before merge.
- Colab today runs batches whose bundles the runner seals; US3 must seal the injected tasks' bundle the same way.

## Secrets, Real Data and Claims Scan
Secrets: none. Real data: none. Claims: cost figures are estimates at the repository's declared prices, labelled so.
