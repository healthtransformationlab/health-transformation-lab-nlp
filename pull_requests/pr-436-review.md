---
pr: 436
branch: fix/435-028-no-org-name-in-task-set
title: "Keep the organisation name out of the task set: drop the one naming task, cut snapshot history"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: Keep the organisation name out of the task set

## Summary
The PR keeps the organisation name that CLAUDE.md forbids out of spec 028's publishable task set:
- A task whose patch or test patch names the organisation is excluded with the reason. On today's history that is one
  task, `htlnlp_91`; 115 remain.
- Snapshots are now one commit holding the base commit's files, with a fixed author, date and message. No history
  comes along.
- Text files at the base that name the organisation get `[org]`, like the statements already do.
- Two guards fail loudly: the build, if any row still names the organisation; and the snapshot, if any file still
  names it or any file other than the redacted ones differs from the base.

The reviewer found no Critical problem. One Important finding and the reproducible Minor ones are fixed on the branch.
Approve with nits.

## Scope of Change
- Files changed: 9
  - `task_graph.py`, `task_mine.py`, `55_build_tasks.py`;
  - their two test files;
  - spec 028's `spec.md` and `tasks.md`;
  - `data/tasks/snapshot_index.csv`, `data/tasks/tasks_excluded.csv`.
- Areas touched: python, data, specs.

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI: clean.
- Organisation name: the code builds the name from parts, as `test_no_org_references.py` does, and no file contains
  it. The exclusion reason never repeats it.

## Findings

### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important): fixed
- **`tasks_excluded.csv` was stale.** It held only its header while T008 said it held the exclusion. `55_build_tasks.py`
  does run here (the GitHub API answered unauthenticated). The regenerated file has one row, `htlnlp_91`. The build
  reports 115 rows (48 A, 45 B, 22 C), the leak check didn't fire, and `tasks_sample.jsonl` is unchanged. T006 and
  T009 now give 115.

### 🔵 Nits (Minor)
- **The two name patterns disagreed: fixed.** `git grep -w` missed the name split by a non-breaking space or a line
  break, and differed on an accented letter just before it. `files_naming_org` now uses `task_mine.names_org`, the
  same definition that redacts, over the files of `git archive`. A test covers the non-breaking space, the line break,
  Latin-1, CRLF and a non-ASCII path, and checks "care questions" and binary files are left alone.
- **Crashes and side effects in redaction: fixed.**
  - Non-ASCII paths, which `git grep` quoted, and Latin-1 files, which crashed the UTF-8 read, now work. Redaction
    reads and writes bytes through `surrogateescape`.
  - CRLF line endings, which text-mode reading turned into LF, are kept byte for byte (tested).
- **File modes weren't compared: fixed.** `_blobs` compares mode and blob, so a lost executable bit counts as a change.
  A test checks a redacted 755 script keeps its mode.
- **No cleanup on failure: fixed.** `snapshot` removes its work folder in a `finally`, and a partial `.tgz` on error. A
  test forces a failure and checks both are gone.
- **`size_bytes` changes on every rebuild: stays as is.** `.git/index` stores filesystem stat data (inode, change time),
  so the archive bytes differ between builds. The head SHA, tree SHA and redacted paths reproduce exactly: rebuilding
  both indexed snapshots matched the committed index on all three, so the index isn't rewritten for a size-only change.
- **`export-ignore` / `export-subst` in `.gitattributes`: stays as is.** They would fail loudly through the "only
  redacted files may differ" check. The repo has no `.gitattributes`.

## Test Coverage
- New tests: exclusion by patch; single-commit snapshot with no history; reproducible head; redaction keeping every
  other file; one shared definition of the name across spellings, encodings, line endings and paths; modes; cleanup on
  failure. Each failed before its change.
- `cd python && python -m pytest -q tests`: 1517 passed, 15 skipped.
- `ruff check` on the changed files: clean.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | |
| Organisation name (CLAUDE.md) | ✅ | Built from parts; no file names it; reasons don't repeat it |
| Test first | ✅ | |
| Python and R in parity | n/a | No labels, scoring or metrics |
| Spec for big changes | ✅ | Spec 028 `spec.md` and `tasks.md` updated |
| `@traced` on public functions | ✅ | `names_org`, `org_exclusion_reason`, `files_naming_org`, `snapshot` |
| Idempotent writes | ✅ | Index keyed by `instance_id`; outputs overwritten whole |
| Commits | ✅ | `Closes #435`, co-author trailer |

## Verdict
Approve with nits. Publishing (#356) still needs the competition's wheelhouse, the Gemma licence and the owner's
go-ahead.
