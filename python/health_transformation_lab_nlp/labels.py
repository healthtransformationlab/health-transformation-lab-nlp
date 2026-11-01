"""Periodontal status, stage, grade and extent from a perio chart.

Follows the AAP "Staging and Grading Periodontitis" worksheet (2017 AAP/EFP
classification; Tonetti, Greenwell & Kornman 2018):
https://www.perio.org/wp-content/uploads/2019/08/Staging-and-Grading-Periodontitis.pdf
Rules as implemented, with what is and isn't modeled: docs/staging_grading.md.

STAGE
  Not periodontitis   no interdental CAL (CAL < 1 mm, or no RBL when CAL isn't
                      charted) and no tooth lost to perio. BOP >= 10% gingivitis,
                      else healthy.
  1. Initial stage from interdental CAL at the site of greatest loss
       I 1-2 mm, II 3-4 mm, III/IV >= 5 mm.
     If CAL is not available, from RBL: I < 15%, II 15-33%, III/IV > 33%
     (beyond the coronal third).
  2. Tooth loss due to periodontitis: none for I/II; 1-4 teeth -> at least III;
     >= 5 teeth -> IV.
  3. Complexity factors shift the stage up, never down:
       PD > 4 mm                                    -> at least II  (stage I: max PD <= 4)
       PD >= 6 mm, vertical bone loss >= 3 mm,
       furcation class II/III                       -> at least III
       at stage III: need for complex rehabilitation
       (mobility >= degree 2, < 20 remaining teeth,
       masticatory dysfunction, bite collapse,
       drifting/flaring, severe ridge defect)       -> IV

GRADE (only for periodontitis)
  Start at B. Direct evidence (RBL or CAL loss over 5 years) if available:
  none A, < 2 mm B, >= 2 mm C. Otherwise indirect: % bone loss / age
  < 0.25 A, 0.25-1.0 B, > 1.0 C. Modifiers raise the grade: smoking < 10/day
  at least B, >= 10/day C; diabetes with HbA1c < 7.0% at least B, >= 7.0% C.

EXTENT  localized < 30% of teeth, generalized >= 30%, or molar/incisor pattern.

This is the GROUND TRUTH for the synthetic data: the chart produces both the
label (here) and the note, so the benchmark asks whether a model can recover
from the text what the chart already knew.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .telemetry import traced


class Status(str, Enum):
    HEALTHY = "healthy"
    GINGIVITIS = "gingivitis"
    P1 = "periodontitis_stage_1"
    P2 = "periodontitis_stage_2"
    P3 = "periodontitis_stage_3"
    P4 = "periodontitis_stage_4"

    @property
    @traced
    def is_periodontitis(self) -> bool:
        return self.value.startswith("periodontitis")


LABELS: list[str] = [s.value for s in Status]


@dataclass(frozen=True)
class PerioChart:
    max_probing_depth_mm: float
    bop_pct: float
    max_cal_mm: float | None          # interdental CAL, worst site; None = not charted
    rbl_pct: float | None             # radiographic bone loss, worst site; None = no radiograph
    teeth_lost_perio: int = 0
    # complexity factors (0 / None = not present or not recorded)
    vertical_defect_mm: float = 0.0
    furcation_class: int = 0
    mobility_degree: int = 0
    remaining_teeth: int | None = None
    complex_rehab: bool = False       # masticatory dysfunction, bite collapse, drifting/flaring, severe ridge defect

    def __post_init__(self) -> None:
        if self.max_cal_mm is None and self.rbl_pct is None:
            raise ValueError("need CAL or RBL to stage")
        if not 0 <= self.bop_pct <= 100:
            raise ValueError(f"bop_pct out of range: {self.bop_pct}")
        if self.rbl_pct is not None and not 0 <= self.rbl_pct <= 100:
            raise ValueError(f"rbl_pct out of range: {self.rbl_pct}")
        if (self.max_cal_mm or 0) < 0 or self.max_probing_depth_mm < 0 or self.teeth_lost_perio < 0:
            raise ValueError("negative chart value")


@traced
def stage_by_cal(cal: float) -> int:
    return 1 if cal <= 2.0 else 2 if cal <= 4.0 else 3


@traced
def stage_by_rbl(rbl: float) -> int:
    return 1 if rbl < 15.0 else 2 if rbl <= 33.0 else 3


@traced
def label_chart(chart: PerioChart) -> Status:
    """Map one perio chart to a status following the AAP worksheet (module docstring)."""
    cal, rbl, lost = chart.max_cal_mm, chart.rbl_pct, chart.teeth_lost_perio
    no_loss = (cal < 1.0) if cal is not None else (rbl <= 0.0)
    if no_loss and lost == 0:
        return Status.GINGIVITIS if chart.bop_pct >= 10.0 else Status.HEALTHY

    # 1. initial stage: CAL first, RBL only when CAL isn't available
    stage = stage_by_cal(cal) if cal is not None else stage_by_rbl(rbl)
    # 2. tooth loss due to periodontitis
    if lost >= 5:
        stage = 4
    elif lost > 0:
        stage = max(stage, 3)
    # 3. complexity shifts up, never down
    pd = chart.max_probing_depth_mm
    if pd > 4.0:
        stage = max(stage, 2)
    if pd >= 6.0 or chart.vertical_defect_mm >= 3.0 or chart.furcation_class >= 2:
        stage = max(stage, 3)
    if stage == 3 and (chart.complex_rehab or chart.mobility_degree >= 2
                       or (chart.remaining_teeth is not None and chart.remaining_teeth < 20)):
        stage = 4
    return {1: Status.P1, 2: Status.P2, 3: Status.P3, 4: Status.P4}[stage]


@traced
def grade_of(status: Status, rbl_pct: float | None, age: int, cigarettes_per_day: int = 0,
             hba1c: float | None = None, diabetes: bool | None = None,
             loss_5yr_mm: float | None = None) -> str:
    """Grade per the AAP worksheet. 'NA' when not periodontitis.

    hba1c is the HbA1c of a patient with diabetes; `diabetes` defaults to
    "an HbA1c is recorded" (the generator records one only for diabetes).
    Pass diabetes=False for a normoglycemic patient whose HbA1c was measured."""
    if not status.is_periodontitis:
        return "NA"
    if loss_5yr_mm is not None:                       # direct evidence first
        grade = "A" if loss_5yr_mm <= 0 else "B" if loss_5yr_mm < 2.0 else "C"
    elif rbl_pct is not None and age:                 # indirect: % bone loss / age
        ratio = rbl_pct / age
        grade = "A" if ratio < 0.25 else "B" if ratio <= 1.0 else "C"
    else:
        grade = "B"                                   # default: assume B
    diabetic = (hba1c is not None) if diabetes is None else diabetes
    if cigarettes_per_day >= 10 or (diabetic and hba1c is not None and hba1c >= 7.0):
        return "C"
    if (cigarettes_per_day > 0 or diabetic) and grade == "A":
        return "B"
    return grade


@traced
def extent_of(status: Status, pct_teeth_involved: float, molar_incisor: bool = False) -> str:
    """Localized < 30% of teeth, generalized >= 30%, or molar/incisor pattern. 'NA' if not periodontitis."""
    if not status.is_periodontitis:
        return "NA"
    if molar_incisor:
        return "molar_incisor"
    return "generalized" if pct_teeth_involved >= 30 else "localized"


@traced
def label_row(row) -> str:
    """pandas apply helper: row with the perio_chart view's column names."""
    def opt(x):
        return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)   # NaN = not charted

    chart = PerioChart(
        max_probing_depth_mm=float(row["max_probing_depth_mm"]),
        bop_pct=float(row["bop_pct"]),
        max_cal_mm=opt(row["max_cal_mm"]),
        rbl_pct=opt(row["rbl_pct"]),
        teeth_lost_perio=int(row.get("teeth_lost_perio", 0) or 0),
    )
    return label_chart(chart).value


