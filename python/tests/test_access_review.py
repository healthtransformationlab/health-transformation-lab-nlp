"""Spec 043 US7 (#933): the owner's review of the AccessBench answer keys comes back into the repo, and the owner's
grades measure how far the AI judge can be trusted. One reviewer, the owner: an owner check, not an expert panel."""

import importlib.util
import json

import pytest

from health_transformation_lab_nlp import access_hard_items as ahi
from health_transformation_lab_nlp import access_phi_items as api
from health_transformation_lab_nlp import access_review as ar
from health_transformation_lab_nlp.paths import REPO_ROOT


def _review(item, verdicts_points, verdicts_flags, **extra):
    return {"must_include": [{"text": t, "verdict": v, "edit_text": e} for t, (v, e) in zip(item["must_include"], verdicts_points)],
            "red_flags": [{"text": t, "verdict": v, "edit_text": e} for t, (v, e) in zip(item["red_flags"], verdicts_flags)],
            "riskiest_wrong_advice_text": "", "missing_point_text": "", "source_code": "yes", "note_text": "",
            "rubric_version": "v1-2026-11-24", **extra}


@pytest.fixture
def hard():
    return ahi.load_items()[0]


def test_keep_rewrite_remove_and_additions(hard):
    n, m = len(hard["must_include"]), len(hard["red_flags"])
    points = [("keep", ""), ("edit", "Says to ask the office which procedure codes were billed")] + [("keep", "")] * (n - 3) + [("remove", "")]
    flags = [("keep", "")] * (m - 1) + [("remove", "")]
    out = ar.apply_key_review(hard, _review(hard, points, flags, missing_point_text="Says to keep every bill and letter",
                                            riskiest_wrong_advice_text="Tells them to stop treatment until the appeal ends"))
    assert out["must_include"][0] == hard["must_include"][0]
    assert out["must_include"][1] == "Says to ask the office which procedure codes were billed"
    assert hard["must_include"][-1] not in out["must_include"]
    assert out["must_include"][-1] == "Says to keep every bill and letter"
    assert out["red_flags"][-1] == "Tells them to stop treatment until the appeal ends"
    assert hard["red_flags"][-1] not in out["red_flags"]
    assert (out["rubric_version"], out["reviewed_by_code"], out["source_check_code"]) == ("v1-2026-11-24", "owner", "yes")
    ahi.validate_item(out)                                   # still a valid screening item
    assert hard["must_include"][1] != out["must_include"][1]  # the input is not changed in place


def test_a_result_that_breaks_the_limits_names_the_item():
    item = next(r for r in api.load_items() if len(r["red_flags"]) == 3)   # three red flags already
    rev = _review(item, [("keep", "")] * len(item["must_include"]), [("keep", "")] * len(item["red_flags"]),
                  riskiest_wrong_advice_text="A fourth red flag")
    with pytest.raises(ValueError, match=item["id"]):
        ar.apply_key_review(item, rev)


def test_a_rewrite_needs_its_text_and_every_row_needs_a_verdict(hard):
    rows = [("keep", "")] * len(hard["must_include"])
    with pytest.raises(ValueError, match="rewrite"):
        ar.apply_key_review(hard, _review(hard, [("edit", "")] + rows[1:], [("keep", "")] * len(hard["red_flags"])))
    with pytest.raises(ValueError, match="verdict"):
        ar.apply_key_review(hard, _review(hard, [("", "")] + rows[1:], [("keep", "")] * len(hard["red_flags"])))


def test_agreement_counts():
    answers = [{"answer_id": "A01", "judge_covered": 4, "judge_red_flags": [False], "judge_harm": "S0"},
               {"answer_id": "A02", "judge_covered": 2, "judge_red_flags": [True], "judge_harm": "S1"},
               {"answer_id": "A03", "judge_covered": 5, "judge_red_flags": [False], "judge_harm": "S0"}]
    grades = [{"answer_id": "A01", "covered": [True] * 4 + [False], "red_flag_said": [False], "harm_code": "S0"},
              {"answer_id": "A02", "covered": [True] * 5, "red_flag_said": [False], "harm_code": "S0"}]
    a = ar.agreement(grades, answers)
    assert a == {"answer_count": 2, "exact_count": 1, "within_one_count": 1, "mean_abs_gap_ratio": 1.5,
                 "red_flag_agree_count": 1, "harm_agree_count": 1, "resource_level_agree_count": 0}
    assert ar.agreement([], answers)["answer_count"] == 0


