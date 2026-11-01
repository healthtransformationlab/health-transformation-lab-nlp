# Feature Specification: Reuse GlobalDentBench evaluation methods

**Feature Branch**: `002-dentbench-methods`

**Created**: 2026-10-25

**Status**: Implemented (v1)

**Input**: User description: "Reference the dental bench study and see if any methods are reusable/applicable."

## Context

GlobalDentBench (Zhao, Liang, Cai et al., arXiv 2605.24636, May 2026) evaluates 12 LLMs
on 8,978 dental items, including 1,590 clinical cases. Its task is different
from ours (answering dental questions vs. reading a chart note), but four of
its evaluation methods transfer directly, and two of its gaps are worth
avoiding. Full mapping: `docs/dentbench_methods.md`.

| GlobalDentBench method | Reuse here |
|------------------------|------------|
| Safety severity S0/S1/S2 for every response; unsafe rate = (S1+S2)/all | Grade every misclassification by clinical consequence; report unsafe and S2 rates per method alongside agreement |
| Reasoning levels L1 recall / L2 routine / L3 individualized, macro-averaged | Difficulty levels per note (stated in 2017 terms / needs translation / must infer or resolve conflict); report agreement per level |
| Judge chosen from 5 candidates by dentist acceptance (2 dentists, 1,800 judgments) | Judge bake-off on the reviewed charts; pick by kappa against reviewers |
| Answers decomposed into key points, each judged covered or not | Judge status, grade and extent as separate verdicts (T011: `judge.COMPONENT_SYSTEM`, `scripts/27_component_judge.py`) |
| Expert audit of a ~30% subset of generated cases | Clinician plausibility audit of synthetic notes (spec 001 T012), sized as a share of the review set |

| GlobalDentBench gap | What we do instead |
|---------------------|--------------------|
| Judge was also an evaluated model (self-preference risk), not addressed | Judge must be a different model family from any LLM it grades; enforced as a check |
| Percent agreement only; no kappa, no confidence intervals | Kappa and bootstrap CIs for judge calibration and every method |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Harm-weighted errors (Priority: P1)

As the study lead, I want each method's errors graded by clinical consequence,
so the paper can say not just how often a method is wrong but how often it is
wrong in a way that harms a patient.

**Independent Test**: Unit tests on the severity matrix; reliability output
contains `unsafe_rate` and `s2_rate` for every method, equal in Python and R.

**Acceptance Scenarios**:

1. **Given** truth stage III, prediction gingivitis, **Then** severity S2 (missed disease with risk of irreversible tooth loss).
2. **Given** truth stage II, prediction healthy, **Then** S1.
3. **Given** truth stage IV, prediction stage III, **Then** S1 (misses the stage IV care pathway).
4. **Given** truth healthy, prediction gingivitis, **Then** S0.
5. **Given** truth gingivitis, prediction stage II, **Then** S1 (unneeded scaling and root planing).

### User Story 2 - Difficulty levels (Priority: P1)

As the analyst, I want every review chart tagged with a difficulty level, so
results show where methods break down, not just an average.

**Independent Test**: Every row of the answer key has `difficulty` in {L1, L2, L3};
the per-level agreement table matches between Python and R.

**Acceptance Scenarios**:

1. **Given** a note stating a 2017-format diagnosis that matches the chart, **Then** L1.
2. **Given** a pre-2017 diagnosis or copied-forward text, **Then** L2.
3. **Given** no diagnosis line, or a written diagnosis that disagrees with the chart, **Then** L3.

### User Story 3 - Judge bake-off (Priority: P2)

As the study lead, I want several candidate judges calibrated on the reviewed
charts and the best one chosen by agreement with reviewers, so the judge
choice is evidence-based and reported.

**Independent Test**: Dry run with three simulated judges writes
`judge_bakeoff.csv` (sensitivity, specificity, kappa, CI) and picks the one
with the highest kappa; the corpus is judged with it.

### Edge Cases

- A method that never answers (coverage 0): unsafe rate undefined, not 0.
- Reviewer consensus missing (tie): visit excluded from harm and level tables.
- A judge that is the same model family as an LLM under evaluation: flagged in the bake-off output.

## Requirements *(mandatory)*

- **FR-001**: `harm.severity(truth, pred)` MUST return S0/S1/S2 per the matrix in `docs/dentbench_methods.md`, marked DRAFT until a periodontist signs it off.
- **FR-002**: The reliability report MUST include `unsafe_rate` (S1+S2) and `s2_rate` per method, over visits where the method answered; R MUST match.
- **FR-003**: The study build MUST assign `difficulty` L1/L2/L3 per visit; reliability MUST write agreement by level per method, macro-averaged; R MUST match.
- **FR-004**: `15_judge.py` MUST support several candidate judges and a bake-off on the calibration set; `16_cost_effectiveness.py` MUST use the selected judge.
- **FR-005**: Bake-off output MUST include kappa with a bootstrap 95% CI and a same-family flag.
- **FR-006**: `docs/references.md` MUST list every paper the repo relies on.

## Success Criteria *(mandatory)*

- **SC-001**: Severity tests pass for all acceptance scenarios.
- **SC-002**: Python/R parity holds for unsafe rates and per-level agreement.
- **SC-003**: Dry run selects the simulated judge with the best calibration.

## Assumptions

- The severity matrix is a draft by analogy to GlobalDentBench's definitions
  (S1 reversible harm, S2 irreversible harm). A periodontist must review it
  before results are reported.
- GlobalDentBench's data are restricted; we reuse methods, not data.
