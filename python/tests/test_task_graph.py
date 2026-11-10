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


def _files(repo, rev, but=None):
    """{path: (mode, blob sha)} of a commit, optionally without one path."""
    out = {}
    for line in _git(repo, "ls-tree", "-r", rev).splitlines():
        meta, path = line.split("\t", 1)
        if path != but:
            out[path] = tuple(meta.split()[::2])
    return out


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
    x = tmp_path / "x"
    with tarfile.open(out) as t:
        t.extractall(x, filter="data")
    repo = x
    assert _files(repo, "HEAD", but=tg.EVALUATOR_CONFTEST) == _files(src, base)   # the base's files exactly
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
    repo = x
    assert (repo / "g.md").read_text() == "from [org] and care questions\n"
    assert (repo / "f.txt").read_text() == "v2\n" and (repo / "h.bin").read_bytes() == b"\x00\x01binary"
    assert tg.files_naming_org(repo, "HEAD") == []
    clean = tg.snapshot(src, base, tmp_path / "c.tgz", work_dir=tmp_path / "w2")
    assert clean["redacted_paths"] == ""
    y = tmp_path / "y"
    with tarfile.open(tmp_path / "c.tgz") as t:
        t.extractall(y, filter="data")
    assert _files(y, "HEAD", but=tg.EVALUATOR_CONFTEST) == _files(src, base)


def _commit_files(tmp_path, files: dict[str, bytes], mode_exec: str | None = None):
    src = tmp_path / "src"
    src.mkdir()
    _git(src, "init", "-q", "-b", "trunk")
    for rel, data in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_bytes(data)
    if mode_exec:
        (src / mode_exec).chmod(0o755)
    _git(src, "add", ".")
    _git(src, "commit", "-q", "-m", "only")
    return src, _git(src, "rev-parse", "HEAD").strip()


def test_one_definition_of_the_name_finds_it_however_it_is_written(tmp_path):
    org = "Care" + "Quest"
    files = {"nbsp.md": ("care" + chr(0xA0) + "quest\n").encode(), "wrapped.md": b"care\nquest here\n",
             "latin1.txt": ("caf\xe9 " + org + "\n").encode("latin-1"), "crlf.md": ("a\r\n" + org + "\r\nb\r\n").encode(),
             "déjà/accént.md": (org + "\n").encode(), "ok.md": b"care questions\n",
             "bin.dat": b"\x00" + org.encode()}
    src, head = _commit_files(tmp_path, files)
    assert tg.files_naming_org(src, head) == sorted(["nbsp.md", "wrapped.md", "latin1.txt", "crlf.md",
                                                     "déjà/accént.md"])
    info = tg.snapshot(src, head, tmp_path / "s.tgz", work_dir=tmp_path / "w")
    x = tmp_path / "x"
    with tarfile.open(tmp_path / "s.tgz") as t:
        t.extractall(x, filter="data")
    repo = x
    assert (repo / "crlf.md").read_bytes() == b"a\r\n[org]\r\nb\r\n"            # line endings kept
    assert (repo / "latin1.txt").read_bytes() == "caf\xe9 [org]\n".encode("latin-1")   # other bytes kept
    assert (repo / "ok.md").read_bytes() == b"care questions\n" and (repo / "bin.dat").read_bytes() == files["bin.dat"]
    assert tg.files_naming_org(repo, "HEAD") == [] and len(info["redacted_paths"].split(";")) == 5


def test_snapshot_keeps_file_modes_and_reproduces_its_commit(tmp_path):
    src, head = _commit_files(tmp_path, {"run.sh": b"#!/bin/sh\necho " + ("Care" + "Quest").encode() + b"\n",
                                          "a.txt": b"x\n"}, mode_exec="run.sh")
    a = tg.snapshot(src, head, tmp_path / "a.tgz", work_dir=tmp_path / "wa")
    b = tg.snapshot(src, head, tmp_path / "b.tgz", work_dir=tmp_path / "wb")
    same = ("snapshot_head_sha", "tree_sha", "commit_count", "redacted_paths")   # .git/index holds file stat data,
    assert {k: a[k] for k in same} == {k: b[k] for k in same}                    # so the tgz bytes may differ
    x = tmp_path / "x"
    with tarfile.open(tmp_path / "a.tgz") as t:
        t.extractall(x, filter="data")
    assert "100755" in _git(x, "ls-tree", "HEAD", "run.sh")


