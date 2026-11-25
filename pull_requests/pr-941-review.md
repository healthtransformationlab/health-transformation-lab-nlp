# PR 941 review: every AccessBench question names its section (oral, medical, mental), and results report by section

Closes #938 (spec 044 US1, epic #937). Range: `origin/main..feat/938-044-access-sections`. Files: `specs/044-access-sections/`
(new), `docs/adr/0014-accessbench-oral-medical-mental-sections.md` (new) and the ADR index,
`python/health_transformation_lab_nlp/access_sections.py` (new), both item files and validators, `access_batch.py`,
`gold_names.py`, `gold_model.py` with rebuilt diagrams and the regenerated contract, the READMEs, and tests.

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none.
- **Real data:** none. The 15 items only gain `section_code: "oral"`.
- **Claims:** the READMEs say the oral section is being built and medical and mental are planned; no score is
  published.

## Findings (verified)

1. **The decision is in an ADR, not only in the spec:** ADR 0014 records the three sections, oral first, discounts in
   every section, and no pooled score, with when to revisit. The mental section's need for a crisis-safety rule before
   any question is scored is written into both.
2. **Two older validator tests** built items without the new required field. Their sample items gained
   `section_code`, so they still test what they were written for (goal tag, planted details missing from the prompt).
3. **The landing README stays at 80 lines:** the AccessBench paragraph was rewritten in place.
4. **Merge order:** PR 936 (resource scoring) touches the same gold files and appends tests to `test_access_batch.py`.
   Whichever merges second needs main merged in and the diagrams and contracts regenerated.

## Checks

- 18 test files covering the AccessBench modules, gold model, contracts, diagrams, decks, telemetry and wording:
  251 passed after the two fixture updates. `test_access_sections.py` failed (no module) before the code.

## Verdict

Approve, merging once CI is green. Nothing runs and nothing is published.
