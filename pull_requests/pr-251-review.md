---
pr: 251
branch: feat/236-026-recheck-page
title: "Add a Records to recheck page to the EHR DQ grader (026 US3)"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: Add a Records to recheck page to the EHR DQ grader (026 US3)

## Summary
The PR adds a second page to the EHR DQ grader dashboard. It shows each mismatch rule's scores against the
truth, the flagged visits with the most rules failed first, and the selected visit's case profile, under a banner
that labels the data synthetic and says what a mismatch is. The review found nothing critical. It found two
important usability problems:
- the profile table couldn't say which visit a row belongs to until a visit was picked;
- a rule filter hid a visit's other failed rules without saying so.

Both are fixed, along with the minor points. Verdict: approve with nits. How the page renders in Databricks is
checked on the next dev deploy.

## Scope of Change
- Files: `dashboards.py`, `dq_grader.lvdash.json` (rebuilt), `test_dashboards.py`, `docs/graders.md`, `tasks.md`, this review
- Commits: 140c62f (the page), then the review fixes
- Range reviewed: `origin/main..feat/236-026-recheck-page`

## CI Status
| Check | Status |
|---|---|
| python, check, postgres, bundle | pending on push; locally `test_dashboards.py` and `test_wording.py` pass |
| r-parity | not affected (no R or scoring change) |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean. The page reads synthetic statuses and measures only.
- **Organization claims:** clean.

## Strengths
- **Valid dashboard JSON.** The two canvas pages have unique names, and every widget name is unique across the dashboard. Each filter has one query per dataset, the same shape as page 1, and the grid stays within 6 columns.
- **Matching types.** `visit_id` is bigint in both datasets the visit filter drives.
- **SQL follows the file's convention:** uppercase keywords, explicit `INNER JOIN`, and a CTE. It reads only four declared gold tables and runs in DuckDB.
- **Small datasets:** 63, 1,275 and 23,218 rows.
- **Wording:** the banner says synthetic, not clinical performance, and "a coding or charting gap, not a clinical error".

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
Both fixed, each with a test:
- **The profile table showed every flagged visit's 26 items with no visit column** until a visit was picked.
  - *Fix:* Visit is now the first column, and the description says "Pick a visit in the Visit filter".
  - *Not done:* a default selection. It needs filter JSON I can't verify outside a workspace.
- **The rule filter narrowed the flagged visits to one row while "Rules failed" still counted all of them**, and it didn't touch the rule scores.
  - *Fix:* it now narrows both tables, and the flagged-visits description says "Rules failed" counts all of a visit's rules.

### 🔵 Nits / suggestions (Minor)
Fixed:
- **The clinic filter dropped the score table's "All" rows** and offered "All" as a choice.
  - *Fix:* it now filters the flagged visits only, as page 1 keeps its checks' All rows. The table description says so.
- **Blank precision wasn't explained.** The rule-score description now says "blank = the rule flags nothing there".
- **One test was close to a tautology.** It compared profile visits with flagged visits by construction. It is replaced by tests on the Visit column and on what each filter narrows.

Noted, nothing to change:
- **Tasks T019–T020 are ticked although the Genie file isn't in this diff.** Its tables, instructions and sample questions landed with #243 and #247, and the PR description says so.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Yes | |
| Synthetic only, no PHI | Yes | |
| No organization claims; vendors cited | Yes | |
| Test first | Yes | Page tests failed first; each fix had a failing test |
| Python and R in parity | N/A | No scoring change |
| Simulated is labelled simulated | Yes | Banner: synthetic records, not clinical performance |
| SQL and data names | Yes | Uppercase as the file is; `INNER JOIN`; CTE; declared gold tables only |
| Words | Yes | `test_wording.py` |
| Configuration | N/A | No settings change |

## Test Coverage
`test_dashboards.py` covers:
- the page order, banner and widgets;
- the single-select visit filter;
- the Visit column in the profile table;
- what each filter narrows and the descriptions that say so;
- that the datasets read only the spec 026 tables;
- that they run in DuckDB, with flagged visits most rules first and rule scores "All" first.

The existing tests run every dataset and check every widget field.

## Verdict
Approve with nits. It can merge once CI is green. Check the page's rendering and filters on the next dev deploy.
