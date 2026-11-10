---
pr: 643
branch: docs/636-028-evaluator-records
title: "028 T017: correct the records that say the competition's evaluator isn't distributed"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-10
reviewer: the authoring session (the diff was read against issue 636 and the starter notebook; no reviewer subagent run)
verdict: approve
---

# PR Review: 028 T017: correct the records that say the competition's evaluator isn't distributed

## Summary
Text only. Two specs and five docstrings said the competition's evaluator is not distributed; it ships in the Kaggle
dataset the starter notebook attaches (#636). Each now says when it was written and where the evaluator is. Nothing
blocking.

## Checks
| Check | Result |
|---|---|
| No behaviour changes | the diff touches docstrings, one test's docstring and two specs; 113 tests in the touched areas pass |
| The correction is itself supported | the starter notebook lists `metric/gemma-4-developer-agent-wheelhouse` and imports `VllmConfig` and `VllmServer` from `adk_submission`; the wheel `swegemma-0.2.11` is in that dataset (issue 636) |
| "the two agree on every agent patch compared" (`agent_harness.py`) | `data/tasks/official_verifier/README.md`: the same verdict on all 25 of Gemma's saved patches; the 18 reference patches where they differ are not agent patches |
| Spec history is kept, not rewritten | spec 035 gets a dated correction above the original text; spec 028 T007 says what was believed and what T013 found |
| Old claim left only where it is quoted to correct it | spec 028 US6 and T017 |
| Past reviews untouched | `pull_requests/` unchanged except this file |
| Wording, organisation-name and benchmark-order tests | pass |
| Branch name and issue link | `docs/636-028-evaluator-records`, `Refs #636` (item 3 of the issue is still open) |

## Should fix later
- `kaggle/cards/tasks.md` says the snapshots' own files are under "its MIT licence". That is right for the commits the
  snapshots hold, but the repository is Apache 2.0 since #639; a few words would stop a reader taking it for a
  contradiction. It reaches Kaggle on the next publish.

## Secrets, PHI and Claims Scan
Secrets: none. PHI or real notes: none. Claims: none added; five wrong statements corrected.
