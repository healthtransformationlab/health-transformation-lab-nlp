"""Spec 022: the Databricks schemas are named for the three benches."""
import pytest

from health_transformation_lab_nlp import schemas


def test_the_schemas_are_named_for_the_benches_in_the_lab_catalog():
    assert schemas.CATALOG == "health_transformation_lab"
    assert schemas.all_schemas() == [
        "landing_perio_bench", "bronze_perio_bench", "silver_perio_bench", "gold_perio_bench",
        "bronze_oral_health_bench", "silver_oral_health_bench", "gold_oral_health_bench",
        "bronze_access_bench", "silver_access_bench", "gold_access_bench",
        "landing_opendental_perio", "bronze_opendental_perio", "silver_opendental_perio", "gold_opendental_perio"]
    assert schemas.schema("perio_bench", "gold") == "gold_perio_bench"


def test_the_open_dental_extract_has_its_own_four_layers():
    # spec 029: the synthetic extract in Open Dental's format, named like the pre-022 OMOP schemas with the format
    # changed: <layer>_opendental_perio
    assert schemas.LAYERS["opendental_perio"] == ("landing", "bronze", "silver", "gold")
    assert schemas.schema("opendental_perio", "silver") == "silver_opendental_perio"


def test_a_bench_without_that_layer_is_refused():
    with pytest.raises(ValueError, match="access_bench has no landing"):
        schemas.schema("access_bench", "landing")
