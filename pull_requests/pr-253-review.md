---
pr: 253
branch: kaggle-results/encoders-40793202256
title: "Add GPU encoder results from Kaggle (gatortron-base, trained in float32)"
author: github-actions[bot]
reviewed_at: 2026-10-29
reviewer: coordinator verification against the Kaggle kernel log
verdict: approve
---

# PR Review: Add GPU encoder results from Kaggle (gatortron-base, trained in float32)

## Summary
This is GatorTron's full rerun after #246 fixed its divergence: the model now trains in float32 whatever its
checkpoint stores.
[Run](https://github.com/healthtransformationlab/health-transformation-lab-nlp/actions/runs/40793202256):
3 epochs at lr 2e-5, Kaggle T4s, 22 minutes of training. The predictions file is byte-identical to the
kernel's output. Approve.

## Scope of Change
- `data/datasets/ai_predictions_gatortron-base+lr2e-05.csv`: 240 rows
- `data/datasets/results_manifest.csv`: one row, `source = kaggle`, with the run URL
- Range reviewed: `origin/main..HEAD`

## Training and scores (synthetic notes; not evidence about real records)
| | failed run (run 3) | this run |
|---|---|---|
| training loss, first → last log | 3.68 → 32.3 → 7.36 | 2.86 → 0.29 |
| classes predicted | 1 | 5 |
| exact status vs answer key | 20.0% | 81.2% |

The four other encoders score 77.9–82.5%, so GatorTron now sits among them.

## Secrets, PHI and Claims Scan
Clean. Status codes and probabilities per synthetic visit id.

## Findings
None. `docs/results.md` still lists GatorTron as "diverged". The README refresh after this merge
(`scripts/28_ladder_vs_truth.py`, `35_readme_results.py`) replaces that line with its score.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets / PHI / org claims | ✅ | |
| Simulated is labelled simulated | ✅ | real fine-tuning on synthetic notes |
| Idempotent writes | ✅ | Load results is keyed by file SHA-256 |

## Verdict
approve. Merge once CI is green.
