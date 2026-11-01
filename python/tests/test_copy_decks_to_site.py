"""The website's copies of the decks are made by .github/scripts/copy_decks_to_site.py and pushed by
.github/workflows/copy-decks-to-site.yml whenever a deck or a cover changes on main (issue #374)."""

import importlib.util

import pytest
import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location(
    "copy_decks_to_site", REPO_ROOT / ".github" / "scripts" / "copy_decks_to_site.py")
cd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cd)

WF = REPO_ROOT / ".github" / "workflows" / "copy-decks-to-site.yml"

# What the site adds after <title>, as on the live site copies (2026-11-01)
ICONS = ('<link rel="icon" href="/favicon.ico" sizes="any"><link rel="icon" href="/favicon.svg" type="image/svg+xml">'
         '<link rel="apple-touch-icon" href="/apple-touch-icon.png"><link rel="manifest" href="/site.webmanifest">'
         '<meta name="theme-color" content="#0F2A33">')


def test_the_site_gets_both_decks_and_both_covers():
    assert cd.DECKS == {"docs/edr/deck.html": "perio-bench/index.html",
                        "docs/pitch/deck.html": "oral-health-bench/index.html"}
    assert cd.COVERS == {"docs/img/edr_deck_cover.png": "img/edr_deck_cover.png",
                         "docs/img/pitch_deck_cover.png": "img/pitch_deck_cover.png"}
    for src in (*cd.DECKS, *cd.COVERS):
        assert (REPO_ROOT / src).is_file(), src


@pytest.mark.parametrize("deck", ["docs/edr/deck.html", "docs/pitch/deck.html"])
def test_a_site_copy_is_the_deck_plus_exactly_the_icon_links(deck):
    assert cd.ICON_LINKS == ICONS
    html = (REPO_ROOT / deck).read_text(encoding="utf-8")
    copy = cd.site_copy(html)
    head, tail = html.split("</title>", 1)
    assert copy == head + "</title>" + ICONS + tail
    assert copy.count(ICONS) == 1 and copy.replace(ICONS, "", 1) == html


def test_a_deck_without_a_title_or_already_with_icons_is_refused():
    with pytest.raises(ValueError, match="title"):
        cd.site_copy("<html><head></head></html>")
    with pytest.raises(ValueError, match="icon"):
        cd.site_copy("<title>t</title>" + ICONS)


def test_build_writes_the_copies_and_reports_only_what_changed(tmp_path):
    changed = cd.build(REPO_ROOT, tmp_path)
    assert sorted(changed) == sorted([*cd.DECKS.values(), *cd.COVERS.values()])
    for src, dst in cd.COVERS.items():
        assert (tmp_path / dst).read_bytes() == (REPO_ROOT / src).read_bytes()
    for src, dst in cd.DECKS.items():
        assert (tmp_path / dst).read_bytes() == cd.site_copy((REPO_ROOT / src).read_text(encoding="utf-8")).encode()
    assert cd.build(REPO_ROOT, tmp_path) == []                         # nothing changed, nothing to commit
    (tmp_path / "perio-bench" / "index.html").write_text("stale", encoding="utf-8")
    (tmp_path / "other.html").write_text("the site's own page", encoding="utf-8")
    assert cd.build(REPO_ROOT, tmp_path) == ["perio-bench/index.html"]
    assert (tmp_path / "other.html").read_text(encoding="utf-8") == "the site's own page"


@pytest.mark.parametrize("token, problem", [("", "missing"), ("   ", "missing"), ("ghp_" + "a" * 36, "fine-grained"),
                                            ("github_pat_short", "fine-grained"), ("github_pat_" + "a" * 82 + " x", "fine-grained")])
def test_a_missing_or_malformed_token_fails_naming_it(token, problem):
    with pytest.raises(ValueError) as e:
        cd.check_token_shape(token)
    assert "SITE_PUSH_TOKEN" in str(e.value) and problem in str(e.value)
    assert token.strip() == "" or token not in str(e.value)            # never echo the value


def test_a_fine_grained_token_passes_the_shape_check():
    cd.check_token_shape("github_pat_" + "A1_b" * 20)


def test_the_cli_token_check_exits_non_zero_naming_the_token(monkeypatch, capsys):
    monkeypatch.delenv("SITE_PUSH_TOKEN", raising=False)
    assert cd.main(["check-token"]) == 1
    assert "SITE_PUSH_TOKEN" in capsys.readouterr().out


def _workflow():
    return yaml.safe_load(WF.read_text())


def test_workflow_runs_on_main_when_a_source_changes_and_by_hand():
    on = _workflow()[True]                                              # yaml reads "on" as True
    assert "workflow_dispatch" in on
    assert on["push"]["branches"] == ["main"]
    paths = on["push"]["paths"]
    for src in (*cd.DECKS, *cd.COVERS, ".github/scripts/copy_decks_to_site.py", ".github/workflows/copy-decks-to-site.yml"):
        assert src in paths, src


def test_workflow_checks_the_token_before_any_work_and_commits_only_on_change():
    steps = _workflow()["jobs"]["copy"]["steps"]
    runs = [s.get("run", "") for s in steps]
    check = next(i for i, r in enumerate(runs) if "check-token" in r)
    push_check = next(i for i, r in enumerate(runs) if "push --dry-run" in r)
    build = next(i for i, r in enumerate(runs) if "copy_decks_to_site.py build" in r)
    assert check < push_check < build
    assert "SITE_PUSH_TOKEN" in runs[push_check]                         # the refusal names the token
    text = WF.read_text()
    assert "secrets.SITE_PUSH_TOKEN" in text
    assert "git diff --cached --quiet" in runs[build]                   # commit only when something changed
    assert "${{ github.sha }}" in runs[build] or "GITHUB_SHA" in runs[build]   # names the source commit
    assert "x-access-token:${SITE_PUSH_TOKEN}@" not in text             # the token never lands in .git/config


def test_the_site_token_is_in_the_register():
    reg = yaml.safe_load((REPO_ROOT / "ops" / "secrets_register.yaml").read_text())["credentials"]
    entry = next(c for c in reg if "SITE_PUSH_TOKEN" in c["stored_in"])
    assert "copy-decks-to-site.yml" in entry["used_by"]
    assert "Contents" in entry["scope"] and "healthtransformationlab.github.io" in entry["scope"]
    assert "90 days" in entry["lifetime"]
