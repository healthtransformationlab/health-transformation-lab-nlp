# PR 952 review: typed privacy gate and item source fields (045 US4, #946)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict

Nothing blocking. Merge once CI is green; if #951 merges first, merge `main` in (both edit the leak lines in
`access_batch.run`).

## Checked

- **Spec and issue:** spec 045 US4 names #946. The issue's contract (`GATED_TYPES` and the four item fields) is
  built; new names (`UNGATED_TYPES`, `leaked_details`, `validate_source_fields`, the three type renames) are recorded
  on the issue as a dated line, with the original text unchanged.
- **Test first:** the gate, source-field and batch tests failed before the code.
- **No claim beyond the evidence:** only the discount items, whose `evidence_source` already says "checked
  2026-11-25", carry a verified date. The 15 others say their source hasn't been checked (null date), so nothing
  pretends to a check that didn't happen.
- **Gate correctness:** PHONE/SSN/MRN match digit by digit with separators but not inside a longer number (tested);
  names and streets match as whole words ignoring case and punctuation; member IDs also match with punctuation
  removed. CITY and STATE never gate (tested in the batch with "Cottondale").
- **Synthetic only:** every planted value is still invented (challenge-pool names, 555 phones, SSN starting 9).
- **Telemetry:** `leaked_details` and `validate_source_fields` are `@traced`.

## Not blocking

- Making every item time-sensitive moves all 21 to L3 under `infer_level`, so `level_code` stops separating items.
  A later change could base the level on something else (reasoning steps, jurisdiction-specific rules).
- The 15 unchecked sources need the owner's review by the 2026-12-31 recheck date.
