# PR #575 review: 000 DOCS7, the tagline "Evidence you can check" (#573)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Issue and branch | `Closes #573`; branch `docs/573-000-tagline` |
| Test first | `test_the_tagline_is_on_the_readme_and_the_edr_cover` failed before the change |
| Generated files | the deck rebuilt by `docs/build_decks.py` from the edited slide, not by hand |
| README | stays at 80 lines (the landing-page test); the stale "rerun pending (#467)" line now gives the rerun counts from `ladder_vs_truth.csv` (203, 187 and 178 of 223, synthetic) |
| Disclaimer | unchanged: personal project, not affiliated with any organization |
| Tests | full Python suite: 2064 passed |

Nothing blocking.
