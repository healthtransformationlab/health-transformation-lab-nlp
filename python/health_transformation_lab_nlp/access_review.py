"""The owner's review of the AccessBench answer keys, brought back into the repo (spec 043 US7, #933).

The owner reviews on a private review page and its decisions are exported as one JSON file per document. A key
decision keeps, rewrites or removes each point and red flag, may add the riskiest wrong advice and a missing point,
and checks the cited source. A grade is the owner's own scoring of one sampled answer, made before seeing the model
or the AI judge. One reviewer, the owner: an owner check, not an expert panel (docs/access_review_protocol.md).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from . import access_discount_items as adi
from . import access_hard_items as ahi
from . import access_phi_items as api
from .paths import REPO_ROOT
from .telemetry import traced

REVIEW_DIR = REPO_ROOT / "data" / "access_bench" / "review"     # committed: decisions, agreement, the answer sample
VERDICTS = ("keep", "edit", "remove")


def _apply_rows(item_id: str, kind: str, rows: list[dict]) -> list[str]:
    out = []
    for i, r in enumerate(rows, start=1):
        verdict = r.get("verdict") or ""
        if verdict not in VERDICTS:
            raise ValueError(f"{item_id}: {kind} {i} has no verdict (keep, edit or remove)")
        if verdict == "keep":
            out.append(r["text"])
        elif verdict == "edit":
            text = (r.get("edit_text") or "").strip()
            if not text:
                raise ValueError(f"{item_id}: {kind} {i} is marked rewrite but has no new text")
            out.append(text)
    return out


@traced
def apply_key_review(item: dict, review: dict) -> dict:
    """The item as the owner's decision leaves it. Raises ValueError naming the item when a row has no verdict, a
    rewrite has no text, or the result breaks the item's limits (3 to 5 points, 1 to 3 red flags)."""
    out = copy.deepcopy(item)
    points = _apply_rows(item["id"], "point", review["must_include"])
    flags = _apply_rows(item["id"], "red flag", review["red_flags"])
    if (review.get("missing_point_text") or "").strip():
        points.append(review["missing_point_text"].strip())
    if (review.get("riskiest_wrong_advice_text") or "").strip():
        flags.append(review["riskiest_wrong_advice_text"].strip())
    out["must_include"], out["red_flags"] = points, flags
    out["rubric_version"] = review.get("rubric_version", "")
    out["reviewed_by_code"] = "owner"
    out["source_check_code"] = review.get("source_code", "")
    if review.get("resources"):                           # the reviewer's correct resources (#935)
        out["resources"] = [{k: str(r.get(k, "")).strip() for k in ("name_text", "url", "phone_text", "purpose_text")}
                            for r in review["resources"] if str(r.get("name_text", "")).strip()]
    validate = (api.validate_item if "planted_phi" in item
                else adi.validate_item if str(item["id"]).startswith("ACC_DISC_") else ahi.validate_item)
    try:
        validate(out, where=item["id"])
    except (ValueError, TypeError) as e:
        raise ValueError(f"{item['id']}: the review leaves {len(points)} points and {len(flags)} red flags, "
                         f"outside the item's limits ({e})") from e
    return out


@traced
def agreement(grades: list[dict], answers: list[dict]) -> dict:
    """How often the owner's grades match the AI judge's on the same answers. The judge kept only a count of points
    covered, so points are compared as counts; red flags and harm as one call each per answer."""
    judge = {a["answer_id"]: a for a in answers}
    pairs = [(g, judge[g["answer_id"]]) for g in grades if g["answer_id"] in judge]
    gaps = [abs(sum(bool(c) for c in g["covered"]) - a["judge_covered"]) for g, a in pairs]
    n = len(pairs)
    return {"answer_count": n,
            "exact_count": sum(1 for x in gaps if x == 0),
            "within_one_count": sum(1 for x in gaps if x <= 1),
            "mean_abs_gap_ratio": round(sum(gaps) / n, 4) if n else 0.0,
            "red_flag_agree_count": sum(1 for g, a in pairs
                                        if any(g["red_flag_said"]) == any(a.get("judge_red_flags") or [])),
            "harm_agree_count": sum(1 for g, a in pairs if g["harm_code"] == a["judge_harm"]),
            "resource_level_agree_count": sum(1 for g, a in pairs if g.get("resource_level") is not None
                                              and g.get("resource_level") == a.get("judge_resource_level"))}


@traced
def load_export(folder: Path) -> dict[str, dict]:
    """Documents exported from the review page, one JSON file each, keyed by document id (the file name). A file
    that wraps the body in `data` (with `id` and `version` beside it) is unwrapped."""
    docs = {}
    for f in sorted(Path(folder).glob("*.json")):
        body = json.loads(f.read_text(encoding="utf-8"))
        if isinstance(body.get("data"), dict) and ("version" in body or "id" in body):
            body = body["data"]
        docs[f.stem] = body
    return docs
