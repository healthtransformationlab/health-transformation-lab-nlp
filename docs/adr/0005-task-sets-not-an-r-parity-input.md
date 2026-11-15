# ADR 0005: The task sets are not an R parity input

Date: 2026-11-15 · Status: accepted · Issue: #715

## Context

`.github/scripts/parity_needed.py` decides whether a pull request starts the `r-parity` job. Every path under `data/`
counted as a possible input, so a pull request that changed only `data/tasks/` (the coding-agent task sets) started
it too. On November 11, #675 and #676 changed only task files, the job couldn't install R (#677), and both were merged
without it. But no script `make_parity_inputs.sh` runs reads `data/tasks/`, and neither does `r/tests/test_parity.R`.
The R test reads only `data/datasets/` and `data/labels/`.

## Decision

The owner decided on November 15, 2026 that `data/tasks/` is not a parity input. `parity_needed.py` leaves it out
(`NEVER`). Everything else under `data/` still starts the job, as do pushes to `main`, manual runs and the Monday run,
which always run parity.

## Consequences

A pull request that changes only task files no longer waits on a five-minute R job, or on R's installer. A test
(`python/tests/test_parity_needed.py`) checks that a change only under `data/tasks/` gives `needed=false`, while one
under `data/datasets/` or `data/labels/` still gives `needed=true`.

## Revisit when

A parity script or `r/tests/test_parity.R` starts reading anything under `data/tasks/`.
