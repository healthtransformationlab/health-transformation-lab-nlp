"""Snapshots and code graphs for the task set (spec 028, US4, #355).

    snapshot     the files at `base_commit` as one commit in a fresh repo on `main`, as a `.tgz`: no history, so
                 nothing after the base and no old commit message can leak through `git log`; the organisation
                 name CLAUDE.md forbids is redacted in the few text files that carried it (#435)
    build_graph  an AST walk over the package into NetworkX node-link JSON with the competition's keys:
                 directed multigraph; nodes `id` (qualified symbol) / `name` (= id) / `text` (the def's source);
                 edges `source` / `target` / `type` ("calls") / `key` (parallel-edge index)
    embed_graph  one 256-float32 unit vector per node, keyed by node id, from the node's source text (its name
                 when empty); `save_embeddings` writes them as an .npz, one array per node (T010)
    wheel_requirements, wheel_download_command
                 the package's runtime, `dev` and `tasks` dependencies, as Python 3.13 binary wheels (T010)

The dataset's format comes from gemma-developer-agent `docs/dataset-format.md` (read from the competition's Data
tab); no competition graph file has been compared here, so the node-id form (`pkg.module.Class.method`, not the
starter notebook's `<repo>;...`) is unverified; the tgz layout (files and `.git` at the root) matches the
competition's (checked by #449's workflow, #452).
"""

from __future__ import annotations

import ast
import io
import os
import shutil
import subprocess
import tarfile
from collections.abc import Callable
from pathlib import Path

import numpy as np

from . import task_mine  # one definition of the organisation name and its redaction
from .telemetry import traced

# The embedding model is named and pinned; the competition doesn't name its own, so parity is unverified (spec 028)
EMBED_MODEL = "google/embeddinggemma-300m"            # gated: the Gemma licence, accepted on Hugging Face
EMBED_REVISION = "57c266a740f537b4dc058e1b0cda161fd15afa75"
EMBED_DIMS = 256                                      # Matryoshka cut of the model's 768, then renormalised
WHEEL_EXTRAS = ("dev", "tasks")                       # tests and graphs; not torch and the model extras
WHEEL_PYTHON = "3.13"
WHEEL_PLATFORMS = ("manylinux_2_28_x86_64", "manylinux_2_17_x86_64", "manylinux2014_x86_64", "any")


@traced
def module_name(path: str, source_root: str) -> str:
    """`python/pkg/core.py` → `pkg.core`; a package's `__init__.py` → the package."""
    rel = path.removeprefix(source_root)
    parts = rel[:-3].split("/")
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


@traced
def package_name(paths: list[str], source_root: str) -> str | None:
    """The package under `source_root` at a given commit: the top-level folder with an `__init__.py`, other than
    tests and scripts (the package was renamed during the history, so it can't be fixed)."""
    names = sorted({p[len(source_root):].split("/")[0] for p in paths
                    if p.startswith(source_root) and p.count("/") == source_root.count("/") + 1
                    and p.endswith("/__init__.py")} - {"tests", "scripts"})
    return names[0] if names else None


def _resolve_from(module: str, is_package: bool, level: int, target: str | None) -> str:
    """The absolute module named by `from <.level target> import ...` inside `module`."""
    if level == 0:
        return target or ""
    base = module.split(".") if is_package else module.split(".")[:-1]
    base = base[: len(base) - (level - 1)] if level > 1 else base
    return ".".join(base + ([target] if target else []))


class _Defs(ast.NodeVisitor):
    """Collect every function, class and method with its qualified name and AST node."""

    def __init__(self, module: str):
        self.module, self.stack, self.found, self._in_class = module, [], [], False

    def _visit_def(self, node):
        qual = ".".join([self.module, *self.stack, node.name])
        self.found.append((qual, node, self.stack[-1] if self._in_class else None))
        self.stack.append(node.name)
        was, self._in_class = self._in_class, isinstance(node, ast.ClassDef)
        self.generic_visit(node)
        self._in_class = was
        self.stack.pop()

    visit_FunctionDef = visit_AsyncFunctionDef = visit_ClassDef = _visit_def


