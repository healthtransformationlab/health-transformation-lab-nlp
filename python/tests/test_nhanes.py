"""Spec 013 G4: NHANES 2009-2014 periodontal exam -> site/tooth tables -> weighted prevalence."""

import numpy as np
import pandas as pd
import pytest

from health_transformation_lab_nlp.nhanes import (
    nhanes_cdc_aap_published,
    sites_from_labels,
    to_site_tables,
    weighted_prevalence,
)

LABELS = {"OHX03PCD": "Pocket depth: upper right 1st molar, distofacial",
          "OHX03PCM": "Pocket depth: upper right 1st molar, midfacial",
          "OHX03PCS": "Pocket depth: upper right 1st molar, mesiofacial",
          "OHX03PCP": "Pocket depth: upper right 1st molar, distolingual",
          "OHX03PCL": "Pocket depth: upper right 1st molar, midlingual",
          "OHX03PCA": "Pocket depth: upper right 1st molar, mesiolingual",
          "OHX03LAD": "Loss of attachment: upper right 1st molar, distofacial"}


def test_site_letters_are_read_from_the_variable_labels():
    m = sites_from_labels(LABELS)
    assert m[("03", "PC", "D")] == "DB" and m[("03", "PC", "M")] == "B" and m[("03", "PC", "S")] == "MB"
    assert m[("03", "PC", "P")] == "DL" and m[("03", "PC", "L")] == "L" and m[("03", "PC", "A")] == "ML"
    assert m[("03", "LA", "D")] == "DB"


def test_unrecognised_label_is_an_error_not_a_guess():
    with pytest.raises(ValueError):
        sites_from_labels({"OHX03PCD": "Pocket depth: upper right 1st molar, somewhere"})


def test_wide_exam_becomes_site_and_tooth_tables():
    per = pd.DataFrame({"SEQN": [1, 2], "OHX03PCD": [3.0, 99.0], "OHX03LAD": [4.0, 99.0]})
    den = pd.DataFrame({"SEQN": [1, 2], "OHX03TC": [2.0, 4.0], "OHX04TC": [5.0, 2.0]})
    sites, teeth = to_site_tables(per, den, {"OHX03PCD": LABELS["OHX03PCD"], "OHX03LAD": LABELS["OHX03LAD"]})
    s = sites.set_index(["SEQN", "tooth", "site"])
    assert s.loc[(1, 3, "DB"), "pd_mm"] == 3.0 and s.loc[(1, 3, "DB"), "cal_mm"] == 4.0
    assert (2, 3, "DB") not in s.index or np.isnan(s.loc[(2, 3, "DB"), "pd_mm"])     # 99 = not assessed
    t = teeth.set_index(["SEQN", "tooth"])
    assert t.loc[(1, 3), "present"] and t.loc[(1, 4), "present"]                        # 2 permanent, 5 root
    assert not t.loc[(2, 3), "present"] and t.loc[(2, 4), "present"]


def test_weighted_prevalence_with_linearized_ci():
    # two strata, two PSUs each; weights make person 1 count double
    d = pd.DataFrame({"y": ["a", "b", "a", "a", "b", "b", "a", "b"],
                      "w": [2, 1, 1, 1, 1, 1, 1, 1], "strata": [1, 1, 1, 1, 2, 2, 2, 2],
                      "psu": [1, 1, 2, 2, 1, 1, 2, 2], "domain": [True] * 8})
    p = weighted_prevalence(d, "y").set_index("category")
    assert p.loc["a", "pct"] == pytest.approx(100 * 5 / 9)
    assert p.loc["a", "ci_low"] < p.loc["a", "pct"] < p.loc["a", "ci_high"]
    assert p["pct"].sum() == pytest.approx(100)


def test_published_targets_are_cited():
    t = nhanes_cdc_aap_published()
    assert set(t["source"]) >= {"Eke et al. 2018 (PMC8094373)", "Tay et al. 2025 (PMC12176459)"}
    assert t.loc[(t.source.str.startswith("Eke")) & (t.category == "total"), "pct"].item() == 42.2


