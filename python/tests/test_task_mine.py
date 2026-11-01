"""The repo's history as a task set (spec 028): tiering, candidates, ids, backfilled issues."""

from health_transformation_lab_nlp import task_mine as tm


def test_issue_number_comes_from_the_branch_or_the_body():
    assert tm.issue_from_branch("feat/71-016-results-loader") == 71
    assert tm.issue_from_branch("claude/great-cerf-qwbqck") is None
    assert tm.issue_from_body("Closes #276\n\n## What changed") == 276
    assert tm.issue_from_body("Refs #12 and fixes #13") == 12
    assert tm.issue_from_body("no link here") is None


def test_squash_subject_names_the_pr():
    assert tm.pr_from_squash_subject("Name Databricks for Good in the pitch deck (#273)") == 273
    assert tm.pr_from_squash_subject("Merge pull request #277 from x/y") is None


def test_spec_number_is_found_in_title_body_or_branch():
    assert tm.spec_from_text("Load results (spec 016 T005)") == "016"
    assert tm.spec_from_text(None, "see specs/014-telemetry") == "014"
    assert tm.spec_from_text("Add a page (026 US3)") == "026"
    assert tm.spec_from_text("nothing") is None


def test_candidate_needs_code_and_tests_and_not_only_a_protected_fix():
    code_and_tests = ["python/health_transformation_lab_nlp/runlog.py", "python/tests/test_runlog.py"]
    assert tm.classify_files(code_and_tests)["is_candidate"] is True
    assert tm.classify_files(["docs/telemetry.md"])["is_candidate"] is False
    assert tm.classify_files(["python/tests/test_x.py"])["is_candidate"] is False
    only_protected = tm.classify_files(["python/pyproject.toml", "python/tests/test_x.py"])
    assert only_protected["is_only_protected_fix"] is True and only_protected["is_candidate"] is False


def test_tiers():
    assert tm.tier_for_pr("feat/71-016-results-loader", "") == ("A", 71)
    assert tm.tier_for_pr("claude/great-cerf-qwbqck", "Closes #90") == ("A", 90)
    assert tm.tier_for_pr("claude/great-cerf-qwbqck", "## What changed") == ("B", None)
    assert tm.tier_for_pr("dependabot/pip/numpy-2", "") == ("tool", None)


def test_instance_ids_prefer_issue_then_pr_then_commit():
    assert tm.instance_id("A", 277, 276, "f8e0094abc") == "htlnlp_276"
    assert tm.instance_id("B", 150, None, "f8e0094abc") == "htlnlp_pr150"
    assert tm.instance_id("C", None, None, "f8e0094abc") == "htlnlp_cf8e0094"


def test_manifest_row_from_a_pr_and_from_a_commit():
    pr = {"number": 277, "title": "Name the benchmarks", "body": "Closes #276", "created_at": "2026-10-29T04:23:55Z",
          "merged_at": "2026-10-29T04:29:55Z", "head": {"ref": "docs/276-bench-order"}}
    commit = {"sha": "f8e009474caf", "parent_sha": "f6fd49ed6a51", "committed_ts": "2026-10-29T04:29:54Z",
              "subject": "Merge pull request #277", "body": ""}
    row = tm.manifest_row("A", pr, commit, ["AGENTS.md"], 276)
    assert row["instance_id"] == "htlnlp_276" and row["statement_source_code"] == "issue"
    assert row["is_candidate"] is False and row["branch_name"] == "docs/276-bench-order"
    direct = {"sha": "abc1234def", "parent_sha": "000", "committed_ts": "2026-10-20T00:00:00Z",
              "subject": "Keep the run log on the volume (spec 014)", "body": "Why: ..."}
    row = tm.manifest_row("C", None, direct, ["python/health_transformation_lab_nlp/runlog.py",
                                              "python/tests/test_runlog.py"], None)
    assert row["instance_id"] == "htlnlp_cabc1234" and row["spec_number"] == "014" and row["is_candidate"] is True
    assert set(row) == set(tm.MANIFEST_COLUMNS)


