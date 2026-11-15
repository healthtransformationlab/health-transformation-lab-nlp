---
pr: 783
branch: docs/763-030-earlier-build-outside-docs
title: "030 DOCS3: remove the 240-chart build from the files outside the docs"
author: jcbowyer
reviewed_at: 2026-11-15
reviewer: independent read-only reviewer subagent (one pass) + coordinator verification of the fixes; the Superpowers plugin was not installed in this session
verdict: approve-with-nits
---

# PR Review: remove the 240-chart build from the files outside the docs

## Summary
This PR finishes issue #763. Five places outside the Markdown docs gave the earlier review set's size: the
chart-review agent's rules file, the gold model and everything generated from it, two Kaggle notebooks, a comment
in the claims register and a docstring. Review found four more. Each now says what it means without a count.
Generated files are rebuilt and differ from `main` only by the edited text. The flow diagram's PNG is
re-rendered with a toolchain that reproduces the committed PNG exactly. A test now reads the earlier size in any
of its wordings across these files. One Important and five Minor findings were fixed in the second commit. The
two draw.io PNGs could not be re-rendered here and are left for the owner, as the PR says. Approve with nits.

## Scope of Change
- Files changed: 19 (+1 binary) excluding this review: rules file, gold model and architecture builders, their
  generated diagrams and contract, a flow diagram and PNG, two notebooks, the claims register, a dashboard, a
  docstring, two test files.
- Areas touched: docs / diagrams / contracts / kaggle / databricks (dashboard caption, folder rules file) / python
  (docstring, tests)
- Commits:
  - `2a9c5d3` Remove the 240-chart build from the files outside the docs
  - `1ba41eb` Fix what the review of the issue 763 change found
- Range reviewed: `6095411..1ba41eb` (reviewer pass on `2a9c5d3`; `1ba41eb` answers it and was checked by the
  coordinator)

## CI Status
| Check | Status |
|---|---|
| Local `pytest -q tests` on `1ba41eb` | 2,693 passed, 35 skipped |
| `73_build_contracts.py --check` | 33 contracts and 2 data products match and validate |
| GitHub checks | run on push; the head commit must be green before merge (AGENTS.md rule 6) |

## Secrets, PHI and Claims Scan
- **Secrets:** clean. In the one-line draw.io file, "token" appears only in LLM token-count column names.
- **PHI / real data:** clean. No data rows changed.
- **Organization claims:** clean.

## Strengths
- Every replacement is count-free, so these files won't go stale when the review set next changes.
- Generated files are proven to differ from `main` only by the edited text. The shorter descriptions were chosen
  so draw.io keeps every table's size: a longer first wording moved 386 lines of layout.
- The flow PNG's re-render is shown to be faithful: the same toolchain on the old source gives the committed PNG
  with 0 differing pixels.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
1. **The gold model still said "review chart (240)"** (the `review_key` `visit_id` description), and the test's
   pattern could not see that form. **Fixed in `1ba41eb`:** "review chart". The pattern reads "(240)" after a
   review-set word, and the test checks every description in the gold model.

### 🔵 Nits / suggestions (Minor)
2. The chart-review `AGENTS.md` is a folder rules file. Only a count is removed. The PR says so, and the merge
   follows the owner's instruction of 2026-11-15.
3. The claims test asserted nothing when runs are pending and only rejected one phrase. **Fixed in `1ba41eb`:** it
   reads the day from `results_manifest.csv`, and checks the other way round when `ladder_pending.csv` has rows.
4. The docstring test missed "7 stage IV training notes". **Fixed in `1ba41eb`:** no number may come before "stage IV".
5. The docstring's "the review set takes the patients who have one" holds only for this build. **Fixed in
   `1ba41eb`:** it points to `study.REVIEW_STRATA`.
6. Not fixed, as stated in the PR: `gold_data_model_full.png` and `gold_logical_architecture.png` show the old text.
   `drawio_render.js` needs `viewer.diagrams.net`, which the session's network blocks; no copy of the viewer was
   found on npm.

Further places the reviewer found giving the old size, all fixed in `1ba41eb`: the logical architecture
(`gold_architecture.py`), the review flow diagram and its PNG, the scorecard dashboard caption, and a test comment.
The reviewer's repo-wide search found nothing else outside `specs/`, `pull_requests/` and lines labelled as the
earlier build, apart from the judge-scorecard test docstring, which describes the earlier judge files accurately.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | |
| No organization claims | ✅ | `test_no_org_references.py` passes |
| Test first | ✅ | 16 of the file's tests fail on `main` |
| Python and R in parity | n/a | no label, scoring, reliability or cost change |
| Generated files not edited by hand | ✅ | regenerated with `gold_erd.py`, `gold_architecture.py`, `73_build_contracts.py`, `mmdc` |
| Wording and benchmark order | ✅ | `test_wording.py`, `test_bench_order.py` pass |
| Changes these rules | ⚠️ | a folder rules file loses a count, with no rule changed; merged on the owner's instruction |
| Issue has its four parts; scope change dated | ✅ | #763; "Changed 2026-11-15" line added for the four extra places |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailers |

## Test Coverage
- `test_docs_current_build.py` now covers 13 files outside the docs, the gold model's descriptions, the ladder
  docstring and the claims comment, on top of #761's guard and pins.
- Not covered: the PNGs' pixels (the flow PNG was compared by hand against a faithful re-render).

## Verdict
Approve with nits. Nothing must change before merge; the head commit needs green CI first.
