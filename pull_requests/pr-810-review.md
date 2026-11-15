# PR 810 review: docs/telemetry.md records the November 15 end-to-end check

Closes #807. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

- **Scope:** one paragraph and one command in `docs/telemetry.md`; no code, settings or data.
- **Numbers from a run:** AppDependencies 8, AppMetrics 8, AppPerformanceCounters 32 are from the workspace query of
  November 15 after the watcher's 15:02 UTC run (#802); named as such.
- **Secrets:** the command reads the workspace id from `az`; no key, connection string or id is written down.
- **Wording, org name, bench order:** `test_wording.py`, `test_no_org_references.py`, `test_bench_order.py` pass.
- **Rules:** changes no agent rule, starts no compute, publishes nothing outside the repo: an agent may merge it when
  green.

Nothing blocking.