def test_backfilled_issue_quotes_the_text_verbatim_and_says_so():
    row = {"pr_number": 150, "merge_commit_sha": "abc1234def", "merged_ts": "2026-10-10T00:00:00Z",
           "base_commit_sha": "000111222", "tier_code": "B", "title_text": "Add the thing (#150)", "spec_number": "016"}
    issue = tm.backfill_issue(row, "## What changed\n- the thing\n")
    assert issue["title_key"] == "016 CHORE" and issue["title_text"] == "Add the thing"
    assert "## What changed\n- the thing" in issue["body"] and "verbatim" in issue["body"]
    assert "PR #150" in issue["body"] and issue["labels"] == ["backfilled"]


def test_the_organisation_name_is_redacted_from_titles_and_branches():
    assert tm.redact("claude/remove-care" + "quest-references") == "claude/remove-[org]-references"
    row = tm.manifest_row("B", {"number": 1, "title": "Drop Care" + "Quest mentions", "body": "", "created_at": "2026-01-01T00:00:00Z",
                                "merged_at": "2026-01-01T00:00:00Z", "head": {"ref": "claude/remove-care" + "quest-references"}},
                          {"sha": "abc1234def", "parent_sha": "000", "committed_ts": "2026-01-01T00:00:00Z",
                           "subject": "x", "body": ""}, ["README.md"], None)
    assert "[org]" in row["title_text"] and "[org]" in row["branch_name"]


# --- US3 (#354): tasks.jsonl rows ---------------------------------------------------------------------------

DIFF = (
    "diff --git a/python/health_transformation_lab_nlp/runlog.py b/python/health_transformation_lab_nlp/runlog.py\n"
    "index 1111111..2222222 100644\n"
    "--- a/python/health_transformation_lab_nlp/runlog.py\n"
    "+++ b/python/health_transformation_lab_nlp/runlog.py\n"
    "@@ -1 +1 @@\n-old\n+new\n"
    "diff --git a/python/tests/test_runlog.py b/python/tests/test_runlog.py\n"
    "new file mode 100644\n"
    "index 0000000..3333333\n"
    "--- /dev/null\n"
    "+++ b/python/tests/test_runlog.py\n"
    "@@ -0,0 +1 @@\n+def test_x(): pass\n"
    "diff --git a/docs/runlog.md b/docs/runlog.md\n"
    "index 4444444..5555555 100644\n"
    "--- a/docs/runlog.md\n"
    "+++ b/docs/runlog.md\n"
    "@@ -1 +1 @@\n-a\n+b\n"
)


def test_a_diff_splits_into_patch_and_test_patch_by_python_tests():
    out = tm.split_diff(DIFF)
    assert out["test_files"] == ["python/tests/test_runlog.py"]
    assert out["patch_files"] == ["python/health_transformation_lab_nlp/runlog.py", "docs/runlog.md"]
    assert out["test_patch"].startswith("diff --git a/python/tests/test_runlog.py") and "+def test_x" in out["test_patch"]
    assert "python/tests/" not in out["patch"] and "+new" in out["patch"] and "+b" in out["patch"]
    assert len(out["patch"]) + len(out["test_patch"]) == len(DIFF)
    assert tm.split_diff("") == {"patch": "", "test_patch": "", "patch_files": [], "test_files": []}


def test_base_commit_is_the_merge_base_for_a_merge_and_the_parent_for_a_squash():
    assert tm.diff_range("s" * 40, ["p" * 40], None) == ("p" * 40, "s" * 40, "parent")
    assert tm.diff_range("m" * 40, ["p" * 40, "h" * 40], "b" * 40) == ("b" * 40, "h" * 40, "merge_base")


def test_the_manifest_records_which_base_it_used():
    assert "base_commit_source_code" in tm.MANIFEST_COLUMNS
    commit = {"sha": "abc1234def", "parent_sha": "000", "committed_ts": "t", "subject": "x", "body": ""}
    assert tm.manifest_row("C", None, commit, [], None)["base_commit_source_code"] == "parent"
    merged = {**commit, "base_sha": "bbb", "base_source": "merge_base"}
    row = tm.manifest_row("C", None, merged, [], None)
    assert row["base_commit_sha"] == "bbb" and row["base_commit_source_code"] == "merge_base"


