# Implementation Plan: bench schemas and Kaggle names (spec 022)

**Spec**: [spec.md](spec.md) · **Issues**: #141 (US1), #142 (US2) · Replaces draft #151 (built on `dental_omop`).

## Approach

1. **Names in one place.** `python/health_transformation_lab_nlp/schemas.py`: the benches, their layers,
   `schema(bench, layer)`, `all_schemas()`, and the legacy suffix.
2. **Bundle.** `databricks/resources/unity_catalog.yml` declares `perio_bench_*`, `oral_health_bench_*` and
   `access_bench_*` schemas and a `perio_bench_data` volume, all `prevent_destroy`; `mlops.yml` declares
   `perio_bench_note_classifier` (name `perio_note_classifier`, in `gold_perio_bench`). Every job points at
   them. The old `landing`/`bronze`/`silver`/`gold` schemas, `data` volume and `perio_note_classifier` model keep
   their keys, but only under `targets.dev` in `databricks.yml` (the one target that deployed them), named with
   `legacy_domain`.
   The `domain` variable goes.
3. **Rename.** Notebook defaults, dashboards and Genie spaces (rebuilt with `scripts/42_build_dashboards.py`),
   Python modules, docs, diagrams (rebuilt and re-rendered) and AGENTS.md use `<layer>_perio_bench`.
4. **Kaggle.** `kaggle/prepare_kernel.py`, `kaggle/publish.py`, the two workflows and `kaggle/README.md` use the
   `perio-bench-*` names.
5. **Rebuild, not copy** (as spec 021): no migration notebook. docs/deployment.md lists the runs and the
   retirement steps.

Learned from #151's review: legacy resources only in the targets that have them; one declaration of the legacy
suffix (`legacy_domain`, read by nothing outside the bundle).

## Tests first

- `test_schemas.py`: the ten names and the catalog.
- `test_bundle.py`: bench schemas at the top level; legacy entries only in dev; jobs, volume and model
  use `perio_bench_*`.
- `test_no_legacy_schema_names.py`: `dental_omop_perio` only in allowed files.
- Kaggle tests: kernel ids and dataset slugs use the new names.

## Environments

dev, uat and prod get the bench schemas on their next deploy. dev keeps its old schemas until retired.
