# ADR 0006: Agent sessions keep a one-year workspace token, held as a network secret

Date: 2026-11-15 · Status: accepted · Issue: #749

## Context

Agent sessions read the dev workspace's job runs and their errors with a workspace personal access token. Until
now the rule (AGENTS.md's credentials table and `ops/secrets_register.yaml`) said:
- scope `all-apis`, 15 days at most, revoked when not needed;
- kept in the cloud environment variable `DATABRICKS_TOKEN`.

**What happened:** the 15-day token expired on 2026-11-11, and nothing replaced it. On 2026-11-15 a session needed
the job runs to find why every deploy was failing (#742), and its call was refused: "Invalid access token".

**The token now in use:** the owner then saved a token for agent sessions as a network secret of the agent's cloud
environment, for the dev workspace's host.
- The session's proxy adds it to requests to that host. No variable in the session holds it, so a command, a file
  or a log in the session can't print it.
- It was made on 2026-10-12, has scope `all-apis`, and expires on 2027-10-12: one year.

The owner chose to keep it rather than replace it with a 15-day token ("keep", November 15, 2026, #749).

## Decision

- **Lifetime:** the workspace token agent sessions use may live up to one year.
- **Where it lives:** a network secret of the agent's cloud environment for the dev workspace's host, never in a variable.
- **The variable:** `DATABRICKS_TOKEN` in the cloud environment holds only a placeholder, never a real token (#784
  sets it). It stays set because the Databricks CLI and the repository's code read it (`databricks_ai`, `llm_reader`,
  `tracking`, `scripts/36_judge_scorecard.py`, `scripts/41_databricks_ai_methods.py`), and the proxy replaces it.
- **Renewal:** the register gives the token's expiry, and it is renewed 14 days before, as every credential is.
- **Scope of the decision:** this covers only the token agent sessions use. Every other credential keeps its own
  lifetime in the register.
- **Why:** the owner's choice ("keep"); no other reason was given.

## Consequences

- **Fewer lapses:** no renewal every 15 days, and fewer gaps like November 11–15, when agent sessions couldn't read
  why a deploy failed.
- **Longer exposure:** a token that leaked would stay valid much longer, and it reaches far. It acts as its owner, a
  workspace admin, with `all-apis`. It can:
  - read the workspace's secret scope `health_transformation_lab` (the Hugging Face token, the Application Insights
    connection string);
  - start jobs on the shared Free Edition allowance and call serving endpoints;
  - make other tokens and service-principal secrets.
- **What it reaches:** everything in the dev workspace, not only this repository's tables.
  - This repository's jobs write synthetic data there, and public NHANES survey files.
  - On 2026-11-15 the landing volume held no copy of the John Snow Labs 48-note file. That file is real clinical
    text, which the de-identification benchmark's `jsl48` tier reads from a volume when it is run with it
    (`06_deid_benchmark.py`).
- **What the network secret does:** it keeps the token out of the session's environment, files and logs. It doesn't
  narrow what the token can do.
- **Later warning:** the digests' forecaster raises it 90 days before it expires (from 2027-07-14), not every
  fortnight.

## Revisit when

- the token is renewed (by 2027-09-28): keeping a year then is a new choice;
- the token may have leaked;
- real clinical text is put in the dev workspace (the de-identification benchmark's `jsl48` tier);
- agent sessions are given access to uat or prod;
- the network-secret storage changes so that a session could read the value.
