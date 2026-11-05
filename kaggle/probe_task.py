"""Write the probe copy of the PerioBench task (#593): the same task file, pushed as `perio-bench-probe` on a few
notes, so a fix can be checked on Kaggle for cents before a full run on every model. Kaggle runs the pushed file
without our environment variables, so the note count is written into the copy.

    python kaggle/probe_task.py --out build/perio_bench_probe.py --n 3

Standard library only, so the workflow needs no install for it.
"""

from __future__ import annotations

import argparse
from pathlib import Path

TASK_FILE = Path(__file__).resolve().parent / "perio_bench_task.py"
SLUG, PROBE_SLUG = "perio-bench", "perio-bench-probe"
_NAME = f'name="{SLUG}"'
_N = 'n = os.environ.get("PERIO_BENCH_N")'


def make_probe(text: str, n: int) -> str:
    """The task file under the probe slug, reading the first `n` notes. Each replaced line must occur exactly once,
    so a task file that changes shape fails here instead of pushing something else."""
    for needle in (_NAME, _N):
        if text.count(needle) != 1:
            raise ValueError(f"expected {needle!r} once in the task file, found {text.count(needle)}")
    return text.replace(_NAME, f'name="{PROBE_SLUG}"').replace(_N, f'n = "{int(n)}"')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=3)
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(make_probe(TASK_FILE.read_text(encoding="utf-8"), args.n), encoding="utf-8")
    print(f"wrote {args.out}: task {PROBE_SLUG}, {args.n} notes")


if __name__ == "__main__":
    main()
