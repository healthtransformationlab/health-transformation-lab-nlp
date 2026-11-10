# PR 639 review: 000 CHORE45: license the repository under Apache 2.0 (#638)

Reviewed against `.claude/review-rubric.md` and AGENTS.md by the authoring session (no reviewer subagent run).

| Check | Result |
|---|---|
| Branch `chore/638-000-apache-licence`, `Closes #638` | ok |
| `LICENSE` is the unmodified Apache 2.0 text (SHA-256 `cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30`) | ok |
| `python/pyproject.toml`, `README.md` and the footer of `docs/edr/README.md` agree with `LICENSE` | ok |
| The `docs/edr/README.md` line changed is hand-written, outside the generated blocks | ok: the phrase appears nowhere in `readme_results.py` or `35_readme_results.py` |
| Guard tests that read the README, docs and names (eight files) | ok: 107 passed |
| Secrets, PHI, organisation claims | clean |
| Full suite and R parity | not run here; CI runs them |

## Notes
- `kaggle/cards/tasks.md` is left saying the repository's own files inside the published snapshots are MIT. That is
  still true: each snapshot is the repository at an earlier commit. When the task set is next published from commits
  after this one, the card should say which snapshots are which.
- `NOTICE` names the third-party files that keep their own licences.
- Versions already published under MIT stay available under MIT.

## Blocking
None. A change of licence is the owner's decision; the owner asked for it in the session that opened this.