def test_statement_and_hints_come_from_the_tier_source():
    issue = {"title": "Run log lost on the volume", "body": "Appends fail on Volumes.", "created_at": "2026-10-01T00:00:00Z"}
    pr = {"title": "Keep the run log in a table", "body": "Closes #9", "created_at": "2026-10-02T00:00:00Z"}
    a = tm.statement_and_hints("A", issue=issue, pr=pr, review="Verdict: approve")
    assert a["problem_statement"] == "Run log lost on the volume\n\nAppends fail on Volumes."
    assert "Closes #9" in a["hints_text"] and "Verdict: approve" in a["hints_text"]
    assert a["created_at"] == "2026-10-01T00:00:00Z"
    b = tm.statement_and_hints("B", pr=pr, review=None)
    assert b["problem_statement"] == "Keep the run log in a table\n\nCloses #9" and b["hints_text"] == ""
    assert b["created_at"] == "2026-10-02T00:00:00Z"
    c = tm.statement_and_hints("C", commit={"message": "Keep the log (028 US3)\n\nWhy: appends fail.",
                                            "committed_ts": "2026-10-03T00:00:00Z"},
                               story="### US3 - rows (P1)\nFor each candidate...", plan="plan text", tasks="tasks text")
    assert c["problem_statement"].startswith("Keep the log (028 US3)\n\nWhy: appends fail.")
    assert "### US3 - rows" in c["problem_statement"] and "plan text" in c["hints_text"] and "tasks text" in c["hints_text"]
    assert c["created_at"] == "2026-10-03T00:00:00Z"


def test_statement_text_is_redacted_like_the_manifest():
    org = "Care" + "Quest"
    out = tm.statement_and_hints("B", pr={"title": f"Drop {org}", "body": f"{org} gone", "created_at": "x"})
    assert org.lower() not in out["problem_statement"].lower() and "[org]" in out["problem_statement"]


def test_story_section_is_cut_from_the_spec():
    spec = "# Spec\n\n### US1 - one (P1) #1\nfirst\n\n### US2 - two (P1)\nsecond\nmore\n\n## Out of scope\nx\n"
    assert tm.story_ref("Build rows (028 US2)") == ("028", 2)
    assert tm.story_ref("no story") is None
    assert tm.story_section(spec, 2) == "### US2 - two (P1)\nsecond\nmore"
    assert tm.story_section(spec, 7) == ""


def test_task_row_has_exactly_the_competition_fields():
    row = tm.task_row("htlnlp_9", "o/r", "b" * 40, {"problem_statement": "p", "hints_text": "", "created_at": "t"},
                      {"patch": "P", "test_patch": "T"})
    assert list(row) == list(tm.TASK_FIELDS)
    assert row["instance_id"] == "htlnlp_9" and row["repo"] == "o/r" and row["patch"] == "P"


def test_exclusion_reason_names_why_a_candidate_is_not_a_task():
    tests = ["python/tests/test_x.py"]
    assert tm.exclusion_reason(["python/pyproject.toml"], tests) == "fix only in grader-stripped files"
    assert tm.exclusion_reason(["docs/a.md"], tests) == "no non-test code change"
    assert tm.exclusion_reason(["python/health_transformation_lab_nlp/a.py"], []) == "no python/tests change"
    assert tm.exclusion_reason(["python/health_transformation_lab_nlp/a.py"], ["python/tests/test_a.py"]) is None


def test_the_committed_sample_has_the_competition_fields_and_no_organisation_name():
    import json

    from health_transformation_lab_nlp.paths import REPO_ROOT
    sample = REPO_ROOT / "data" / "tasks" / "tasks_sample.jsonl"
    rows = [json.loads(line) for line in sample.read_text().splitlines() if line.strip()]
    assert rows and all(list(r) == list(tm.TASK_FIELDS) for r in rows)
    assert all(tm.redact(json.dumps(r)) == json.dumps(r) for r in rows)
