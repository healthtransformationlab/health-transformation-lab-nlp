# PR 865 review: each note-reading model ranked, paired against the leader and its neighbours, with what drives its score

Closes #863. Range: `origin/main..feat/863-042-model-drivers`. Files: `python/health_transformation_lab_nlp/model_drivers.py`
(new), `python/scripts/74_model_drivers.py` (new), `python/tests/test_model_drivers.py` (new),
`data/datasets/model_drivers/*.csv` (new, 7 tables), `docs/model_drivers.md` (new, generated), `docs/edr/README.md`
(a generated block), `README.md` (one link in an existing row), `specs/042-model-drivers/` (new).

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none. No settings, no credentials.
- **Real data:** none. Every input is a committed prediction on the synthetic review charts.
- **Claims:** every number on the pages is computed from `ladder_preds.csv` by the script, and `--check` fails when a
  page is stale. Counts read after the runs are labelled "described, not tested". Each pair has its own exact
  McNemar p. Pooled counts over pairs are never given a p, because the pairs share charts.

## Findings (verified)

1. **The landing README's 80-line limit** (`test_decks.py`) failed when the block went into `README.md`. Fixed: the
   block moved to the study page, and the landing page links to the drill-down from its existing Scientists row.
2. **Model features add almost nothing to the AUC (0.52 alone; 0.80 → 0.80 added to chart facts)**, while the
   pair-by-pair contrasts show a +6 median for the stage 4 rule. These don't contradict each other: the fit is
   additive and has no interactions, and the stage 4 rule only helps stage 4 charts (12 of 223). The page says this,
   and the spec lists interactions as out of scope. An earlier draft named "larger model" as "the biggest model
   driver" when its AUC drop was 0.001. That was misleading and is gone.
3. **The seed noise floor is as large as the feature medians** (−6 to 0 against +6). The README block says so and
   names the only feature with pairs below p = 0.05 (larger model, 2 of 6).
4. **The stage 4 rule uses the answer key's own rules**, which flatters it on synthetic charts. The README block says
   so next to the number.
5. **Every public function is traced** (`test_telemetry_calls.py`), fixed in the second commit.

## Compliance

- Spec first: `specs/042-model-drivers/` covers both stories, with issue numbers next to them.
- Branch `feat/863-042-model-drivers`, issue #863, `Closes #863`.
- Data names: typed suffixes throughout (`_count`, `_pct`, `_ratio`, `_code`, `_text`, `is_`). No bare `name`,
  `type` or `value`.
- Test first: `test_model_drivers.py` was written and failed (no module) before the code.

## Checks

- `pytest tests/test_model_drivers.py tests/test_decks.py tests/test_readme_results.py tests/test_telemetry_calls.py`:
  all pass. The full suite: 3,042 passed, plus the one telemetry failure fixed in the second commit.
- `python scripts/74_model_drivers.py --check` and `python scripts/35_readme_results.py --check`: both exit 0.

## Verdict

Approve. Docs and a new analysis only. Nothing changes in an existing number or in any environment.
