"""#467: predictions carry the note set they were made on, so a rebuilt note set never scores them against the new
answer key. Every number is SYNTHETIC."""

import pandas as pd
import pytest

from health_transformation_lab_nlp import note_set, results_store
from health_transformation_lab_nlp.paths import DATASETS_DIR


def _key(folder, ids, text="note {}"):
    (folder / "answer_key").mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"visit_id": ids, "truth_status": "healthy", "note_text": [text.format(i) for i in ids]}) \
        .to_csv(folder / "answer_key" / "review_key.csv", index=False)


def _preds(folder, name, ids):
    pd.DataFrame({"visit_id": ids, "pred": "healthy"}).to_csv(folder / f"ai_predictions_{name}.csv", index=False)


def test_the_fingerprint_follows_the_notes_not_the_row_order():
    a = pd.DataFrame({"visit_id": [1, 2], "note_text": ["x", "y"]})
    assert note_set.fingerprint(a) == note_set.fingerprint(a.iloc[::-1])
    assert note_set.fingerprint(a) != note_set.fingerprint(a.assign(note_text=["x", "z"]))
    assert note_set.fingerprint(a) != note_set.fingerprint(a.assign(visit_id=[1, 3]))
    assert len(note_set.fingerprint(a)) == 64


def test_a_stamp_is_idempotent_and_replaces_the_files_row(tmp_path):
    _key(tmp_path, [1, 2])
    _preds(tmp_path, "a", [1, 2])
    note_set.stamp(tmp_path, ["ai_predictions_a.csv"], "f" * 64)
    note_set.stamp(tmp_path, ["ai_predictions_a.csv"])
    note_set.stamp(tmp_path, ["ai_predictions_a.csv"])
    reg = note_set.read_register(tmp_path)
    assert list(reg["file"]) == ["ai_predictions_a.csv"]
    assert reg["note_set_sha256"].iloc[0] == note_set.current(tmp_path)


def test_a_file_is_current_only_on_the_note_set_it_was_made_on(tmp_path):
    _key(tmp_path, [1, 2])
    for name in ("same", "old", "unrecorded_same", "unrecorded_other"):
        _preds(tmp_path, name, [3, 4] if name == "unrecorded_other" else [1, 2])
    note_set.stamp(tmp_path, ["ai_predictions_same.csv"])
    note_set.stamp(tmp_path, ["ai_predictions_old.csv"], "0" * 64)
    assert note_set.is_current(tmp_path, "ai_predictions_same.csv")
    assert not note_set.is_current(tmp_path, "ai_predictions_old.csv")
    # no recorded note set: derived from the visits the file holds
    assert note_set.is_current(tmp_path, "ai_predictions_unrecorded_same.csv")
    assert not note_set.is_current(tmp_path, "ai_predictions_unrecorded_other.csv")
    _key(tmp_path, [1, 2], text="rebuilt note {}")          # same visit ids, new notes
    assert not note_set.is_current(tmp_path, "ai_predictions_same.csv")


def test_prediction_files_splits_current_from_pending_with_where_they_came_from(tmp_path):
    _key(tmp_path, [1, 2])
    _preds(tmp_path, "new", [1, 2])
    _preds(tmp_path, "gpu", [1, 2])
    pd.DataFrame({"visit_id": [1, 2], "pred": "healthy"}).to_csv(tmp_path / "simulated_ai_predictions_x.csv")
    note_set.stamp(tmp_path, ["ai_predictions_new.csv"])
    note_set.stamp(tmp_path, ["ai_predictions_gpu.csv"], "0" * 64)
    pd.DataFrame({"file": ["ai_predictions_gpu.csv"], "source": ["kaggle"], "run_url": ["https://x/runs/1"],
                  "recorded_at": ["t"]}).to_csv(tmp_path / results_store.MANIFEST, index=False)
    current, pending = note_set.prediction_files(tmp_path)
    assert [p.name for p in current] == ["ai_predictions_new.csv"]
    assert list(pending["method_name"]) == ["gpu"]
    row = pending.iloc[0]
    assert (row["source_name"], row["run_url"], row["note_set_sha256"]) == ("kaggle", "https://x/runs/1", "0" * 64)
    assert row["current_note_set_sha256"] == note_set.current(tmp_path)


