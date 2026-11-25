# Decision records

A decision record (ADR) says what we decided, why, and what would make us revisit it.
Action items say what still has to be done. They are kept apart:

| | Lives in | Closed when |
|---|---|---|
| **Decision** | `docs/adr/NNNN-slug.md`, numbered in order, never renumbered | never closed: a later ADR supersedes it |
| **Action item** | a GitHub issue labelled `action-item` (or a row in [action_items.md](../action_items.md)) | the work is merged |

An issue may ask for a decision to be *made* or *written down*; the decision itself goes in an ADR,
and the issue is closed by the pull request that adds it. Work a decision leads to gets its own issue.
Don't record a decision only in an issue thread or a PR description.

## Writing one

Copy [template.md](template.md) to the next number. Status is `proposed`, `accepted`, or
`superseded by NNNN`. To change a decision, write a new ADR and mark the old one superseded;
don't rewrite the old one.

## Index

| # | Decision | Status |
|---|---|---|
| [0001](0001-synthetic-public-two-languages.md) | Synthetic data, public repo, R and Python against one contract | accepted |
| [0002](0002-no-feature-store-for-now.md) | No feature store for now | accepted |
| [0003](0003-static-data-quality-page.md) | The data-quality report is a static page, not a FastAPI app | accepted |
| [0004](0004-task-set-under-two-licences.md) | The coding-agent task set is offered under CC BY 4.0 or Apache 2.0 | accepted |
| [0005](0005-colab-runs-need-the-open-network-accepted.md) | A Colab run starts only when its entry accepts an open network | accepted |
| [0006](0006-agent-sessions-keep-a-one-year-workspace-token.md) | Agent sessions keep a one-year workspace token, held as a network secret | accepted |
| [0007](0007-gpu-hours-are-a-reserve-and-score-questions-go-to-the-leaderboard.md) | GPU hours are a reserve; score questions go to the leaderboard | accepted |
| [0008](0008-modal-runs-start-on-their-own-under-a-cost-cap.md) | Modal runs start on their own under a cost cap; above it they wait for the owner | accepted |
| [0009](0009-task-sets-not-an-r-parity-input.md) | The task sets are not an R parity input | accepted |
| [0010](0010-agent-run-traces-may-carry-full-content.md) | A coding-agent run's own trace may reach telemetry in full; dental records never do | accepted |
| [0011](0011-kaggle-gpu-weekly-threshold.md) | Kaggle GPU runs may start under a weekly threshold (amends 0007) | accepted |
| [0012](0012-retire-the-old-trace-experiment.md) | Retire the old trace experiment /Shared/gemma-agent-runs | accepted |
| [0013](0013-loader-owned-model-ranking-experiments.md) | The two model-ranking MLflow experiments are made by their loaders, not the bundle | accepted |
| [0014](0014-accessbench-oral-medical-mental-sections.md) | AccessBench covers oral, medical and mental health access, oral first | accepted |
