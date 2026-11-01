"""Spec 029 T001: the Open Dental columns the extract uses are checked against Open Dental's own source, recorded
with the file and commit they came from, and the plan follows what the source says."""

from health_transformation_lab_nlp.paths import REPO_ROOT

RESEARCH = REPO_ROOT / "specs" / "029-tooth-loss" / "research.md"
TABLES = ["patient", "procedurelog", "procedurecode", "treatplan", "proctp", "perioexam", "periomeasure",
          "toothinitial", "definition", "disease", "diseasedef", "clinic"]


def test_every_table_is_recorded_with_its_source_file_and_commit():
    text = RESEARCH.read_text(encoding="utf-8")
    assert "github.com/OpenDental/OpenDental" in text and "24_3" in text and "d804c19" in text
    for table in TABLES:
        assert f"### `{table}`" in text, table
    for col in ("PatNum", "ProcStatus", "ToothNum", "Dx", "DiagnosticCode", "IcdVersion", "SequenceType", "IntTooth",
                "ToothValue", "MBvalue", "InitialType", "Category", "Icd10Code", "SmokingSnoMed", "ClinicNum"):
        assert f"`{col}`" in text, col


def test_what_the_source_corrects_in_the_plan():
    text = RESEARCH.read_text(encoding="utf-8")
    assert "CAL is not stored" in text                         # computed from probing and gingival margin
    assert "100" in text and "GingMargin" in text              # 100+ encodes a negative margin
    plan = (REPO_ROOT / "specs" / "029-tooth-loss" / "plan.md").read_text(encoding="utf-8")
    assert "research.md" in plan and "computed" in plan and "SmokingSnoMed" in plan
    assert "Existing Other Prov" in text                       # an extraction done elsewhere is another way to be missing


def test_the_source_is_a_reference_and_no_code_is_copied():
    refs = (REPO_ROOT / "docs" / "references.md").read_text(encoding="utf-8")
    assert "github.com/OpenDental/OpenDental" in refs and "GPL" in refs
    assert "public class" not in RESEARCH.read_text(encoding="utf-8")   # names and meanings only, no source code
