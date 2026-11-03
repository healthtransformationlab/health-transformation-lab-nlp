"""Spec 033 US2 (#485): the smoking and diabetes shares are settings of synthetic.draw_risk and open_dental.Params.
draw_risk's defaults stay the old placeholders; the Open Dental extract (US2) and the study build (US3, #486) take the
published US figures (docs/synthetic_data.md; docs/references.md items 72 and 73). Every number is SYNTHETIC."""

import math
import random

import pytest

from health_transformation_lab_nlp import open_dental as od
from health_transformation_lab_nlp import synthetic
from health_transformation_lab_nlp.synthetic import RiskFactors, draw_risk

N = 200_000


def _old_draw_risk(rng: random.Random) -> RiskFactors:
    """draw_risk as it was before spec 033, copied here so the defaults can be held to it."""
    smoke = rng.choices([0, rng.randint(1, 9), rng.randint(10, 30)], weights=[0.82, 0.10, 0.08])[0]
    hba1c = rng.choice([round(rng.uniform(5.8, 6.9), 1), round(rng.uniform(7.0, 10.5), 1)]) \
        if rng.random() < 0.12 else None
    return RiskFactors(smoke, hba1c)


def _within(observed: float, share: float, n: int = N, z: float = 4.0) -> bool:
    return abs(observed - share) <= z * math.sqrt(share * (1 - share) / n)


def _shares(risks):
    n = len(risks)
    return (sum(r.cigarettes_per_day > 0 for r in risks) / n,
            sum(r.cigarettes_per_day >= 10 for r in risks) / n,
            sum(r.hba1c is not None and r.hba1c >= synthetic.DIABETES_HBA1C for r in risks) / n)


def test_the_defaults_draw_exactly_what_draw_risk_drew_before():
    a, b = random.Random(42), random.Random(42)
    assert [draw_risk(a) for _ in range(20_000)] == [_old_draw_risk(b) for _ in range(20_000)]
    assert a.random() == b.random()                       # and leave the stream in the same place


def test_the_defaults_are_the_old_shares():
    rng = random.Random(1)
    smokers, heavy, diabetes = _shares([draw_risk(rng) for _ in range(N)])
    assert _within(smokers, 0.18) and _within(heavy, 0.08)
    assert _within(diabetes, 0.12 * synthetic.DIABETES_OF_HBA1C)


@pytest.mark.parametrize("smoking, heavy_fraction, diabetes", [(0.116, 0.44, 0.158), (0.30, 0.5, 0.05)])
def test_the_shares_are_recovered_on_a_large_seeded_draw(smoking, heavy_fraction, diabetes):
    kw = synthetic.risk_kwargs(smoking, heavy_fraction, diabetes)
    rng = random.Random(7)
    smokers, heavy, dm = _shares([draw_risk(rng, **kw) for _ in range(N)])
    assert _within(smokers, smoking)
    assert _within(heavy, smoking * heavy_fraction)
    assert _within(dm, diabetes)


def test_risk_kwargs_round_trips_the_old_defaults():
    kw = synthetic.risk_kwargs(0.18, 0.08 / 0.18, 0.12 * synthetic.DIABETES_OF_HBA1C)
    assert kw["light_smoker_share"] == pytest.approx(0.10)
    assert kw["heavy_smoker_share"] == pytest.approx(0.08)
    assert kw["hba1c_share"] == pytest.approx(0.12)


def test_risk_kwargs_rejects_impossible_shares():
    with pytest.raises(ValueError, match="smoking_share"):
        synthetic.risk_kwargs(1.2, 0.4, 0.1)
    with pytest.raises(ValueError, match="diabetes_share"):
        synthetic.risk_kwargs(0.1, 0.4, 0.9)            # needs more than everyone to have an HbA1c


def test_the_extract_takes_the_published_us_shares():
    p = od.Params()
    assert p.smoking_share == 0.116       # US adults 2022, NHIS (references item 72)
    assert p.diabetes_share == 0.158      # US adults 20+, NHANES 2021-2023, HbA1c >= 6.5 (item 73)
    assert 0 < p.heavy_smoking_fraction < 1


def test_the_extract_draws_its_patients_at_those_shares():
    p = od.Params(n_patients=4000)
    tables, _ = od.build(p, seed=5)
    pat = tables["patient"]
    smokes = pat["smokingsnomed"].isin(["449868002", "428041000124106"]).mean()
    t2 = tables["diseasedef"].loc[tables["diseasedef"]["diseasename"] == "Type 2 diabetes mellitus", "diseasedefnum"]
    dm = tables["disease"]["diseasedefnum"].isin(t2).sum() / len(pat)
    assert _within(smokes, p.smoking_share, n=len(pat))
    assert _within(dm, p.diabetes_share, n=len(pat))


def test_the_norm_follows_the_extracts_shares():
    p = od.Params()
    rng = random.Random("an independent check")
    kw = od.risk_kwargs(p)
    ratios = [od.entry_other_rate_ratio(draw_risk(rng, **kw), p) for _ in range(20000)]
    assert od.entry_other_rate_norm(p) == pytest.approx(sum(ratios) / len(ratios), abs=0.01)
    more = od.Params(smoking_share=0.4)
    assert od.entry_other_rate_norm(more) > od.entry_other_rate_norm(p)
