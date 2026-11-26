---
pr: 980
branch: feat/979-044-veteran-dental-set
title: "044 US4: a veterans' dental question set in AccessBench's oral section"
author: jcbowyer
reviewed_at: 2026-11-26
reviewer: claude-code (in-session checklist against .claude/review-rubric.md; local pytest)
verdict: approve-with-nits
---

# PR Review: a veterans' dental question set in AccessBench's oral section

## Summary

Closes #979. Eight synthetic questions on VA dental care, added to the oral section as their own set
(`fixture=veteran_dental`), loaded and validated like the discount set, and wired into the batch, the review page and
the job's dropdown. Spec 044 gains US4. Because the VA and eCFR pages could not be opened, every item says so, with no
verified date, and a test holds that line. Approve: the set is fit to review and to run in simulated mode. It is not
fit to publish a score from until T033 is done.

## Scope of Change

One items file, one loader module (a copy of the discount loader with its own prefix and path), the batch's fixture
list and `all_items()`, the review script's `FILES`, a notebook dropdown, a bundle-variable description, the
AccessBench README row, spec 044 (spec, plan, tasks) and tests.

## CI Status

Pending at review time; local `pytest -k "access or bench_order or wording or no_org or conventions"`: 299 passed.

## Secrets, PHI and Claims Scan

No secrets. The questions are synthetic and carry no names, phones or member numbers; the phone numbers in them are
public VA lines (877-222-8387, 877-424-3838), to be confirmed in T033. No organization is described beyond the VA's
public programs. No result or score is claimed.

## Strengths

- Honest sourcing: the items say they are unopened rather than borrowing a check date, and a test enforces it.
- Covers the cases where a general answer goes wrong at a cost: the 180-day window, "every rated veteran gets free
  dental", VADIP being paid insurance, TRDP having ended.
- The swelling question puts urgent care first, matching ADR 0015's one omission that counts as harm.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

- T033: open the VA and eCFR pages and correct each point before any live score of the set is published. Details most
  likely to need correcting: the minimum service length for one-time post-discharge care, VADIP's current status and
  insurers, and the travel-pay rating threshold.

### 🔵 Nits / suggestions (Minor)

- `access_veteran_items.py` duplicates the discount loader except for its prefix and path; a shared loader taking both
  would remove the copy once a third such set arrives.
- The eCFR link uses the short `/current/title-38/section-17.161` form; confirm it resolves when the pages are opened.

## Repo-Rule Compliance

| Rule | Status |
|---|---|
| No secrets | ✅ |
| Synthetic only, no PHI | ✅ `is_simulated: true` on every item; refused otherwise |
| Test first | ✅ the new test file failed (module missing) before the code |
| Simulated is labelled simulated | ✅ no score claimed |
| Spec for big changes | ✅ spec 044 US4 with plan and tasks |
| Configuration | ✅ no new setting; one description changes; no environment's values change |
| Telemetry | ✅ public functions carry `@traced` |
| Commits | ✅ |

## Test Coverage

Loading, ids, section and domain; the unopened-source rule; the swelling question's urgent-care point; refusal of a
bad id, link, point count or a non-synthetic row; the batch scoring the set and `all` including it.

## Verdict

approve-with-nits
