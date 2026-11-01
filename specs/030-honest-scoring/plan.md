# Implementation Plan: say plainly what a synthetic score means (spec 030)

**Spec**: [spec.md](spec.md) · **Issue**: #387

1. Tests first (`test_ladder_eval.py`, `test_readme_results.py`): `stageable`, `uses_answer_key_rules`, the
   leaderboard's flag and link, and the scoring page.
2. `ladder_eval.stageable` and `uses_answer_key_rules`, each `@traced`.
3. `28_ladder_vs_truth.py` writes `ladder_by_stageable.csv`; `r/tests/test_parity.R` recomputes it with
   `by_difficulty` (no new R function needed).
4. `readme_results.py` marks rule-sharing methods and links `docs/scoring.md`; rerun `35_readme_results.py`.
5. `docs/scoring.md`; one line in the Hugging Face results card; a scoring page on the website (its own repo).
