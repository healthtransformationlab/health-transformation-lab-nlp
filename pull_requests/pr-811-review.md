---
pr: 811
branch: feat/806-028-modal-auto-cap
title: "028 AI16: Modal runs start on their own under a cost cap, and wait for the owner above it"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-15
reviewer: a read-only reviewer subagent over 5f6da9f (rubric step 3), which read Modal 1.6.4's source for the billing and app-list output; each finding then checked by the authoring session against GitHub's documented behaviour and the code before acting on it (step 4)
verdict: approve (after the second commit; the first had one blocking finding)
---

# PR Review: 028 AI16: Modal runs start on their own under a cost cap, and wait for the owner above it

## Summary
The owner asked to "automate with cap, approve if over some reasonable limit". The first commit split the Modal
workflow into three jobs:

- `check`: the checks, then whether the run needs approval;
- `approve`: in `modal-approval`, only when needed;
- `run`: the run itself.

A run starts on its own within 5 USD a run and 25 USD a month.

The reviewer found:

- **one blocking finding:** a re-run skipped both checks;
- **four Should-fix findings:**
  - a branch set its own limits;
  - an empty decision went through;
  - a waiting run blocked others;
  - the gate proved a rule existed, not that anyone approved;
- **four nits.**

The second commit fixes each blocking and Should-fix finding, each closed by default and each with a test. Of the
nits, three are fixed and one is left to the owner (see Should fix). What no workflow can check is said in ADR 0008.
Nothing blocking remains. Merging starts no run.

## Scans
- **Secrets:** none. The approval environment holds no secret, and no credential is written to a file or echoed.
- **PHI / real data:** none.
- **Organization claims:** none.

## Findings and what was done
| # | Severity | Finding | Checked by | Outcome |
|---|---|---|---|---|
| 1 | 🔴 Blocking | "Re-run failed jobs" re-runs only `run`. It reuses `approve`'s success and `check`'s spend reading, so a once-approved or once-under-limit run could go again with neither check. | GitHub's re-run model: jobs not re-run keep their results and outputs | Fixed. `run`'s first step refuses any attempt but the first (`GITHUB_RUN_ATTEMPT`). The spend is also read again just before the run (`approval --approved <approve's result>`), and the run stops if it is now over and was not approved. Tests cover the step order and every branch of the recheck. |
| 2 | 🟡 Should fix | The limits, the workflow and `modal_official.py` came from the dispatched branch. A branch that raised `modal_auto_max_usd` ran under its own limit. | the workflow reads the checkout | Fixed for the limits: `check` and `run` read `main`'s `ops/cost_settings.yaml` (`git show FETCH_HEAD:...`, `--limits`). A branch whose workflow, `modal_official.py` or cost settings differ from `main`'s always waits for approval (`gating_changed`). A branch that rewrites the workflow to drop those checks is beyond what the workflow can see; ADR 0008 says so, and names the hard boundary (secrets in an environment only `main` may use). Tests. |
| 3 | 🟡 Should fix | An empty `needs_approval` skipped `approve`, and `run` accepted the skip. Renaming the output or the step id passed the tests. | the reviewer's mutations | Fixed. `approve` runs unless the decision is exactly `false`. `run` accepts a skipped `approve` only when the decision is exactly `false`. The test asserts both conditions exactly, and the outputs' wiring to the step ids. The reviewer's three mutations now each fail a test. |
| 4 | 🟡 Should fix | The concurrency group covered the whole workflow, so a run waiting for approval (up to 30 days) held it, and runs queued behind it were cancelled. | GitHub's concurrency model | Fixed. The group is on the `run` job alone, so checks and approvals proceed side by side and only runs go one at a time. The recheck covers spend changes meanwhile. Test. |
| 5 | 🟡 Should fix | The gate proved a reviewer rule existed, not that anyone approved this run. An admin's bypass (`can_admins_bypass`) starts a waiting job with no review. | GitHub's review-history endpoint (`GET /actions/runs/{run_id}/approvals`) | Fixed. The gate also reads this run's review history and refuses unless an approval for `modal-approval` is recorded. It logs who approved. ADR 0008 says an approval is only as strong as the reviewer's account: agent sessions here have no tool to review deployments, and must not approve their own runs. Tests: bypass (no review), a rejection, an approval for another environment, and an unreadable history. |
| 6 | 🔵 Nit | "a month of them cannot spend past the credit" claimed too much: billing lag, image builds and start-up are outside `max_usd`. | read | Fixed: the ADR names them and the 5 USD margin. |
| 7 | 🔵 Nit | The input description repeated "Over 5", a second copy of the setting. | read | Fixed: it names `modal_auto_max_usd`. |
| 8 | 🔵 Nit | `"metered_cost": true` read as 1.0, and `busy` given an object raised `AttributeError`. | ran | Fixed: both refused by name. Tests. |
| 9 | 🔵 Nit | AGENTS.md's GPU rule says nothing of Modal, and this changes who may start paid runs. | AGENTS.md "Branches and issues" 6 | AGENTS.md is not changed. The policy is the owner's own ask in this session, recorded in ADR 0008. A Modal line in AGENTS.md would change the rules and is left for the owner. |

Mutation check: each of these eight changes makes at least one test fail.

- the three from the reviewer:
  - renaming the decision output;
  - renaming the step id;
  - `&&` to `||` in `run.if`;
- accepting any skipped `approve`;
- dropping the re-run refusal;
- dropping the approval-history check;
- treating an empty `gating_changed` as unchanged;
- dropping the recheck's refusal.

## Residual risk
- **The GitHub API shapes** (the environment's `protection_rules`, the run's review history) come from GitHub's
  documentation and could not be called from the session; the API paths are blocked by its proxy. If either differs,
  an over-limit run is refused, not let through. The first approved run will show it.
- **`modal billing summary`** may not be open to the Starter plan, or to this token. Then every run waits for
  approval, which is safe but defeats the automation. The first run's log will say.
- **A branch that rewrites the workflow** can drop the checks (ADR 0008).

## Compliance
| Rule | Result |
|---|---|
| Test first | Each fix has a test that fails without it (the mutations above). |
| Settings declared once, changed by PR | Two limits in `ops/cost_settings.yaml`, read from `main`. |
| Settings and credentials checked before work | Unchanged, plus the approval decision and the recheck before the GPU. |
| Decisions in ADRs | ADR 0008, with what the workflow cannot check. |
| Every credential in the register | The register now says the Modal token was not in `dev` on November 15. |
| Wording, benchmark order, organization names | Their tests pass. |

## Checks
- `tests/test_modal_official.py`: 25 passed.
- Whole suite on the second commit, `pytest -q -n auto tests`: 2,828 passed, 37 skipped.
- `ruff check` on the changed Python files: clean.

## Should fix
- **For the owner:**
  - add the Modal token to `dev`;
  - create `modal-approval` with themselves as required reviewer;
  - if wanted, add a Modal line to AGENTS.md's GPU rules (this changes the rules).

## Secrets, Real Data and Claims Scan
Secrets: none. Real data: none. Claims: none.
