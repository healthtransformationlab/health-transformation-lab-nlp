# PR 589 review: each failing cost and performance check's severity

Refs #576 (T011). Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- Test first: four new tests in `test_governance.py` failed before the change:
  - a passed budget is SEV3 and a pass has no severity;
  - drift is SEV4 and late is SEV3, as the runbook says;
  - failing cost data is SEV3, and a report has no severity;
  - the gold column is declared.
  Full suite: 2,158 passed, 4 skipped.
- Severity follows AGENTS.md "Alerts and severity": a check below threshold is SEV3, and cost drift is SEV4. The
  performance levels are read from `ops/runbook.yaml`, so they can't drift from the doctor's classes.
- A REPORT is never an alert: completeness rows carry no severity, since billing lags.
- Gold: `severity_code` is declared, with its comment. The SQL-conventions and table-comments tests pass, and record
  rows leave it empty.

## Findings
- Not blocking: no digest job reads these yet (spec 027 T023). Until it exists, a failing budget is visible on the
  dashboards (T012) and in `dq_check`, but it isn't emailed. T011 is ticked with that stated.

Nothing blocking. It starts no run, so it can merge when CI is green.
