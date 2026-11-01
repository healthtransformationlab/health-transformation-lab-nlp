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
