# PR 928 review: the deck copy workflow stages access-bench/index.html

Closes #927. Range: `origin/main..fix/927-043-stage-access-deck`. Files: `.github/workflows/copy-decks-to-site.yml` (one
path added to `git add`) and `python/tests/test_copy_decks_to_site.py` (one regression test).

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none. The credential steps are unchanged.
- **Real data:** none.

## Findings (verified)

1. **Root cause:** run 45497653299 logged "changed: access-bench/index.html", but the commit step stages a
   hand-written list of paths, which #926 didn't extend. So the site commit d8d27d0 carried the other two decks'
   new nav link and no page for it to point to. #926's tests checked the script's `DECKS` and the workflow's
   trigger paths, but not this list.
2. **The regression test** reads the `git add` line and asserts that every destination in `DECKS`, `PAGES` and
   `COVERS` is on it. It failed before the fix and passes after.
3. **Merging publishes:** the workflow triggers on its own file, so merging pushes the missing page. That completes
   the publish the owner approved on 2026-11-24 (#926).

## Checks

- `pytest tests/test_copy_decks_to_site.py`: 22 passed.

## Verdict

Approve, merging once CI is green.
