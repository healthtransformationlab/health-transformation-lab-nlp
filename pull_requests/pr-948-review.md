# PR 948 review: the oral section gets a dental discount and voucher question set

Closes #939 (spec 044 US2, epic #937). Range: `origin/main..feat/939-044-discount-questions`. Files:
`benchmarks/access_bench/items/discount_voucher_items.jsonl` (new, 6 items), `access_discount_items.py` (new),
`access_batch.py` (`fixture=discount_voucher`), `access_review.py` and `80_access_review.py`, the notebook dropdown and
`databricks.yml` description, the AccessBench README, spec 044 tasks, and tests.

Reviewed by the agent session that wrote it; a research subagent drafted the items. Read it knowing that.

## Scans

- **Secrets:** none.
- **Real data:** none. Six synthetic questions; no names or contact details.
- **Sources:** every fact and resource came from an official or primary page the subagent opened on 2026-11-25: NIDCR
  "Finding Dental Care", the ADA's "Types of Dental Plans", the CFPB's May 2023 report and release on medical credit
  cards, Okunseri et al. 2019 (PMC6574867) on Mission of Mercy events, and the IRS 501(r)(4) and 501(r)(6) pages.
  Each item carries `evidence_urls` and "checked 2026-11-25".

## Findings (verified)

1. **Two suggested topics were dropped, not guessed:** Donated Dental Services and HRSA's sliding-fee details. Their
   pages refused the request, so the subagent swapped in topics it could source (Medicare and dentures; nonprofit
   hospital financial assistance).
2. **Known gap for the owner's review:** ACC_DISC_005 (dentures on Medicare) doesn't mention Medicare Advantage
   dental benefits, which three external reviews raise elsewhere. medicare.gov couldn't be opened to verify it, so it
   wasn't added unverified.
3. **Positive points only:** none of the 24 points starts "Does not", "Omits" or "Never" (tested), in line with spec
   045.
4. **The subagent's network change:** it added 14 official hosts to the owner's personal cloud environment, approved by
   the owner at the prompt. One retry with a browser-like user agent was refused by the permission system; nothing in
   the items depends on it.

## Checks

- 11 test files (the new item tests, batch, review, bundle, sections, telemetry, wording): 133 passed. The new tests
  failed (no module) before the code.

## Verdict

Approve, merging once CI is green. The items go through the owner's review before any score of theirs is published.
