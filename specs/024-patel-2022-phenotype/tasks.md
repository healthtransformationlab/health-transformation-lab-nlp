# Tasks: the PerioDx phenotype method of Patel et al. 2022 (spec 024)

Implementation starts after this spec, plan and tasks are reviewed.

## US1 #201: PerioDx Diagnoser

- [x] T001 [US1] Read Fig. 2 arrow by arrow; record each reading as a named constant or parameter, with the
  figure cited
- [x] T002 [US1] Failing tests: one chart per branch, grade not assessable, bone-loss categories
- [x] T003 [US1] `periodx.chart_status` (named for what it does, not `diagnose`: AGENTS.md "Words"); R twin `r/R/14_spec024.R`; parity inputs and check

## US2 #202: PerioDx Extractor

- [x] T004 [US2] `PERIODX_TERMS` from the 2017 classification and the synthetic note templates
- [x] T005 [US2] Failing tests: snippets with negation off and on, abbreviations, no diagnosis
- [x] T006 [US2] `periodx.note_status` (the Extractor), two steps, no new dependency

## US3 #203: stepwise phenotype, scored

- [x] T007 [US3] Failing tests: stepwise order, deciding section, section and merged completeness,
  `confusion_scores` (one-vs-rest and pooled), script 18 still 24 orderings plus one row, existing datasets
  unchanged
- [x] T008 [US3] `phenotype_patel2022`; `periodx_visits.csv`; `algorithm_patel2022` in grader tables, gold
  names, dashboards and the order comparison
- [x] T009 [US3] Completeness CSV; `reliability.confusion_scores` (precision, recall, F1) for the Diagnoser and
  the Extractor; R twins and parity for the merge and the scores
- [x] T010 [US3] Docs: results beside the paper's cited figures, labelled synthetic vs real records; when `algorithm_patel2022`
  joins `readme_results.PHENOTYPES`, update its row in `docs/algorithms.md` (source [4], accuracy from
  results.md), which `test_algorithms_doc.py` checks (#213)

## US4 #204: A2 checked, citations corrected

- [x] T011 [US4] Failing test: `test_rule_order_citation.py` with the corrected wording
- [x] T012 [US4] References item 4 (full citation, implementation, inconsistencies); evidence rules,
  walkthrough, `phenotype.py` comment, action item A2
- [x] T013 Full test suite, `ruff`, R parity; review file for each implementation PR
