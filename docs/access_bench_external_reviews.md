# AccessBench external reviews and the consolidated recommendation (2026-11-25)

> Personal learning project, not affiliated. AccessBench questions are synthetic. The reviews below are AI models'
> opinions, kept as suggestions for the owner's review; models invent links and rules, so every resource a review names
> is checked before it enters an answer key.

On 2026-11-25 five AI models reviewed AccessBench's 15 questions, answer keys and scoring with
[the external review prompt](../benchmarks/access_bench/prompts/external_review.md): **ChatGPT, Gemini, Microsoft
Copilot, Perplexity and Grok**. Claude Code added a sixth review from the repository's data. Each review, one tab per
model with a comparison tab and the consolidated table, is in the owner's private spreadsheet:
https://claude.ai/artifact/1LCVwniS1fdEXKnkUz8hdo. ChatGPT rated the design 6.0 of 10 (concept 9, telling models
apart 4); the others gave no number.

## What the data shows (Claude Code's review)

| Measure | Value | Source |
|---|---|---|
| Key points that only check an error is absent | 30 of 75 (40%): 15 padded red flags, 15 "does not" points | the item files and `access_keypoint_judge.key_points` |
| Items marked time-sensitive | 0 of 15 | the item files |
| Live answers that tripped a red flag or were graded above S0 | 0 of 60 | runs 1051138559836529, 728325600787442, 587381582818833 |
| Answers cut off at the first 300-token limit | 37 of 60 | runs 1051138559836529, 728325600787442 |
| gpt-oss-120b answers that still filled a 1,500-token budget | 14 of 15 | run 587381582818833 |
| What the judge stores per answer | a count of points, not which | `fact_access_answer` |

## Where the reviews agree

All five: answers can score well by mentioning the right ideas without a usable next step; harm grades are unclear at
the borders; a link that opens isn't proof a resource fits; an independent second reviewer is needed and claims stay
preliminary until then; the set is too narrow. Four of five: the 19-year-old in Florida is covered by the under-21 rule
(EPSDT); state and Medicare items should be marked time-sensitive; a Medicaid member generally can't be billed for a
covered service. Three of five: remove the padded and "does not" points; remove the Healthy People OH-08 point; town
names shouldn't fail the privacy gate. Copilot and Grok keep the negative points and OH-08.

## Consolidated recommendation

| # | Recommendation | Claude's call | Lands in |
|---|---|---|---|
| 1 | Score positive actions only | adopt | spec 045 US1 |
| 2 | Report next step, coverage, resources, harm and privacy separately; no blended number | adopt | spec 045 US1 |
| 3 | A safe-next-step check: first action, whom, when, fallback | adopt | spec 045 US2 |
| 4 | Per-point verdicts with the quoted span, stored | adopt | spec 045 US2 |
| 5 | Harm grades S0-S2 with definitions and examples; privacy apart | adopt (Perplexity's three levels) | spec 045 US2 |
| 6 | Seeded control answers to test the judge | adopt | spec 045 US3 |
| 7 | Resource level by fit, not specificity | adopt; replaces PR 936's wording | spec 045 US2 |
| 8 | Privacy gate on real identifiers across the whole answer; city and state usable | adopt | spec 045 US4 |
| 9 | Time sensitivity, jurisdiction, source version and dates on every item | adopt | spec 045 US4 |
| 10 | Comparable runs: one answer budget, closed-book and tools apart, truncation recorded | adopt | batch settings |
| 11 | Answer-key fixes with 4-5 of 5 agreeing (EPSDT, balance billing, Medicaid/CHIP, VADIP, Medicare Advantage, urgent triage) | adopt | owner's review |
| 12 | Realistic red flags instead of strawmen | adopt | owner's review |
| 13 | Natural prompts (no "simulated", no MRN, no "under-21 pathway") | adopt | owner's review |
| 14 | Healthy People OH-08 point | remove from the patient's score, keep as a method note | owner's call |
| 15 | An independent second reviewer with an adjudication protocol | adopt | action item for the owner |
| 16 | Claim only preliminary judge-vs-owner agreement until then | adopt now | this page, the protocol |
| 17 | Broaden the set (contrastive pairs, more dental topics, strata by decision) | adopt gradually | spec 044 and later |
| 18-20 | Pairwise preference judging; weak baselines; publish keys and link checks with scores | later / at publication | later |
