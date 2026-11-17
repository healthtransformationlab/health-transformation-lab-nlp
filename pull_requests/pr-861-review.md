# PR 861 review: the bundle declares the agent-trace schema and an experiment bound to it

Closes #856. Range: `origin/main..feat/856-041-agent-traces-bundle`. Files: `databricks/resources/agent_traces.yml`
(new), `python/tests/test_agent_traces_bundle.py` (new), `.github/workflows/ci.yml`, `.github/workflows/deploy.yml`,
`docs/deployment.md`, `specs/041-agent-traces-uc/tasks.md`.

## Scans

- **Secrets:** none. The grant names a group, not a person; no email address is in the bundle
  (`test_no_email_address_is_written_in_the_bundle_or_the_deploy` passes).
- **Real data:** none. **Organization claims:** none.

## Findings (verified)

- 🟡 Should fix (not blocking): `trace_location` is a Private Preview field. `bundle validate` accepts it and the
  probe's API call worked, but the deploy is the first time the bundle itself creates such an experiment. If the deploy
  fails at the experiment, the follow-up keeps the schema and moves the experiment under the dev target, recorded on
  #856.
- 🟡 Should fix (not blocking): `auth_check.yml` and `catch-up.yml` still pin CLI 1.3.0. They only sign in and list job
  runs, never the bundle, so they need nothing newer. The test covers the two workflows that read the bundle.
- 🔵 Nit: the experiment is a bundle resource under `/Shared`, not under `${workspace.root_path}` as
  `dental_experiment` is. That is on purpose: the loader (US2) and people find it at one path in every target.

## Compliance

| Rule | Result |
|---|---|
| Test first | ✅ 4 of the 5 new tests failed before the YAML and the pin |
| Settings change by PR, saying which environments | ✅ the description lists dev, uat and prod |
| Same names in every target | ✅ declared at the top level, no per-target names |
| prevent_destroy on data | ✅ schema and experiment |
| Spec before code | ✅ spec 041 merged (#860); plan.md on main |

## Checks

- `databricks bundle validate -t dev` with CLI 1.22.1: `Validation OK!`
- `pytest -q tests -k "ci or workflow or deploy or bundle or genie or dashboard or wording or org_ref"`: 477 passed,
  2 skipped.

## Verdict

Ready to merge once CI is green. After the merge deploy, record the experiment's trace location on #856 (T005).
