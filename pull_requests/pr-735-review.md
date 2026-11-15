# PR #735 review: match Kaggle's form of a file name, which drops the +

Refs #695. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict
Nothing blocking.

## Checks
- **Tests first:** three new tests failed before the change. The card test that changed now expects Kaggle's
  names, which is the point of the fix.
- **No dataset change:** published files keep their current Kaggle names, so no version or `schema_sha256` change is
  needed (spec 039). Only the metadata step and the card text change.
- **No publish in this PR:** re-sending the card (#695 part 2) is a metadata-only run on Kaggle and waits for the
  owner.
- **Scope:** `kaggle_name` only drops `+`, the one character Kaggle was seen to drop. Another character Kaggle
  rewrites would show up the same way, as "not on Kaggle yet".
