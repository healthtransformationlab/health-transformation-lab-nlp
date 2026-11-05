# PR 596 review: send the daily and weekly digests

Refs #359 (T023, digest job). Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- Test first: 17 tests in `test_digests.py` and 2 in `test_bundle.py`, written failing first. The
  `AlertEvaluationState` test was added after review caught `AlertState`, a type the live API would reject.
  Full suite: 2,188 passed, 4 skipped.
- AGENTS.md "Alerts and severity":
  - SEV3 goes to the daily digest and SEV4 to the weekly, one message per owner per period, each problem once with
    a count (the package's `digest`);
  - SEV1 and SEV2 never wait: the doctor pages runs, and this job fails on a SEV1/SEV2 forecast so its failure email
    pages;
  - a repeating SEV2 is flagged for level review.
- Settings: catalog and schema are required and checked first. `digest_email` is optional: empty means a warning
  and no alerts, but the digests are still built. The address comes from the `ALERT_EMAIL` GitHub variable only;
  `test_no_email_address_is_written_in_the_bundle_or_the_deploy` passes.
- Idempotent: delete-then-append by `digest_key`. A rerun that finds nothing clears the day's earlier rows. The
  alerts are upserted by name.
- Limited compute: the job is created paused. Merging starts no run; unpausing is the owner's call.
- Dependency: pipeline-doctor is pinned to a commit, and `requires-python` is raised to 3.11, its floor; every
  runtime here is 3.12.
- Gold: both tables are declared, with comments that state the grain. The SQL-conventions and table-comments tests
  pass.

## Findings
- Not blocking: the SQL alerts calls (`alerts_v2.list_alerts`, `create_alert`, `update_alert`) are untested
  against the live API. If they fail on the first run, the job warns and the digests are in the tables.
- Not blocking: the alerts' email body uses `{{QUERY_RESULT_TABLE}}`. If the alert templates don't fill that
  variable, the email still links to the alert, whose query shows the message.
- Not blocking: this repo keeps its own `doctor.py` until `duration_drift` and `fix_text` are upstream in
  pipeline-doctor (the T023 sub-task stays open).

Nothing blocking. It creates a paused job and starts no run, so it can merge when CI is green.
