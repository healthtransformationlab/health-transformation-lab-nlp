# PR 876 review: the tooth-loss model compared with five other kinds of model

Closes #867. Range: `origin/feat/864-042-model-drivers-uc..feat/867-042-tooth-loss-drivers`. Files:
`python/health_transformation_lab_nlp/tooth_loss_drivers.py` and `tooth_loss_drivers_load.py` (new),
`python/scripts/78_tooth_loss_drivers.py` and `79_load_tooth_loss_drivers.py` (new),
`python/tests/test_tooth_loss_drivers.py` (new, 16 tests), `docs/tooth_loss_drivers.md` (new, generated), four
`data/datasets/model_drivers/tooth_loss_*.csv` (new), `docs/tooth_loss.md` (one link), `python/pyproject.toml`
(`interpret-core` in the `ml` extra), `specs/042-model-drivers/` (US4).

Written by a subagent of this session and reviewed by the session. Read it knowing that.

## Scans

- **Secrets:** none. The loader uses the existing settings `DATABRICKS_HOST`, `DATABRICKS_TOKEN` and
  `DATABRICKS_WAREHOUSE_ID`.
- **Real data:** none. A synthetic Open Dental extract made by the generator in this repo.
- **Claims:** every number on the page comes from the script's CSVs, and `--check` fails when one is stale. The
  candidates are labelled post hoc (`is_prespecified = false`) wherever they appear.

## Findings (verified)

1. **The plan's models are reproduced.** I checked the rank CSV against the subagent's table (7 rows, all equal).
   `scripts/51` with its defaults gives the AUCs in `docs/tooth_loss.md`, and a test pins the two plan models to
   `tooth_loss_model.run`.
2. **The recommendation doesn't overreach.** "Keep the plan's models" rests on 20 paired comparisons with no
   candidate beyond the interval. The random-forest gain on teeth missing at entry is reported with its caveats:
   it is scored only against the synthetic key, and calibration there is poor. The page says that any change needs
   an analysis-plan amendment first, and it changes neither the plan nor `tooth_loss_model.py`.
3. **The EBM runs without interactions**, for time (about 3 s against 46 s per fit). The page says so.
4. **The branch was cut before #869's last commit**, so its diff reverted T007's tick in `tasks.md`. Fixed by
   merging the base.
5. **The build takes 45-65 minutes on CPU**, most of it tuning the random forest on the stability seeds. The page
   is regenerated with `--page-only` when only wording changes.

## Checks

- `pytest tests/test_tooth_loss_drivers.py tests/test_telemetry_calls.py tests/test_wording.py
  tests/test_no_org_references.py tests/test_tooth_loss.py`: 69 passed.
- `scripts/78_tooth_loss_drivers.py --page-only --check`: exit 0. The subagent's full `--check` refit reproduced all
  four CSVs byte for byte.
- Databricks: `gold_opendental_perio.tooth_loss_model_rank` / `_contrast` / `tooth_loss_driver` /
  `tooth_loss_model_seed` have 42 / 42 / 364 / 140 rows, one `run_id` each, and 0 uncommented columns. MLflow has
  7 runs; a second load wrote 0.

## Verdict

Approve. A new analysis, its docs and its tables. No existing number, plan or environment setting changes.
