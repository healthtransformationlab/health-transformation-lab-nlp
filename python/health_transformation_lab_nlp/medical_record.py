"""A synthetic medical record for each synthetic person (spec 023 US1, #198).

Every value here is synthetic. The record stands in for the medical side of linked medical and dental records, after
Patel et al. 2026 (docs/references.md, item 53), whose data is real and never comes into this repo; only rates and
links from published sources are used, each cited below.

- **Conditions** (`CONDITIONS`): each is drawn given the person's periodontal status and age band only. The base rate
  for the age band applies to people outside the exposed statuses; in the exposed statuses the odds are multiplied by
  the cited odds ratio. So the age-adjusted (Mantel-Haenszel) odds ratio is the cited one by construction. The links
  are associations built into the generator, not causes, and the generator never changes a chart or a label to fit a
  condition: it reads them and nothing else reads it.
- **Diabetes** is not drawn: it is the generator's own HbA1c >= 6.5, as `study.py` decides, so the two never
  disagree. HbA1c stays in the visits (`hba1c`); it is not repeated here.
- **Blood pressure** follows the hypertension flag and the NCHS definition (140/90 or on medication), with the share
  of people with hypertension whose blood pressure is controlled by age band.
- **ASA physical-status class** (I to IV) follows from the conditions, smoking and control, using the ASA
  definitions' adult examples.

The record uses its own random stream (`random.Random(f"{seed}:medical")`), drawn after the study's draws, and goes
to its own file, so every existing dataset stays byte-identical (FR-001).

Respiratory, haematologic and endocrine conditions other than diabetes are named in Patel et al. 2026 as
contributing. Respiratory disease is here as COPD (cited rate and link). Haematologic and other endocrine conditions
are left out: the plan admits them only with a checked rate and link source, and none has been checked yet.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import pandas as pd

from .telemetry import traced

PERIODONTITIS = frozenset({"periodontitis_stage_1", "periodontitis_stage_2", "periodontitis_stage_3",
                           "periodontitis_stage_4"})
STAGE_2_TO_4 = frozenset({"periodontitis_stage_2", "periodontitis_stage_3", "periodontitis_stage_4"})

DIABETES_HBA1C = 6.5          # the generator's threshold (study.py): HbA1c >= 6.5 is diabetes
UNCONTROLLED_HBA1C = 7.0      # the generator's split (synthetic.DIABETES_EXTRA): >= 7.0 uncontrolled
OR_TOLERANCE_LOG = 0.25       # a recovered age-adjusted odds ratio is within this of the cited one, on the log
#                              scale, on 10,000 people (about 3 standard errors for the rarest condition)


@dataclass(frozen=True)
class Condition:
    column: str
    label: str
    base_rates: tuple[tuple[int, int | None, float], ...]   # (lowest age, highest age or None, rate) by age band
    rate_source: str
    odds_ratio: float                                         # in the exposed statuses, against the rest
    exposed_statuses: frozenset[str]
    odds_ratio_source: str


CONDITIONS: tuple[Condition, ...] = (
    Condition(
        "is_hypertension", "hypertension",
        ((18, 39, 0.075), (40, 59, 0.332), (60, None, 0.631)),
        "Fryar CD, Ostchega Y, Hales CM, Zhang G, Kruszon-Moran D. Hypertension prevalence and control among "
        "adults: United States, 2015-2016. NCHS Data Brief No. 289, October 2017 (key findings: 7.5% at 18-39, "
        "33.2% at 40-59, 63.1% at 60 and over)",
        1.22, STAGE_2_TO_4,
        "Muñoz Aguilera E, Suvan J, Buti J, et al. Periodontitis is associated with hypertension: a systematic "
        "review and meta-analysis. Cardiovasc Res 2020;116(1):28-39, PMID 31549149 (abstract: moderate-severe "
        "periodontitis OR 1.22, 95% CI 1.10-1.35; moderate-severe taken here as stages II-IV)"),
    Condition(
        "is_ckd", "chronic kidney disease",
        ((18, 44, 0.06), (45, 64, 0.13), (65, None, 0.34)),
        "CDC. Chronic Kidney Disease in the United States, 2026 (NHANES August 2021-August 2023: 6% at 18-44, "
        "13% at 45-64, 34% at 65 and over)",
        1.60, PERIODONTITIS,
        "Kapellas K, Singh A, Bertotti M, Nascimento GG, Jamieson LM. Periodontal and chronic kidney disease "
        "association: a systematic review and meta-analysis. Nephrology (Carlton) 2019;24(2):202-212, "
        "doi:10.1111/nep.13225 (abstract: pooled OR 1.60, 95% CI 1.44-1.79, for CKD with periodontitis)"),
    Condition(
        "is_cvd", "cardiovascular disease",
        ((18, 44, 0.009), (45, 64, 0.059), (65, None, 0.182)),
        "NCHS. QuickStats: percentage of adults aged >=18 years with diagnosed heart disease, by urbanization level "
        "and age group, National Health Interview Survey, United States, 2020. MMWR 2022;71(23) (0.9% at 18-44, "
        "5.9% at 45-64, 18.2% at 65 and over)",
        1.19, PERIODONTITIS,
        "Janket SJ, Baird AE, Chuang SK, Jones JA. Meta-analysis of periodontal disease and risk of coronary heart "
        "disease and stroke. Oral Surg Oral Med Oral Pathol Oral Radiol Endod 2003;95(5):559-569, PMID 12738947 "
        "(abstract: summary RR 1.19, 95% CI 1.08-1.32; the relative risk is used here as an odds ratio, which "
        "understates the odds ratio a little where heart disease is common)"),
    Condition(
        "is_copd", "chronic obstructive pulmonary disease (respiratory)",
        ((18, 24, 0.004), (25, 44, 0.014), (45, 54, 0.029), (55, 64, 0.074), (65, 74, 0.089), (75, None, 0.105)),
        "Weeks JD, Elgaddal N. Chronic obstructive pulmonary disease in adults age 18 and older: United States, "
        "2023. NCHS Data Brief No. 529, May 2025 (Figure 1: 0.4% at 18-24, 1.4% at 25-44, 2.9% at 45-54, 7.4% at "
        "55-64, 8.9% at 65-74, 10.5% at 75 and over)",
        2.08, PERIODONTITIS,
        "Zeng XT, Tu ML, Liu DY, Zheng D, Zhang J, Leng W. Periodontal disease and risk of chronic obstructive "
        "pulmonary disease: a meta-analysis of observational studies. PLoS One 2012;7(10):e46508, "
        "doi:10.1371/journal.pone.0046508 (pooled OR 2.08, 95% CI 1.48-2.91)"),
)

_DB289 = ("Fryar CD, et al. NCHS Data Brief No. 289, October 2017: hypertension is systolic >= 140 mmHg or diastolic "
          ">= 90 mmHg or taking medication; controlled is < 140 and < 90 among people with hypertension")
# Each blood-pressure draw is uniform, in whole mmHg, within the band the NCHS definition sets. The band's outer
# ends (lowest normal, highest raised reading) are a repo choice of plausible readings, not a sourced number.
MEASURES = {
    "normal": {"systolic_bp_mmhg": (100, 139), "diastolic_bp_mmhg": (60, 89), "source": _DB289},
    "controlled": {"systolic_bp_mmhg": (110, 139), "diastolic_bp_mmhg": (65, 89), "source": _DB289},
    "raised": {"systolic_bp_mmhg": (140, 179), "diastolic_bp_mmhg": (80, 109), "source": _DB289},
}
HYPERTENSION_CONTROL = {
    "by_age": ((18, 39, 0.325), (40, 59, 0.508), (60, None, 0.494)),
    "source": "Fryar CD, et al. NCHS Data Brief No. 289, October 2017 (controlled hypertension among adults with "
              "hypertension: 32.5% at 18-39, 50.8% at 40-59, 49.4% at 60 and over)",
}
ASA_SOURCE = ("American Society of Anesthesiologists. ASA Physical Status Classification System (approved 2014, "
              "last amended 13 December 2020): I a normal healthy patient; II mild systemic disease (adult examples: "
              "current smoker, well-controlled diabetes or hypertension, mild lung disease); III severe systemic "
              "disease (poorly controlled diabetes or hypertension, COPD, history of myocardial infarction or "
              "coronary artery disease more than 3 months ago); IV severe systemic disease that is a constant threat "
              "to life. Repo choices, not the ASA's: chronic kidney disease counts as II (the ASA's kidney example, "
              "end-stage disease on dialysis, is not modelled), diabetes is poorly controlled at HbA1c >= 7.0, and "
              "three or more class III findings stand in for class IV")

COLUMNS = ["person_id", "is_diabetes", *[c.column for c in CONDITIONS], "systolic_bp_mmhg", "diastolic_bp_mmhg",
           "asa_class_code", "is_synthetic"]


def _band_rate(bands, age: int) -> float:
    for lo, hi, rate in bands:
        if age >= lo and (hi is None or age <= hi):
            return rate
    raise ValueError(f"age {age} is outside every declared age band")


@traced
def condition_probability(condition: Condition, age: int, status: str) -> float:
    """The chance of the condition for this age and periodontal status: the band's base rate, its odds multiplied by
    the cited odds ratio in the exposed statuses."""
    p = _band_rate(condition.base_rates, age)
    if status not in condition.exposed_statuses:
        return p
    odds = condition.odds_ratio * p / (1 - p)
    return odds / (1 + odds)


@traced
def asa_class(record: dict, cigarettes_per_day: int, hba1c: float | None) -> str:
    """ASA physical-status class from the record (ASA_SOURCE gives the definitions and the repo's choices)."""
    raised = record["systolic_bp_mmhg"] >= 140 or record["diastolic_bp_mmhg"] >= 90
    poor_dm = record["is_diabetes"] and hba1c is not None and hba1c >= UNCONTROLLED_HBA1C
    severe = sum([poor_dm, record["is_hypertension"] and raised, record["is_copd"], record["is_cvd"]])
    if severe >= 3:
        return "IV"
    if severe:
        return "III"
    if record["is_diabetes"] or record["is_hypertension"] or record["is_ckd"] or cigarettes_per_day > 0:
        return "II"
    return "I"


@traced
def draw_medical_record(person_id: int, age: int, status: str, cigarettes_per_day: int, hba1c: float | None,
                        rng: random.Random) -> dict:
    """One synthetic person's medical record. Draws in a fixed order: each condition, then blood pressure."""
    rec: dict = {"person_id": int(person_id),
                 "is_diabetes": bool(hba1c is not None and hba1c >= DIABETES_HBA1C)}
    for c in CONDITIONS:
        rec[c.column] = rng.random() < condition_probability(c, age, status)
    if not rec["is_hypertension"]:
        band = "normal"
    else:
        band = "controlled" if rng.random() < _band_rate(HYPERTENSION_CONTROL["by_age"], age) else "raised"
    m = MEASURES[band]
    rec["systolic_bp_mmhg"] = rng.randint(*m["systolic_bp_mmhg"])
    rec["diastolic_bp_mmhg"] = rng.randint(*m["diastolic_bp_mmhg"])
    rec["asa_class_code"] = asa_class(rec, int(cigarettes_per_day), hba1c)
    rec["is_synthetic"] = True
    return rec


@traced
def people_from_visits(visits: pd.DataFrame) -> pd.DataFrame:
    """One row per person from their latest visit: age, periodontal status, smoking and HbA1c then.

    The latest visit is the one the chart-review set uses, and the status the generator keeps (once periodontitis,
    the highest stage reached)."""
    cols = ["person_id", "age", "truth_status", "cigarettes_per_day", "hba1c"]
    last = visits.sort_values(["person_id", "visit_date"]).groupby("person_id").tail(1)
    return last[cols].reset_index(drop=True)


@traced
def medical_records(people: pd.DataFrame, seed: int) -> pd.DataFrame:
    """The synthetic medical record, one row per person, from its own random stream."""
    rng = random.Random(f"{seed}:medical")
    rows = [draw_medical_record(r.person_id, int(r.age), r.truth_status, int(r.cigarettes_per_day),
                                None if pd.isna(r.hba1c) else float(r.hba1c), rng)
            for r in people.sort_values("person_id").itertuples()]
    return pd.DataFrame(rows, columns=COLUMNS)
