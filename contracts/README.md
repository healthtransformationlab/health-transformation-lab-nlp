# Data contracts and data products (spec 038)

One [Open Data Contract Standard](https://github.com/bitol-io/open-data-contract-standard) (ODCS) v3.1.0 file per
gold table: its three-part name, its grain, every column with its type and description, its primary key and its
foreign keys. ODCS is a YAML standard from Bitol, a Linux Foundation AI & Data project, under Apache-2.0.
Above them, one [Open Data Product Standard](https://github.com/bitol-io/open-data-product-standard) (ODPS) v1.0.0
file per gold schema groups its contracts into a data product: its purpose, status and one output port per table.

The files are **generated** from [`diagrams/_build/gold_model.py`](../diagrams/_build/gold_model.py) (and, for a
product's purpose, the schema's comment in
[`databricks/resources/unity_catalog.yml`](../databricks/resources/unity_catalog.yml)) by
[`python/scripts/73_build_contracts.py`](../python/scripts/73_build_contracts.py) and never edited by hand: the gold
model stays the only place a table is declared. They describe structure only, with no rows and no numbers. The
data they describe is synthetic and not for clinical use, and this is a personal learning project, not affiliated
with any employer or organization.

| Path | Holds |
|---|---|
| `gold_perio_bench/<table>.odcs.yaml` | the 32 tables in `health_transformation_lab.gold_perio_bench` |
| `gold_opendental_perio/<table>.odcs.yaml` | `fact_tooth_loss_prediction`, from the Open Dental extract (spec 029) |
| `products/<bench>.odps.yaml` | one data product per gold schema: `perio_bench` and `opendental_perio` |
| `schema/` | the ODCS v3.1.0 and ODPS v1.0.0 JSON Schemas from their release tags, vendored unchanged, with their sources and SHA-256 ([README](schema/README.md)) |

## Regenerate and check

```bash
cd python && pip install -e ".[dev]"            # jsonschema, which validates every contract
python scripts/73_build_contracts.py            # rewrite the contracts and products after changing gold_model.py
python scripts/73_build_contracts.py --check    # exit 1 naming each stale file, 0 when all match
```

Every contract and product is validated against its vendored schema first; one that fails makes the script exit 2
before anything is written. `python/tests/test_data_contracts.py` and `python/tests/test_data_products.py` fail CI
when a file is missing, extra, stale or invalid, so a change to a gold table and its contract and product land in the
same pull request.

## From the gold model to a contract

| Gold model | ODCS |
|---|---|
| table name | `name` and `schema[0].id`; `id` and `schema[0].physicalName` are the three-part name |
| schema (`gold_perio_bench`, `gold_opendental_perio`) | `domain` (`perio_bench`, `opendental_perio`) and a tag |
| table description (its grain) | `description.purpose`, `schema[0].description`, `schema[0].dataGranularityDescription` |
| column name, type, description | `properties[].id` and `name`, `physicalType`, `description`; `logicalType` bigint to integer, double to number, string, boolean, date, timestamp |
| column key `PK` | `primaryKey: true` and `primaryKeyPosition` (1, 2, ... in declaration order) |
| relationship (solid line in the diagram) | `relationships[]`, `type: foreignKey`, with ODCS fully qualified references (lists for composite keys): `from` is `schema/<table>/properties/<column>` in the same contract, `to` is `<parent>.odcs.yaml#/schema/<parent>/properties/<column>` in the parent's contract; the diagram's cardinality and label are `customProperties` |
| writer, area | `customProperties` and `description.limitations`; area is also a tag |

Left out on purpose:

- **Foreign keys to `review_key`.** The answer key is a CSV file, not a table (`table_comments.NOT_TABLES`), so a
  reference to it would point at no contract. Nine foreign keys remain, all between gold tables.
- **Derived relationships** (dashed lines in the diagram): a value worked out from another table is not a key.
- **Keys are logical only.** Delta enforces no primary or foreign key; the contract says so in `limitations`.
- **Unity Catalog's text cleanup.** Descriptions are the gold model's text as written. The comments
  `table_comments.apply` writes to Unity Catalog pass through its cleanup, which writes `·` as a comma, so a few
  read slightly differently there.
- **A version bump rule.** Every contract is `version: 1.0.0`; until a rule for bumping it is chosen, git history
  is the record of how a contract changed.
- **Quality rules, service levels, servers, team and pricing.** Nothing declares them yet, so the contracts don't
  invent them.

## From a gold schema to a data product

| Source | ODPS |
|---|---|
| schema (`gold_perio_bench`) | `id` (`health_transformation_lab.gold_perio_bench`), `name`, `domain` (`perio_bench`) and a tag |
| the schema's `comment` in `unity_catalog.yml` | `description.purpose` |
| each table's contract | one `outputPorts[]` entry: `name` (the table), `description` (its grain), `type: table`, `version` and `contractId` (the contract's `version` and `id`) |

Every product is `status: active` and `version: 1.0.0`, like the contracts. No input ports: the silver tables the gold
tables come from have no contracts yet.

## Reading them with other tools

- **Ontos** ([databrickslabs/ontos](https://github.com/databrickslabs/ontos), Databricks Labs, experimental) is a
  Databricks App for data products and data contracts. It validates contracts against ODCS v3.1.0 and bundles the
  ODPS v1.0.0 schema for products (`src/backend/src/schemas/`), the versions these files use. It is not deployed
  from this repo.
- **DQX** ([databrickslabs/dqx](https://github.com/databrickslabs/dqx), Databricks Labs) can generate data-quality
  checks from an ODCS contract. None are generated or run here yet.

Upgrading to a later ODCS or ODPS version means vendoring its schema ([schema/README.md](schema/README.md)), changing
`ODCS_API_VERSION` or `ODPS_API_VERSION` in `python/health_transformation_lab_nlp/data_contracts.py` and regenerating.
