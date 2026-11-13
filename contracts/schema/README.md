# ODCS JSON Schema v3.1.0 (vendored)

The official JSON Schema of the [Open Data Contract Standard](https://github.com/bitol-io/open-data-contract-standard)
(ODCS), version v3.1.0, copied unchanged. `health_transformation_lab_nlp.data_contracts.validate` checks every
contract in `contracts/` against it (spec 038).

- Source: https://raw.githubusercontent.com/bitol-io/open-data-contract-standard/v3.1.0/schema/odcs-json-schema-v3.1.0.json
  (the `v3.1.0` release tag; the copy on `main` has since changed in five places)
- Project: Open Data Contract Standard, by Bitol, a Linux Foundation AI & Data project
- Licence: Apache-2.0 (the project's own licence)
- Downloaded: 2026-11-13
- SHA-256: 2cb7dd6fe43344d2233e0406438622681dc3ebadcf8f0d606a15b40c8f6752c0
- The same file Databricks Labs Ontos bundles (`src/backend/src/schemas/odcs-json-schema-v3.1.0.json` in
  [databrickslabs/ontos](https://github.com/databrickslabs/ontos)): its SHA-256 matches

To move to a later version (v3.2.0 exists), add its schema file beside this one, change `ODCS_API_VERSION` and
`SCHEMA_FILE` in `data_contracts.py`, and run `python scripts/73_build_contracts.py`.
