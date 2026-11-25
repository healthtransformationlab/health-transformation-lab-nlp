"""Bring the owner's AccessBench review back into the repo (spec 043 US7, #933).

Export the review page's documents first (the Artifact database tool's `list` with `out_dir`), then:

    python scripts/80_access_review.py --keys-dir EXPORT/keys [--grades-dir EXPORT/grades]           # print changes
    python scripts/80_access_review.py --keys-dir EXPORT/keys [--grades-dir EXPORT/grades] --write   # apply them

With --write: both item files are rewritten with the reviewed answer keys, and data/access_bench/review/ gets
key_review.json (every raw decision) and agreement.json (the owner against the AI judge). An item whose result
breaks its limits is listed and left as it was.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from health_transformation_lab_nlp import access_hard_items as ahi
from health_transformation_lab_nlp import access_phi_items as api
from health_transformation_lab_nlp import access_review as ar

FILES = {"phi": api.ITEMS_PATH, "perio_screening": ahi.ITEMS_PATH}
SAMPLE = ar.REVIEW_DIR / "answer_sample_587381582818833.json"


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--keys-dir", type=Path, required=True)
    p.add_argument("--grades-dir", type=Path)
    p.add_argument("--answers", type=Path, default=SAMPLE)
    p.add_argument("--out-dir", type=Path, default=ar.REVIEW_DIR)
    p.add_argument("--write", action="store_true")
    a = p.parse_args(argv)

    reviews = ar.load_export(a.keys_dir)
    needs_call, changed = [], {}
    for name, path in FILES.items():
        rows = _rows(path)
        for i, row in enumerate(rows):
            if row["id"] not in reviews:
                continue
            try:
                new = ar.apply_key_review(row, reviews[row["id"]])
            except ValueError as e:
                needs_call.append(str(e))
                continue
            for field in ("must_include", "red_flags"):
                for t in row[field]:
                    if t not in new[field]:
                        print(f"{row['id']} {field}: - {t}")
                for t in new[field]:
                    if t not in row[field]:
                        print(f"{row['id']} {field}: + {t}")
            rows[i] = new
            changed.setdefault(name, rows)
        if name in changed:
            changed[name] = rows
    print(f"{len(reviews)} questions reviewed; {sum(1 for _ in reviews) - len(needs_call)} apply cleanly")
    for msg in needs_call:
        print("needs your call:", msg)

    agreement = None
    if a.grades_dir:
        grades = list(ar.load_export(a.grades_dir).values())
        agreement = ar.agreement(grades, json.loads(a.answers.read_text(encoding="utf-8")))
        print("agreement with the AI judge:", json.dumps(agreement))

    if a.write:
        for name, rows in changed.items():
            FILES[name].write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        a.out_dir.mkdir(parents=True, exist_ok=True)
        (a.out_dir / "key_review.json").write_text(json.dumps(reviews, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if agreement is not None:
            (a.out_dir / "agreement.json").write_text(json.dumps(agreement, indent=2) + "\n", encoding="utf-8")
        print("written:", ", ".join(str(FILES[n]) for n in changed) or "no item files", "and", a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
