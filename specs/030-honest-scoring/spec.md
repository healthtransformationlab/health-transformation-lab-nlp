# Feature Specification: say plainly what a synthetic score means

**Feature Branch**: `feat/387-030-honest-scoring`
**Created**: 2026-10-31
**Status**: Draft
**Input**: The owner noticed that the synthetic answer key looks more accurate than any real evaluation could be, which isn't logical.

## Why

PerioBench scores every method against the generator's truth: the repo's own 2017 rules (`labels.py`) applied to
measurements the generator invented. That truth is right by construction. A synthetic score therefore shows how
well a method recovers our rules through the noise we added. It doesn't show how often a method is right about real
patients. Nobody knows that without a reference standard on real records. Two things make the gap worse, and the
leaderboard doesn't show either:
- **Rule-based methods share the answer key's rules.** The keyword rules, the rules baseline, the rule phenotypes,
  the "+ stage 4 rule" hybrids, and the probing chart and radiograph read alone all turn measurements into a status
  with `labels.py`, the same rules that made the truth. They start with an advantage that real data won't give them.
- **Some records can't be staged.** 13 of the 240 review charts have no probing chart and no radiograph. Staging
  needs attachment loss or bone loss, so on those records a method "right" against the truth is guessing from what
  the note says.

## User Scenarios & Testing

### User Story 1 - Say plainly what a synthetic score means (Priority: P1) #387

A reader of the leaderboard, the decks or the website can tell, without asking:
- what a synthetic score measures, and what it doesn't;
- which methods share the answer key's rules;
- how each method does on records that can be staged and on records that can't;
- how real records would be scored (specialist review, model agreement against specialist-to-specialist
  agreement, `cannot_determine`), and what a low-cost reference on real data could be.

**Independent Test**: the stageable split's numbers match by hand on a small case, R matches Python, every
leaderboard row carries the flag, and the page exists and is linked from the leaderboard.

**Acceptance Scenarios**:

1. **Given** a review chart with neither a probing chart nor a radiograph, **Then** it is "not_stageable", and
   every other chart is "stageable".
2. **Given** the ladder predictions, **When** `28_ladder_vs_truth.py` runs, **Then** `ladder_by_stageable.csv`
   gives each method's n and accuracy on each group, and `r/tests/test_parity.R` gets the same numbers from R.
3. **Given** the leaderboard (`docs/results.md`), **Then** every method that uses the answer key's rules is marked,
   and the page explaining scoring is linked from its header.

### Edge Cases

- A method that answers `cannot_determine` or nothing on a chart counts as wrong against the truth, as now. The
  split shows where that happens.
- The flag is about how a method works, not how well it does. A rule method can still score lower.

## Requirements

- **FR-001** `ladder_eval.stageable(key)`: "stageable" when the chart has a probing chart (`probing_chart` isn't
  `unknown`) or a radiograph (`rad_present` is 1), else "not_stageable".
- **FR-002** `ladder_eval.uses_answer_key_rules(method)`: true for `note_rules`, `rules_baseline`, any `+rules4`
  hybrid, `algorithm_v0`, `algorithm_design`, `probing_chart` and `radiograph_ai`.
- **FR-003** `28_ladder_vs_truth.py` writes `data/datasets/ladder/ladder_by_stageable.csv` (method, stageable_code,
  n, accuracy) using `ladder_eval.by_difficulty`. The R twin uses `by_difficulty` in `r/R/10_ladder.R`, checked by
  `r/tests/test_parity.R`.
- **FR-004** The leaderboard marks rule-sharing methods and links `docs/scoring.md` from its header. The Hugging
  Face results card and the website say the same thing in short form.
- **FR-005** `docs/scoring.md` explains, in plain words:
  - synthetic scoring is agreement with the synthetic answer key, not accuracy;
  - real scoring follows OHDSI's acceptance test, already built (`reliability.agreement_vs_humans`);
  - `cannot_determine` is a reviewer answer, reported apart;
  - a low-cost reference: a chart-derived reference on fully charted records, plus a small review by people
    already involved.

## Success Criteria

- **SC-001** No synthetic score is called "accuracy" on the website or the scoring page without saying it is
  agreement with the synthetic answer key.
- **SC-002** R parity covers the stageable split.

## Out of scope

- Changing the answer key or the six labels. The truth stays as it is; the split and the flag say how far to trust
  it.
- Paying for a reviewer panel.
