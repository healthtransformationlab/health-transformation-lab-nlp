# PR 860 review: spec 041, coding-agent traces in Unity Catalog, declared in the bundle

Refs #855 (epic). Range: `origin/main..spec/855-041-agent-traces-uc`. Files: `specs/041-agent-traces-uc/spec.md`,
`plan.md`, `tasks.md` (all new).

## Scans

- **Secrets:** none. The workspace host and token are named only as settings; no values appear anywhere.
- **Real data:** none. The traces are coding-agent runs on public code, scrubbed under ADR 0010.
- **Organization claims:** none. Databricks features are described from Databricks' own docs, which are linked.

## Findings (verified)

- 🟡 Should fix (not blocking): the spec says the probe worked on default storage, while Databricks' docs exclude
  default storage catalogs. Both are true today. The spec lists it as the first risk, and US1's PR is where the field
  itself is first tried.
- 🟡 Should fix (not blocking): each merge deploys uat as well as dev. If uat's workspace lacks the preview, US1 has
  to declare the experiment under the dev target only. The spec's Risks say so, and US1's PR decides it from the
  deploy log.
- 🔵 Nit: the four story issues (#856 to #859) copy their names from `plan.md`'s table. Checked by eye: the schema,
  experiment, prefix, files, columns and setting match.

## Compliance

| Rule | Result |
|---|---|
| Spec before code | ✅ no code in this PR; each story's issue names the spec |
| Issue has four parts | ✅ #855 to #859 each have Problem, Done when, Contract and Read first |
| Epic with sub-issues (specs from November 14) | ✅ #856 to #859 are sub-issues of #855 |
| SQL and data names | ✅ the two views and the count table use singular names and typed suffixes. Databricks' own tables keep their names (FR-002), as OMOP's do |
| No number is a result until a run produced it | ✅ the only counts are the 414 traces and 65 verdicts, from the MLflow runs named in the private repository's PR 21 review |
| Wording and organization tests | ✅ `test_wording.py`, `test_no_org_references.py`, `test_bench_order.py`: 37 passed |

## Verdict

Ready to merge once CI is green. It is docs only and changes no environment.
