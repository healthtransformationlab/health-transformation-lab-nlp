---
pr: 413
branch: ci/374-copy-decks-to-site
title: "000 CHORE3: copy the built decks to the website automatically when they change on main"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: coordinator verification (no reviewer subagent run)
verdict: approve
---

# PR Review: 000 CHORE3: copy the built decks to the website automatically

## Summary
This implements issue #374 as written. A workflow rebuilds the website's copies of the two decks and their covers
on every push to main that touches them, and by hand. It commits to the site only when something changed, naming
the source commit. The copy logic is a small standard-library script with its own tests.

Building against the live site's current copies leaves both decks byte-identical, so the icon links the script adds
are exactly the ones the site carries today. Approve, once the owner has made the token.

## Tests
- A site copy equals the deck plus exactly the icon links, for both decks.
- The build reports only changed files and leaves the site's other pages alone.
- A missing or malformed token fails naming `SITE_PUSH_TOKEN`, without echoing the value.
- The workflow's triggers, step order (token check, push check, build) and commit-only-on-change are checked.
- Full suite: 1214 passed, 16 skipped.

## Secrets, PHI and Claims Scan
Clean.
- **Token:** checked before any work (shape, then a `git push --dry-run` that needs write access). It goes in an
  HTTP header from the environment, never into a URL, `.git/config` or `$GITHUB_ENV`; its base64 form is masked.
- **Register:** the new entry names where it is made, its scope, where it is stored, what breaks and who renews it.
  `expires: unknown` until it is created (the register allows only a date, `never` or `unknown`).
- **Data:** none. Only the decks and their covers are copied.

## Findings
None blocking.
- **Not yet run:** the workflow fails at its first step until `SITE_PUSH_TOKEN` exists. Run it once by hand after
  saving the secret, then write the expiry date in the register.
- **Icon links are pinned:** if the site changes its icon links, update `ICON_LINKS` in the script and the test.
- **Organisation approval:** a fine-grained token owned by the organisation may need approving there before it works.

## Rubric
- Configuration: one setting (`SITE_PUSH_TOKEN`), checked before work, failing at once naming it.
- Secrets register: updated in the same PR, and the AGENTS.md credentials table too.
- Idempotent writes: a rerun with nothing changed commits nothing.
- `Closes #374`; branch `ci/374-copy-decks-to-site`.
