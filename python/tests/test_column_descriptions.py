"""#694: Kaggle drops column descriptions sent through its API (Kaggle/kaggle-cli#1207), so the owner enters them in
Kaggle's editor. kaggle/column_descriptions.py lists each one, by the file name Kaggle shows, from dataset_docs.yaml."""
import importlib.util
import sys

from health_transformation_lab_nlp.paths import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "kaggle"))
_spec = importlib.util.spec_from_file_location("column_descriptions", REPO_ROOT / "kaggle" / "column_descriptions.py")
cd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cd)


def test_every_column_of_the_results_dataset_is_listed_with_its_description():
    rows = cd.column_rows("results")
    assert rows and all(r["description_text"] for r in rows)
    assert all("+" not in r["file_name"] for r in rows)                 # Kaggle's form of the name (#695)
    assert {r["dataset_slug"] for r in rows} == {"perio-bench-results"}
    files = {r["file_name"] for r in rows}
    assert "ai_predictions_bert-basecw.csv" in files


def test_the_page_has_a_copy_button_per_column_and_escapes_text():
    rows = [{"dataset_slug": "d", "file_name": "f.csv", "column_name": "a<b", "description_text": "x & <y>"}]
    html = cd.page(rows)
    assert html.count('class="copy"') == 1
    assert "a&lt;b" in html and "x &amp; &lt;y&gt;" in html and "<y>" not in html
    assert "kaggle.com/datasets/" in html                                # each file links to its editor


def test_the_task_sets_three_csv_files_are_listed_without_a_full_build():
    rows = cd.column_rows("tasks")
    assert {r["file_name"] for r in rows} == {"tasks_excluded.csv", "task_gates.csv", "swegemma_verification.csv"}
    assert all(r["description_text"] for r in rows)