def _imports(tree: ast.Module, module: str, is_package: bool) -> dict[str, str]:
    """Local name → absolute dotted name, from the module's top-level imports."""
    names: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for a in node.names:
                names[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            src = _resolve_from(module, is_package, node.level, node.module)
            for a in node.names:
                names[a.asname or a.name] = f"{src}.{a.name}" if src else a.name
    return names


def _dotted(expr: ast.expr) -> list[str] | None:
    parts = []
    while isinstance(expr, ast.Attribute):
        parts.append(expr.attr)
        expr = expr.value
    if isinstance(expr, ast.Name):
        return [expr.id, *reversed(parts)]
    return None


@traced
def build_graph(sources: dict[str, str], package: str, source_root: str, meta: dict) -> dict:
    """NetworkX node-link JSON for the package's functions, classes and methods, with `calls` edges that resolve
    through same-module names, imports (absolute and relative), `self.<method>` and `<Class>.<method>`.
    Files that don't parse are skipped; files outside the package (tests, scripts) are not walked."""
    prefix = source_root + package.replace(".", "/") + "/"
    parsed = []
    for path in sorted(sources):
        if not path.endswith(".py") or not path.startswith(prefix):
            continue
        try:
            tree = ast.parse(sources[path])
        except SyntaxError:
            continue
        mod = module_name(path, source_root)
        parsed.append((path, mod, path.endswith("/__init__.py"), tree))

    nodes, defs = {}, []
    for path, mod, is_pkg, tree in parsed:
        v = _Defs(mod)
        v.visit(tree)
        for qual, node, cls in v.found:
            nodes[qual] = {"id": qual, "name": qual, "text": ast.get_source_segment(sources[path], node) or ""}
            defs.append((qual, node, cls, mod, _imports(tree, mod, is_pkg)))

    edges: dict[tuple[str, str], dict] = {}
    for qual, node, cls, mod, imports in defs:
        if isinstance(node, ast.ClassDef):
            continue
        owner = qual.rsplit(".", 1)[0]
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            parts = _dotted(call.func)
            if not parts:
                continue
            head, rest = parts[0], parts[1:]
            if head == "self" and cls and rest:
                cands = [f"{owner}.{rest[0]}"]
            elif head in imports:
                cands = [".".join([imports[head], *rest])]
            else:
                cands = [".".join([mod, *parts])]
            for target in cands:
                if target in nodes and target != qual and (qual, target) not in edges:
                    edges[(qual, target)] = {"source": qual, "target": target, "type": "calls", "key": 0}
    return {"directed": True, "multigraph": True, "graph": dict(meta),
            "nodes": list(nodes.values()), "edges": list(edges.values())}


def _git(cwd: Path, *args: str, stdin: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=cwd, input=stdin, capture_output=True, check=True).stdout


SNAPSHOT_AUTHOR = ("task-set", "task-set@invalid")


def _decode(data: bytes) -> str:
    """Bytes as text that encodes back to the same bytes (invalid UTF-8 kept via surrogateescape)."""
    return data.decode("utf-8", errors="surrogateescape")


def _text_files(repo: Path, commit: str) -> dict[str, bytes]:
    """path -> contents of every text file at `commit` (binary: a NUL in the first 8 KB, as the repo's tests)."""
    out = {}
    with tarfile.open(fileobj=io.BytesIO(_git(repo, "archive", "--format=tar", commit))) as t:
        for m in t.getmembers():
            if m.isfile():
                data = t.extractfile(m).read()
                if b"\0" not in data[:8192]:
                    out[m.name] = data
    return out


@traced
def files_naming_org(repo: Path, commit: str) -> list[str]:
    """Paths of text files at `commit` that name the organisation CLAUDE.md forbids. One definition of the name,
    `task_mine.names_org`, so finding and redacting always agree (#435)."""
    return sorted(p for p, data in _text_files(repo, commit).items() if task_mine.names_org(_decode(data)))


def _blobs(cwd: Path, rev: str) -> dict[str, str]:
    """path -> "<mode> <blob SHA>" for every file at `rev`, so a lost executable bit counts as a change."""
    out = _git(cwd, "ls-tree", "-r", "-z", rev).decode("utf-8", errors="surrogateescape")
    blobs = {}
    for e in filter(None, out.split("\0")):
        meta, path = e.split("\t", 1)
        mode, _, sha = meta.split()
        blobs[path] = f"{mode} {sha}"
    return blobs


# Files left out of every snapshot: received with no stated redistribution licence, so not republished outside the
# repository (owner's decision, PR #515). The course's BIO files; MACCROBAT itself (CC BY 4.0) stays.
WITHHELD_PATHS = ("data/external/maccrobat/course/",)


EVALUATOR_CONFTEST = "conftest.py"   # the one file a snapshot adds to its base (spec 028 US6, #641)
EVALUATOR_CONFTEST_TEXT = '''\
# Added to this snapshot so the Gemma 4 Developer Agent competition's evaluator can import the package.
# The evaluator puts the repository root on the import path; this repository's package lives in python/.
# This puts python/ there too, for the tests and for any script a test starts.
import os
import sys
from pathlib import Path

_PKG = str(Path(__file__).resolve().parent / "python")
if _PKG not in sys.path:
    sys.path.insert(0, _PKG)
os.environ["PYTHONPATH"] = os.pathsep.join(
    [_PKG] + [p for p in os.environ.get("PYTHONPATH", "").split(os.pathsep) if p and p != _PKG])
'''


@traced
def snapshot(repo: Path, base_commit: str, out_tgz: Path, work_dir: Path) -> dict:
    """The files at `base_commit` as one commit in a fresh repo on `main`, packed as a `.tgz` with one
    repository's files and `.git` at the archive root, as the competition's are: the harness unpacks each one
    straight into /workspace (#452). No history: earlier commit messages and files stay behind. Text files that name the
    organisation CLAUDE.md forbids have the name replaced with `[org]`, as the statements and hints are, byte for
    byte elsewhere (line endings and non-UTF-8 bytes kept); files under WITHHELD_PATHS are left out (PR #515); every
    other file is the base's, mode and content (checked), and the redacted and withheld paths are returned (#435).
    One file is added, inside the commit: EVALUATOR_CONFTEST at the root, which puts python/ on the import path so the
    competition's evaluator can import the package (US6, #641); a base that already has one is refused.
    The commit's author, date (the base's committer date)
    and message ("Snapshot of <base_commit>") are fixed, so a rebuild gives the same head SHA; it differs from
    `base_commit`, which is why the head is returned. The work folder is removed whatever happens."""
    dest = work_dir / "workspace"
    if dest.exists():
        shutil.rmtree(dest)
    try:
        dest.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(_git(repo, "archive", "--format=tar", base_commit))) as t:
            t.extractall(dest, filter="tar")
        withheld = sorted(p for p in _blobs(repo, base_commit) if p.startswith(WITHHELD_PATHS))
        for rel in withheld:
            (dest / rel).unlink()
            parent = (dest / rel).parent
            while parent != dest and not any(parent.iterdir()):   # no empty folder left in the archive
                parent.rmdir()
                parent = parent.parent
        named = [p for p in files_naming_org(repo, base_commit) if p not in withheld]
        for rel in named:
            f = dest / rel
            f.write_bytes(task_mine.redact(_decode(f.read_bytes())).encode("utf-8", errors="surrogateescape"))
        if (dest / EVALUATOR_CONFTEST).exists():   # it would be overwritten: decide by hand what to do
            raise RuntimeError(f"{base_commit} already has a root {EVALUATOR_CONFTEST}: the snapshot adds its own")
        (dest / EVALUATOR_CONFTEST).write_text(EVALUATOR_CONFTEST_TEXT, encoding="utf-8")
        when = _git(repo, "show", "-s", "--format=%cI", base_commit).decode().strip()
        env = {**os.environ, "GIT_AUTHOR_NAME": SNAPSHOT_AUTHOR[0], "GIT_AUTHOR_EMAIL": SNAPSHOT_AUTHOR[1],
               "GIT_COMMITTER_NAME": SNAPSHOT_AUTHOR[0], "GIT_COMMITTER_EMAIL": SNAPSHOT_AUTHOR[1],
               "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
        _git(dest, "init", "-q", "-b", "main")
        _git(dest, "-c", "core.autocrlf=false", "add", "-A", "-f")
        subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m",
                        f"Snapshot of {base_commit}"], cwd=dest, env=env, check=True, capture_output=True)
        head = _git(dest, "rev-parse", "HEAD").decode().strip()
        base_blobs, snap_blobs = _blobs(repo, base_commit), _blobs(dest, "HEAD")
        changed = sorted(p for p in base_blobs.keys() | snap_blobs.keys() if base_blobs.get(p) != snap_blobs.get(p))
        if changed != sorted(named + withheld + [EVALUATOR_CONFTEST]):   # redacted, withheld, and the one added file
            raise RuntimeError(f"snapshot differs from {base_commit} beyond the redacted files: {changed[:5]}")
        if files_naming_org(dest, "HEAD"):
            raise RuntimeError(f"snapshot of {base_commit} still names the organisation CLAUDE.md forbids")
        count = int(_git(dest, "rev-list", "--count", "--all").decode().strip())
        tree = _git(dest, "rev-parse", "HEAD^{tree}").decode().strip()
        _git(dest, "gc", "-q", "--prune=now")
        out_tgz.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(out_tgz, "w:gz") as t:
            for child in sorted(dest.iterdir()):   # files at the root, no wrapping folder (#452)
                t.add(child, arcname=child.name)
    except BaseException:
        out_tgz.unlink(missing_ok=True)
        raise
    finally:
        shutil.rmtree(dest, ignore_errors=True)
    return {"base_commit": base_commit, "snapshot_head_sha": head, "tree_sha": tree, "commit_count": count,
            "redacted_paths": ";".join(named), "withheld_paths": ";".join(withheld),
            "size_bytes": out_tgz.stat().st_size}


