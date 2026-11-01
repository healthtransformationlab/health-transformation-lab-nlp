"""Spec 028 US4 (#355): snapshots by fast-export and the AST code graph in NetworkX node-link JSON."""

import json
import subprocess
import tarfile

import pytest

from health_transformation_lab_nlp import task_graph as tg

PKG = {
    "python/pkg/__init__.py": "",
    "python/pkg/util.py": "def helper(x):\n    return x + 1\n\n\ndef unused():\n    pass\n",
    "python/pkg/core.py": (
        "from .util import helper\n"
        "from . import util\n"
        "\n\n"
        "def run(x):\n"
        "    return helper(x) + util.helper(x) + local(x)\n"
        "\n\n"
        "def local(x):\n"
        "    return Box(x).size()\n"
        "\n\n"
        "class Box:\n"
        "    def __init__(self, x):\n"
        "        self.x = x\n"
        "\n"
        "    def size(self):\n"
        "        return self._calc()\n"
        "\n"
        "    def _calc(self):\n"
        "        return helper(self.x)\n"
    ),
    "python/pkg/broken.py": "def oops(:\n",
    "python/tests/test_core.py": "def test_x():\n    pass\n",
}


def test_module_names_come_from_the_path_under_the_source_root():
    assert tg.module_name("python/pkg/core.py", "python/") == "pkg.core"
    assert tg.module_name("python/pkg/__init__.py", "python/") == "pkg"


def test_the_package_is_found_at_each_base_even_after_a_rename():
    old = ["python/old_pkg/__init__.py", "python/old_pkg/a.py", "python/tests/__init__.py",
           "python/scripts/x.py"]
    assert tg.package_name(old, "python/") == "old_pkg"
    assert tg.package_name(list(PKG), "python/") == "pkg"
    assert tg.package_name(["README.md"], "python/") is None


def test_graph_has_the_dataset_keys_and_qualified_nodes():
    g = tg.build_graph(PKG, package="pkg", source_root="python/", meta={"repo": "o/r", "base_commit": "b" * 40})
    assert g["directed"] is True and g["multigraph"] is True and g["graph"]["base_commit"] == "b" * 40
    ids = {n["id"] for n in g["nodes"]}
    assert {"pkg.util.helper", "pkg.util.unused", "pkg.core.run", "pkg.core.local", "pkg.core.Box",
            "pkg.core.Box.size", "pkg.core.Box._calc", "pkg.core.Box.__init__"} <= ids
    assert not any(i.startswith("tests") or "oops" in i for i in ids)   # only the package; broken files skipped
    node = next(n for n in g["nodes"] if n["id"] == "pkg.util.helper")
    assert node["name"] == node["id"] and node["text"] == "def helper(x):\n    return x + 1"
    assert all(set(n) == {"id", "name", "text"} for n in g["nodes"])


def test_call_edges_resolve_imports_locals_and_self():
    g = tg.build_graph(PKG, package="pkg", source_root="python/", meta={})
    edges = {(e["source"], e["target"]) for e in g["edges"]}
    assert ("pkg.core.run", "pkg.util.helper") in edges          # from .util import helper; util.helper
    assert ("pkg.core.run", "pkg.core.local") in edges           # same module
    assert ("pkg.core.local", "pkg.core.Box") in edges           # class call
    assert ("pkg.core.Box.size", "pkg.core.Box._calc") in edges  # self.method
    assert ("pkg.core.Box._calc", "pkg.util.helper") in edges
    assert all(set(e) == {"source", "target", "type", "key"} and e["type"] == "calls" and e["key"] == 0
               for e in g["edges"])
    assert len(edges) == len(g["edges"])                         # one edge per caller and callee


def test_networkx_reads_the_graph_when_installed():
    nx = pytest.importorskip("networkx")
    g = tg.build_graph(PKG, package="pkg", source_root="python/", meta={})
    G = nx.node_link_graph(json.loads(json.dumps(g)), edges="edges")
    assert G.is_directed() and G.is_multigraph() and G.has_edge("pkg.core.run", "pkg.util.helper")


def _git(cwd, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "-c", "commit.gpgsign=false",
                           *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def _three_commits(tmp_path, middle_message="second message"):
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "trunk")
    for i, msg in enumerate(["first message", middle_message, "third message"]):
        (src / "f.txt").write_text(f"v{i}\n")
        _git(src, "add", ".")
        _git(src, "commit", "-q", "-m", msg)
    return src, _git(src, "rev-list", "--reverse", "HEAD").split()[1]


def test_snapshot_is_one_commit_with_the_base_files_and_no_history(tmp_path):
    src, base = _three_commits(tmp_path, middle_message="secret history line")
    out = tmp_path / "snap.tgz"
    info = tg.snapshot(src, base, out, work_dir=tmp_path / "work")
    assert out.exists() and info["commit_count"] == 1
    assert info["tree_sha"] == _git(src, "rev-parse", f"{base}^{{tree}}").strip()   # the base's files exactly
    x = tmp_path / "x"
    with tarfile.open(out) as t:
        t.extractall(x, filter="data")
    repo = x / "workspace"
    assert (repo / "f.txt").read_text() == "v1\n"
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"
    assert _git(repo, "rev-list", "--count", "--all").strip() == "1"
    log = _git(repo, "log", "--all", "--format=%B")
    assert "secret history line" not in log and "first message" not in log   # no history message comes along
    assert base in log                                               # the message names the base it was cut from
    assert _git(repo, "status", "--porcelain") == ""


def test_snapshot_is_reproducible(tmp_path):
    src, base = _three_commits(tmp_path)
    a = tg.snapshot(src, base, tmp_path / "a.tgz", work_dir=tmp_path / "wa")
    b = tg.snapshot(src, base, tmp_path / "b.tgz", work_dir=tmp_path / "wb")
    assert a["snapshot_head_sha"] == b["snapshot_head_sha"]          # fixed author, date and message


def test_snapshot_redacts_the_organisation_name_and_keeps_every_other_file(tmp_path):
    src, base = _three_commits(tmp_path)
    (src / "g.md").write_text("from " + "Care" + "Quest" + " and care questions\n")
    (src / "h.bin").write_bytes(b"\x00\x01binary")
    _git(src, "add", ".")
    _git(src, "commit", "-q", "-m", "c3")
    head = _git(src, "rev-parse", "HEAD").strip()
    assert tg.files_naming_org(src, head) == ["g.md"] and tg.files_naming_org(src, base) == []
    info = tg.snapshot(src, head, tmp_path / "s.tgz", work_dir=tmp_path / "w")
    assert info["redacted_paths"] == "g.md"
    x = tmp_path / "x"
    with tarfile.open(tmp_path / "s.tgz") as t:
        t.extractall(x, filter="data")
    repo = x / "workspace"
    assert (repo / "g.md").read_text() == "from [org] and care questions\n"
    assert (repo / "f.txt").read_text() == "v2\n" and (repo / "h.bin").read_bytes() == b"\x00\x01binary"
    assert tg.files_naming_org(repo, "HEAD") == []
    clean = tg.snapshot(src, base, tmp_path / "c.tgz", work_dir=tmp_path / "w2")
    assert clean["redacted_paths"] == "" and clean["tree_sha"] == _git(src, "rev-parse", f"{base}^{{tree}}").strip()
