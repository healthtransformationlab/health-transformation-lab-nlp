---
pr: 466
branch: feat/446-032-preset
title: "032 US7: a named preset runs the analysis options together"
author: jcbowyer
reviewed_at: 2026-11-01
reviewer: self-review (agent), against .claude/review-rubric.md
verdict: approve-with-nits
---

# PR Review: 032 US7: a named preset runs the analysis options together

## Summary
This PR adds `analysis_presets.yaml` with two presets. `repo_v1` holds today's defaults, written out, and a test
checks each one against the code. `exploratory_1` turns on the spec's options together. `presets.py` loads, checks
and runs a preset. `scripts/58_preset.py` runs a preset beside `repo_v1` and writes 21 synthetic CSVs to
`data/datasets/presets/`. `docs/presets.md` explains it all. No existing behaviour or committed result changes.
Approve with nits.

## Scope of Change
- Files changed: 28 (21 of them generated CSVs)
  - code: `presets.py`, `analysis_presets.yaml`, `scripts/58_preset.py`;
  - tests: `tests/test_presets.py`;
  - docs: `docs/presets.md`, a link in `docs/tooth_loss.md`, T007 ticked in `specs/032-analysis-options/tasks.md`;
  - data: `data/datasets/presets/synthetic_preset_{exploratory_1,repo_v1}_*.csv`.
- Areas touched: python, docs, data.

## Secrets, PHI and Claims Scan
- **Secrets:** none in the diff.
- **PHI / real data:** none. The CSVs are aggregates of generated data. Group names are generator values: office
  numbers, provider numbers, race categories, age bands and insurance types.
- **Organisation claims:** none. The presets and comments name settings only. The start dates are commented as
  synthetic stand-ins. `test_no_org_references.py` and `test_wording.py` pass.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important)
None.
### 🔵 Nits (Minor)
- **Output folder and script number differ from the spec.** The spec names
  `scripts/56_exploratory_preset.py` writing to `data/results/`. 56 is taken, and `data/results/` is git-ignored (it
  can move to a Volume via `DENTAL_DATA_ROOT`). The PR uses `58_preset.py` and `DATASETS_DIR / "presets"` (committed),
  and says so in the PR body. The spec text can be brought in line when US8 touches it. This PR doesn't edit the spec
  beyond the task tick, per the brief.
- **`stage4_rules` shows "changed: no".** US4 already reports the 20-teeth and 10-pairs rules by default, so both
  presets list all six. That is accurate, and the docs say why.
- **Tooth-loss exclusions use the same count as script 51.** They come from `tooth_table` plus `with_first_exam_date`,
  which reads the age at first exam, while `run()` filters on the age at loss. With `min_age` 18 on this synthetic
  extract both give 0 under age. This is inherited behaviour and not changed here.
- **Each preset regenerates both synthetic data sets.** This doubles the generation time (about 6 minutes in all,
  most of it XGBoost tuning). That is fine for a manual script.
- **Small held-out set under `exploratory_1`.** The 2018 start date and the 20% test share leave 88 held-out teeth
  (242 under `repo_v1`), and there are no bootstrap intervals (`--n-boot 0`). The docs warn not to read the higher AUC
  as a better model.

## Test Coverage
- 26 new tests in `tests/test_presets.py`, written first; they failed on import before `presets.py` existed:
  - loading, unknown preset, unknown or missing setting, bad values (each naming the setting);
  - `repo_v1` against every current code default, one test per setting, with a guard that every setting has one;
  - the settings table;
  - small end-to-end runs of both presets: every part present, labelled synthetic, with `preset_name`; visits left
    out by start date; groupings; all six stage rules; people in both parts reported; insurance in the consistency
    split; ICC only when turned on.
- Full suite: 1613 passed, 16 skipped. `ruff check` is clean on the changed Python files.
- Determinism: two runs of `run_preset` give byte-identical CSV text for every part.
- `repo_v1` reproduces the committed `data/datasets/classify_status` summaries exactly: accuracy 0.797 for 5level and
  0.881 for 3level.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | Generated data; every row `data_label=synthetic` |
| No organization claims | ✅ | Presets name settings only |
| Test first | ✅ | Failing test commit first (3cde4fa) |
| Python and R in parity | ✅ n/a | No labels, scoring, stage rule or reliability code changed; R parity not run |
| Simulated is labelled simulated | ✅ | Files `synthetic_*`; docs and printout say SYNTHETIC; the ICC's placeholder components are called out |
| Seeds fixed | ✅ | Generator seed 42, classifier seed 3, ICC seed 13, all defaults |
| Paths | ✅ | `DATASETS_DIR`, `REPO_ROOT` from `paths.py` |
| Spec for big changes | ✅ | Spec 032 US7, T007 ticked |
| Telemetry | ✅ | Every public function in `presets.py` has `@traced` |
| Words | ✅ | No "diagnose"; we find gum disease in records |
| Configuration | ✅ | Settings checked before any work; the script loads both presets first |
| Commits | ✅ | Imperative subjects, bodies say why, trailers present |
| Docs | ✅ | `docs/presets.md`, linked from `docs/tooth_loss.md` |

## Verdict
Approve with nits. With no preset run, no other committed result changes. US8 flips the defaults later.
