---
pr: 705
branch: feat/704-038-data-products
title: "038 US2: each gold schema is an ODPS data product whose output ports point at its contracts"
author: jcbowyer
reviewed_at: 2026-11-13
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve
---

# PR Review: 038 US2: each gold schema is an ODPS data product whose output ports point at its contracts

## Summary

The PR adds an Open Data Product Standard (ODPS) v1.0.0 file for each gold schema that has contracts:
`perio_bench` and `opendental_perio`. Each product has one output port per table, pointing at that table's ODCS contract
(#703) by `contractId` and `version`, and its purpose is the schema's comment in the bundle.

An independent reviewer read the commit read-only and found nothing blocking, plus three nits. It also traced Ontos's
import code to check that the products' shape is one Ontos reads. Each nit was checked here and fixed in `dc763d1`. The
verdict is approve: merging starts no run and publishes nothing.

## Scope of Change

- Files changed: 12 (+1,161 / −72). About 950 of those lines are the vendored ODPS schema and the two generated product
  files.
- Areas touched: python, contracts, docs, specs
- Commits:
  - `287188d` 038 US2: each gold schema is an ODPS data product whose output ports point at its contracts
  - `dc763d1` Pin what write_products leaves alone; cache the bundle read; Ontos import order
  - this file
- Range reviewed: `6494b7f..c10bad5` before the rebase (the same change as `acb5c5e..287188d`), then `dc763d1` here

## CI Status

| Check | Status |
|---|---|
| all checks | running when written; the merge waits for every check to be green on the last commit |

## Secrets, PHI and Claims Scan

- **Secrets:** none.
- **PHI or real data:** none. The products describe structure only.
- **Organisation claims:** none.
- **Company claims:** only Bitol (the standards body) and Databricks Labs Ontos are named, and each claim is checked
  against Ontos's own source:
  - Ontos bundles the ODPS v1.0.0 schema, and the SHA-256 matches the vendored file.
  - Its repository layer is written for "ODPS v1.0.0".
  - It looks a port's `contractId` up among the contracts it already holds (`data_products_manager.py`).
- **Wording, bench order, org names:** clean. Only `perio_bench` and `opendental_perio` appear.

## Strengths

- One declaration per fact: ports come from `all_contracts()`, and the purpose is read from the bundle's schema
  comment.
- What the schema requires is present: `apiVersion`, `kind`, `id` and `status` on each product, and `name`, `version`
  and `contractId` on each port.
- Output is deterministic: ports follow the gold model's order, products come from `dict.fromkeys`, and keys are not
  sorted.
- `write_products` and `stale_products` look only at `products/*.odps.yaml`. The contract functions never touch
  `products/`, because `GOLD_FOLDERS` doesn't include it.

## Findings

### 🔴 Blocking (Critical)

None.

### 🟡 Should fix (Important, non-blocking)

None.

### 🔵 Nits / suggestions (Minor)

1. **Nothing showed what `write_products` leaves alone** (`python/tests/test_data_products.py`).
   - **How it was verified:** read the test file. It had no case with a non-product file in `products/`, or a contract,
     surviving `write_products`.
   - **Fixed:** `test_writing_products_leaves_everything_but_product_files_alone` puts a README in `products/` and a
     contract in a gold folder, and checks both are byte-for-byte unchanged afterwards.
2. **The bundle was parsed once per schema** (`data_contracts._schema_comment`).
   - **Fixed:** `_bundle_schemas()` reads it once per process, with `@cache`, as `_json_schema` does.
3. **Ontos's import order wasn't documented.**
   - **How it was verified:** Ontos resolves a port's `contractId` against contracts it already holds
     (`data_products_manager.py`, lines 3680 to 3690 and 664 to 675 at the commit read).
   - **Fixed:** `contracts/README.md` says the contracts go in before the products.

## Repo-Rule Compliance

| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | scan above |
| Synthetic only, no PHI | ✅ | structure only; each product's `usage` says synthetic and not for clinical use |
| No organization claims; vendors cited | ✅ | Bitol and Ontos, each checked against its own source |
| Test first | ✅ | `test_data_products.py` was written first: 11 of 12 tests failed before the code, and the 12th passed only because there were no files, so it now asserts the count |
| Python and R in parity | n/a | no labels, scoring, reliability or cost-effectiveness change |
| Simulated is labelled simulated | n/a | no numbers |
| Seeds fixed | n/a | |
| Paths | ✅ | `paths.CONTRACTS_DIR` and `REPO_ROOT`; no hard-coded `data/` |
| Spec for big changes | ✅ | spec 038 US2 in `spec.md`, `plan.md` and `tasks.md`; issue #704 with its four parts and a dated line |
| Prices | n/a | |
| Deck figures | n/a | |
| Commits | ✅ | imperative subjects, bodies say why, co-author trailer |
| Docs | ✅ | `contracts/README.md`, `contracts/schema/README.md`, NOTICE |
| Configuration | ✅ | no setting changes |
| Secrets register | n/a | no credential |
| Idempotent writes | ✅ | products are overwritten whole and stale ones removed only in `products/`; writing twice gives the same bytes |
| Alerts | n/a | |
| `@traced` on public functions | ✅ | `test_telemetry_calls.py` passes |

## Test Coverage

Tested:
- one product per gold schema with contracts, and none extra
- validation, and a product without `status` reported
- one port per table in the gold model's order, each `contractId` a committed contract with the same `version`
- the purpose equal to the bundle's comment, and the usage sentence
- `product("gold_oral_health_bench")` raising `KeyError`
- stale, missing and extra product files, and `write_products` fixing them while leaving everything else alone
- byte-identical rewrites
- the script's `--check` naming a stale product, and its exit 2 on an invalid product
- the vendored schema's SHA-256

Run here on `dc763d1`, rebased onto `acb5c5e`:
- `pytest tests/test_data_products.py tests/test_data_contracts.py`: 62 passed
- the rule tests: passed
- `ruff`: clean
- `--check`: clean

Not tested: an actual Ontos import. Ontos isn't deployed here, and the spec leaves that out of scope.

## Verdict

**Approve.** The three nits are fixed in `dc763d1`. It merges when every check is green on the last commit
(AGENTS.md, rule 6).
