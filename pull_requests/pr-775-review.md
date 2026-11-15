---
pr: 775
branch: fix/774-035-sandbox-python-under-tmp
title: "035 BUG2: mount the sandbox's private /tmp before the binds, so a Python under /tmp stays visible"
author: jcbowyer (agent session)
reviewed_at: 2026-11-15
reviewer: an independent read-only reviewer subagent (given the diff, the rubric, AGENTS.md and CLAUDE.md, not the author's conclusions; Superpowers isn't installed in this session) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 035 BUG2: mount the sandbox's private /tmp before the binds, so a Python under /tmp stays visible

## Summary
The agent harness's sandbox bound the running interpreter's folders into its root, then mounted an empty `/tmp` on
top. A Python installed under `/tmp` was hidden, `python3` fell back to the system's (no pytest), and verification
failed even the reference patch. Six tests in `test_agent_harness.py` failed in a cloud session for that reason and
passed in CI. This pull request mounts the private `/tmp` first and the binds on top.

The reviewer found nothing critical or important. One minor finding mattered for isolation: binds on top of the
private `/tmp` meant a bind of `/tmp` or `/` itself would show the host's `/tmp`. Such a bind is now left out, and a
test proves it. Approve with nits; it waits for the owner because merging runs the deploy.

## Scope of Change
- Files changed: 3: `agent_harness.py`, `test_agent_harness.py` and this review
- Areas touched: python
- Commits:
  - `a8ea9be` Mount the sandbox's private /tmp before the binds, so a Python under /tmp stays visible
  - `1579f30` Leave out a bind that would show the host's /tmp, and check privacy with a canary
  - this file
- Range reviewed: `6095411..a8ea9be` by the reviewer; `a8ea9be..1579f30` by the coordinator, from the findings

## CI Status
| Check | Status |
|---|---|
| `check`, `changes`, `postgres`, `bundle`, `azure-infra`, `python-databricks-runtime` | pass on `a8ea9be` |
| `python` | running on `a8ea9be` when this was written |
| `r-parity` | skipped (no R-relevant change) |
| `1579f30` and this file | CI runs again on push; the head must be green before merge |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
  - The diff and the commit messages hold no credential.
  - The tests set no real value: `KAGGLE_API_KEY` in the existing test is `not-a-real-key`.
- **PHI / real data:** clean.
- **Organization claims:** clean.

## Strengths
- A minimal, well-placed change, with a comment citing #774 at the line.
- The test checks all three properties (visible, read-only, `/tmp` writable and private) and cleans up after itself.
- **It doesn't depend on where the interpreter lives:** it binds its own folder under `/tmp`, so it guards CI too.
- **It reproduces the cloud-session failure exactly:** the six tests fail on the base and pass on the head.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
1. **Fixed in `1579f30`: a bind of `/tmp`, `/` or a folder above the sandbox's root showed the host's `/tmp`.**
   - Why: with the private `/tmp` mounted first, such a bind landed on top of it. The base hid it only by accident.
   - Reproduced by the reviewer: binding `/tmp` showed the host's `/tmp` names, including the session's MCP config files, read-only.
   - How likely: it needs `sys.prefix` to be `/tmp` or `/`, or `TMPDIR` inside the interpreter's folder. Very unlikely, but it would show host files.
   - Fix: `Sandbox.run` leaves out any bind that is `/tmp`, or is `/` or a folder above the sandbox's root or the workspace.
   - Test: `test_a_bind_that_would_show_the_hosts_tmp_is_left_out` binds `/tmp`, `/` and the temporary folder, and checks that an unbound canary in the host's `/tmp` stays hidden while the private `/tmp` stays writable. It failed before the guard and passes with it.
2. **Fixed in `1579f30`: the test's privacy check counted `htlnlp_` entries in `/tmp`.**
   - That count could pass with a host `/tmp` leak when `TMPDIR` is set elsewhere.
   - It now makes an unbound canary folder in the host's `/tmp` and checks the sandbox can't see it.

Not taken, because they predate this pull request (noted for a follow-up if wanted):
- **The read-only remount fails open:** a failed remount carries on silently (`mount -o remount,bind,ro ... || true`). On a host that refused it, a bound folder would stay writable from the sandbox. The new test's "Read-only" assertion would catch it in a test run, but production runs would not.
- **The bind list is split on spaces:** `for d in $binds` is unquoted, so a path with a space or a glob character would break.
- **Spec 035 lists the environment as `PATH`, `HOME`, `LANG` and `PYTHONPATH` only:** `_env` also sets `PYTHONDONTWRITEBYTECODE` and `PYTHONUSERBASE`.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan clean |
| Synthetic only, no PHI | ✅ | |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | the new test failed on the base (the bound folder didn't exist inside); the guard's test failed before the guard |
| Python and R in parity | n/a | |
| Spec for big changes | n/a | a fix with tests; spec 035's "a private /tmp" is now true for an interpreter under /tmp too |
| Configuration | ✅ | no setting changes; no Databricks job changes |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailers |
| Telemetry | ✅ | no new public functions |
| Secrets register, idempotent writes, alerts, seeds, paths, prices, deck figures | n/a | |

## Test Coverage
- **`tests/test_agent_harness.py` from a virtual environment under `/tmp`** (this session's, the #774 setup):
  - `main`'s harness: 7 failed (the six, and the new test), 36 passed.
  - `a8ea9be`: 43 passed.
  - `1579f30`: 44 passed.
- **The harness, agent and telemetry tests:** `test_agent_harness`, `test_official_agent`, `test_gemma_agent`, `test_telemetry_agent` and `test_telemetry_calls`: 152 passed on `1579f30`. With the rule tests on `a8ea9be`: 194 passed.
- **The whole suite on `a8ea9be`, with the deploy job's packages:** 2,613 passed, 39 skipped, none failed. That is the first fully green local run in this session; the six harness failures are gone.
- **`ruff check`:** clean on both files.
- **Not tested here:** a host where the read-only remount is refused (see above).

## Verdict
Approve with nits. Nothing must change before merge. It waits for the owner: `python/` isn't in the deploy
workflow's path filter, so merging runs the deploy and its Load results on the Free Edition workspace (AGENTS.md
rule 6).
