---
pr: 246
branch: fix/226-002-gatortron-fp16-weights
title: "Train the encoders in float32 whatever the checkpoint stores"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator verification (CPU reproduction with the real model)
verdict: approve
---

# PR Review: Train the encoders in float32 whatever the checkpoint stores

## Summary
This PR finds and fixes the root cause of GatorTron's divergence (#226): a float16 checkpoint trained as
float16. It's a one-line fix, with a test written first that runs without torch. The cause was reproduced
and the fix confirmed on CPU with the real `UFNLP/gatortron-base`: the loss went NaN at step 2 as loaded,
and fell to 1.50 at step 2 once cast. Approve.

## Scope of Change
- `python/health_transformation_lab_nlp/rungs.py`: `.float()` after `from_pretrained`, with the reason
- `python/tests/test_rungs_checkpoint.py`: one test with fake `transformers`/`datasets` modules
- Range reviewed: `origin/main..HEAD`

## How it was found
- The Kaggle log for GatorTron showed training loss 3.68 → 5.21 → 13.3 → 32.3 at lr 2e-5. The four other
  encoders fell from about 2.8 to 0.15–0.42 with the same trainer and GPUs.
- On CPU, the initial loss was normal (1.95 against ln 6 = 1.79). Then step 2 was NaN, in float32 maths with
  gradient clipping, so the learning rate wasn't the cause.
- A parameter scan showed every weight loaded as `torch.float16`, including the new classifier head. The
  checkpoint has no non-finite values.
- Casting to float32 removed the NaN.

## Secrets, PHI and Claims Scan
Clean.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important)
None.

### 🔵 Nits (Minor)
- `docs/results.md` still says GatorTron "diverged ... to rerun on a GPU at a lower learning rate". The
  README refresh after its results PR rewrites that line from the scores.
- The `gatortron-base=2e-5` learning-rate override was a workaround for this bug. It stays for now, so the
  rerun keeps the output name `gatortron-base+lr2e-05`. Dropping it is a separate choice.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets / PHI / org claims | ✅ | |
| Test first | ✅ | the new test failed before the fix |
| Seeds fixed | ✅ | unchanged |
| Commits | ✅ | |

## Test Coverage
`cd python && pytest -q tests`: 998 passed, 15 skipped. The Kaggle full rerun of `gatortron-base` from this
branch is the end-to-end check.

## Verdict
approve. Merge once CI is green, then the GatorTron results PR.
