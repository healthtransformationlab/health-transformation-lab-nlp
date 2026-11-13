---
pr: 703
branch: feat/702-038-data-contracts
title: "038 US1: an ODCS data contract for every gold table, generated from the gold model"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve
---

# PR Review: 038 US1: an ODCS data contract for every gold table, generated from the gold model

## Summary

The PR gives each of the 33 gold tables an Open Data Contract Standard (ODCS) v3.1.0 contract, generated from
`diagrams/_build/gold_model.py` by `python/scripts/73_build_contracts.py` and validated against the vendored ODCS JSON
Schema. An independent reviewer read the range `origin/main...ab66a4b` read-only and came back approve-with-nits:
two "should fix" findings and four nits. Each was traced here before it was written down, and all six are dealt with in
the last commit (below). The verdict is approve: nothing blocking is left, and merging starts no run and publishes
nothing.

## Scope of Change

- Files changed: 46 (+7,086 / −4). Of those, 33 are generated contracts (about 3,500 lines) and one is the vendored
  JSON Schema (about 3,000 lines). The hand-written part is about 600 lines.
- Areas touched: python, contracts, docs, specs
- Commits:
  - `375ca7e` 038 US1: an ODCS data contract for every gold table, generated from the gold model
  - `ab66a4b` Test the build script's exit-2 paths and contract()'s refusals
  - the review fixes and this file (the last commit)
- Range reviewed: `origin/main...ab66a4b` by the reviewer, then the last commit here

## CI Status

| Check | Status |
|---|---|
| check (PR conventions) | success on `ab66a4b` |
| bundle, postgres, r-parity, azure-infra, changes | success on `ab66a4b` |
| python-databricks-runtime | success on `ab66a4b` |
| python | running on `ab66a4b` when written; the merge waits for every check to be green on the last commit |

## Secrets, PHI and Claims Scan

- **Secrets:** clean over the whole diff, including the contracts and the schema. The only matches are columns named
  `*_token_count` and the schema's example of a `password` format.
- **PHI or real data:** clean. The contracts hold table structure only: names, types, descriptions and keys.
- **Organisation claims:** none.
- **Company claims:** each one cites a source that says it. Ontos's README states ODCS v3.1.0, and its code bundles the
  same schema file vendored here (the SHA-256 matches). DQX's README says it can generate quality rules from ODCS
  contracts.

## Strengths

- One declaration: every contract comes from the gold model, and a test fails when the two drift apart.
- The reviewer counted the mapping independently: 33 of 33 tables, 454 of 454 columns, 55 of 55 primary-key columns
  and 9 foreign keys.
- Output is deterministic: with PyYAML 6.0.1 and jsonschema 4.18.0 in a fresh environment, nothing is stale or invalid.
- Without jsonschema, the module still imports and the script exits 2 with the install command.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

