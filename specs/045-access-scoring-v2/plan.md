# Implementation Plan: AccessBench scoring v2 (spec 045)

**Date**: 2026-11-25

## US1 (#943)

`access_keypoint_judge.positive_points(row)` = `must_include` minus entries starting "Does not", "Do not", "Omits" or
"Never"; `negative_checks(row)` = those plus `red_flags`. Coverage is computed from the judge's existing per-point
`covered` list on the padded `key_points`: the positive points are those indices, so v2 verdicts score without a new
prompt. `score_verdict` returns `covered`; `access_batch.run` adds `positive_point_count`,
`covered_positive_point_count` and `coverage_ratio`. `score_ratio` stays as the legacy padded score. Gold columns via
`gold_names`, `gold_model` (diagrams), `scripts/73_build_contracts.py`.

## US2 (#944)

Prompt v3 asks for `point_verdicts: [{verdict, span}]` over `positive_points`, `next_step_pass`, harm with the spec's
definitions and the fit-based resource level. `parse_verdict` accepts v1/v2 shapes. New columns `is_next_step_pass`,
`point_verdict_text`.

## US3 (#945)

`benchmarks/access_bench/controls/control_answers.jsonl` and `access_controls.py`; `access_batch.run(controls=True)`
adds `control:<label>` rows.

## US4 (#946)

`access_phi_items.GATED_TYPES`; normalized matching before `deid.leak_check`; item fields and validators; items
updated with jurisdiction and dates.

## Constitution check

Synthetic only; test first; names follow AGENTS.md; no blended number.

## US5 (#957)

Edit the item files directly; `docs/access_bench_key_v2.md` lists each change and who asked; new sources named, `source_verified_date` null until opened.
