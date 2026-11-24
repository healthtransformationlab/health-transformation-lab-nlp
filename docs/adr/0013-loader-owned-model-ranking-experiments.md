# ADR 0013: The two model-ranking MLflow experiments are made by their loaders, not the bundle

Date: 2026-11-24 · Status: accepted · Issue: #921

## Context

Spec 042 loads PerioBench's multi-model rankings into Databricks. Two MLflow experiments already exist on the
dev workspace because their loaders created them on first run:

- `/Shared/perio-bench-model-ranking` — one run per note-reading method, and one Unity Catalog trace per LLM
  reader call (`health_transformation_lab.ops_agent_trace`, table prefix `perio_reader`), from
  `scripts/75_load_model_drivers.py` / `model_drivers_load.py` (US2).
- `/Shared/tooth-loss-model-comparison` — one run per tooth-loss model, from
  `scripts/79_load_tooth_loss_drivers.py` / `tooth_loss_drivers_load.py` (US4). No Unity Catalog trace location;
  runs only.

Coding-agent traces follow a different path: `/Shared/coding-agent-runs` is declared in
`databricks/resources/agent_traces.yml` (spec 041), so deploy creates it with a fixed `trace_location` before any
loader runs.

An experiment's `trace_location` cannot be changed after it is created (Databricks; same constraint as ADR 0012 /
spec 041). Spec 042's Risks left open whether to **adopt** the loader-made experiments or **rebuild** them under
the bundle. Declaring the existing names in the bundle would clash with what is already there. Rebuilding would
mean deleting the live experiments (and the 669 perio-reader traces already loaded), recreating them from the
bundle, and reloading.

## Decision

- **Adopt the loader-made experiments.** `/Shared/perio-bench-model-ranking` and
  `/Shared/tooth-loss-model-comparison` stay owned by their loaders. They are **not** declared in
  `databricks/resources/agent_traces.yml` or any other bundle resource.
- The perio-ranking experiment keeps its Unity Catalog trace location as the loader set it on first create
  (`ops_agent_trace` / `perio_reader`). Do not recreate that experiment to move traces.
- New ranking or comparison experiments of this kind (method features as params, scores as metrics; optional
  reader traces) are created the same way: by the loader on first use, with the trace location chosen at create
  time when traces are needed. The coding-agent experiment remains the one that the bundle declares.

## Consequences

- Deploy never tries to create or rename these two experiments, so there is no name clash with what the loaders
  already made.
- A fresh workspace gets the experiments the first time someone runs the loaders, not at `bundle deploy`. That is
  acceptable: the gold tables and runs are produced by those same scripts.
- The bundle is no longer the single inventory of every MLflow experiment. The loaders' module constants
  (`EXPERIMENT` in `model_drivers_load.py` and `tooth_loss_drivers_load.py`) and this ADR are the record for these
  two.
- Deleting either experiment to "put it in the bundle" would drop existing runs and (for perio-ranking) traces;
  restore from trash within 30 days only if that was a mistake, then reload from the committed CSVs.

## Revisit when

- Databricks lets an experiment's `trace_location` be set or changed after create, so the bundle could adopt the
  existing names without a rebuild.
- A new environment must have the experiments before any loader runs (for example a deploy-time grant or a Genie
  space that points at them), and that need outweighs keeping create in the loader.
- Either experiment is retired or replaced; write a new ADR for the replacement, as ADR 0012 did for the old
  coding-agent experiment.
