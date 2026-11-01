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