def test_a_failed_snapshot_leaves_no_work_folder(tmp_path, monkeypatch):
    src, head = _commit_files(tmp_path, {"a.txt": b"x\n"})
    monkeypatch.setattr(tg, "_blobs", lambda cwd, rev: {"surprise": "0"} if rev == "HEAD" else {"a.txt": "1"})
    with pytest.raises(RuntimeError):
        tg.snapshot(src, head, tmp_path / "s.tgz", work_dir=tmp_path / "w")
    assert not (tmp_path / "w" / "workspace").exists() and not (tmp_path / "s.tgz").exists()


def test_snapshot_has_the_files_and_git_at_the_archive_root_like_the_competition(tmp_path):
    """The harness unpacks each snapshot straight into /workspace (#452), so no wrapping folder."""
    from health_transformation_lab_nlp import competition_check as cc
    src, base = _three_commits(tmp_path)
    tg.snapshot(src, base, tmp_path / "s.tgz", work_dir=tmp_path / "w")
    layout = cc.snapshot_layout(tmp_path / "s.tgz")
    assert layout["root_folder"] is None and layout["git_dir"] == ".git"
    with tarfile.open(tmp_path / "s.tgz") as t:
        assert "f.txt" in {m.name for m in t.getmembers()}


# --- embeddings and wheels (T010) -------------------------------------------------------------------------------

def _fake_encode(calls):
    """A stand-in for EmbeddingGemma: 768 floats per text, the first one the text's length, so tests can tell
    texts apart, and records every batch it was given."""
    import numpy as np

    def encode(texts):
        calls.append(list(texts))
        out = np.zeros((len(texts), 768), dtype="float64")
        for i, t in enumerate(texts):
            out[i, 0], out[i, 1], out[i, 300] = len(t), 1.0, 99.0   # column 300 is cut off by truncation
        return out
    return encode


def test_embeddings_give_one_256_float32_unit_vector_per_node_keyed_by_node_id():
    import numpy as np
    g = tg.build_graph(PKG, "pkg", "python/", {"instance_id": "t1"})
    vectors = tg.embed_graph(g, _fake_encode([]))
    assert sorted(vectors) == sorted(n["id"] for n in g["nodes"])
    texts = {n["id"]: n["text"] for n in g["nodes"]}
    for node_id, v in vectors.items():
        assert v.shape == (256,) and v.dtype == np.float32
        n = len(texts[node_id])   # cut to 256 then renormalised: column 300's 99 must not count in the norm
        assert np.allclose(v[:2], [n / np.hypot(n, 1), 1 / np.hypot(n, 1)]) and not v[2:].any()


def test_embeddings_encode_each_distinct_text_once_and_reuse_a_shared_cache():
    g = tg.build_graph(PKG, "pkg", "python/", {"instance_id": "t1"})
    calls, cache = [], {}
    tg.embed_graph(g, _fake_encode(calls), cache=cache)
    first = sum(len(c) for c in calls)
    assert first == len({n["text"] for n in g["nodes"]})
    tg.embed_graph(g, _fake_encode(calls), cache=cache)   # the next base shares most of its functions
    assert sum(len(c) for c in calls) == first


def test_a_node_with_no_source_text_is_embedded_from_its_name():
    calls = []
    g = {"nodes": [{"id": "pkg.f", "name": "pkg.f", "text": ""}], "edges": []}
    tg.embed_graph(g, _fake_encode(calls))
    assert calls == [["pkg.f"]]


def test_embeddings_round_trip_through_npz_and_match_the_competition_check(tmp_path):
    from health_transformation_lab_nlp import competition_check as cc
    g = tg.build_graph(PKG, "pkg", "python/", {"instance_id": "t1"})
    path = tmp_path / "t1.npz"
    tg.save_embeddings(tg.embed_graph(g, _fake_encode([])), path)
    summary = cc.embedding_summary(path)
    assert summary["arrays"] == len(g["nodes"])
    assert summary["shapes"] == [cc.OUR_VECTOR[0]] and summary["dtypes"] == [cc.OUR_VECTOR[1]]


def test_wheel_requirements_are_the_packages_runtime_and_test_dependencies():
    pyproject = (
        '[project]\ndependencies = ["pandas>=2.0", "pyyaml>=6"]\n'
        '[project.optional-dependencies]\ndev = ["pytest>=8", "ruff>=0.5"]\ntasks = ["networkx>=3.4"]\n'
        'models = ["torch>=2.2"]\n'
    )
    assert tg.wheel_requirements(pyproject) == ["networkx>=3.4", "pandas>=2.0", "pytest>=8", "pyyaml>=6"]


def test_wheel_download_command_targets_python_313_binaries_only(tmp_path):
    cmd = tg.wheel_download_command(["pandas>=2.0"], tmp_path / "wheels")
    assert cmd[:4] == ["pip", "download", "--only-binary=:all:", "--python-version"] and cmd[4] == "3.13"
    assert "--platform" in cmd and str(tmp_path / "wheels") in cmd and cmd[-1] == "pandas>=2.0"


