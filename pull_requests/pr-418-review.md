---
pr: 418
branch: feat/130-004-reference-answers
title: "004 AI1: reference answers per reader field from the generator's truth"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: 004 AI1: reference answers per reader field from the generator's truth

## Summary
Adds a reference-answer table for the MedGemma reader: one row per review visit (240), one column per field the
reader returns (status, grade, extent), taken from the synthetic generator's truth in `answer_key/review_key.csv`
(option 1 of #130), with the note's stated status and the source on every row. It works: the committed CSV is
reproduced exactly by `53_reference_answers.py` from the committed key, and again from the key that
`make_parity_inputs.sh` regenerates (byte-identical). No scoring changes, so no R side is needed yet (#132 adds it).
Approve with nits: nothing blocking.

## Scope of Change
- Files changed: 7 (+169 / -1, excluding `data/datasets/answer_key/reference_answers.csv`, 241 lines)
- Areas touched: python / docs / specs / data
- Commits:
  - 95d988c Add reference answers per reader field from the generator's truth
  - c913a64 Renumber the reference-answer script to 53
  - 4bf8423 Merge remote-tracking branch 'origin/main' into feat/130-004-reference-answers
- Range reviewed: `54b2d92..4bf8423`

## CI Status
| Check | Status |
|---|---|
| python | success |
| postgres | success |
| r-parity | success |
| bundle | success |
| check (PR conventions) | success |

## Secrets, PHI and Claims Scan
- Secrets: clean (grep of the diff for tokens, keys, passwords, credentialed URLs).
- PHI / real data: clean. The CSV holds visit ids, labels and the source string; no note text, names or dates.
- Organization claims: clean; no organization named; the "Words" rule holds (no diagnose/diagnosis phrasing).

## Strengths
- The reference comes from the truth the generator used to write each note, so it avoids the anchoring bias of
  marking the model's answers (option 3 of the issue) and costs no reviewer time.
- `note_stated_status` keeps record mismatches visible: a reader that copies a wrong note can be told apart from one
  that misreads a right note.
- States plainly that pocket depths and bleeding have no column because the reader doesn't return them, rather than
  inventing a field.
- A test ties the committed CSV to the committed answer key and to the visits both MedGemma runs read.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- `python/scripts/53_reference_answers.py`: takes no `--seed`. It is deterministic (it reads the key that
  `10_build_study.py --seed 42` writes) and the docstring says so; the source string records the seed. Verified by
  rerunning the build pipeline: same file. Fine as is; noted because the brief asked for a "seeded script".
- The issue says "40 notes"; the table covers all 240 review visits, the set both committed MedGemma runs read. A
  superset, so the issue's done-when is met; worth a line on the issue when it closes.
- `docs/medgemma.md` is also edited by open PR #417; expect a small text conflict for whichever merges second.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | generator truth only |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | `test_reference_answers.py` written and failing before the module |
| Python and R in parity | ✅ | no labels, scoring or metrics changed; R twin comes with #132 |
| Simulated is labelled simulated | ✅ | no results presented |
| Seeds fixed | ✅ | deterministic from the seed-42 build |
| Paths | ✅ | `paths.DATASETS_DIR` |
| Spec for big changes | ✅ | spec 004 US5, FR-009, T021 |
| Commits | ✅ | imperative, body says why, co-author trailer |
| Docs | ✅ | `docs/medgemma.md`, `data/datasets/README.md` |
| Configuration / secrets register / alerts | n/a | none added |
| Idempotent writes | ✅ | CSV overwritten |
| Telemetry | ✅ | `@traced` on `reference_answers` |

## Test Coverage
6 tests: column layout matches the reader's fields, NA rule for grade and extent, truth kept over the note, source
recorded, committed CSV equals a fresh build from the committed key, and coverage of both MedGemma runs' visits.
Locally: `python -m pytest -q tests` 1253 passed, 15 skipped (before the main merge; after it, the affected tests
pass); `ruff check` clean on changed files.

## Verdict
approve-with-nits. Nothing must change before merge; merge before #424, which builds on it.
