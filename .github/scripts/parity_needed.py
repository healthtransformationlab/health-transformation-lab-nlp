"""Does a pull request need the R parity job? (issue #152)

R parity reruns the Python pipeline in python/scripts/make_parity_inputs.sh and compares R with it. It is needed when
a changed file is one that pipeline depends on:
  - the scripts make_parity_inputs.sh runs, and the health_transformation_lab_nlp modules they import, followed through every
    module they import in turn;
  - r/, the inputs the scripts read (data/, eval/, synthea/, omop/, models.yaml, costs.yaml), the package's
    dependencies (python/pyproject.toml), and this check and the CI workflow themselves.
Everything else (docs, tests, dashboards, notebooks, infra, modules the pipeline never imports) cannot change what R
is compared against. Pushes to main, manual runs and the weekly run don't ask: they always run parity.

It also says whether anything but docs changed (issue #244): a pull request that changes only Markdown and images
skips the CI jobs docs can't affect, so every check still reports and can be required on main.

    BASE=<sha> HEAD=<sha> python .github/scripts/parity_needed.py    # prints needed= and code=true|false for $GITHUB_OUTPUT
"""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = "python/scripts/make_parity_inputs.sh"
PACKAGE = "python/health_transformation_lab_nlp"
ALWAYS = ("r/", "data/", "eval/", "synthea/", "omop/", "models.yaml", "costs.yaml", "python/pyproject.toml",
          SCRIPT, ".github/scripts/parity_needed.py", ".github/workflows/ci.yml")


def _imported_modules(path: Path) -> set[str]:
    """health_transformation_lab_nlp modules a file imports (absolute, or relative inside the package)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    inside = path.parent.name == "health_transformation_lab_nlp"
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                parts = a.name.split(".")
                if parts[0] == "health_transformation_lab_nlp" and len(parts) > 1:
                    out.add(parts[1])
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level and inside:                       # from .x import y, from . import x
                base = "health_transformation_lab_nlp" + ("." + base if base else "")
            parts = base.split(".")
            if parts[0] != "health_transformation_lab_nlp":
                continue
            if len(parts) > 1:
                out.add(parts[1])
            else:                                          # from health_transformation_lab_nlp import a, b
                out |= {a.name for a in node.names}
    return out


def dependencies(root: Path = ROOT) -> set[str]:
    """Repo-relative paths of the scripts make_parity_inputs.sh runs and every package module they reach."""
    scripts = sorted(set(re.findall(r"python (scripts/[\w.]+\.py)", (root / SCRIPT).read_text())))
    files = {SCRIPT} | {f"python/{s}" for s in scripts}
    todo = [root / "python" / s for s in scripts] + [root / PACKAGE / "__init__.py"]
    seen = set()
    while todo:
        path = todo.pop()
        if path in seen or not path.exists():
            continue
        seen.add(path)
        files.add(path.relative_to(root).as_posix())
        todo += [root / PACKAGE / f"{m}.py" for m in _imported_modules(path)]
    return files


DOC_SUFFIXES = (".md", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".pdf", ".drawio")


def code_changed(changed: list[str]) -> bool:
    """True when a changed file is anything but prose or an image. Slides, scripts and builders under docs/ or
    diagrams/ count as code: tests read them."""
    return any(not c.lower().endswith(DOC_SUFFIXES) for c in changed)


def needed(changed: list[str], root: Path = ROOT) -> bool:
    deps = dependencies(root)
    return any(c in deps or c.startswith(ALWAYS) for c in changed)


if __name__ == "__main__":
    base, head = os.environ.get("BASE", ""), os.environ.get("HEAD", "")
    changed = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"], cwd=ROOT, check=True,
                             capture_output=True, text=True).stdout.split()
    hits = sorted(c for c in changed if c in dependencies() or c.startswith(ALWAYS))
    print(f"needed={'true' if hits else 'false'}")
    print(f"code={'true' if code_changed(changed) else 'false'}")
    print(f"{len(hits)} of {len(changed)} changed files reach R parity: {', '.join(hits[:10]) or 'none'}", file=sys.stderr)