def test_two_nodes_with_the_same_source_text_are_encoded_once_and_share_a_vector():
    import numpy as np
    calls = []
    same = "def f():\n    return 1\n"
    g = {"nodes": [{"id": "pkg.a.f", "name": "pkg.a.f", "text": same},
                   {"id": "pkg.b.f", "name": "pkg.b.f", "text": same}], "edges": []}
    v = tg.embed_graph(g, _fake_encode(calls))
    assert calls == [[same]] and np.array_equal(v["pkg.a.f"], v["pkg.b.f"])


def test_snapshot_withholds_files_without_a_redistribution_licence(tmp_path, monkeypatch):   # PR #515, owner's call
    src, base = _three_commits(tmp_path)
    (src / "data" / "external" / "x" / "course").mkdir(parents=True)
    (src / "data" / "external" / "x" / "course" / "train.txt").write_text("received as is\n")
    (src / "data" / "external" / "x" / "README.md").write_text("kept\n")
    _git(src, "add", ".")
    _git(src, "commit", "-q", "-m", "c3")
    head = _git(src, "rev-parse", "HEAD").strip()
    monkeypatch.setattr(tg, "WITHHELD_PATHS", ("data/external/x/course/",))
    info = tg.snapshot(src, head, tmp_path / "s.tgz", work_dir=tmp_path / "w")
    assert info["withheld_paths"] == "data/external/x/course/train.txt"
    with tarfile.open(tmp_path / "s.tgz") as t:
        names = t.getnames()
    assert "data/external/x/README.md" in names and not [n for n in names if "/course" in n]
    assert tg.snapshot(src, base, tmp_path / "b.tgz", work_dir=tmp_path / "wb")["withheld_paths"] == ""


def test_the_course_files_are_withheld():
    assert tg.WITHHELD_PATHS == ("data/external/maccrobat/course/",)


# --- spec 028 US6 (#641): the competition's evaluator must be able to import the package from a snapshot ---------

def test_snapshot_adds_one_root_conftest_inside_its_single_commit(tmp_path):
    src, base = _three_commits(tmp_path)
    info = tg.snapshot(src, base, tmp_path / "s.tgz", work_dir=tmp_path / "w")
    x = tmp_path / "x"
    with tarfile.open(tmp_path / "s.tgz") as t:
        t.extractall(x, filter="data")
    assert (x / tg.EVALUATOR_CONFTEST).read_text() == tg.EVALUATOR_CONFTEST_TEXT
    assert info["commit_count"] == 1 and _git(x, "status", "--porcelain") == ""      # committed, nothing loose
    assert set(_files(x, "HEAD")) - set(_files(src, base)) == {tg.EVALUATOR_CONFTEST}   # the only file added


def test_the_added_conftest_puts_python_on_the_import_path_for_tests_and_their_scripts(tmp_path, monkeypatch):
    """The evaluator puts the repository root on the path; the package is in python/. Loading the conftest must make
    the package importable here and in any process a test starts (PYTHONPATH)."""
    import os
    import runpy
    import sys
    root = tmp_path / "workspace"
    (root / "python" / "somepkg").mkdir(parents=True)
    (root / "python" / "somepkg" / "__init__.py").write_text("VALUE = 7\n")
    (root / tg.EVALUATOR_CONFTEST).write_text(tg.EVALUATOR_CONFTEST_TEXT)
    monkeypatch.setattr(sys, "path", [p for p in sys.path if "workspace" not in p])
    monkeypatch.setenv("PYTHONPATH", str(root))
    runpy.run_path(str(root / tg.EVALUATOR_CONFTEST))
    assert str(root / "python") == sys.path[0]
    assert os.environ["PYTHONPATH"].split(os.pathsep) == [str(root / "python"), str(root)]
    out = subprocess.run([sys.executable, "-c", "import somepkg; print(somepkg.VALUE)"], capture_output=True,
                         text=True, check=False, env={**os.environ, "PYTHONSAFEPATH": "1"}, cwd=tmp_path)
    assert out.stdout.strip() == "7", out.stderr


def test_snapshot_refuses_a_base_that_already_has_a_root_conftest(tmp_path):
    src, head = _commit_files(tmp_path, {"conftest.py": b"x = 1\n", "a.txt": b"x\n"})
    with pytest.raises(RuntimeError, match="conftest.py"):
        tg.snapshot(src, head, tmp_path / "s.tgz", work_dir=tmp_path / "w")
    assert not (tmp_path / "s.tgz").exists()
