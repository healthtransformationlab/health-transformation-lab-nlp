# Vendored JSON Schemas (spec 038)

The official JSON Schemas of two Bitol standards, copied unchanged. `health_transformation_lab_nlp.data_contracts`
checks every file in `contracts/` against them: `validate` the contracts, `validate_product` the data products.

## ODCS v3.1.0: `odcs-json-schema-v3.1.0.json`

The [Open Data Contract Standard](https://github.com/bitol-io/open-data-contract-standard) (ODCS), version v3.1.0.

- Source: https://raw.githubusercontent.com/bitol-io/open-data-contract-standard/v3.1.0/schema/odcs-json-schema-v3.1.0.json
  (the `v3.1.0` release tag; the copy on `main` has since changed in five places)
- Project: Open Data Contract Standard, by Bitol, a Linux Foundation AI & Data project
- Licence: Apache-2.0 (the project's own licence)
- Downloaded: 2026-11-13
- SHA-256: 2cb7dd6fe43344d2233e0406438622681dc3ebadcf8f0d606a15b40c8f6752c0
- The same file Databricks Labs Ontos bundles (`src/backend/src/schemas/odcs-json-schema-v3.1.0.json` in
  [databrickslabs/ontos](https://github.com/databrickslabs/ontos)): its SHA-256 matches

## ODPS v1.0.0: `odps-json-schema-v1.0.0.json`

The [Open Data Product Standard](https://github.com/bitol-io/open-data-product-standard) (ODPS), version v1.0.0. v1.1.0
exists; v1.0.0 is the version Databricks Labs Ontos bundles (`src/backend/src/schemas/odps-json-schema-v1.0.0.json`
in [databrickslabs/ontos](https://github.com/databrickslabs/ontos)), and this is that same file: its SHA-256 matches.

- Source: https://raw.githubusercontent.com/bitol-io/open-data-product-standard/v1.0.0/schema/odps-json-schema-v1.0.0.json
  (the `v1.0.0` release tag; the copy on `main` has since changed one description)
- Project: Open Data Product Standard, by Bitol, a Linux Foundation AI & Data project
- Licence: Apache-2.0 (the project's own licence)
- Downloaded: 2026-11-13
- SHA-256: 2730fbde0d9ba6d73d47798ada98b3a6dded9c6a14d3d44fa3c69c2c2575ff73

## Upgrading

To move to a later version (ODCS v3.2.0 and ODPS v1.1.0 exist), add its schema file beside these, change
`ODCS_API_VERSION` and `SCHEMA_FILE`, or `ODPS_API_VERSION` and `ODPS_SCHEMA_FILE`, in `data_contracts.py`, and run
`python scripts/73_build_contracts.py`.
