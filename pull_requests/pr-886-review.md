# Review: weekly Kaggle GPU threshold (#886)

## What changed
- ADR 0011: above ~10h reserve floor, Kaggle GPU may start without a fresh yes; at/below floor and for submissions, yes required. Amends ADR 0007.
- AGENTS.md rationing bullets match ADR 0011.
- Test asserts weekly threshold + ADR 0011.

## Risk
Policy only. Does not start GPU runs. Colab remains default.
