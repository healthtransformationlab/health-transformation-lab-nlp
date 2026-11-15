---
pr: 759
branch: spec/752-040-telemetry-tasks
title: "spec 040: tasks whose statements are written from a failing run's telemetry"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-15
reviewer: the authoring session (each figure re-read at its source after writing; each name checked against the code it refers to; no reviewer subagent run)
verdict: approve
---

# PR Review: spec 040: tasks whose statements are written from a failing run's telemetry

## Summary
Spec, plan, tasks and checklist for spec 040, from the design of #714 and its decisions of #736. The spec departs
from the design in three evidenced ways: the registered test moves to injected tasks, `symptom` is added as their
baseline, and a new story records row counts on spans first. Docs only. Nothing blocking. The owner should read the
three departures; the pull request leads with them.

## Checks
| Check | Result |
|---|---|
| Spec number 040 | `specs/` on `main` ends at 039; no open pull request or remote branch holds a 040 |
| "23 of the 93 ... in their failing test's trace, and 7 on a failure's traceback" | `data/tasks/trace_reach.csv`: 51 rows (the tasks whose fix edits an existing function), `is_edited_in_trace` True in 23, `is_edited_on_traceback` True in 7 |
| "not a fair benchmark condition" | `python/scripts/68_trace_reach.py` docstring, quoted exactly |
| The `report` arm: 3 / 1 / 1 / 88, p = 1.0 | `data/tasks/official_agent_runs/README.md`, "The paired tests": `colab-report`, addendum 3, 93 pairs, 0 left out, both 3, baseline only 1, context only 1, neither 88, p 1.0; `context_pairs_colab_report.csv` has 93 rows |
| "4 of the 30 screened are fixes, 14 features and 12 maintenance" | `data/tasks/screening/agent_screen.csv`, `change_kind_code` |
| "No pipeline span records a row count today" | `pipeline_step(` is called only in `telemetry.py`'s docstring and `test_telemetry.py`; `annotate(` with a row or count argument appears nowhere in the package or scripts; `start_script` sets `pipeline.step`, `pipeline.kind` and `data.label` only |
| Span attributes the writer reads | `telemetry.py`: `pipeline.step`, `pipeline.kind`, `data.label` (from `data_label`); `_record_failure` sets `error.type`, records the exception (an event carrying the stack trace) and sets status `ERROR` with `str(e)[:500]`; a traced function's span is named `<module>.<function>` (`traced` wraps `trace_call`) |
| `DENTAL_TELEMETRY_LEVEL=detail` | `trace_call` makes no span when the function's level is above `_State.level` (default `call`), and `annotate` writes nothing without a span |
| The six target modules | each has its own test file on `main` (`test_results_store.py`, `test_nhanes.py`, `test_study.py`, `test_completeness.py`, `test_tooth_loss_dq.py`, `test_dq_site.py`) and `@traced` functions that mention `pd.DataFrame`; the incident pipelines are as `data/ops/incident.csv` names them |
| Script number 74 | `python/scripts/` on `main` ends at `73_build_contracts.py` |
| Reused scripts exist | `kaggle/official_agent_run.py` (`--label`), `kaggle/colab_official.py`, `python/scripts/70_context_pairs.py`, `69_failure_report.py`, `task_gate.evaluator_verified` |
| Cost | 1,800 main + 60 pilot + up to about 270 history task-runs, at 76 GPU-seconds a task (`colab-statement`) = 45.0 GPU-hours; x 1.87 USD (`ops/cost_settings.yaml`, `a100_usd_per_gpu_hour`) = 84 USD |
| Power unchanged | the primary test pairs two conditions on 200 tasks, as in the design's decision 1; the third condition adds runs, not a test |
| Spec, plan, issues agree | every name in the plan's table is in its issue; #753 and #754 carry dated lines for what the plan settled (two `symptom` outcomes; the fault-attempt columns and the level), and nothing was rewritten |
| Issues | epic #752 and stories #753 to #758 each have Problem, Done when, Contract and Read first; each story is a sub-issue of the epic, as `AGENTS.md` asks of specs written from November 14 |
| Wording, names, conventions | `pytest -q tests/test_wording.py tests/test_no_org_references.py tests/test_bench_order.py tests/test_no_legacy_schema_names.py tests/test_rename.py tests/test_pr_conventions.py`: 104 passed; `pr_conventions.py` passes for the branch and `Refs #752` |
| Line length | no prose line over 120 characters; the long lines are table rows and two story headings that carry their issue titles |

## Should fix
- Nothing before merge.
- `/speckit-analyze` before the first `feat` branch (tasks.md, T020).
- US6 must list its exact functions in its pull request; the plan names modules, not functions.
- The `symptom` template stands for an underspecified statement; it is not a person's. The spec says so under
  "Risks", and every result built on it must say so too.
- If the owner rejects any of the three departures, the spec, plan and issues #753 to #758 change together.

## Secrets, Real Data and Claims Scan
Secrets: none. Real data: none. Claims: no result is claimed; every figure is a committed one or a stated
calculation. Nothing is published and no compute runs; the stories' GPU runs and publishes each wait for the owner.