def test_classify_people_end_to_end_on_nhanes_shaped_tables():
    from health_transformation_lab_nlp.nhanes import classify_people
    letters = {"D": "distofacial", "M": "midfacial", "S": "mesiofacial", "P": "distolingual", "L": "midlingual",
               "A": "mesiolingual"}
    teeth = [t for t in range(2, 32) if t not in (16, 17)]
    labels = {f"OHX{t:02d}{m}{x}": f"{'Pocket depth' if m == 'PC' else 'Loss of attachment'}: tooth {t}, {w}"
              for t in teeth for m in ("PC", "LA") for x, w in letters.items()}
    per = pd.DataFrame([{"SEQN": s, "OHDPDSTS": 1, **{v: 2.0 for v in labels}} for s in (1, 2)])
    for t in (3, 8):                                   # person 2: interproximal CAL 6 on two teeth, PD 5
        per.loc[1, f"OHX{t:02d}LAS"] = 6.0
        per.loc[1, f"OHX{t:02d}PCS"] = 5.0
    den = pd.DataFrame([{"SEQN": s, "OHDDESTS": 1, **{f"OHX{t:02d}TC": 2.0 for t in range(1, 33)}} for s in (1, 2, 3)])
    den.loc[2, [c for c in den if c.endswith("TC")]] = 4.0  # person 3: no teeth
    demo = pd.DataFrame({"SEQN": [1, 2, 3], "RIDAGEYR": [40, 55, 70], "WTMEC2YR": [1e4] * 3,
                         "SDMVSTRA": [1, 1, 2], "SDMVPSU": [1, 2, 1]})
    p = classify_people(per, den, demo, labels).set_index("SEQN")
    assert p.loc[1, "cdc_aap"] == "none" and p.loc[1, "aces"] == "periodontitis_stage_1"   # CAL 2 everywhere
    assert p.loc[2, "cdc_aap"] == "severe"
    assert p.loc[2, "aces"] == "periodontitis_stage_3" and p.loc[2, "aces_no_complexity"] == "periodontitis_stage_3_4"
    assert p.loc[3, "edentulous"] and p.loc[3, "aces"] == "edentulous"


def test_no_dentition_exam_is_not_edentulous():
    """OHDDESTS 3 (exam not done) leaves every tooth code blank: that is missing, not zero teeth.
    Counting them doubled edentulous prevalence (16% vs Tay 2025's 6.7%)."""
    from health_transformation_lab_nlp.nhanes import classify_people
    labels = {"OHX03PCD": "Pocket depth: tooth 3, distofacial"}
    per = pd.DataFrame({"SEQN": [9], "OHDPDSTS": [3], "OHX03PCD": [np.nan]})
    tc = {f"OHX{t:02d}TC": np.nan for t in range(1, 33)}
    den = pd.DataFrame([{"SEQN": 9, "OHDDESTS": 3, **tc}, {"SEQN": 10, "OHDDESTS": 1, **tc, "OHX08TC": 4.0}])
    demo = pd.DataFrame({"SEQN": [9, 10], "RIDAGEYR": [60, 60], "WTMEC2YR": [1e4] * 2,
                         "SDMVSTRA": [1, 1], "SDMVPSU": [1, 2]})
    p = classify_people(per, den, demo, labels).set_index("SEQN")
    assert not p.loc[9, "edentulous"]
    assert not p.loc[10, "edentulous"]     # exam done but teeth not all recorded: unknown, not edentulous


def test_dentition_exam_status_is_required():
    from health_transformation_lab_nlp.nhanes import classify_people
    per = pd.DataFrame({"SEQN": [1], "OHDPDSTS": [1], "OHX03PCD": [2.0]})
    den = pd.DataFrame({"SEQN": [1], "OHX03TC": [2.0]})
    demo = pd.DataFrame({"SEQN": [1], "RIDAGEYR": [40], "WTMEC2YR": [1e4], "SDMVSTRA": [1], "SDMVPSU": [1]})
    with pytest.raises(KeyError, match="OHDDESTS"):
        classify_people(per, den, demo, {"OHX03PCD": "Pocket depth: tooth 3, distofacial"})


def test_xpt_names_and_labels_are_text_even_when_pandas_gives_bytes(monkeypatch, tmp_path):
    # NHANES perio job on Databricks, 2026-10-28: its pandas returned the XPORT field names and labels as bytes,
    # and sites_from_labels failed with "cannot use a string pattern on a bytes-like object"
    from health_transformation_lab_nlp import nhanes

    class Reader:
        fields = ({"name": b"OHX02PCD", "label": b"Pocket depth: upper right 2nd molar, distofacial  "},
                  {"name": "SEQN", "label": "Respondent sequence number"})

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return pd.DataFrame({"SEQN": [1.0], "OHX02PCD": [3.0]})

    monkeypatch.setattr(nhanes.pd, "read_sas", lambda *a, **kw: Reader())
    _, labels = nhanes.read_xpt(tmp_path / "OHXPER_J.xpt")
    assert labels == {"OHX02PCD": "Pocket depth: upper right 2nd molar, distofacial",
                      "SEQN": "Respondent sequence number"}
    assert nhanes.sites_from_labels(labels) == {("02", "PC", "D"): "DB"}