def test_record_stamps_the_note_set_and_refuses_another_sets_visits(tmp_path):
    src, dest = tmp_path / "src", tmp_path / "dest"
    src.mkdir()
    _key(dest, [1, 2])
    _preds(src, "medgemma-x", [1, 2])
    results_store.record(src, dest, "https://x/runs/2", min_rows=2)
    assert note_set.is_current(dest, "ai_predictions_medgemma-x.csv")
    assert note_set.read_register(dest).set_index("file").loc["ai_predictions_medgemma-x.csv",
                                                               "note_set_sha256"] == note_set.current(dest)
    _preds(src, "medgemma-x", [7, 8])
    with pytest.raises(ValueError, match="note set"):
        results_store.record(src, dest, "https://x/runs/3", min_rows=2)


def test_every_committed_prediction_file_records_its_note_set():
    reg = note_set.read_register(DATASETS_DIR).set_index("file")
    files = sorted(p.name for p in DATASETS_DIR.glob("*.csv") if note_set.PATTERN.match(p.name))
    assert files, "no committed predictions"
    assert [f for f in files if f not in reg.index] == []
    assert note_set.JUDGE_FILE in reg.index


def test_the_ladder_scores_only_current_predictions_and_lists_the_rest_as_pending():
    ladder = pd.read_csv(DATASETS_DIR / "ladder" / "ladder_vs_truth.csv")
    pending = pd.read_csv(DATASETS_DIR / "ladder" / note_set.PENDING_FILE)
    _, expected = note_set.prediction_files(DATASETS_DIR)
    assert sorted(pending["method_name"]) == sorted(expected["method_name"])
    scored = {m.removesuffix("+rules4") for m in ladder["method"]}
    assert not scored & set(pending["method_name"])


def test_a_full_run_on_rebuilt_notes_replaces_a_larger_file_from_the_old_notes(tmp_path):
    # #467: the review set went from 240 notes to 223. The old file's 240 rows were made on the old notes, so they
    # don't set the bar for a full run on the new ones; a smaller test run on the new notes is still refused.
    dest, src = tmp_path / "datasets", tmp_path / "out"
    src.mkdir()
    _key(dest, [1, 2, 3, 4, 5], text="old note {}")
    _preds(dest, "m", [1, 2, 3, 4, 5])
    note_set.stamp(dest, ["ai_predictions_m.csv"])                     # made on the old notes
    _key(dest, [1, 2, 3])                                              # the rebuild: fewer, different notes
    _preds(src, "m", [1, 2])
    with pytest.raises(ValueError, match="fewer rows"):
        results_store.record(src, dest, "https://x/runs/4", min_rows=3)
    _preds(src, "m", [1, 2, 3])
    assert results_store.record(src, dest, "https://x/runs/5", min_rows=3) == ["ai_predictions_m.csv"]
    assert len(pd.read_csv(dest / "ai_predictions_m.csv")) == 3 and note_set.is_current(dest, "ai_predictions_m.csv")


def test_a_file_already_on_the_current_notes_still_sets_the_bar(tmp_path):
    dest, src = tmp_path / "datasets", tmp_path / "out"
    src.mkdir()
    _key(dest, [1, 2, 3, 4])
    _preds(dest, "m", [1, 2, 3, 4])
    note_set.stamp(dest, ["ai_predictions_m.csv"])
    _preds(src, "m", [1, 2, 3])
    with pytest.raises(ValueError, match="fewer rows"):
        results_store.record(src, dest, "https://x/runs/6", min_rows=3)
