# PR 874 review: each de-identification tool ranked, paired on the same identifiers, with what drives its leaks

Closes #866. Stacked on PR 869. Range: `feat/864-042-model-drivers-uc..feat/866-042-deid-drivers`. Files:
`python/health_transformation_lab_nlp/deid_drivers.py`, `python/scripts/76_deid_drivers.py`,
`python/scripts/77_load_deid_drivers.py`, `python/tests/test_deid_drivers.py` (new); `data/deid/drivers/span_result.csv.gz`
and `data/datasets/model_drivers/deid_*.csv` (new); `docs/deid_drivers.md` (new, generated); `docs/deidentification.md`
(a link); `specs/042-model-drivers/` (US3).

Written by a subagent of the coordinating session and reviewed by the coordinator, who reran the tests and the check.

## Scans

- **Secrets:** none. The loader uses the SDK's own auth.
- **Real data:** none. The identifiers are fake PHI the generator put in synthetic notes. The span file holds offsets,
  categories and hit flags, not note text.
- **Claims:** the per-identifier file reproduces `data/deid/scores.csv` in 60 of 60 tool-tier cells. The coordinator
  checked the leader: 2,599 of 2,714 = 0.9576, the committed entity recall, so 115 leaked, as on the study page.

## Findings

1. **The McNemar p is optimistic.** It treats identifiers as independent, but those in one note move together. The page
   says so, and the CIs and rank ranges resample notes. Read the p values as a ranking aid.
2. **ai_mask is unpaired** (it can't run off Databricks). It is shown from totals with a Wilson interval, with no p
   and no rank range. A paired rerun on the workspace is a follow-up.
3. **Rerun dependencies aren't declared.** Presidio, spaCy `en_core_web_lg`, transformers and CPU torch were
   installed by hand for `--rerun`. `pyproject.toml` has no extra for them. That isn't needed for `--check`, which
   reads the committed span file, but should be added before anyone reruns it in CI.
4. **Nit:** the generated plain-words line reads "regex rules added (none to regex_v2) or extended (regex to
   regex_v2)". It is correct but clumsy; fix it in the generator later.
5. `rank_position_count` is written as a float in the CSV (NaN for the unpaired row). This is harmless.

## Compliance

Spec 042 US3, issue #866 and `Closes #866`. The test was written first. Typed names, every public function traced,
tables replaced on each load with the batch key.

## Checks

`test_deid_drivers.py` and `test_telemetry_calls.py`: 27 passed. `76_deid_drivers.py --check`: 0. Dev workspace:
8 tables, row counts equal to the CSVs, 0 uncommented columns.

## Verdict

Approve after PR 869. Finding 3 (declare the rerun extra) is a follow-up, not a blocker.
