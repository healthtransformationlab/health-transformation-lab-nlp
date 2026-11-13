# Implementation plan: Open Data Contracts (spec 038)

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
  - `name`, `physicalName` (the three-part name), `physicalType: table`, `logicalType: object`, `description` and
    `dataGranularityDescription` (both the grain)
  - `customProperties` `writer` and `area`
- `properties`, one per column in declaration order:
  - `name`, `physicalType` (the gold model's type), `description`
  - `logicalType`: bigint to integer, double to number, string, boolean, date, timestamp
  - `primaryKey: true` and `primaryKeyPosition` (1, 2, ... in declaration order) for columns whose key contains PK
- `relationships`, one per relationship in `gold_model.RELATIONSHIPS` whose child is the table and that isn't
  `derived` (a dashed line is not a key): `type: foreignKey`, with `from` and `to` in `table.column` form, as lists
  when the key has more than one column. Relationships whose parent is `review_key` are left out: the answer key
  is a file in `NOT_TABLES`, so it has no contract to point at. Nine foreign keys remain (added 2026-11-13, as on
  #702)
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
