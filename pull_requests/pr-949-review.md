# PR 949 review: medical and mental sections start with discount and voucher seeds

Closes #940 (spec 044 US3, epic #937). Files: `benchmarks/access_bench/seeds/medical_discounts.md` and
`mental_discounts.md` (new), the AccessBench README's Sections table, spec 044 tasks.

Reviewed by the agent session that wrote it; a research subagent drafted the seeds. Read it knowing that.

## Scans

- **Secrets, real data:** none. Seed ideas only, no scored items.
- **Sources:** each seed names an official page opened on 2026-11-25 (IRS 501(r)(4) and (r)(6), CFPB, 988lifeline.org,
  FindTreatment.gov, CDC "Mental Health Resources"). What couldn't be opened is listed as not yet sourced.

## Findings

1. **No scored medical or mental items:** per ADR 0014 they wait until the oral review process has run once.
2. **Crisis safety:** the mental seeds restate ADR 0014's rule that a crisis-safety rule comes before any mental item is
   scored.

## Checks

- `test_wording`, `test_no_org_references`, `test_bench_order`, `test_access_sections`: 44 passed.

## Verdict

Approve, merging once CI is green. Docs only.
