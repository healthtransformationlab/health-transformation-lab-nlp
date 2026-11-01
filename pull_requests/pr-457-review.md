---
pr: 457
branch: docs/456-004-medgemma-both-versions
title: "Show both MedGemma versions on slide 4 and the README: 4B got 196, the newer 1.5 4B got 185"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: coordinator verification (wording and figures re-derived from the committed results)
verdict: approve
---

# PR Review: Show both MedGemma versions on slide 4 and the README

## Summary
The README and PerioBench slide 4 showed only MedGemma 1.5 4B's 185 of 240, while the results page shows MedGemma 4B
(v1) at 196. Both figures are real runs. Slide 4 now gives 196 for MedGemma 4B and names the newer 1.5 4B's 185, and
the notes add their scores without the rule (187 and 182). The README line does the same.

The slide footer said "CPU, 2026-10-26"; the 4B run was on Kaggle GPUs on 28 October, so the footer now covers both.
Approve.

## Scope of Change
- Files changed: 6
  - `README.md`, `docs/edr/slides/04-results.html`, `docs/claims.yaml`;
  - the rebuilt `docs/edr/deck.html` and `full_text_and_notes.md`;
  - this review.
- Area touched: docs.

## Secrets, PHI and Claims Scan
Clean.

## Deck figures (rubric step 5)
| Figure | Source | Re-derived |
|---|---|---|
| 196 | `docs/edr/README.md` row "Medical AI, untrained (MedGemma 4B) + stage 4 rule \| 196 of 240"; `ladder_vs_truth.csv` medgemma-4b-it+rules4, 0.8166667 × 240 | 196 ✅ |
| 185 | `ladder_vs_truth.csv` medgemma-1.5-4b-it+rules4, 0.7708333 × 240 | 185 ✅ |
| 187, 182 (notes) | medgemma-4b-it 0.7791667 × 240; medgemma-1.5-4b-it 0.7583333 × 240 | 187, 182 ✅ |

The wording "both close to keyword rules (189)" and "neither can be told apart" is supported. The differences from
note_rules are +0.029 (−0.004 to +0.067) and −0.017 (−0.042 to +0.008); both intervals include 0.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important)
None. The footer's run date and hardware were wrong for the 4B run; this PR fixes it.
### 🔵 Nits (Minor)
None.

## Test Coverage
- `test_deck_claims.py` passes with 196 registered.
- Full suite: 1540 passed, 15 skipped.
- Slide 4 rendered in Chromium at 1920×1080: no element overflows.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| Deck figures | ✅ | 196 registered; all figures re-derived |
| Words rule | ✅ | |
| Generated files | ✅ | Decks rebuilt with `build_decks.py` |
| Commits | ✅ | `Closes #456` |

## Verdict
Approve.