@traced
def embed_graph(graph: dict, encode: Callable[[list[str]], np.ndarray], dims: int = EMBED_DIMS,
                cache: dict[str, np.ndarray] | None = None) -> dict[str, np.ndarray]:
    """One float32 unit vector of `dims` per node, keyed by node id. `encode` maps texts to an (n, >= dims) array;
    each distinct text is encoded once, and `cache` (text -> vector) carries over between graphs, since most
    functions are the same from one base commit to the next."""
    cache = {} if cache is None else cache
    texts = {n["id"]: (n.get("text") or n["name"]) for n in graph["nodes"]}
    todo = sorted({t for t in texts.values() if t not in cache})
    if todo:
        raw = np.asarray(encode(todo), dtype=np.float64)[:, :dims]
        norms = np.linalg.norm(raw, axis=1, keepdims=True)
        unit = np.divide(raw, norms, out=np.zeros_like(raw), where=norms > 0).astype(np.float32)
        cache.update(zip(todo, unit))
    return {node_id: cache[t] for node_id, t in texts.items()}


@traced
def save_embeddings(vectors: dict[str, np.ndarray], path: Path) -> None:
    """An .npz with one array per node, named by node id (overwritten whole, so re-runnable)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        np.savez_compressed(f, **vectors)


@traced
def wheel_requirements(pyproject_text: str) -> list[str]:
    """The runtime dependencies plus the `dev` and `tasks` extras: what the target tests import in the sandbox."""
    import tomllib  # Python 3.11+; imported here so the package still imports on 3.10 (requires-python)
    project = tomllib.loads(pyproject_text)["project"]
    extras = project.get("optional-dependencies", {})
    reqs = list(project.get("dependencies", []))
    for name in WHEEL_EXTRAS:
        reqs += [r for r in extras.get(name, []) if not r.startswith("ruff")]   # a linter, not imported by tests
    return sorted(set(reqs), key=str.lower)


@traced
def wheel_download_command(requirements: list[str], out_dir: Path) -> list[str]:
    """`pip download` of binary wheels for the Python 3.13 x86_64 Linux sandbox, with their dependencies."""
    platforms = [x for p in WHEEL_PLATFORMS for x in ("--platform", p)]
    return ["pip", "download", "--only-binary=:all:", "--python-version", WHEEL_PYTHON, *platforms,
            "--dest", str(out_dir), *requirements]