# Spec 029 US3 (#371): teeth lost to periodontitis, counted four ways, decide stage III vs IV (>= 5 teeth -> IV).
# A missing tooth seldom says why it was lost; `expected_perio_loss` counts the recorded periodontal losses plus the
# model's probability for each missing tooth with no recorded reason (specs/029-tooth-loss/analysis_plan.md, s. 10).
# R twin: r/R/16_spec029.R.
STAGE4_COUNT_RULES = ("recorded_only", "every_missing", "expected_perio_loss", "truth")
STAGE4_TEETH = 5


@traced
def expected_perio_loss(recorded_perio: int, unlabelled_probs) -> float:
    """Recorded periodontal losses plus the sum of P(lost to periodontitis) over the unlabelled missing teeth."""
    return float(recorded_perio) + float(sum(float(p) for p in unlabelled_probs))


@traced
def stage4_rule(rule: str, recorded_perio: int, missing: int, unlabelled_probs=(), true_perio: int | None = None
                ) -> bool:
    """Stage IV by tooth loss under one counting rule (STAGE4_COUNT_RULES): the count is 5 teeth or more.
    recorded_only: extractions with a periodontal diagnosis; every_missing: every missing tooth; expected_perio_loss:
    recorded plus the model's probabilities; truth: the synthetic answer key (never available on real records)."""
    if rule not in STAGE4_COUNT_RULES:
        raise ValueError(f"unknown stage IV counting rule {rule!r}; one of {STAGE4_COUNT_RULES}")
    if rule == "truth" and true_perio is None:
        raise ValueError("the truth rule needs true_perio")
    count = {"recorded_only": lambda: recorded_perio, "every_missing": lambda: missing,
             "expected_perio_loss": lambda: expected_perio_loss(recorded_perio, unlabelled_probs),
             "truth": lambda: true_perio}[rule]()
    return bool(count >= STAGE4_TEETH)
