"""Spec 024 US2: the PerioDx Extractor (Patel et al. 2022): status, stage, extent and grade from a note by keyword,
in two steps (keep the note if it mentions a periodontal diagnosis term; read extent, stage and grade by stemming
and string similarity). Negation off by default, as published; a switch turns it on.

Every snippet is synthetic, written in the forms the repo's note templates use (clinical_notes.py, dx_patterns.py)."""

import pytest

from health_transformation_lab_nlp import periodx as px


def read(text, **kw):
    f = px.note_status(text, **kw)
    return f.status, f.stage, f.extent, f.grade


def test_acceptance_1_full_2017_diagnosis():
    assert read("Generalized periodontitis Stage III Grade B") == (px.PERIODONTITIS, 3, "generalized", "B")
    assert px.note_status("Generalized periodontitis Stage III Grade B").section == "M2"


def test_acceptance_2_missed_negation_is_the_published_behaviour_and_the_switch_fixes_it():
    note = "no evidence of bone loss, gingivitis localized"
    off = px.note_status(note)
    assert off.status == px.PERIODONTITIS and off.stage is None and off.label == "unknown"
    on = px.note_status(note, negation=True)
    assert (on.status, on.extent, on.label) == (px.LOCALIZED_GINGIVITIS, "localized", "gingivitis")


@pytest.mark.parametrize("note", ["Pt here for recall. Prophy, OHI given. RTC 6 mo.",
                                  "CC: no c/o\nperio charting done.\nNV: recall 6 mo", ""])
def test_acceptance_3_no_periodontal_terms_is_no_diagnosis_not_healthy(note):
    f = px.note_status(note)
    assert (f.status, f.label) == (px.NO_DIAGNOSIS, "unknown")


@pytest.mark.parametrize("note, expected", [
    ("d: localized stage ii grade b periodontitis.", (px.PERIODONTITIS, 2, "localized", "B")),
    ("Dx: Gen. perio St III Gr B", (px.PERIODONTITIS, 3, "generalized", "B")),
    ("Perio IIIB, gen.", (px.PERIODONTITIS, 3, "generalized", "B")),
    ("Stage II/Grade B perio.", (px.PERIODONTITIS, 2, px.NOT_ASSESSABLE, "B")),
    ("st. 2 perio", (px.PERIODONTITIS, 2, px.NOT_ASSESSABLE, px.NOT_ASSESSABLE)),
    ("d- stage iv grade iii periodontitis, generalized", (px.PERIODONTITIS, 4, "generalized", "C")),
    ("Localized Stage 1 Grade A", (px.PERIODONTITIS, 1, "localized", "A")),
    ("d: generalzied periodontitis stage 3 grade c", (px.PERIODONTITIS, 3, "generalized", "C")),
    ("d: locallized periodontitis stage i grade a.", (px.PERIODONTITIS, 1, "localized", "A")),
    ("Generalized moderate chronic periodontitis.", (px.PERIODONTITIS, 2, "generalized", px.NOT_ASSESSABLE)),
    ("Localized slight chronic periodontitis.", (px.PERIODONTITIS, 1, "localized", px.NOT_ASSESSABLE)),
])
def test_stage_grade_and_extent_in_the_forms_and_abbreviations_the_notes_use(note, expected):
    assert read(note) == expected


@pytest.mark.parametrize("note, status", [
    ("Diagnosis: Clinical Gingival Health on an Intact Periodontium", px.HEALTH),
    ("Perio health.", px.HEALTH),
    ("Periodontium WNL.", px.HEALTH),
    ("d: generalized plaque induced gingivitis", px.GENERALIZED_GINGIVITIS),
    ("Dental biofilm-induced gingivitis, localized.", px.LOCALIZED_GINGIVITIS),
    ("Gingivitis.", px.GINGIVITIS),
    ("dx: ging", px.GINGIVITIS),
])
def test_health_and_gingivitis(note, status):
    assert px.note_status(note).status == status


def test_findings_that_only_look_healthy_are_not_health():
    assert px.note_status("PD 1-3mm WNL; FMX: crestal bone WNL").status == px.NO_DIAGNOSIS


def test_perio_alone_is_not_a_diagnosis():
    assert px.note_status("pt here for perio eval. perio charting done. perio consult").status == px.NO_DIAGNOSIS


def test_the_most_severe_current_diagnosis_wins_and_copied_forward_text_is_left_out():
    note = ("Dx: localized periodontitis stage II grade B. Hx gingivitis.\n\n-- copied from visit 01/02/2023 --\n"
            "Dx at that visit: Stage III periodontitis.")
    assert read(note)[:2] == (px.PERIODONTITIS, 2)
    assert read(note, multiple="most_severe")[:2] == (px.PERIODONTITIS, 3)


def test_two_stages_in_the_current_text_take_the_higher():
    assert read("stage 2 grade b periodontitis, previously stage 3")[1] == 3


def test_negation_switch_only_drops_terms_inside_a_negated_window():
    note = "no bleeding on probing, not stage 3. Generalized periodontitis stage II grade B"
    assert read(note)[1] == 3                      # negation off: "not stage 3" is read as stage 3
    assert read(note, negation=True)[:2] == (px.PERIODONTITIS, 2)


def test_negation_off_by_default():
    assert px.NEGATION_DEFAULT is False


def test_unknown_multiple_rule_is_refused():
    with pytest.raises(ValueError):
        px.note_status("gingivitis", multiple="latest")


def test_term_table_lists_its_source_for_every_term():
    assert {"term", "field", "value", "source"} <= set(px.PERIODX_TERMS[0]._fields)
    for t in px.PERIODX_TERMS:
        assert t.source in px.TERM_SOURCES, t
    assert any(t.source == "synthetic notes" for t in px.PERIODX_TERMS)     # the repo's abbreviations


def test_stemmer_and_similarity():
    assert px.stem("generalized") == px.stem("generalised") == "general"
    assert px.similar("generlized", "generalized") and not px.similar("gingival", "gingivitis")
    assert not px.similar("periodontium", "periodontitis")
