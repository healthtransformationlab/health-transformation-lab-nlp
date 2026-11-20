"""#888: Colab watch records state changes for the ideas panel and phone pings."""
import importlib.util
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("colab_watch", REPO_ROOT / "kaggle" / "colab_watch.py")
cw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cw)


def test_load_prev_reads_labels(tmp_path: Path):
    path = tmp_path / "status.json"
    path.write_text(json.dumps({"rows": [{"label": "a", "state": "running"}, {"label": "b", "state": "finished"}]}))
    assert cw.load_prev(path) == {"a": "running", "b": "finished"}


def test_append_log_and_write_status(tmp_path: Path, monkeypatch):
    status = tmp_path / "status.json"
    log = tmp_path / "log.jsonl"
    monkeypatch.setattr(cw, "STATUS_PATH", status)
    monkeypatch.setattr(cw, "LOG_PATH", log)
    cw.append_log(log, {"ts": "t", "label": "x", "from": "running", "to": "stale", "kind": "stale"})
    assert "stale" in log.read_text()
    cw.write_status(status, {"updated_ts": "t", "rows": [], "events": []})
    assert json.loads(status.read_text())["updated_ts"] == "t"


def test_mirror_to_ideas(tmp_path: Path):
    dest = tmp_path / "colab_launches.json"
    cw.mirror_to_ideas({"updated_ts": "t", "rows": []}, dest)
    assert json.loads(dest.read_text())["updated_ts"] == "t"
