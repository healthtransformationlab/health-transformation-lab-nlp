"""Databricks schema names, one set per bench (spec 022).

    perio_bench        periodontal status from charts: everything built so far (landing, bronze, silver, gold)
    oral_health_bench  the umbrella scorecard (bronze, silver, gold; empty for now)
    access_bench       does an answer help someone actually get care (bronze, silver, gold; empty for now)
    opendental_perio   spec 029: a synthetic extract in Open Dental's table format and the tooth-loss model
                       (landing, bronze, silver, gold); named like the pre-022 OMOP schemas, with the format
                       changed to Open Dental

All live in the health_transformation_lab catalog (spec 021), with the same names in every target (AGENTS.md,
Conventions); databricks/resources/unity_catalog.yml declares them.

    schema       <layer>_<bench>
    all_schemas  every bench schema, in bundle order
"""

from __future__ import annotations

from .telemetry import traced

CATALOG = "health_transformation_lab"
LAYERS: dict[str, tuple[str, ...]] = {
    "perio_bench": ("landing", "bronze", "silver", "gold"),
    "oral_health_bench": ("bronze", "silver", "gold"),
    "access_bench": ("bronze", "silver", "gold"),
    "opendental_perio": ("landing", "bronze", "silver", "gold"),
}


@traced
def schema(bench: str, layer: str) -> str:
    if layer not in LAYERS[bench]:
        raise ValueError(f"{bench} has no {layer} schema (layers: {LAYERS[bench]})")
    return f"{layer}_{bench}"


@traced
def all_schemas() -> list[str]:
    return [schema(bench, layer) for bench, layers in LAYERS.items() for layer in layers]
