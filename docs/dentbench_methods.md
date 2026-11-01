# Methods reused from GlobalDentBench

Spec: [specs/002-dentbench-methods](../specs/002-dentbench-methods/spec.md).

**GlobalDentBench** (Zhao, Liang, Cai et al., [arXiv 2605.24636](https://arxiv.org/abs/2605.24636),
May 2026) evaluates 12 LLMs on 8,978 dental items from 88 countries:
licensing-exam multiple choice, textbook short answers, and 1,590 clinical
cases from published case reports. Its task differs from ours (answering
dental questions vs. reading a chart note), and its data are restricted, so we
reuse **methods, not data**.


## In plain words

**How can a wrong label be unsafe?** The label itself doesn't hurt anyone; what's done because of it
can. Every wrong label is graded by what would happen if a dentist acted on it:

| Mistake | Example | What could happen | Grade |
|---|---|---|---|
| Right, or a near miss with the same care | stage II called stage I; healthy called gingivitis | Same treatment either way | S0, safe |
| Disease missed, mild | stage I–II called gingivitis | Treatment delayed; still reversible in practice | S1, reversible harm |
| Disease missed, severe | stage III–IV called healthy or gingivitis | No referral or deep cleaning while bone keeps being lost; teeth can be lost | **S2, irreversible harm** |
| Disease that isn't there | healthy called periodontitis | Needless deep cleaning (scaling and root planing) or referral | S1 |
| Severe disease under-staged | stage III called stage II | Misses the surgical or specialist pathway | S1 |
| Over-staged by two or more | stage I called stage III | Overtreatment | S1 |

**Unsafe rate** = share of charts with an S1 or S2 mistake. Two methods with the same agreement
can differ a lot here, depending on *which* mistakes they make. This grid is a draft, pending a
periodontist's sign-off.

**Results by difficulty.** Some charts are easy: the diagnosis is written in 2017 terms and
matches the measurements (level 1). Some need translating old terms or ignoring text copied from
an earlier visit (level 2). The hardest have no written diagnosis, or one that contradicts the
chart (level 3). Agreement is reported per level, so a method that only handles easy charts
doesn't look better than it is.

**One verdict per part.** GlobalDentBench splits each answer into key points and judges each one.
Here the judge gives a separate verdict for status, grade and extent (`scripts/27_component_judge.py`),
so a prediction with the right stage but the wrong grade isn't simply "correct" or "incorrect".
Each part gets its own judge calibration (sensitivity and specificity against reviewer consensus).
Simulated dry run (not a result): the note-rules reader agrees with reviewer consensus on 81% of
statuses, 99% of grades and 93% of extents where both say periodontitis. Grade has almost no wrong
predictions to calibrate on, so its judge specificity isn't measurable yet.

Both ideas come from GlobalDentBench (a dental AI benchmark, arXiv 2605.24636), which grades AI
answers to dental questions the same way.

## What we reused

| GlobalDentBench | Here | Where |
|-----------------|------|-------|
| **Safety severity.** Every response graded S0 (safe / low-risk), S1 (potential reversible harm), S2 (potential irreversible or life-threatening harm). Unsafe rate = (S1+S2)/all | Every misclassification graded by clinical consequence (matrix below). `unsafe_rate` and `s2_rate` reported per method next to agreement | `harm.py`, `reliability.py`, `r/R/04_reliability.R` |
| **Reasoning levels.** L1 recall, L2 routine reasoning, L3 individualized reasoning; results macro-averaged across levels | Difficulty per chart: L1 diagnosis stated in 2017 terms and matches the chart; L2 must translate pre-2017 terms or ignore copied-forward text; L3 no diagnosis written, or the written one disagrees with the chart. Agreement per level plus macro average | `study.difficulty`, `reliability.by_level`, `by_level.csv` |
| **Judge selection.** Five candidate LLM judges compared on 1,800 judgments reviewed by two dentists; the one with highest dentist acceptance (98.15%) used | Judge bake-off on the human-reviewed charts: sensitivity, specificity, **kappa with bootstrap CI** per candidate; highest-kappa eligible judge is used for the corpus | `cost_effectiveness.bakeoff`, `15_judge.py`, `judge_bakeoff.csv` |
| **Key-point scoring.** Case answers decomposed into five key points, each judged covered or not | Planned: judge status, grade and extent as separate verdicts once the grade/extent readers are validated | spec 002 task T011 |
| **Expert audit of generated items.** ~30% of generated cases audited by dentists | Clinician plausibility audit of synthetic notes | spec 001 task T012 |

## What we deliberately do differently

| GlobalDentBench | Why it matters | Here |
|-----------------|----------------|------|
| The judge (Gemini-3-Flash-Preview) was also one of the 12 models evaluated; self-preference isn't discussed | A judge may favour its own family's answers | A judge of the same family as any evaluated LLM can't be selected (`same_family_as_classifier`) |
| Judge validation reported as raw percent agreement; no kappa | Percent agreement is inflated when most answers are correct | Kappa against reviewer consensus, with a bootstrap CI, plus sensitivity and specificity |
| Point estimates only; no confidence intervals | Differences between models can be within noise | Bootstrap CIs on corrected accuracy and on judge kappa |
| Severity assigned by the judge model | The severity of a wrong stage is a clinical rule, not a model opinion | Severity is a fixed matrix applied to (truth, prediction) pairs, signed off by a periodontist |

## Severity matrix (DRAFT, pending periodontist sign-off)

| Truth → Prediction | Severity | Reason |
|--------------------|:--------:|--------|
| correct | S0 | |
| healthy ↔ gingivitis | S0 | same care |
| periodontitis stage I–II called healthy or gingivitis | S1 | delayed treatment, reversible |
| periodontitis stage III–IV called healthy or gingivitis | **S2** | risk of irreversible attachment and tooth loss |
| healthy or gingivitis called periodontitis | S1 | unneeded scaling and root planing or referral |
| stage III–IV under-staged | S1 | misses the surgical / referral pathway |
| stage II called stage I | S0 | same initial care |
| over-staged by one stage | S0 | |
| over-staged by two or more | S1 | overtreatment |

## Dry-run output (synthetic, simulated reviewers and judges; not a result)

Agreement with reviewer consensus by difficulty:

| Method | L1 | L2 | L3 | Macro |
|--------|---:|---:|---:|------:|
| Note rules | 0.99 | 1.00 | 0.43 | 0.81 |
| TF-IDF | 0.87 | 0.86 | 0.83 | 0.85 |
| Rule-based algorithm v0 | 0.99 | 1.00 | 0.87 | 0.96 |

Unsafe rate: note rules 0.09, TF-IDF 0.14.

This is the kind of finding the levels make visible: rules are near-perfect
when the diagnosis is written plainly and collapse when it isn't (L3), while
the learned model is flatter across levels but makes more clinically unsafe
errors. On real notes the numbers will differ; the breakdown is what to report.

Judge bake-off (simulated candidates):

| Judge | Sensitivity | Specificity | Kappa (95% CI) | Same family as classifier | Selected |
|-------|------------:|------------:|----------------|:-------------------------:|:--------:|
| sim-judge-a | 0.96 | 0.87 | 0.83 (0.79–0.87) | no | ✓ |
| sim-judge-b (lenient) | 0.99 | 0.68 | 0.74 (0.68–0.78) | yes | |
| sim-judge-c | 0.82 | 0.85 | 0.59 (0.54–0.65) | no | |

The lenient judge would have looked best on percent agreement alone, because
most predictions are correct and it almost always says "correct". Kappa and
specificity expose it.
