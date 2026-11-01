---
pr: 414
branch: docs/204-024-patel-citations
title: "024 US4: correct what cites Patel et al. 2022 for the rule order"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: agent self-review against the rubric (no reviewer subagent run)
verdict: approve
---

# PR Review: 024 US4: correct what cites Patel et al. 2022 for the rule order

## Summary
This finishes spec 024 US4 (#204; T011, T012). The PMC full text (PMC9788909) was read again for this PR. Its
order is the structured diagnosis section, then clinical notes, then periodontal charting. There is no exam-form or
PSR step, and the order itself was never validated against experts.

Several places still said or implied that the exam-form-first order (`algorithm_design`) came from the paper:
- `docs/references.md` item 4 said `algorithm_design` "follows this order".
- `docs/evidence_rules.md` said it came "after Patel et al.".
- `docs/code_walkthrough.md` and the `phenotype.py` comment said the order was "not yet checked".
- `docs/action_items.md` A2 said the order "matches in outline".
- `docs/standards.md` credited the paper with the order too. It is generated, so the fix is in its builder.

Each now says the exam-form-first order is the repo's own and points to `algorithm_patel2022` for the paper's
order. This meets the US4 acceptance scenario. Approve.

## Tests
- `test_rule_order_citation.py` was extended first. All 5 tests failed on main's wording, and they now pass.
- The tests check each place and reject the old claims ("after Patel", "follows this order", "not yet checked",
  "matches in outline").
- The named suites pass (37 passed). The full suite passes too: 1201 passed, 16 skipped.

## Secrets, PHI and Claims Scan
Clean.
- **Data:** documentation and one code comment only. No data or results change.
- **Claims:** they now say less than before, and only what the paper states. The paper's own inconsistencies are
  recorded rather than resolved. The Fig. 1 figure-swap point is carried from spec 024. The figure is an image and
  could not be read as text here.
- **Wording:** the "Words" rule holds ("case finding", never the avoided phrases), and `test_wording.py` passes.

## Findings
None blocking.
- **Diagnosis codes:** the paper does report periodontal diagnosis codes, in its structured diagnosis section (M1).
  The docs now describe the repo's codes attached to done or planned procedures as the repo's own stand-in for that
  section, rather than saying the paper has no codes at all.
- **Pre-existing lint:** `ruff` reports SIM102 at `phenotype.py:92`, which is outside this change.

## Rubric
- Generated files were regenerated, not edited by hand (`standards.md` via `scripts/48_standards_doc.py`).
- No new public functions, so there is nothing new to `@traced`.
- Python/R parity is unaffected.
- `Closes #204`. The branch name follows `docs/<issue>-<slug>`.
