---
pr: 509
branch: chore/508-028-gate-script-tests
title: "028 CHORE3: test the gate script's apply step, name T011's file, list KAGGLE_API_KEY"
author: johncbowyer
reviewed_at: 2026-11-03
reviewer: coordinator review (small change: one test file and two one-line doc edits)
verdict: approve
---

# PR Review: 028 CHORE3: test the gate script's apply step, name T011's file, list KAGGLE_API_KEY

## Summary
This closes the three nits from the PR #505 review: a test file for the wiring in `57_gate_tasks.py`, a T011 note
on which file to publish, and the cloud Kaggle variable in AGENTS.md's credentials table. The tests are
characterization tests of code already on `main`, and each guard was removed in turn to show its test fails
without it. Nothing blocking. Because it edits AGENTS.md, rule 6 keeps it for the owner's "merge".

## Scope of Change
- Files changed: 4 (+91 / -2)
- Areas touched: python (tests), docs (AGENTS.md), specs
- Commits: 509a45c 028 CHORE3: test the gate script's apply step, name T011's file, list KAGGLE_API_KEY
- Range reviewed: `origin/main..509a45c`

## CI Status
| Check | Status |
|---|---|
| CI on the head | see the PR's checks; local suite below |

## Secrets, PHI and Claims Scan
- Secrets: clean. The AGENTS.md row names a variable, never a value.
- PHI / real data: clean. The test fixtures are made-up ids (`htlnlp_1`, `htlnlp_2`).
- Organization claims: clean.

## Strengths
- The tests run the real script, loaded with `importlib` the way `test_decks.py` loads `build_decks.py`, with every
  path pointed at `tmp_path`, so the committed `data/tasks/` is never touched.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
None.
### 🔵 Nits / suggestions (Minor)
1. The tests set the script's module-level paths by name. If the script renames one, the fixture's `setattr`
   fails with an AttributeError rather than silently writing to `data/tasks/`, so this is safe as written.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| No organization claims | ✅ | |
| Test first | ✅ | tests of existing code; each shown failing with its guard removed |
| Python and R in parity | n/a | |
| Paths | ✅ | test paths in `tmp_path`; `REPO_ROOT` from `paths` |
| Spec for big changes | n/a | tasks.md T011 note only |
| Commits | ✅ | |
| Secrets register | ✅ | already lists `KAGGLE_API_KEY` (#505); the table now matches |
| Rules change | ⚠️ | edits AGENTS.md: waits for the owner's "merge" (rule 6) |

## Test Coverage
7 new tests in `tests/test_gate_tasks_script.py`. Local: `pytest -q tests` 1901 passed, 15 skipped; `ruff check`
clean.

## Verdict
approve. Merge waits for the owner, since AGENTS.md changes.
