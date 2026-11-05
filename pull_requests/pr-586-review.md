# PR 586 review: each job run's cost from the billing system tables

Refs #568 (T007). Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Checks
- Test first: six tests in `test_doctor_job.py` failed (five) or were new (the notebook order) before the code:
  - a price that changes mid-period;
  - several SKUs;
  - a SKU with no price (no partial cost);
  - empty, not zero, with no usage;
  - a span's value wins;
  - one warning when billing can't be read, and the queries' filters.
  Full suite: 2,133 passed, 4 skipped.
- Settings: billing is optional data. It warns and carries on, never fails the doctor (AGENTS.md, configuration).
- Read-only: two SELECTs over the doctor's lookback (`HISTORY_DAYS`), job usage only (`job_run_id is not null`),
  USD prices only.
- Idempotent: cost is recomputed on each doctor run from billing, and the doctor's writes are unchanged
  (delete-then-append by run).
- `@traced` on the three new public functions (telemetry test passes).
- No secret in code or logs. The warning names the grant, not any identity's id.

## Findings
- Not blocking: no DBU column. It needs a suffix for a fractional quantity (owner's call); `cost_usd` carries the
  number the doctor uses.
- Not blocking: until the grant is made, every run's cost stays empty in dev and uat. That is the designed fallback
  (FR-002, FR-003), and the warning says what's needed.
- Not blocking: list prices aren't discounts, so `cost_usd` is the list cost, as its description says.

Nothing blocking. It starts no run, so it can merge when CI is green.
