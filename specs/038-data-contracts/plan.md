# Implementation plan: Open Data Contracts and Data Products (spec 038)

## Sources of truth

- `diagrams/_build/gold_model.py` stays the only declaration of the gold tables. Contracts are generated from it and
  never edited by hand, as `docs/edr/README.md` is generated.
- Which schema a table is in, and which declared tables are files, come from `table_comments.GOLD_SCHEMA` and
  `table_comments.NOT_TABLES`, each declared once. The gold model is loaded with `table_comments`' loader.

## Names (copied to issue #702)

- Module `health_transformation_lab_nlp.data_contracts`, every public function `@traced`:
  - `ODCS_API_VERSION = "v3.1.0"`
  - `contract(name: str) -> dict`: one ODCS document for one gold table
  - `all_contracts() -> dict[str, dict]`, keyed `<schema>/<table>`
  - `write_contracts(root: Path = CONTRACTS_DIR) -> list[Path]`: writes every contract, removes stale `.odcs.yaml`
    files in the schema folders, and returns the files written
  - `stale_contracts(root: Path = CONTRACTS_DIR) -> list[str]`: relative paths that are missing, differ or shouldn't
    be there
  - `validate(doc: dict) -> list[str]`: JSON Schema errors against the vendored schema, empty when valid
- `paths.CONTRACTS_DIR = REPO_ROOT / "contracts"`
- Script `python/scripts/73_build_contracts.py [--check] [--root <dir>]` (`--root` defaults to `contracts/`); a
  contract that fails ODCS validation makes it exit 2 before anything is written (added 2026-11-13, as on #702)
- Files: `contracts/README.md`, `contracts/schema/odcs-json-schema-v3.1.0.json`, `contracts/schema/README.md`,
  `contracts/gold_perio_bench/<table>.odcs.yaml` and `contracts/gold_opendental_perio/<table>.odcs.yaml`

## Mapping, one table to one document

- Top level:
  - `apiVersion: v3.1.0`, `kind: DataContract`, `id: health_transformation_lab.<schema>.<table>`, `name: <table>`,
    `version: 1.0.0`, `status: active`, `domain` (`perio_bench` or `opendental_perio`)
  - `description`: `purpose` is the table's grain; `usage` says synthetic, not for clinical use, not affiliated;
    `limitations` says logical keys only (Delta enforces none) and who writes it
  - `tags: [synthetic, <bench>, <area>]`
- One `schema` element:
  - `id` and `name` (the table; `id` added 2026-11-13, as on #702), `physicalName` (the three-part name),
    `physicalType: table`, `logicalType: object`, `description` and
    `dataGranularityDescription` (both the grain)
  - `customProperties` `writer` and `area`
- `properties`, one per column in declaration order:
  - `id` and `name` (the column; `id` added 2026-11-13), `physicalType` (the gold model's type), `description`
  - `logicalType`: bigint to integer, double to number, string, boolean, date, timestamp
  - `primaryKey: true` and `primaryKeyPosition` (1, 2, ... in declaration order) for columns whose key contains PK
- `relationships`, one per relationship in `gold_model.RELATIONSHIPS` whose child is the table and that isn't
  `derived` (a dashed line is not a key): `type: foreignKey`, with `from` and `to` in `table.column` form, as lists
  when the key has more than one column. Relationships whose parent is `review_key` are left out: the answer key
  is a file in `NOT_TABLES`, so it has no contract to point at. Nine foreign keys remain (added 2026-11-13, as on
  #702). Changed 2026-11-13, as on #702: `from` and `to` are ODCS fully qualified references, `from`
  `schema/<table>/properties/<column>` and `to` `<parent>.odcs.yaml#/schema/<parent>/properties/<column>`,
  because ODCS's references page keeps the shorthand for elements in the same contract; each carries the
  diagram's `cardinality` and `label` as `customProperties`
- YAML: a first-line comment saying the file is generated and from what, keys in the order above, `sort_keys` off,
  and a trailing newline, so a rerun is byte-identical

## Validation

- `jsonschema`'s validator for the schema's own draft (2019-09). `jsonschema>=4.18` joins the `dev` extra, because
  only tests and the script use it, and it's imported inside `validate`.

## Tests (written first): `python/tests/test_data_contracts.py`

- One committed contract per table, and none extra
- Every committed contract validates; a broken document (no `apiVersion`) returns errors
- Columns, types, keys, positions and foreign keys match the gold model for every table
- Schemas: `fact_tooth_loss_prediction` in `gold_opendental_perio`, the rest in `gold_perio_bench`
- Every contract's `usage` says synthetic and not for clinical use
- `stale_contracts` is empty for the committed files; after one file is edited in a copy, it names that file, and
  `write_contracts` makes it empty again; an extra file is named too
- The script's `--check` exits 0 on the committed tree and 1, naming the file, on a stale copy

## Docs

- `contracts/README.md`: what the files are, how to regenerate and check them, and how Ontos and DQX would read them
- `README.md`: one line pointing to `contracts/`
- `NOTICE`: the vendored ODCS JSON Schema (Apache-2.0, Bitol)

## US2: data products (#704)

### Names (copied to issue #704)

- In `health_transformation_lab_nlp.data_contracts`, every new public function `@traced`:
  - `ODPS_API_VERSION = "v1.0.0"`
  - `product(schema: str) -> dict`: one ODPS document for one gold schema, `KeyError` when it has no contracts
  - `all_products() -> dict[str, dict]`, keyed `products/<bench>`
  - `write_products(root: Path = CONTRACTS_DIR) -> list[Path]`: writes every product, removes stale
    `products/*.odps.yaml` files, and returns the files written
  - `stale_products(root: Path = CONTRACTS_DIR) -> list[str]`: relative paths that are missing, differ or shouldn't be
    there
  - `validate_product(doc: dict) -> list[str]`: JSON Schema errors against the vendored ODPS schema, empty when valid
- The script's `--check` and `--root` cover the product files too; an invalid product exits 2 before anything is written
- Files: `contracts/products/perio_bench.odps.yaml`, `contracts/products/opendental_perio.odps.yaml`,
  `contracts/schema/odps-json-schema-v1.0.0.json`

### Mapping, one gold schema to one product

- `apiVersion: v1.0.0`, `kind: DataProduct`, `id: health_transformation_lab.<schema>`, `name: <schema>`,
  `version: 1.0.0`, `status: active`, `domain: <bench>`, `tags: [synthetic, <bench>]`
- `description`: `purpose` is the schema's `comment` in `databricks/resources/unity_catalog.yml`; `usage` is the
  contracts' usage sentence; `limitations` says structure only and logical keys only
- `outputPorts`, one per contract in the schema, in the gold model's order: `name` (the table), `description` (its
  grain), `type: table`, `version` and `contractId` (the contract's `version` and `id`)
- YAML as for the contracts: a first-line comment naming both sources, keys in this order, a trailing newline

### Version

ODPS v1.0.0, because Databricks Labs Ontos bundles `odps-json-schema-v1.0.0.json` and its repository layer is written
for v1.0.0. v1.1.0 adds optional fields and loosens what an output port requires, and is a later upgrade.

### Tests (written first): `python/tests/test_data_products.py`

- One committed product per gold schema with contracts, and none extra
- Every committed product validates; one without `status` returns errors
- Ports: one per table in the gold model's order, each `contractId` a committed contract with the same `version`
- Purpose equals the bundle's schema comment; usage says synthetic and not for clinical use
- `product("gold_oral_health_bench")` raises `KeyError`
- `stale_products` names an edited, a missing and an extra file; `write_products` makes it empty and leaves the
  contracts alone; writing twice gives the same bytes
- The script's `--check` names a stale product; an invalid product exits 2 before anything is written
