"""Stand-in perio charts and patient attributes until the custom Synthea perio
module exists.

Synthea's built-in dental module gives people and recall visits but no chart
numerics. Until synthea/modules/dental_periodontal_exam.json is written, this
draws a plausible chart per (person, visit) from a latent severity, nudged by
age, plus the patient factors the 2017 classification uses for grade
(smoking, diabetes) and the extent of involvement.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .labels import LABELS, PerioChart, Status, label_chart
from .telemetry import traced

# Latent severity mix for US adults, roughly shaped on NHANES 2009-2014
# (about 4 in 10 adults 30+ with some periodontitis, most mild/moderate).
# Plausible, not a prevalence estimate.
_SEVERITY_WEIGHTS = {"healthy": 0.30, "gingivitis": 0.28, "mild": 0.18,
                     "moderate": 0.15, "severe": 0.07, "advanced": 0.02}


@dataclass(frozen=True)
class RiskFactors:
    cigarettes_per_day: int      # 0 = non-smoker
    hba1c: float | None          # None = not measured; >= 6.5 diabetes, 5.8-6.4 pre-diabetes


DIABETES_HBA1C = 6.5     # HbA1c (%) at which a synthetic person has diabetes, the NHANES laboratory cut-off
# Of the people with an HbA1c on record, the share at or above 6.5: half are drawn from 5.8-6.9 (rounded to 0.1, so
# 6.45 and up count) and half from 7.0-10.5.
DIABETES_OF_HBA1C = 0.5 + 0.5 * (6.9 - 6.45) / (6.9 - 5.8)


@traced
def draw_risk(rng: random.Random, light_smoker_share: float = 0.10, heavy_smoker_share: float = 0.08,
              hba1c_share: float = 0.12) -> RiskFactors:
    """Cigarettes a day (1-9 for a light smoker, 10-30 for a heavy one) and HbA1c (None for not on record).

    The defaults are the study's SYNTHETIC placeholders, kept because its benchmark notes were scored by external
    model runs (spec 033 US3); `risk_kwargs` gives the arguments for published shares (spec 033 US2)."""
    weights = [round(1 - light_smoker_share - heavy_smoker_share, 12), light_smoker_share, heavy_smoker_share]
    smoke = rng.choices([0, rng.randint(1, 9), rng.randint(10, 30)], weights=weights)[0]
    hba1c = rng.choice([round(rng.uniform(5.8, 6.9), 1), round(rng.uniform(7.0, 10.5), 1)]) \
        if rng.random() < hba1c_share else None
    return RiskFactors(smoke, hba1c)


@traced
def risk_kwargs(smoking_share: float, heavy_smoking_fraction: float, diabetes_share: float) -> dict[str, float]:
    """`draw_risk`'s arguments for a share of smokers (of whom a fraction smoke 10 or more a day) and a share with
    diabetes (HbA1c >= DIABETES_HBA1C). Fails at once on a share no draw can reach."""
    if not 0 <= smoking_share <= 1 or not 0 <= heavy_smoking_fraction <= 1:
        raise ValueError(f"smoking_share and heavy_smoking_fraction must be in [0, 1], got {smoking_share}, "
                         f"{heavy_smoking_fraction}")
    hba1c_share = diabetes_share / DIABETES_OF_HBA1C
    if not 0 <= hba1c_share <= 1:
        raise ValueError(f"diabetes_share must be in [0, {DIABETES_OF_HBA1C:.3f}], got {diabetes_share}")
    heavy = smoking_share * heavy_smoking_fraction
    return {"light_smoker_share": smoking_share - heavy, "heavy_smoker_share": heavy, "hba1c_share": hba1c_share}


@traced
def draw_chart(age: int, rng: random.Random, case_mix: float = 0.0) -> PerioChart:
    """case_mix > 0 moves weight from healthy toward moderate/severe disease
    (a clinic with sicker patients); < 0 the other way. Range about -0.1..0.1."""
    w = dict(_SEVERITY_WEIGHTS)
    if age >= 50:  # shift mass toward disease with age
        w["healthy"] -= 0.10
        w["moderate"] += 0.06
        w["severe"] += 0.04
    w["healthy"] -= case_mix
    w["moderate"] += 0.6 * case_mix
    w["severe"] += 0.4 * case_mix
    w = {k: max(v, 0.005) for k, v in w.items()}
    sev = rng.choices(list(w), weights=list(w.values()))[0]
    u = rng.uniform
    if sev == "healthy":
        return PerioChart(u(1, 3), u(0, 9), 0, 0)
    if sev == "gingivitis":
        return PerioChart(u(2, 4), u(10, 45), u(0, 0.9), u(0, 10))
    if sev == "mild":
        return PerioChart(u(3, 4), u(10, 40), u(1, 2), u(0, 14))   # stage I: max PD <= 4 (AAP)
    if sev == "moderate":
        return PerioChart(u(4, 5.5), u(15, 50), u(3, 4), u(15, 33))
    if sev == "severe":
        return PerioChart(u(6, 8), u(25, 70), u(5, 8), u(34, 60), rng.randint(0, 4))
    return PerioChart(u(6, 10), u(30, 80), u(5, 10), u(40, 80), rng.randint(5, 10))


@traced
def draw_pct_teeth_involved(chart: PerioChart, rng: random.Random) -> float:
    """Share of teeth with attachment loss; drives extent (localized < 30%)."""
    if chart.max_cal_mm < 1:
        return 0.0
    return round(rng.uniform(5, 29) if rng.random() < 0.5 else rng.uniform(30, 90), 0)


# ---------------------------------------------------------------- histories (spec 005)
# Planning placeholders, not estimates: CAL gain per year for a periodontitis
# patient, raised by the risk factors the AAP grade uses.
BASE_CAL_MM_PER_YEAR = (0.05, 0.25)
SMOKER_EXTRA = {"light": 0.10, "heavy": 0.30}      # < 10 / >= 10 cigarettes a day
DIABETES_EXTRA = {"controlled": 0.10, "uncontrolled": 0.30}   # HbA1c < 7.0 / >= 7.0
ONSET_PER_VISIT = 0.03          # healthy/gingivitis -> early periodontitis
TREAT_PROB = 0.6                # periodontitis visit -> scaling and root planing
TREATED_RATE_FACTOR = 0.4       # progression after treatment


@dataclass(frozen=True)
class HistoryVisit:
    chart: PerioChart
    status: Status          # truth: the stage reached is kept (see draw_history)
    treated_before: bool    # periodontal therapy at an earlier visit


@traced
def cal_rate_per_year(risk: RiskFactors, rng: random.Random) -> float:
    r = rng.uniform(*BASE_CAL_MM_PER_YEAR)
    if risk.cigarettes_per_day >= 10:
        r += SMOKER_EXTRA["heavy"]
    elif risk.cigarettes_per_day > 0:
        r += SMOKER_EXTRA["light"]
    if risk.hba1c is not None and risk.hba1c >= 6.5:      # diabetes; 5.8-6.4 is pre-diabetes
        r += DIABETES_EXTRA["uncontrolled" if risk.hba1c >= 7.0 else "controlled"]
    return r


@traced
def draw_history(age: int, n_visits: int, risk: RiskFactors, rng: random.Random,
                 case_mix: float = 0.0, months_between: float = 6.0) -> list[HistoryVisit]:
    """One patient's charts over recall visits.

    - Attachment loss, bone loss and teeth lost never decrease.
    - Periodontitis progresses at a rate set by smoking and diabetes; therapy slows it
      and lowers probing depth and bleeding.
    - Healthy and gingivitis patients can flip between the two, or develop early periodontitis.
    - Truth status: once periodontitis, always periodontitis, and the stage reached is
      kept even when pockets shrink after therapy (repo assumption; see
      docs/action_items.md).
    """
    c = draw_chart(age, rng, case_mix)
    pd_, bop, cal, rbl, lost = c.max_probing_depth_mm, c.bop_pct, c.max_cal_mm, c.rbl_pct, c.teeth_lost_perio
    rate = cal_rate_per_year(risk, rng)
    treated, best = False, None
    out = []
    step = months_between / 12
    for k in range(n_visits):
        if k:
            if cal >= 1:
                gain = rate * step * (TREATED_RATE_FACTOR if treated else 1.0) * rng.uniform(0.5, 1.5)
                cal = min(cal + gain, 12.0)
                rbl = min(rbl + gain * rng.uniform(4, 8), 95.0)
                pd_ = max(pd_ + (gain if not treated else -rng.uniform(0, 0.3)), min(pd_, 2.0))
                bop = min(max(bop + rng.uniform(-10, 10), 0), 100)
                if cal >= 6 and rng.random() < 0.05:
                    lost += 1
            elif rng.random() < ONSET_PER_VISIT:
                cal, rbl = rng.uniform(1.0, 1.8), max(rbl, rng.uniform(5, 12))
                bop = max(bop, rng.uniform(15, 40))
            else:   # healthy <-> gingivitis
                if bop < 10 and rng.random() < 0.15:
                    bop = rng.uniform(10, 35)
                elif bop >= 10 and rng.random() < 0.30:
                    bop = rng.uniform(0, 9)
        chart = PerioChart(round(pd_, 1), round(bop, 1), round(cal, 2), round(rbl, 1), lost)
        status = label_chart(chart)
        if best is not None and best.is_periodontitis and LABELS.index(best.value) > LABELS.index(status.value):
            status = best
        best = status if best is None or LABELS.index(status.value) > LABELS.index(best.value) \
            or not status.is_periodontitis else best
        out.append(HistoryVisit(chart, status, treated))
        if status.is_periodontitis and not treated and rng.random() < TREAT_PROB:
            treated = True   # therapy at this visit: pockets and bleeding drop by the next one
            pd_ = max(pd_ - rng.uniform(0.5, 1.5), min(pd_, 2.0))
            bop = bop * rng.uniform(0.3, 0.6)
    return out
