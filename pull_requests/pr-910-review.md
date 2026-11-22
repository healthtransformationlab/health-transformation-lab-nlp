# PR 910 review

Closes #909. Refs #849. Range: tip of `data/849-028-colab-public-bundle` (Colab run branch; ADR 0005, not for merge to main).

## Scope
- `kaggle/colab_official_run.json`: drop unfinished e8fixtests arms (keep finished c2); queue `devset-exp025-c1..c4` at the top.
- `kaggle/official_agent_bundle.py` + test: keep `LICENSE.txt` / `NOTICE.txt` when present (Apache 2.0 public archive).

## Checks
- Uploaded private packs match `c31be8fix` task order; LICENSE/NOTICE member hashes match the notebook manifest.
- `colab_status.py --gpu A100` → `next on A100: devset-exp025-c1`.
- Private idea note: gemma-developer-agent-private#84.

## Blocking
None for the queue. Do not merge this branch to main (ADR 0005). Cherry-pick the LICENSE packing change separately if main should keep it.

## Non-blocking
- Stale arms still on the list (`devset-cidris-c1/c4`, `devset-cpub-r2-c4`) sit below the new queue; status still picks exp025-c1 first.
