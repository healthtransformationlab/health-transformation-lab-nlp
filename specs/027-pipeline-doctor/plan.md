# Implementation Plan: the pipeline doctor

**Branch**: `027-pipeline-doctor` | **Date**: 2026-10-28 | **Spec**: [spec.md](spec.md)

## Summary
A pure-pandas module (`doctor.py`) computes the five signals from the run table, classifies a failed
run with rules, recommends the first allowed runbook action with its impact and severity, and decides per
failure class whether it may act alone. Config and runbook are YAML in `ops/` so a person can read and
change them without code. A later job wires it to the bundle's run data, the judge endpoint and
notifications.

## Technical context
- Python 3.12, pandas, PyYAML (already dependencies). No new dependencies.
- No Spark in the module or tests; the job notebook reads system tables into pandas.
- Tests: pytest, fixtures built in the test from small frames and the `ops/` YAML.

## Design
| Piece | File |
|---|---|
| Config: one entry per pipeline (owner, SLA, expectations, retry, runbook, data label) | `ops/pipeline_config.yaml` |
| Runbook: one entry per failure class (ordered allowed actions, reversible, severity, escalation) | `ops/runbook.yaml` |
| Incident set: the repo's own incidents as run rows with the action taken | `data/ops/incident.csv` |
| `load_config`, `load_runbook`, `signals`, `classify`, `recommend`, `graduation`, `evaluate` | `python/health_transformation_lab_nlp/doctor.py` |
| Tests | `python/tests/test_doctor.py` |
| Job `pipeline_doctor` (serverless CPU), run after a pipeline fails or daily (US5) | `databricks/resources/jobs.yml`, `databricks/notebooks/12_pipeline_doctor.py` |
| Judge on root-cause answers (US6) | `mlflow_judge.py` (existing pattern) |
| Docs: the four tables, the ladder, how to add an incident | `docs/dataops.md` |

### Classification rules (US1), in order; the first that fires wins
1. `config`: `error_type_name` in {KeyError, ValueError, MissingSetting} or `error_text` mentions a
   setting, secret or connection string.
2. `platform`: `error_type_name` in {Py4JException, OSError, ResourceExhausted, CUDAError} or the text
   says GPU, Illegal seek, signal, killed, memory.
3. `schema_drift`: `schema_sha256` differs from the last ok run of the pipeline.
4. `volume_anomaly`: `row_out_count` outside 0.5x-2x the trailing median of the last N ok runs (N=5).
5. `quality_fail`: `check_failed_count` > 0.
6. `source_late`: the run never started or `freshness_seconds` > `sla_seconds`.
7. `unknown`: everything else (the only class the LLM rung sees).

### Recommend (US2)
Action = `allowed_action_codes[0]` for the class, unless the run already tried it (`retry` after
`retry_max_count` retries moves to the next action). Impact = downstream names reachable in one hop
from the pipeline's outputs in `dim_lineage_edge`. Severity and owner from the runbook and config.
Notification is a template filled from the row: no free LLM text in a notification.

### Graduation (US3)
Per class, take the last N decisions (N=5, configurable). `automatic` if all `is_match` and the runbook
entry `is_reversible`; `recommend_only` if the last two are both misses, or fewer than N decisions exist,
or the entry is not reversible.

## Constitution check
Synthetic and public data only; the module never touches notes (test). No R parity change (no reported
metric changes; the eval is an ops metric, reported with intervals and labelled SIMULATED until real
decisions exist). Test-first. `@traced` on every public function. Names follow AGENTS.md. Every
write in the job is delete-then-append by `run_id`.
