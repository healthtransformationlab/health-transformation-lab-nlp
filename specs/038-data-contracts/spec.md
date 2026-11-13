# Feature Specification: Open Data Contracts for the gold tables

**Feature Branch**: `feat/702-038-data-contracts`

**Created**: 2026-11-13

**Status**: implemented

**Input**: the owner asked to add open data contracts, the Open Data Contract Standard that Databricks Labs Ontos reads,
to this repository and to Open Navigator. Each gold table is already declared once, in
`diagrams/_build/gold_model.py`: its grain, typed columns, keys and relationships. Only this repository can read that
file. A data contract in a published standard lets governance tools (Ontos), quality-rule generators (Databricks
Labs DQX) and other repositories read the same declaration. It also gives this repository's rule that an issue says
what a test will check (AGENTS.md, "What an issue says") a standard place to point for a table's names.

The standard is the [Open Data Contract Standard](https://bitol-io.github.io/open-data-contract-standard/latest/home)
(ODCS), a Linux Foundation (Bitol) project under Apache-2.0. Version v3.1.0 is used because Ontos implements it; v3.2.0
exists and is a later upgrade.

> Personal learning project; synthetic data only. A contract describes a table's structure. It holds no rows and no
> numbers, and every contract says the data is synthetic and not for clinical use.

## User stories

### US1 - Every gold table has an Open Data Contract, generated from the gold model (P1) #702

- `contracts/<schema>/<table>.odcs.yaml` exists for every table in `gold_model.TABLES` except `review_key`, which is
  a file, not a table (`table_comments.NOT_TABLES`). No other contract files are there.
- Every contract validates against the official ODCS v3.1.0 JSON Schema, vendored at
  `contracts/schema/odcs-json-schema-v3.1.0.json` with its source, licence and SHA-256 beside it.
- A contract's columns, logical and physical types, descriptions, primary keys (with positions) and foreign keys match
  `gold_model.py`. A change there without regenerating fails `python/tests/test_data_contracts.py`.
- `python scripts/73_build_contracts.py --check` exits 1 and names each stale file when a contract is out of date,
  and exits 0 when all match. Without `--check`, it rewrites them.
- The tooth-loss table points at `health_transformation_lab.gold_opendental_perio`; every other table points at
  `health_transformation_lab.gold_perio_bench` (`table_comments.GOLD_SCHEMA`, one declaration).
- Every contract says the data is synthetic and not for clinical use.

## Out of scope

- Deploying Ontos (a Databricks App) or generating DQX quality rules from the contracts. Each is its own story, run on
  shared compute only on the owner's word. `contracts/README.md` says how either would read the files.
- ODCS `quality` rules beyond keys, because the gold model declares none yet.
- Silver, bronze and OMOP tables, which the gold model doesn't declare.
- ODCS v3.2.0, a later upgrade once Ontos reads it.
