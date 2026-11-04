---
pr: 549
branch: feat/543-035-agent-harness
title: "035 US1: a local runner for the competition's documented harness, sandboxed and proven with scripted models"
author: johncbowyer
reviewed_at: 2026-11-04
reviewer: superpowers requesting-code-review subagent (against HARNESS_README) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 035 US1: a local runner for the competition's documented harness

## Summary
This rebuilds the competition's documented harness (guide sections 4.2 to 8.2) locally, so an agent can be scored
on spec 028's task set while the official evaluator isn't distributed. A reviewer compared it against the guide
before the PR and found two Critical problems:
- commands ran on the host, where a model could read this repository's history and the task files (every
  reference patch) and reach the network;
- the host's secrets were in the commands' environment.

Both are fixed with a namespace sandbox, and verification runs inside it too. The reviewer's eight other findings
are fixed. The full calibration found five more environment gaps, and CI found one, the interpreter's path; all
are fixed. Calibration: `calib:oracle` 111 of 113, `calib:null` 0 of 113. Approve with nits.

## Scope of Change
- Areas touched: python (new `agent_harness.py`, `scripts/59_run_agent.py`, tests), specs, data
  (`data/tasks/agent_runs/`, four calibration tables)
- Commits: f23b602 (runner), 8d4a137 (sandbox and review fixes), 9ed159d (the running Python first on PATH)
- Range reviewed: `origin/main..9ed159d`

## CI Status
| Check | Status |
|---|---|
| python, python-databricks-runtime | success on 9ed159d. On 8d4a137 they failed: no namespaces on GitHub's runner, and the allow-listed PATH missed `/opt/hostedtoolcache`. Fixed in 9ed159d. |
| postgres, r-parity, bundle, azure-infra, check | success |

## Secrets, PHI and Claims Scan
- Secrets: clean, and the harness now keeps them from models. The sandbox's environment is allow-listed. A test
  plants a key and checks that neither a command nor the agent's verified code can see it.
- PHI / real data: clean. The tasks are code, and the run tables hold ids and counts.
- Claims: every row names its harness. The note says it is not the competition's evaluator, and the calibration
  models are `calib:`.

## Findings
### 🔴 Blocking (Critical)
None remaining. Both Critical findings from the pre-PR review are fixed:
- host repo, task files and network were reachable: namespaces, read-only system binds, no network;
- secrets were in the environment: an allow-listed environment.

### 🟡 Should fix (Important, non-blocking)
None remaining. Fixed from the review:
- `/workspace` is now real;
- the resolution criterion is the guide's: required tests must pass, not skip;
- an empty tool list now means no tools;
- malformed and JSON-string arguments come back as errors.

Fixed from the calibration and CI:
- `PYTHONSAFEPATH` broke this repository's script-running tests, so it's dropped;
- loopback was down in the new network namespace;
- `PYTHONUSERBASE`;
- `/dev/fd` and `/dev/shm`;
- the running Python first on PATH.

### 🔵 Nits / suggestions (Minor)
1. On a host without unprivileged namespaces (GitHub's runner), the sandbox tests skip and calibration runs
   unsandboxed. A real model refuses to run there. The Kaggle GPU run (#544) must confirm the sandbox works on
   Kaggle first.
2. Two tasks can't be verified here: one needs a Postgres server, one needs R. They are listed, and left out of a
   model's denominator (spec 035).
3. Known gaps against the guide are listed in the spec: no ADK or context compaction, no sub-agents or skills, and
   five `git apply` variants.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets / PHI / claims | ✅ | the sandbox keeps secrets from models |
| Test first | ✅ | 39 harness tests, each seen failing first; the CI fix was reproduced in CI, not locally (this host's system Python has the packages) |
| Telemetry | ✅ | public functions and methods `@traced` |
| Paths | ✅ | `paths.TASKS_DIR` |
| Spec for big changes | ✅ | spec 035 |
| Simulated / calibration labelled | ✅ | `calib:oracle`, `calib:null` |
| Limited compute | n/a | runs nothing on a GPU; US2 waits for the owner |

## Test Coverage
`tests/test_agent_harness.py`: 39 tests. Local full suite: 2034 passed, 3 skipped. CI is green on 9ed159d.

## Verdict
approve-with-nits.
