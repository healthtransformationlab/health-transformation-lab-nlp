# PR 587 review: duration drift, and the file and setting to fix

Refs #570 (T008). Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- Test first: four of the five new tests in `test_doctor.py` failed before the code. The fifth, cost anomaly winning
  over drift, already held and guards the order. Full suite: 2,133 passed, 4 skipped.
- Rules order: `duration_drift` sits just before `unknown`. Every earlier class still wins, and the incident eval
  (`evaluate`, `ablation`) is unchanged.
- Severity: SEV4 for both cost and duration drift, the weekly digest, as AGENTS.md "Alerts and severity" puts cost
  drift.
- Allow-list: duration drift's actions are `investigate` then `page_owner`. The doctor never recommends off the list
  (`test_recommend_never_returns_an_action_off_the_list` covers every class, the new one included).
- Fix text: each "file: setting" names a file that exists (tested). The notification carries it, with no row data.

## Findings
- Not blocking: `fix_text` points at files and settings, not values. Choosing a new timeout or model is left to the
  person or agent session that takes it, under the usual PR rules.
- Not blocking: the 2× bound is a default. Spec 036's plan allows tuning it against run history once billing and
  run data accumulate.

Nothing blocking. It starts no run, so it can merge when CI is green.
