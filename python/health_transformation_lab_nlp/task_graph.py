"""Snapshots and code graphs for the task set (spec 028, US4, #355).

    snapshot     the files at `base_commit` as one commit in a fresh repo on `main`, as a `.tgz`: no history, so
                 nothing after the base and no old commit message can leak through `git log`; the organisation
                 name CLAUDE.md forbids is redacted in the few text files that carried it (#435)
    build_graph  an AST walk over the package into NetworkX node-link JSON with the competition's keys:
                 directed multigraph; nodes `id` (qualified symbol) / `name` (= id) / `text` (the def's source);
                 edges `source` / `target` / `type` ("calls") / `key` (parallel-edge index)

The dataset's format comes from gemma-developer-agent `docs/dataset-format.md` (read from the competition's Data
tab); no competition graph file has been compared here, so the node-id form (`pkg.module.Class.method`, not the
starter notebook's `<repo>;...`) and the tgz layout (one `workspace/` folder) are unverified.
"""

from __future__ import annotations

import ast
import io
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

from . import task_mine  # one definition of the organisation name and its redaction
from .telemetry import traced


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


# the organisation CLAUDE.md forbids, as a git grep pattern (built from parts, like task_mine._ORG)
_ORG_GREP = "care" + "[[:space:]_-]?" + "quests?"
SNAPSHOT_AUTHOR = ("task-set", "task-set@invalid")


@traced
def files_naming_org(repo: Path, commit: str) -> list[str]:
    """Paths of text files at `commit` that name the organisation CLAUDE.md forbids (case-insensitive, whole
    words, so "care questions" doesn't count)."""
    r = subprocess.run(["git", "grep", "-l", "-I", "-i", "-w", "-E", _ORG_GREP, commit], cwd=repo,
                       capture_output=True, text=True, check=False)   # exit 1 = no match
    if r.returncode == 1:
        return []
    r.check_returncode()
    return sorted(line.split(":", 1)[1] for line in r.stdout.splitlines() if ":" in line)


def _blobs(cwd: Path, rev: str) -> dict[str, str]:
    """path -> blob SHA for every file at `rev`."""
    out = _git(cwd, "ls-tree", "-r", "-z", rev).decode()
    return {e.split("\t", 1)[1]: e.split()[2] for e in out.split("\0") if e}


@traced
def snapshot(repo: Path, base_commit: str, out_tgz: Path, work_dir: Path, arcname: str = "workspace") -> dict:
    """The files at `base_commit` as one commit in a fresh repo on `main`, packed as a `.tgz` with one
    `<arcname>/` folder. No history: earlier commit messages and files stay behind. Text files that name the
    organisation CLAUDE.md forbids have the name replaced with `[org]`, as the statements and hints are; every other
    file is the base's byte for byte (checked), and the redacted paths are returned (#435). The commit's author,
    date (the base's committer date) and message ("Snapshot of <base_commit>") are fixed, so a rebuild gives the
    same head SHA; it differs from `base_commit`, which is why the head is returned."""
    named = files_naming_org(repo, base_commit)
    dest = work_dir / arcname
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    archive = _git(repo, "archive", "--format=tar", base_commit)
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:
        t.extractall(dest, filter="tar")
    for rel in named:
        f = dest / rel
        f.write_text(task_mine.redact(f.read_text(encoding="utf-8")), encoding="utf-8")
    when = _git(repo, "show", "-s", "--format=%cI", base_commit).decode().strip()
    env = {**os.environ, "GIT_AUTHOR_NAME": SNAPSHOT_AUTHOR[0], "GIT_AUTHOR_EMAIL": SNAPSHOT_AUTHOR[1],
           "GIT_COMMITTER_NAME": SNAPSHOT_AUTHOR[0], "GIT_COMMITTER_EMAIL": SNAPSHOT_AUTHOR[1],
           "GIT_AUTHOR_DATE": when, "GIT_COMMITTER_DATE": when}
    _git(dest, "init", "-q", "-b", "main")
    _git(dest, "add", "-A", "-f")
    subprocess.run(["git", "-c", "commit.gpgsign=false", "commit", "-q", "--no-verify", "-m",
                    f"Snapshot of {base_commit}"], cwd=dest, env=env, check=True, capture_output=True)
    head = _git(dest, "rev-parse", "HEAD").decode().strip()
    base_blobs, snap_blobs = _blobs(repo, base_commit), _blobs(dest, "HEAD")
    changed = sorted(p for p in base_blobs.keys() | snap_blobs.keys() if base_blobs.get(p) != snap_blobs.get(p))
    if changed != named:   # only the redacted files may differ from the base, and nothing may be added or lost
        raise RuntimeError(f"snapshot differs from {base_commit} beyond the redacted files: {changed[:5]}")
    if files_naming_org(dest, "HEAD"):
        raise RuntimeError(f"snapshot of {base_commit} still names the organisation CLAUDE.md forbids")
    count = int(_git(dest, "rev-list", "--count", "--all").decode().strip())
    tree = _git(dest, "rev-parse", "HEAD^{tree}").decode().strip()
    _git(dest, "gc", "-q", "--prune=now")
    out_tgz.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out_tgz, "w:gz") as t:
        t.add(dest, arcname=arcname)
    shutil.rmtree(dest)
    return {"base_commit": base_commit, "snapshot_head_sha": head, "tree_sha": tree, "commit_count": count,
            "redacted_paths": ";".join(named), "size_bytes": out_tgz.stat().st_size}
