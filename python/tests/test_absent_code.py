"""Spec 032 US3 (#442): how the diagnosis-code source reads a visit with no gum-disease code."""

import pandas as pd
import pytest

from health_transformation_lab_nlp import phenotype as ph
from health_transformation_lab_nlp.labels import Status
from health_transformation_lab_nlp.sources import READERS, UNKNOWN, read_proc_dx
from health_transformation_lab_nlp.study import apply_deid, generate_visits, read_methods

PLAN = "D0120 D1110"
CODES = ["", "Z01.20", "K05.10", "K05.00", "K05.311", "K05.322", "K05.313", "K05.3", "K05.6", "Z00.00"]


def test_no_answer_reads_the_code_alone():
    assert ph.ABSENT_CODE_RULES[0] == "no_answer"
    for dx in CODES:
        for plan in ("", PLAN):
            assert ph.read_dx_code(dx, plan, "no_answer") == read_proc_dx(dx)


def test_the_default_reads_a_plan_with_no_gum_disease_code_as_healthy_or_gingivitis():
    # spec 032 US8 (#448): the default since then; the benchmark build keeps no_answer (study.build_study)
    assert ph.DEFAULT_ABSENT_CODE == "healthy_or_gingivitis"
    assert ph.read_dx_code("", PLAN) == "healthy" and ph.read_dx_code("", "") == UNKNOWN


def test_a_plan_with_no_gum_disease_code_reads_as_healthy_standing_for_healthy_or_gingivitis():
    rule = "healthy_or_gingivitis"
    assert ph.ABSENT_CODE_STATUS == Status.HEALTHY.value          # one of the six statuses
    assert ph.read_dx_code("", PLAN, rule) == "healthy"            # a plan, no code
    assert ph.read_dx_code("Z00.00", PLAN, rule) == "healthy"      # a plan, a code that isn't gum disease
    assert ph.read_dx_code("", "", rule) == UNKNOWN                # no plan: still no answer
    assert ph.read_dx_code(None, None, rule) == UNKNOWN
    assert ph.read_dx_code("K05.3", PLAN, rule) == UNKNOWN         # a gum-disease code it can't read stays unread
    for dx in ("Z01.20", "K05.10", "K05.322"):                     # a code it can read is read as before
        assert ph.read_dx_code(dx, PLAN, rule) == read_proc_dx(dx)


def test_an_unknown_rule_fails_at_once():
    with pytest.raises(ValueError, match="absent_code"):
        ph.read_dx_code("", PLAN, "healthy")


def test_the_frame_is_unchanged_under_no_answer_and_both_code_columns_follow_the_rule():
    df = pd.DataFrame({"proc_dx_completed_raw": ["", "K05.10", ""], "proc_dx_planned_raw": ["", "", "K05.322"],
                       "proc_codes_planned_raw": [PLAN, PLAN, ""]})
    for c in ("proc_dx_completed", "proc_dx_planned"):
        df[c] = [read_proc_dx(v) for v in df[c + "_raw"]]
    assert ph.with_absent_code(df, "no_answer").equals(df)
    assert ph.with_absent_code(df).equals(ph.with_absent_code(df, "healthy_or_gingivitis"))   # the default (US8)
    out = ph.with_absent_code(df, "healthy_or_gingivitis")
    assert list(out["proc_dx_completed"]) == ["healthy", "gingivitis", UNKNOWN]
    assert list(out["proc_dx_planned"]) == ["healthy", "healthy", "periodontitis_stage_2"]
    with pytest.raises(ValueError, match="proc_codes_planned_raw"):
        ph.with_absent_code(df.drop(columns="proc_codes_planned_raw"), "healthy_or_gingivitis")


def test_read_methods_takes_the_rule_and_defaults_to_healthy_or_gingivitis():
    df = generate_visits(40, seed=11).rename(columns={c: c + "_raw" for c in READERS})
    df, _ = apply_deid(df)
    plain = read_methods(df, absent_code="no_answer")
    ruled = read_methods(df)                                   # the default since spec 032 US8
    no_code = df["proc_dx_completed_raw"] == ""
    assert no_code.any() and (plain.loc[no_code, "proc_dx_completed"] == UNKNOWN).all()
    assert (ruled.loc[no_code, "proc_dx_completed"] == "healthy").all()    # every synthetic visit has a plan
    assert ruled.loc[~no_code, "proc_dx_completed"].equals(plain.loc[~no_code, "proc_dx_completed"])