1. **Foreign-key targets didn't resolve under ODCS** (`data_contracts.py`, `_relationships`).
   - **What was wrong:** all nine `to` values used the shorthand `table.column`, such as `dim_result_file.file_sha256`.
     ODCS v3.1.0's references page says the file part can be left out only for elements in the same contract. It
     recommends fully qualified references for references across contracts, and each contract here holds one table.
   - **How it was verified:** the page was read from the `v3.1.0` tag (`docs/references.md`, "Same Contract
     References" and "When to use each"). All nine targets are outside their own contract.
   - **Fixed:**
     - `from` is now `schema/<table>/properties/<column>`, and `to` is
       `<parent>.odcs.yaml#/schema/<parent>/properties/<column>`.
     - The `schema` element and each property carry `id`.
     - Each relationship carries the diagram's `cardinality` and `label` as `customProperties`. The label is what says
       the `dim_result_file` keys hold only for repo and Kaggle rows.
     - The test now resolves every target in the committed file it names.
     - Issue #702 and `plan.md` carry the change as dated lines.

2. **`write_contracts` deleted files it didn't own** (`data_contracts.py`, both globs).
   - **What was wrong:** it removed every `*/*.odcs.yaml` it hadn't just written. That included `schema/`, which its
     docstring said was left alone. With `--root`, it did this in any folder.
   - **How it was verified:** reproduced on a scratch copy, which lost `schema/example.odcs.yaml` and
     `silver_opendental_perio/patient.odcs.yaml`.
   - **Fixed:** both functions now look only in `GOLD_FOLDERS` (`gold_perio_bench` plus the schemas that
     `table_comments.GOLD_SCHEMA` names). A new test puts files in both of those places and checks that neither is
     deleted or reported.

### 🔵 Nits / suggestions (Minor)

3. **The vendored schema was `main`'s copy, not the v3.1.0 release.**
   - **How it was verified:** the vendored file's SHA-256 was `f99a…`, which is `main`'s. The tag's is `2cb7dd6f…`,
     and so is the copy Ontos bundles. The two differ in five places, including the reference and id patterns.
   - **Fixed:**
     - The tag's copy is vendored now, and the README gives the tag URL, the SHA-256 and the match with Ontos's copy.
     - A new test checks the README's SHA-256 against the file. It caught a wrong hash typed into the README while
       this commit was being written.
4. **The foreign-key test repeated the code's rule.**
   - **Fixed:** the nine expected keys are now written out in the test. Another test counts nine in all and none to
     `review_key`, and one table's top-level fields (`id`, `tags`, `customProperties`, `limitations`) are asserted.
5. **Descriptions differ from Unity Catalog's comments.**
   - **What's going on:** `table_comments._text` writes `·` as a comma before a comment reaches Unity Catalog.
   - **Kept as is, and documented:** contracts keep the gold model's text as written, and `contracts/README.md` says
     how the two differ. Reusing `_text` would put its " , " artefacts into the contracts. Changing `_text` is
     `table_comments`' own concern.
6. **T006 was ticked before the review existed.** This file is that review.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan above |
| Synthetic only, no PHI | ✅ | structure only; every contract's `usage` says synthetic and not for clinical use |
| No organization claims; vendors cited | ✅ | Ontos and DQX cited from their own repositories |
| Test first | ✅ | `test_data_contracts.py` was written first and failed at collection; each review fix has a test that fails without it |
| Python and R in parity | n/a | no labels, scoring, reliability or cost-effectiveness change |
| Simulated is labelled simulated | n/a | no numbers |
| Seeds fixed | n/a | no generator or sampler |
| Paths | ✅ | `paths.CONTRACTS_DIR`; no hard-coded `data/` |
| Spec for big changes | ✅ | spec 038 with `plan.md` and `tasks.md`; issue #702 with its four parts and dated lines |
| Prices | n/a | |
| Deck figures | n/a | no deck touched |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailer |
| Docs | ✅ | `contracts/README.md`, `contracts/schema/README.md`; the README link is on an existing line, so it stays at 80 lines |
| Configuration | ✅ | no setting changes in any environment |
| Secrets register | n/a | no credential |
| Idempotent writes | ✅ | contracts are overwritten whole, and stale files are removed only in the gold folders; writing twice gives the same bytes |
| Alerts | n/a | |
| `@traced` on public functions | ✅ | `test_telemetry_calls.py` passes |
| Wording, bench order, org names | ✅ | `test_wording.py`, `test_bench_order.py`, `test_no_org_references.py` pass |

## Test Coverage

Tested:
- one contract per table and none extra
- validation, and a broken document reported
- columns, types, keys and positions for every table
- the nine foreign keys, written out and resolved in their target files
- the tooth-loss schema
- the usage sentence
- stale, edited and extra files
- files outside the gold folders left alone
- byte-identical rewrites
- the script's `--check`, its exit 2 on an invalid contract or without jsonschema
- `contract()` refusing `review_key` and unknown names
- the vendored schema's SHA-256

Run here on the last commit:
- `pytest tests/test_data_contracts.py`: 48 passed
- the rule tests above and `ruff check` on the changed Python files: clean
- `python scripts/73_build_contracts.py --check`: 33 contracts match and validate against the v3.1.0 tag's schema

The whole suite ran on `375ca7e`: 2,558 passed, 4 skipped, plus the README line fix.

Not tested: how Ontos or DQX read the files. Neither is deployed here, and the spec leaves both out of scope.

## Verdict

**Approve.** Both "should fix" findings and the four nits are dealt with in the last commit. It merges when every
check is green on that commit (AGENTS.md, rule 6): it starts no run, publishes nothing outside the repository and
deletes nothing.
