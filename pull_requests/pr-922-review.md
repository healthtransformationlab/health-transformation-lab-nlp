# PR 922 review: loader-owned model-ranking MLflow experiments (ADR 0013)

Closes #921. Range: `origin/main..docs/921-042-loader-mlflow-experiments`. Files:
`docs/adr/0013-loader-owned-model-ranking-experiments.md` (new), `docs/adr/README.md`,
`specs/042-model-drivers/spec.md` (Risks), `README.md` (PerioBench pitch slide count).

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none. Docs only.
- **Real data:** none. Mentions of workspace experiment paths and the already-loaded synthetic reader traces only.
- **Claims:** the two experiment names and loader entry points match `model_drivers_load.py` /
  `tooth_loss_drivers_load.py`; the bundle still declares only `/Shared/coding-agent-runs`.

## Findings (verified)

1. **Decision matches what is already true in code.** The loaders create the experiments; the ADR records adopt,
   not rebuild, so deploy stays free of a name clash.
2. **Spec 042 Risks no longer leaves the choice open.** It cites ADR 0013.
3. **Landing README said "13 slides" after #880 made the main path 7 plus appendix.** Updated in this PR so the
   lab and the website CTA can agree; the website homepage fix is a separate PR on the site repo.

## Checks

- `pytest tests/test_wording.py tests/test_no_org_references.py tests/test_decks.py tests/test_bench_order.py`:
  53 passed.

## Verdict

Approve. Docs and ADR only; no environment change. Merge under AGENTS.md #497 once CI is green.