def test_load_export_reads_one_file_per_document(tmp_path):
    (tmp_path / "keys").mkdir()
    (tmp_path / "keys" / "ACC_X.json").write_text(json.dumps({"id": "ACC_X", "version": 3, "data": {"source_code": "no"}}))
    (tmp_path / "keys" / "ACC_Y.json").write_text(json.dumps({"source_code": "yes"}))
    got = ar.load_export(tmp_path / "keys")
    assert got == {"ACC_X": {"source_code": "no"}, "ACC_Y": {"source_code": "yes"}}


def test_script_prints_changes_and_writes_only_with_write(tmp_path, monkeypatch, capsys):
    spec = importlib.util.spec_from_file_location("s80", REPO_ROOT / "python/scripts/80_access_review.py")
    s80 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s80)
    item = ahi.load_items()[0]
    keys = tmp_path / "keys"
    keys.mkdir()
    rev = _review(item, [("keep", "")] * len(item["must_include"]), [("keep", "")] * len(item["red_flags"]),
                  missing_point_text="Says to keep every bill")
    (keys / f"{item['id']}.json").write_text(json.dumps(rev))
    hard_copy, phi_copy = tmp_path / "hard.jsonl", tmp_path / "phi.jsonl"
    hard_copy.write_text(ahi.ITEMS_PATH.read_text())
    phi_copy.write_text(api.ITEMS_PATH.read_text())
    monkeypatch.setattr(s80, "FILES", {"perio_screening": hard_copy, "phi": phi_copy})
    out_dir = tmp_path / "review"
    assert s80.main(["--keys-dir", str(keys), "--out-dir", str(out_dir)]) == 0
    assert "Says to keep every bill" in capsys.readouterr().out
    assert hard_copy.read_text() == ahi.ITEMS_PATH.read_text()          # a dry run changes nothing
    assert s80.main(["--keys-dir", str(keys), "--out-dir", str(out_dir), "--write"]) == 0
    first = json.loads(hard_copy.read_text().splitlines()[0])
    assert first["must_include"][-1] == "Says to keep every bill" and first["reviewed_by_code"] == "owner"
    assert json.loads((out_dir / "key_review.json").read_text())[item["id"]]["missing_point_text"] == "Says to keep every bill"


def test_the_answer_sample_is_committed():
    rows = json.loads((ar.REVIEW_DIR / "answer_sample_587381582818833.json").read_text())
    assert len(rows) == 40 and len({r["answer_id"] for r in rows}) == 40
    assert {r["model"] for r in rows} and all(sum(1 for r in rows if r["model"] == m) == 10 for m in {r["model"] for r in rows})
    assert (REPO_ROOT / "docs" / "access_review_protocol.md").is_file()


# ---------- US8 (#935): the reviewer's correct resources ----------

def test_apply_key_review_keeps_the_reviewers_resources(hard):
    res = [{"name_text": "HRSA health center finder", "url": "https://findahealthcenter.hrsa.gov/", "phone_text": "",
            "purpose_text": "find a sliding-fee clinic"}]
    out = ar.apply_key_review(hard, _review(hard, [("keep", "")] * len(hard["must_include"]),
                                            [("keep", "")] * len(hard["red_flags"]), resources=res))
    assert out["resources"] == res
    ahi.validate_item(out)
    bad = dict(out, resources=[{"name_text": "x", "url": "http://insecure.example/"}])
    with pytest.raises(ValueError, match="https"):
        ahi.validate_item(bad)


def test_agreement_counts_resource_level():
    answers = [{"answer_id": "A01", "judge_covered": 4, "judge_red_flags": [False], "judge_harm": "S0", "judge_resource_level": 2}]
    grades = [{"answer_id": "A01", "covered": [True] * 4 + [False], "red_flag_said": [False], "harm_code": "S0", "resource_level": 2}]
    assert ar.agreement(grades, answers)["resource_level_agree_count"] == 1


def test_the_external_review_prompt_holds_every_question_and_no_placeholder(tmp_path):
    spec = importlib.util.spec_from_file_location("s81", REPO_ROOT / "python/scripts/81_external_review_prompt.py")
    s81 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s81)
    out = tmp_path / "prompt.md"
    assert s81.main(["--out", str(out)]) == 0
    text = out.read_text()
    assert "[PASTE QUESTIONS HERE]" not in text and "Never make up a URL or phone number" in text
    for r in api.load_items() + ahi.load_items():
        assert r["id"] in text
    assert "resource specificity" in text.lower()
