# PR 926 review: publish the AccessBench deck at healthtransformationlab.org/access-bench

Closes #925. Range: `origin/main..docs/925-043-publish-access-deck`. Files: `.github/scripts/copy_decks_to_site.py`,
`.github/workflows/copy-decks-to-site.yml`, `docs/build_decks.py` (`SITE_PAGES`), the three rebuilt `deck.html`
files, `python/tests/test_copy_decks_to_site.py` and `python/tests/test_pptx.py`.

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none. The workflow's credential handling (`SITE_DEPLOY_KEY`, else `SITE_PUSH_TOKEN`) is unchanged.
- **Real data:** none.
- **Claims:** no slide text changes. Only the top nav gains an AccessBench link.

## Findings (verified)

1. **This PR publishes outside the repo**, so under AGENTS.md rule 6 it waits for the owner's "merge". The owner
   gave it in the session on 2026-11-24 ("Do it", replying to "putting it on the site ... needs your go-ahead").
2. **The two existing deck pages change on the site too**, but only by the new nav link: `git diff` shows one changed
   line in each `deck.html`.
3. **No cover image** for AccessBench. The README section has none, so none is copied; `COVERS` is unchanged.
4. **The site's home page** lives in the website repository and isn't touched here. The deck is reachable from the
   other two decks' nav and at its own URL.

## Checks

- `pytest tests/test_copy_decks_to_site.py tests/test_pptx.py tests/test_decks.py tests/test_deck_claims.py
  tests/test_bench_order.py`: 170 passed. Both changed tests failed before the change.

## Verdict

Approve, merging on the owner's go-ahead once CI is green.
