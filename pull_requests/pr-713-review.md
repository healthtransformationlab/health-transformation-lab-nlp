---
pr: 713
branch: chore/712-014-telemetry-every-script
title: "Send telemetry from every pipeline script and Python job"
author: claude
reviewed_at: 2026-11-14
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve
---

# PR Review: Send telemetry from every pipeline script and Python job

## Summary
Every script in `python/scripts/` now calls `telemetry.setup()` and opens a run span named for itself, with a data
label. Before this, only 17 of 70 did, so most `@traced` spans went nowhere. Every Databricks job task that runs a
Python notebook now passes the telemetry switch, and its notebook reads it. The seven notebooks that run package
code in-process also set up telemetry and open and end their own run span. The first review found three Important
and five Minor issues: wrong data labels, notebook run spans never ended, a test that could leave telemetry state
behind, and test gaps. All eight are fixed in `e64a01f` and covered by the extended test. Verdict: approve.

## Scope of Change
- Files changed: 64 (+415 / -25)
- Areas touched: python (scripts, tests), databricks (jobs, notebooks), docs
- Commits:
  - c23cc58 Send telemetry from every pipeline script and Python job
  - 580d314 Sort the new telemetry imports and drop an unused noqa
  - e64a01f Fix telemetry labels and end notebook run spans, from the PR review
- Range reviewed: `336f87d..e64a01f`

## CI Status
| Check | Status |
|---|---|
| check (PR conventions) | success on 580d314 |
| changes | success on 580d314 |
| bundle | success on 580d314 |
| postgres | success on 580d314 |
| r-parity | success on 580d314 |
| azure-infra | success on 580d314 |
| python, python-databricks-runtime | running on 580d314; e64a01f queued |

## Secrets, PHI and Claims Scan
- Secrets: clean. The only matches are the function name `use_databricks_secret` and the existing secret scope's
  name, never a value.
- PHI / real data: clean. No data files change.
- Organization claims: clean.

## Strengths
- Coverage is complete and enforced. All 69 scripts are covered (`_trace_plugin.py`, a pytest plugin, is left out
  with its reason). Each is named for itself, and `test_telemetry_scripts.py` fails CI if one drops out.
- Scripts that tests load have no import side effects: those with a `__main__` guard set up inside `main()`, and
  `73_build_contracts.py` sets up only under `__main__`.
- In `02` and `03`, setup comes after the `sys.path` insert.
- Each notebook calls `use_databricks_secret` after the package is installed, where the `tracking` import already sat.
- The jobs.yml edits sit in the right tasks, and the YAML parses. The SQL `llm_judge` job is excluded, with the
  reason given in the docs and the issue.
- No new settings: the existing `telemetry_exporter` bundle variable and secret are reused, and a missing secret
  still turns telemetry off, never the job.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
All three are fixed in e64a01f.
1. **`python/scripts/15_judge.py`: simulated dry run labelled synthetic.** The label tested `--simulated`, a flag
   the script doesn't have. Its dry run is `--backend simulated --simulated-review`. Verified by evaluating the
   expression on the documented command line, which gave `synthetic`. Fixed: the label now reads the parsed
   arguments, matching the script's own `simulated_` output prefix.
2. **`python/scripts/34_phi_tagger_regex.py`: MACCROBAT labelled synthetic.** It reads `data/external/maccrobat`,
   as 32 and 33 do, and those are labelled `public`. Fixed: `public`.
3. **Notebooks 10–14: run span never ended.** `start_script` ends the span at `atexit`, which a notebook's process
   may not run. Fixed: each in-process notebook calls `telemetry.end_script()`. In 13 and 14 the call comes before
   their deliberate alert `raise`. A notebook's error goes to IPython, not `sys.excepthook`, so a failed notebook
   doesn't mark its run span failed. The failure stays on the raising function's `@traced` span, and
   `docs/telemetry.md` now says so.

### 🔵 Nits / suggestions (Minor)
All five are fixed in e64a01f.
4. **`docs/telemetry.md`: incomplete list of in-process notebooks.** `01_run_benchmark` and `07_judge_scorecard`
   (which makes the paid judge calls) run package code in-process without `setup()`. Fixed: both now set up,
   start and end a run span, and the docs list all seven.
5. **`python/scripts/39_telemetry_levels.py`: a ternary that is always false.** The script has no `--simulated`
   flag. Fixed: `synthetic`.
6. **`python/scripts/14_benchmark_cost.py`: `--simulate-missing` runs labelled synthetic.** That flag adds simulated
   predictions. Fixed: `simulated` when the flag is given.
7. **`python/scripts/73_build_contracts.py`: tests leave telemetry state behind.** `test_data_contracts.py` and
   `test_data_products.py` call `main()` in-process, which replaced `sys.excepthook` and left a run span open.
   Verified by calling `main(['--check'])`. Fixed: setup only under `__main__`.
8. **`python/tests/test_telemetry_scripts.py`: gaps.** It accepted any label and didn't check the in-process
   notebooks. Fixed:
   - a table of the scripts whose label must say `public` or name their dry-run flag;
   - a check that no label tests a flag its script never declares;
   - a check that the seven in-process notebooks set up, start and end a span named for themselves.

   Re-run against the pre-fix code, the new checks fail on findings 1, 2, 3, 4 and 6.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | Scan clean |
| Synthetic only, no PHI | ✅ | No data files changed |
| No organization claims; vendors cited | ✅ | None made |
| Test first | ✅ | `test_telemetry_scripts.py` failed first (52 scripts, 9 job tasks), then the review's new checks failed before e64a01f |
| Python and R in parity | ✅ | No labels, scoring, reliability or cost-effectiveness changed; `r-parity` green |
| Simulated is labelled simulated | ✅ | Dry runs now label their spans `simulated` |
| Seeds fixed | n/a | No new generators |
| Paths | ✅ | No hard-coded `data/` added |
| Spec for big changes | ✅ | Work under spec 014 US1; a chore issue (#712), no dataset, metric or label-rule change |
| Prices | n/a | |
| Deck figures | n/a | |
| Commits | ✅ | Imperative subjects, bodies say why, `Closes`/`Refs #712`, co-author trailers |
| Docs | ✅ | `docs/telemetry.md` describes the coverage and the notebook failure limit |
| Configuration | ✅ | Existing `telemetry_exporter` reused; every environment gets it on its next deploy, as the PR says |
| Secrets register | ✅ | No new credential; the existing Application Insights secret is reused |
| Idempotent writes | n/a | No table writes changed |
| Alerts | n/a | No new alerts |

## Test Coverage
- `test_telemetry_scripts.py` (7 tests) covers:
  - script setup and run-span names;
  - labels, including public and dry-run;
  - flags tested in labels;
  - the job switch and the notebooks reading it;
  - the in-process notebooks' setup, start and end.
- Run locally: the full suite on c23cc58 (2540 passed, 37 skipped). After the later commits:
  - the 475 tests that read the notebooks;
  - the 184 that load the edited scripts;
  - 241 across the telemetry, contracts, data products, bundle, doctor job, judge scorecard, tracking and wording
    tests.
- `ruff check` on the changed files reports nothing that `main` doesn't already report.
- Not covered: the Databricks runs themselves (no workspace here). The spans reach Application Insights on each
  job's next run.

## Verdict
Approve. Nothing blocking remains. Merge once `python` and `python-databricks-runtime` are green on e64a01f. The PR
changes deployed job parameters, so it deploys to dev on merge, but it starts no run and publishes nothing.
