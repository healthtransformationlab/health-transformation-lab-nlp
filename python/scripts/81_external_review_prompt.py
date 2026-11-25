"""Print the prompt that asks another AI model to review AccessBench, with the questions filled in (spec 043 US8, #935).

    python scripts/81_external_review_prompt.py                 # to the screen
    python scripts/81_external_review_prompt.py --out FILE      # to a file

The prompt is benchmarks/access_bench/prompts/external_review.md (the part below its "---" line). What a model says
back is a suggestion for the owner's review (docs/access_review_protocol.md), never a review result.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from health_transformation_lab_nlp import access_hard_items as ahi
from health_transformation_lab_nlp import access_phi_items as api
from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.paths import REPO_ROOT

TEMPLATE = REPO_ROOT / "benchmarks" / "access_bench" / "prompts" / "external_review.md"
FIELDS = ("id", "domain", "prompt", "must_include", "red_flags", "resources", "evidence_source", "source_thread_url",
          "knowledge_cutoff_sensitive")


def questions() -> list[dict]:
    """Every question with the fields a reviewer needs; planted details listed by their text."""
    out = []
    for r in api.load_items() + ahi.load_items():
        q = {k: r[k] for k in FIELDS if k in r}
        if "planted_phi" in r:
            q["planted_fake_details"] = [p["text"] for p in r["planted_phi"]]
        out.append(q)
    return out


def prompt() -> str:
    body = TEMPLATE.read_text(encoding="utf-8").split("\n---\n", 1)[1].lstrip("\n")
    return body.replace("[PASTE QUESTIONS HERE]",
                        "```json\n" + json.dumps(questions(), indent=1, ensure_ascii=False) + "\n```")


def main(argv=None) -> int:
    telemetry.setup()
    telemetry.start_script("81_external_review_prompt", data_label="synthetic")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    text = prompt()
    if a.out:
        a.out.write_text(text, encoding="utf-8")
        print(f"wrote {a.out} ({len(text):,} characters)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
