# PR #764 review: make the Colab helper fail loudly where it failed quietly

Closes #691. Reviewed against `.claude/review-rubric.md`, AGENTS.md and #691's "Done when".

## Verdict
Nothing blocking.

## Checks
- **Done when:** each of items 1-8 has a test that fails with the old code put back (commit ced66c8 records that
  check). Item 6 can't be fixed from the repository, since blocking the network needs the machine. It is guarded by an
  explicit per-run acknowledgement and recorded as ADR 0005, which #691 allows by saying a later run must
  check it first.
- **Check settings before doing work (AGENTS.md):** `check_colab_options` fails before any Kaggle call. A failed
  status call or an unreadable run list now stops the run instead of guessing.
- **No run, no publish:** stand-ins only, and the committed run list doesn't accept an open network (tested), so
  merging starts nothing.
- **Registered analyses kept:** #691 asks that #687's analyses keep the audit as committed. The new counts are
  added beside the old ones (`tool_call_count`, `network_tool_call_count`); `command_count` and
  `network_command_count` are unchanged.
- **Conflicts:** none with `main` or open PR #740.

## Not blocking
- The four kernel assertions that only search source text remain (a smaller item in #691).
- The size check trusts Kaggle's `total_bytes`. If Kaggle ever reports compressed sizes, a run stops rather than
  going on, which is the safer failure.