def test_sites_are_read_from_the_abbreviations_in_the_real_nhanes_labels():
    # #174: the OHXPER files of 2009-10, 2011-12 and 2013-14 name the site by an abbreviation token, not a word.
    # These are the real labels of tooth 2's six pocket-depth sites (OHXPER_H.xpt, CDC public data).
    labels = {"OHX02PCD": "LOA: Max R(2M) DF FGM-sulcus(mm)", "OHX02PCM": "LOA: Max R(2M) MdF FGM-sulcus(mm)",
              "OHX02PCS": "LOA: Max R(2M) MF FGM-sulcus(mm)", "OHX02PCP": "LOA: Max R(2M) DL FGM-sulcus(mm)",
              "OHX02PCL": "LOA: Max R(2M) MdL FGM-sulcus(mm)", "OHX02PCA": "LOA: Max R(2M) ML FGM-sulcus(mm)",
              "OHX02LAD": "LOA: Max R(2M) DF calculated AL(mm)"}
    assert sites_from_labels(labels) == {
        ("02", "PC", "D"): "DB", ("02", "PC", "M"): "B", ("02", "PC", "S"): "MB",     # DF is inside MdF: whole tokens
        ("02", "PC", "P"): "DL", ("02", "PC", "L"): "L", ("02", "PC", "A"): "ML",
        ("02", "LA", "D"): "DB"}


def test_edentulism_by_age_band_is_weighted_within_each_band():
    """Spec 033 US4 (#500): the share with no natural teeth per age band, in the same domain as adults30_all
    (a complete periodontal exam, or edentulous)."""
    from health_transformation_lab_nlp.nhanes import EDENTULOUS_AGE_BANDS, edentulous_by_age

    people = pd.DataFrame({"RIDAGEYR": [32, 33, 40, 41, 70, 71, 72, 29],
                           "perio_complete": [True, True, True, False, True, False, False, True],
                           "edentulous": [False, True, False, False, False, True, True, True],
                           "w": [1.0, 3.0, 1.0, 1.0, 2.0, 1.0, 1.0, 5.0],
                           "strata": [1, 1, 1, 1, 2, 2, 2, 1], "psu": [1, 2, 1, 2, 1, 2, 1, 2]})
    out = edentulous_by_age(people).set_index("age_band_low_num")
    assert list(out.index) == [low for low, _ in EDENTULOUS_AGE_BANDS]
    assert out.loc[30, "edentulous_pct"] == pytest.approx(75.0)      # weights 1 and 3; the 29-year-old is out
    assert out.loc[35, "edentulous_pct"] == pytest.approx(0.0)       # the 41-year-old has no exam: out
    assert out.loc[35, "n_domain"] == 1
    assert out.loc[65, "edentulous_pct"] == pytest.approx(50.0)
    assert out.loc[30, "age_band_high_num"] == 34 and pd.isna(out.loc[75, "age_band_high_num"])
    assert out.loc[75, "n_domain"] == 0 and pd.isna(out.loc[75, "edentulous_pct"])


def test_missing_teeth_by_age_band_counts_lost_natural_teeth_weighted():
    """Spec 037: how many natural teeth (third molars aside) adults have lost, by age band: the weighted mean and the
    shares with none lost and with six or more lost (all lost included), among people with a dentition exam."""
    from health_transformation_lab_nlp.nhanes import MISSING_AGE_BANDS, missing_teeth_by_age

    teeth = [t for t in range(1, 33) if t not in (1, 16, 17, 32)]
    def person(seqn, missing, status=1):
        row = {"SEQN": seqn, "OHDDESTS": status}
        row.update({f"OHX{t:02d}TC": (4 if i < missing else 2) for i, t in enumerate(teeth)})
        return row
    den = pd.DataFrame([person(1, 0), person(2, 2), person(3, 6), person(4, 28), person(5, 0, status=3),
                        person(6, 1)])
    demo = pd.DataFrame({"SEQN": [1, 2, 3, 4, 5, 6], "RIDAGEYR": [30, 31, 70, 72, 30, 20],
                         "WTMEC2YR": [1.0, 3.0, 1.0, 1.0, 9.0, 9.0], "SDMVSTRA": [1, 1, 2, 2, 1, 1],
                         "SDMVPSU": [1, 2, 1, 2, 1, 2]})
    out = missing_teeth_by_age(den, demo).set_index("age_band_low_num")
    assert list(out.index) == [low for low, _ in MISSING_AGE_BANDS]
    assert out.loc[25, "mean_missing_num"] == pytest.approx((0 * 1 + 2 * 3) / 4)   # no exam (5) and age 20 (6) out
    assert out.loc[25, "none_lost_pct"] == pytest.approx(25.0)
    assert out.loc[25, "six_or_more_pct"] == pytest.approx(0.0)
    assert out.loc[65, "six_or_more_pct"] == pytest.approx(100.0)
    assert out.loc[65, "mean_missing_num"] == pytest.approx(17.0)
    assert out.loc[65, "dentate_mean_missing_num"] == pytest.approx(6.0)        # the edentulous 72-year-old out
    assert out.loc[25, "dentate_none_lost_pct"] == pytest.approx(25.0)
    assert out.loc[25, "n_domain"] == 2
