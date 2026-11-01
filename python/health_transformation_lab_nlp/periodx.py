"""PerioDx, the phenotype method of Patel et al. 2022 (spec 024).

Patel JS, Brandon R, Tellez M, Albandar JM, Rao R, Krois J, Wu H. Developing automated computer algorithms to
phenotype periodontal disease diagnoses in electronic dental records. Methods Inf Med 2022;61(S2):e125-e133,
doi:10.1055/s-0042-1757880, CC BY-NC-ND 4.0 (docs/references.md item 4).

The paper finds periodontal status in a dental record from three sections, in order: the structured diagnosis
(M1), the PerioDx Extractor on the clinical notes (M2), and the PerioDx Diagnoser on the periodontal chart (M3).
"PerioDx Diagnoser" is the paper's name for its chart rule tree; here it identifies status in a synthetic chart,
nothing more.

    chart_status(chart, age, ...)   the Diagnoser: Fig. 2 as drawn, top to bottom
    chart_from_summary(...)         the repo's summary chart (worst-site values) as the figure's inputs
    note_status(note, negation=False)   the Extractor: keyword reading of a note, two steps, as the paper describes

Every threshold is a named constant citing "Patel et al. 2022, Fig. 2" (FR-002). Where the figure's arrows leave
a step open, the step is a named parameter whose default is the reading spec 024 records. A missing input uses
the parameter's documented fallback (absent, or "no"), and the finding lists it in `partial`.

Synthetic data only. The paper's data (one dental school, under its IRB) is not public and never comes here.
r/R/14_spec024.R is the base-R twin; r/tests/test_parity.R checks it.
"""

from __future__ import annotations

import difflib
import functools
import math
import re
from dataclasses import dataclass, field
from typing import NamedTuple

from .telemetry import traced

# ---------------------------------------------------------------- Fig. 2 thresholds
BOP_LOCALIZED_PCT = 10.0       # Patel et al. 2022, Fig. 2: BOP < 10% health; 10-30% localized gingivitis
BOP_GENERALIZED_PCT = 30.0     # Patel et al. 2022, Fig. 2: BOP > 30% generalized gingivitis
DETECTABLE_BL_PCT = 0.0        # Patel et al. 2022, Fig. 2 "detectable marginal bone loss": any recorded loss > 0%
ENTRY_CAL_MM = 2.0             # Patel et al. 2022, Fig. 2: interproximal CAL > 2 mm ...
ENTRY_TEETH = 2                # Patel et al. 2022, Fig. 2: ... at 2+ non-adjacent teeth (also the recession question)
RECESSION_CAL_MM = 2.0         # Patel et al. 2022, Fig. 2: buccal/lingual recession with CAL > 2 mm ...
RECESSION_PD_MM = 3.0          # Patel et al. 2022, Fig. 2: ... and PD > 3 mm
POCKET_PD_MM = 4.0             # Patel et al. 2022, Fig. 2: "any PD >= 4 mm"
MIDDLE_THIRD_BL_PCT = 33.0     # Patel et al. 2022, Fig. 2: bone loss into the middle third (> 33%)
III_IV_CAL_MM = 5.0            # Patel et al. 2022, Fig. 2: CAL >= 5 mm at 2+ adjacent teeth
ADJACENT_TEETH = 2             # Patel et al. 2022, Fig. 2: "2+ adjacent teeth"
FURCATION_CLASS_MIN = 2        # Patel et al. 2022, Fig. 2: furcation class II/III
VERTICAL_BL_MM = 3.0           # Patel et al. 2022, Fig. 2: vertical bone loss >= 3 mm
III_IV_PD_MM = 5.0             # Patel et al. 2022, Fig. 2: PD > 5 mm at 2+ adjacent teeth
OCCLUDING_PAIRS_MIN = 10       # Patel et al. 2022, Fig. 2: fewer than 10 occluding pairs gives stage IV
TRAUMA_MOBILITY_DEGREE = 2     # Patel et al. 2022, Fig. 2: secondary occlusal trauma, mobility degree >= 2 ...
TRAUMA_TEETH_MIN = 5           # Patel et al. 2022, Fig. 2: ... at >= 5 teeth gives stage IV
TOOTH_LOSS_IV = 5              # Patel et al. 2022, Fig. 2: 1-4 teeth lost to perio stage III, 5 or more stage IV
STAGE_II_BL_PCT = 15.0         # Patel et al. 2022, Fig. 2: BL < 15% stage I, 15-33% stage II
STAGE_II_PD_MM = 5.0           # Patel et al. 2022, Fig. 2: PD 4 mm stage I, PD 5 mm stage II
STAGE_II_CAL_MM = 3.0          # Patel et al. 2022, Fig. 2: CAL 1-2 mm stage I, CAL 3-4 mm stage II
EXTENT_GENERALIZED_PCT = 30.0  # Patel et al. 2022, Fig. 2: < 30% of teeth localized, >= 30% generalized
GRADE_A_RATIO = 0.25           # Patel et al. 2022, Fig. 2: % bone loss / age < 0.25 ...
GRADE_C_RATIO = 1.0            # Patel et al. 2022, Fig. 2: ... 0.25-1.0, > 1.0 grade C
HEAVY_SMOKER_PER_DAY = 10      # Patel et al. 2022, Fig. 2: ">= 10 per day" gives grade C
HBA1C_C_PCT = 7.0              # Patel et al. 2022, Fig. 2: "HbA1c >= 7.0" gives grade C

# ---------------------------------------------------------------- readings of open arrows (spec 024 defaults)
III_IV_NO_TOOTH_LOSS = 3       # Patel et al. 2022, Fig. 2 dead end: a III/IV case with no complexity factor and no
#                                tooth lost reaches the bone-loss box, which has no branch for BL > 33%. Stage III:
#                                the criteria placed it at III or IV and nothing pointed to IV (spec 024 US1).
STAGE_I_II_HIGHER = True       # Patel et al. 2022, Fig. 2 bone-loss box: a chart meeting stage I and stage II
#                                measures at once goes to the higher stage (spec 024 US1); a measure beyond the
#                                stage II band (a single 6 mm pocket) meets "at least stage II" the same way.
GRADE_MID_ENTRY = "per_day"    # Patel et al. 2022, Fig. 2: from 0.25 to 1.0 the arrow enters at ">= 10 per day",
#                                so the grade is C or B, never A (spec 024 US1).
# Bands are contiguous: "1-2 mm" is 1 <= x < 3, "3-4 mm" is 3 <= x < 5, "PD = 4" is 4 <= x < 5.

# ---------------------------------------------------------------- fallbacks for a missing input
# Not charted means absent: no teeth meet the count, no furcation, no vertical defect, no mobility, no complexity
# factor; occluding pairs not counted means 10 or more (nothing pointed to IV); no HbA1c in the HbA1c box means no.
OCCLUDING_PAIRS_UNKNOWN = OCCLUDING_PAIRS_MIN

FIG2_CONSTANTS = ("BOP_LOCALIZED_PCT", "BOP_GENERALIZED_PCT", "DETECTABLE_BL_PCT", "ENTRY_CAL_MM", "ENTRY_TEETH",
                  "RECESSION_CAL_MM", "RECESSION_PD_MM", "POCKET_PD_MM", "MIDDLE_THIRD_BL_PCT", "III_IV_CAL_MM",
                  "ADJACENT_TEETH", "FURCATION_CLASS_MIN", "VERTICAL_BL_MM", "III_IV_PD_MM", "OCCLUDING_PAIRS_MIN",
                  "TRAUMA_MOBILITY_DEGREE", "TRAUMA_TEETH_MIN", "TOOTH_LOSS_IV", "STAGE_II_BL_PCT",
                  "STAGE_II_PD_MM", "STAGE_II_CAL_MM", "EXTENT_GENERALIZED_PCT", "GRADE_A_RATIO", "GRADE_C_RATIO",
                  "HEAVY_SMOKER_PER_DAY", "HBA1C_C_PCT", "III_IV_NO_TOOTH_LOSS", "STAGE_I_II_HIGHER",
                  "GRADE_MID_ENTRY")

# Bone loss recorded as the paper's form categories: (low, high) in percent (spec 024 edge cases).
BL_BANDS = {"<15": (0.0, 15.0), "15-33": (15.0, 33.0), ">33": (33.0, 100.0)}

# ---------------------------------------------------------------- the figure's status boxes
HEALTH = "periodontal_health"
REDUCED_HEALTHY = "reduced_healthy_periodontium"
GINGIVAL_INFLAMMATION = "gingival_inflammation_past_periodontitis"
LOCALIZED_GINGIVITIS = "localized_gingivitis"
GENERALIZED_GINGIVITIS = "generalized_gingivitis"
PERIODONTITIS = "periodontitis"
GINGIVITIS = "gingivitis"            # the Extractor, when the note gives no extent
NO_DIAGNOSIS = "no_diagnosis"        # the Extractor, when the note names no periodontal diagnosis
NOT_ASSESSABLE = "not_assessable"
UNKNOWN = "unknown"
# The figure's boxes in the six labels the benchmark scores. A reduced periodontium that is healthy, or inflamed,
# is periodontal health or gingivitis on a reduced periodontium in the 2017 classification (Chapple et al. 2018).
STATUS_TO_LABEL = {HEALTH: "healthy", REDUCED_HEALTHY: "healthy", GINGIVAL_INFLAMMATION: "gingivitis",
                   LOCALIZED_GINGIVITIS: "gingivitis", GENERALIZED_GINGIVITIS: "gingivitis", GINGIVITIS: "gingivitis"}

TEETH_FULL = 28   # the summary chart's dentition: 28 teeth, third molars left out (this repo's assumption)


@dataclass(frozen=True)
class PerioDxChart:
    """The inputs Fig. 2 asks about. None = not charted (the fallback applies and the finding is partial).

    bone_loss_pct is a percentage or one of the form's categories in BL_BANDS. Tooth counts are the number of
    teeth meeting the figure's test; pct_teeth_involved is the share of teeth lost to periodontitis or meeting
    the case's stage pairs (see tooth_involved), used for extent."""
    bop_pct: float
    max_pd_mm: float
    bone_loss_pct: float | str | None = None
    max_cal_mm: float | None = None
    interproximal_cal_teeth: int | None = None   # non-adjacent teeth with interproximal CAL > 2 mm
    recession_teeth: int | None = None           # teeth with buccal/lingual recession, CAL > 2 mm and PD > 3 mm
    cal5_adjacent_teeth: int | None = None       # adjacent teeth with CAL >= 5 mm
    pd5_adjacent_teeth: int | None = None        # adjacent teeth with PD > 5 mm
    furcation_class: int | None = None
    vertical_bone_loss_mm: float | None = None
    occluding_pairs: int | None = None
    mobility2_teeth: int | None = None           # teeth with mobility degree >= 2 (secondary occlusal trauma)
    complex_rehab: bool | None = None            # drifting, bite collapse, flaring or a severe ridge defect
    teeth_lost_perio: int = 0
    pct_teeth_involved: float | None = None
    molar_incisor: bool = False

    def __post_init__(self) -> None:
        if isinstance(self.bone_loss_pct, str) and self.bone_loss_pct not in BL_BANDS:
            raise ValueError(f"bone loss category {self.bone_loss_pct!r} is not one of {sorted(BL_BANDS)}")
        if not 0 <= self.bop_pct <= 100:
            raise ValueError(f"bop_pct out of range: {self.bop_pct}")


@dataclass(frozen=True)
class PerioDxFinding:
    """What PerioDx found: the figure's status box, stage I-IV, extent, grade, the section that decided (M1, M2,
    M3), and the inputs that used a fallback."""
    status: str
    stage: int | None = None
    extent: str = "NA"
    grade: str = "NA"
    section: str = "M3"
    partial: tuple[str, ...] = field(default=())

    @property
    @traced
    def label(self) -> str:
        """The six-label status the benchmark scores, or 'unknown' (periodontitis with no stage, no status)."""
        if self.status == PERIODONTITIS:
            return f"periodontitis_stage_{self.stage}" if self.stage else UNKNOWN
        return STATUS_TO_LABEL.get(self.status, UNKNOWN)


def _bl_range(bl: float | str) -> tuple[float, float]:
    return BL_BANDS[bl] if isinstance(bl, str) else (float(bl), float(bl))


def _count(c: PerioDxChart, name: str, used: list[str]) -> int:
    v = getattr(c, name)
    if v is None:
        used.append(name)
        return 0
    return int(v)


@traced
def tooth_involved(stage: int, cal_mm: float, pd_mm: float) -> bool:
    """Is a tooth involved at the case's stage? Patel et al. 2022, Fig. 2, extent box:
    III/IV: CAL >= 5 and PD >= 4, or CAL 3-4 and PD >= 6; II: CAL 3-4 and PD 4-5, or CAL 1-2 and PD >= 5;
    I: CAL 1-2 and PD = 4 (bands contiguous, as above)."""
    cal12, cal34 = 1.0 <= cal_mm < 3.0, 3.0 <= cal_mm < 5.0
    if stage >= 3:
        return (cal_mm >= 5.0 and pd_mm >= 4.0) or (cal34 and pd_mm >= 6.0)
    if stage == 2:
        return (cal34 and 4.0 <= pd_mm < 6.0) or (cal12 and pd_mm >= 5.0)
    return cal12 and 4.0 <= pd_mm < 5.0


@traced
def pct_teeth_involved(stage: int, teeth: list[tuple[float, float]], teeth_lost_perio: int = 0) -> float:
    """Share (0-100) of teeth lost to periodontitis or involved at the stage; teeth = (CAL, PD) per present tooth."""
    n = len(teeth) + teeth_lost_perio
    return 100.0 * (teeth_lost_perio + sum(tooth_involved(stage, c, p) for c, p in teeth)) / n if n else float("nan")


def _entry(c: PerioDxChart, used: list[str]) -> bool:
    """The three entry questions; True if any is yes."""
    if c.bone_loss_pct is None:
        bl = False
    else:
        bl = isinstance(c.bone_loss_pct, str) or float(c.bone_loss_pct) > DETECTABLE_BL_PCT
    if bl:
        return True
    if c.interproximal_cal_teeth is not None and c.interproximal_cal_teeth >= ENTRY_TEETH:
        return True
    if c.recession_teeth is not None and c.recession_teeth >= ENTRY_TEETH:
        return True
    used += [n for n in ("bone_loss_pct", "interproximal_cal_teeth", "recession_teeth") if getattr(c, n) is None]
    return False


def _severe(c: PerioDxChart, used: list[str]) -> bool:
    """The four stage III/IV criteria, in the figure's order."""
    bl = c.bone_loss_pct
    tests = {"bone_loss_pct": None if bl is None else (bl == ">33" if isinstance(bl, str)
                                                         else float(bl) > MIDDLE_THIRD_BL_PCT),
             "cal5_adjacent_teeth": None if c.cal5_adjacent_teeth is None else c.cal5_adjacent_teeth >= ADJACENT_TEETH,
             "furcation_class": None if c.furcation_class is None else c.furcation_class >= FURCATION_CLASS_MIN,
             "vertical_bone_loss_mm": (None if c.vertical_bone_loss_mm is None
                                       else c.vertical_bone_loss_mm >= VERTICAL_BL_MM),
             "pd5_adjacent_teeth": None if c.pd5_adjacent_teeth is None else c.pd5_adjacent_teeth >= ADJACENT_TEETH}
    if any(v for v in tests.values()):
        return True
    used += [n for n, v in tests.items() if v is None]
    return False


def _stage(c: PerioDxChart, used: list[str]) -> int:
    severe = _severe(c, used)
    if severe:
        pairs = c.occluding_pairs
        if pairs is None:
            used.append("occluding_pairs")
            pairs = OCCLUDING_PAIRS_UNKNOWN
        if pairs < OCCLUDING_PAIRS_MIN:
            return 4
        if _count(c, "mobility2_teeth", used) >= TRAUMA_TEETH_MIN:
            return 4
        if c.complex_rehab is None:
            used.append("complex_rehab")
        elif c.complex_rehab:
            return 4
    lost = c.teeth_lost_perio                                  # every path passes the tooth-loss box
    if lost >= TOOTH_LOSS_IV:
        return 4
    if lost >= 1:
        return 3
    if severe:
        return III_IV_NO_TOOTH_LOSS
    bl = c.bone_loss_pct
    if bl is None:
        used.append("bone_loss_pct")
        bl_ii = False
    else:
        bl_ii = bl in ("15-33", ">33") if isinstance(bl, str) else float(bl) >= STAGE_II_BL_PCT
    if c.max_cal_mm is None:
        used.append("max_cal_mm")
    cal_ii = c.max_cal_mm is not None and c.max_cal_mm >= STAGE_II_CAL_MM
    return 2 if (bl_ii or c.max_pd_mm >= STAGE_II_PD_MM or cal_ii) else 1


def _extent(c: PerioDxChart, used: list[str]) -> str:
    if c.molar_incisor:
        return "molar_incisor"
    if c.pct_teeth_involved is None:
        used.append("pct_teeth_involved")
        return NOT_ASSESSABLE
    return "generalized" if c.pct_teeth_involved >= EXTENT_GENERALIZED_PCT else "localized"


def _ratio_band(r: float) -> str:
    return "low" if r < GRADE_A_RATIO else "mid" if r <= GRADE_C_RATIO else "high"


def _grade(c: PerioDxChart, age: float | None, cigarettes_per_day: float | None, diabetes: bool | None,
           hba1c: float | None, used: list[str]) -> str:
    if c.bone_loss_pct is None or not age:
        used.append("bone_loss_pct" if c.bone_loss_pct is None else "age")
        return NOT_ASSESSABLE
    lo, hi = _bl_range(c.bone_loss_pct)
    band = _ratio_band(lo / age)
    if _ratio_band(hi / age) != band:                     # a category spanning two ratio bands
        used.append("bone_loss_pct")
        return NOT_ASSESSABLE
    if band == "high":
        return "C"
    if cigarettes_per_day is None:
        used.append("cigarettes_per_day")
        cigarettes_per_day = 0
    if diabetes is None:
        used.append("diabetes")
        diabetes = False
    to_hba1c = band == "low" and cigarettes_per_day <= 0 and diabetes
    if band == "low" and cigarettes_per_day <= 0 and not diabetes:
        return "A"
    if not to_hba1c and cigarettes_per_day >= HEAVY_SMOKER_PER_DAY:   # the ">= 10 per day" box
        return "C"
    if hba1c is None:                                     # the "HbA1c >= 7.0" box
        if diabetes:
            used.append("hba1c")
        return "B"
    return "C" if hba1c >= HBA1C_C_PCT else "B"


@traced
def chart_status(chart: PerioDxChart, age: float | None = None, cigarettes_per_day: float | None = 0,
                 diabetes: bool | None = False, hba1c: float | None = None) -> PerioDxFinding:
    """The PerioDx Diagnoser: Patel et al. 2022, Fig. 2, from the chart to status, stage, extent and grade."""
    c, used = chart, []
    if not _entry(c, used):
        if c.bop_pct < BOP_LOCALIZED_PCT:
            status = HEALTH
        elif c.bop_pct <= BOP_GENERALIZED_PCT:
            status = LOCALIZED_GINGIVITIS
        else:
            status = GENERALIZED_GINGIVITIS
        return PerioDxFinding(status, section="M3", partial=tuple(used))
    if c.max_pd_mm < POCKET_PD_MM:
        status = REDUCED_HEALTHY if c.bop_pct < BOP_LOCALIZED_PCT else GINGIVAL_INFLAMMATION
        return PerioDxFinding(status, section="M3", partial=tuple(used))
    stage = _stage(c, used)
    extent = _extent(c, used)
    grade = _grade(c, age, cigarettes_per_day, diabetes, hba1c, used)
    return PerioDxFinding(PERIODONTITIS, stage, extent, grade, "M3", tuple(dict.fromkeys(used)))


@traced
def chart_from_summary(max_pd_mm: float, bop_pct: float, max_cal_mm: float | None, rbl_pct: float | None,
                       teeth_lost_perio: int, pct_teeth_involved: float | None) -> PerioDxChart:
    """The repo's summary chart (worst-site PD, CAL and bone loss, BOP, teeth lost, share of teeth with attachment
    loss) as the figure's inputs. This repo's reading, since the summary has no tooth-level sites:

    - the teeth with attachment loss are round(share x teeth present), teeth present = 28 - teeth lost;
    - a worst-site measure past a threshold is taken to hold at all of them, adjacent or not as the test needs;
    - recession, furcation, vertical defects, occluding pairs, mobility and complexity factors are not in the
      summary: None, so the figure's fallback applies and the finding says so;
    - the extent share is (teeth with attachment loss + teeth lost) / 28."""
    lost = int(teeth_lost_perio)
    n = None if pct_teeth_involved is None else math.floor(pct_teeth_involved / 100.0 * (TEETH_FULL - lost) + 0.5)

    def at(ok: bool) -> int | None:
        return None if n is None else (n if ok else 0)

    return PerioDxChart(
        bop_pct=float(bop_pct), max_pd_mm=float(max_pd_mm),
        bone_loss_pct=None if rbl_pct is None else float(rbl_pct),
        max_cal_mm=None if max_cal_mm is None else float(max_cal_mm),
        interproximal_cal_teeth=None if max_cal_mm is None else at(max_cal_mm > ENTRY_CAL_MM),
        cal5_adjacent_teeth=None if max_cal_mm is None else at(max_cal_mm >= III_IV_CAL_MM),
        pd5_adjacent_teeth=at(max_pd_mm > III_IV_PD_MM),
        teeth_lost_perio=lost,
        pct_teeth_involved=None if n is None else 100.0 * (n + lost) / TEETH_FULL)


def _opt(x) -> float | None:
    return None if x is None or (isinstance(x, float) and math.isnan(x)) else float(x)


@traced
def chart_from_row(row) -> PerioDxChart | None:
    """A visits_structured.csv row (rec_* columns) as the figure's inputs; None when the visit wasn't charted."""
    pd_, bop = _opt(row.get("rec_max_probing_depth_mm")), _opt(row.get("rec_bop_pct"))
    if not bool(row.get("charted", True)) or pd_ is None or bop is None:
        return None
    return chart_from_summary(pd_, bop, _opt(row.get("rec_max_cal_mm")), _opt(row.get("rec_rbl_pct")),
                              int(_opt(row.get("rec_teeth_lost_perio")) or 0), _opt(row.get("rec_pct_teeth_involved")))


# ================================================================ the PerioDx Extractor (notes)
# Patel et al. 2022, Methods: a two-step keyword program. (1) Normalize the note (case, special characters, stop
# words) and keep it only if it mentions a periodontal diagnosis, from a bag of the 2017 classification's extent,
# stage, grade and severity terms. (2) Read extent, stage and grade with stemming and string similarity against
# that word list. The paper used gensim word vectors for similarity; here difflib's ratio at SIMILARITY stands in,
# so no new dependency (spec 024 plan). Negation is off by default, as published: the paper names missed negation
# ("not the presence of bone loss") and abbreviations ("ging", "st. 2 perio") as its error sources.


class Term(NamedTuple):
    term: str      # normalized words
    field: str     # disease | extent | severity | stage_cue | grade_cue
    value: str     # what the term means in that field
    source: str    # one of TERM_SOURCES


TERM_SOURCES = {
    "2017 classification": "Tonetti, Greenwell & Kornman 2018; Chapple et al. 2018 (health and gingivitis terms)",
    "1999 classification": "Armitage 1999: severity of chronic periodontitis, read as the paper's severity terms",
    "Patel et al. 2022": "terms the paper's own error analysis shows the program reading ('bone loss')",
    "synthetic notes": "abbreviations the repo's synthetic note templates write (clinical_notes.py, dx_patterns.py)",
}
# The word list (FR-003): 2017 classification terms and the repo's synthetic abbreviations, never real notes.
PERIODX_TERMS = (
    Term("periodontitis", "disease", PERIODONTITIS, "2017 classification"),
    Term("gingivitis", "disease", GINGIVITIS, "2017 classification"),
    Term("periodontal health", "disease", HEALTH, "2017 classification"),
    Term("gingival health", "disease", HEALTH, "2017 classification"),
    Term("bone loss", "disease", PERIODONTITIS, "Patel et al. 2022"),
    Term("ging", "disease", GINGIVITIS, "synthetic notes"),
    Term("perio health", "disease", HEALTH, "synthetic notes"),
    Term("periodontium wnl", "disease", HEALTH, "synthetic notes"),
    Term("perio wnl", "disease", HEALTH, "synthetic notes"),
    Term("generalized", "extent", "generalized", "2017 classification"),
    Term("localized", "extent", "localized", "2017 classification"),
    Term("molar incisor", "extent", "molar_incisor", "2017 classification"),
    Term("gen", "extent", "generalized", "synthetic notes"),
    Term("loc", "extent", "localized", "synthetic notes"),
    Term("stage", "stage_cue", "", "2017 classification"),
    Term("st", "stage_cue", "", "synthetic notes"),
    Term("perio", "stage_cue", "", "synthetic notes"),
    Term("grade", "grade_cue", "", "2017 classification"),
    Term("gr", "grade_cue", "", "synthetic notes"),
    Term("slight", "severity", "1", "1999 classification"),
    Term("mild", "severity", "1", "1999 classification"),
    Term("moderate", "severity", "2", "1999 classification"),
    Term("severe", "severity", "3", "1999 classification"),
    Term("advanced", "severity", "3", "1999 classification"),
)
STOP_WORDS = frozenset(["a", "an", "the", "of", "on", "in", "at", "to", "for", "with", "and", "or", "is", "was", "are", "be", "by", "as", "from", "this", "that", "pt"])
NEGATION_CUES = frozenset(["no", "not", "without", "denies", "negative", "absent", "absence", "free"])   # minimal NegEx-style list
NEGATION_WINDOW = 5            # a cue negates the next 5 words of its clause
NEGATION_DEFAULT = False       # as published
SIMILARITY = 0.85              # difflib ratio for a word of 5+ letters to match a term; shorter words match exactly
SEVERITY_WINDOW = 3            # a severity word counts when "periodontitis" follows within 3 words
MULTIPLE_RULES = ("most_severe_current", "most_severe")
MULTIPLE_DEFAULT = "most_severe_current"   # spec 024 edge case: several diagnoses, the most severe current one
_ROMAN = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "1": 1, "2": 2, "3": 3, "4": 4}
_GRADE = {"a": "A", "b": "B", "c": "C", "i": "A", "ii": "B", "iii": "C"}
_NUMERAL = re.compile(r"^(iv|iii|ii|i|[1-4])([abc])?$")
_DISEASE_RANK = {HEALTH: 0, GINGIVITIS: 1, PERIODONTITIS: 2}
_EXTENT_RANK = {"localized": 1, "molar_incisor": 2, "generalized": 3}
_SUFFIXES = ("izing", "ising", "ized", "ised", "ize", "ise", "ation", "ing", "ed", "es", "s")
_COPIED = re.compile(r"--\s*copied from visit", re.IGNORECASE)


@functools.lru_cache(maxsize=65536)
def _stem(word: str) -> str:
    for s in _SUFFIXES:
        if word.endswith(s) and len(word) - len(s) >= 4:
            return word[: -len(s)]
    return word


@functools.lru_cache(maxsize=262144)
def _similar(word: str, term: str) -> bool:
    if word == term:
        return True
    if min(len(word), len(term)) < 5:
        return False
    ratio = max(difflib.SequenceMatcher(None, word, term).ratio(),
                difflib.SequenceMatcher(None, _stem(word), _stem(term)).ratio())
    return ratio >= SIMILARITY


@traced
def stem(word: str) -> str:
    """A small suffix stripper: 'generalized', 'generalised' -> 'general'."""
    return _stem(word)


@traced
def similar(word: str, term: str) -> bool:
    """Does a word match a term? Exact for short words; otherwise difflib ratio >= SIMILARITY, raw or stemmed.
    (The per-word helpers note_status uses are cached and untraced: they run millions of times per build.)"""
    return _similar(word, term)


def _clauses(text: str) -> list[list[str]]:
    """Step 1, normalize: lowercase, abbreviation dots kept with their word, split into clauses, special
    characters to spaces. Each clause is a list of words."""
    t = re.sub(r"\b(st|gr|gen|loc|dx)\.", r"\1 ", text.lower())
    out = []
    for clause in re.split(r"[;,\n]|\.(?=\s|$)", t):
        words = re.sub(r"[^a-z0-9]+", " ", clause).split()
        if words:
            out.append(words)
    return out


def _negated(words: list[str], on: bool) -> list[bool]:
    neg, left = [], 0
    for w in words:
        if on and w in NEGATION_CUES:
            neg.append(True)
            left = NEGATION_WINDOW
            continue
        neg.append(left > 0)
        left = max(left - 1, 0)
    return neg


def _match(words: list[str], field_: str) -> list[tuple[int, Term]]:
    """Terms of one field found in a clause (stop words dropped first): (position of the first word, term)."""
    kept = [(i, w) for i, w in enumerate(words) if w not in STOP_WORDS]
    hits = []
    for j, (i, w) in enumerate(kept):
        for t in PERIODX_TERMS:
            if t.field != field_:
                continue
            parts = t.term.split()
            if len(parts) == 1 and _similar(w, parts[0]) or len(parts) == 2 and j + 1 < len(kept) and _similar(w, parts[0]) and _similar(kept[j + 1][1], parts[1]):
                hits.append((i, t))
    return hits


@traced
def note_status(note: str, negation: bool = NEGATION_DEFAULT, multiple: str = MULTIPLE_DEFAULT) -> PerioDxFinding:
    """The PerioDx Extractor: the most specific periodontal status the note's words support, or 'no_diagnosis'.

    A stage, grade or severity term implies periodontitis; several diagnoses give the most severe (status, then
    stage, grade and extent each at their worst); multiple='most_severe_current' leaves out copied-forward text."""
    if multiple not in MULTIPLE_RULES:
        raise ValueError(f"multiple must be one of {MULTIPLE_RULES}")
    text = _COPIED.split(note or "")[0] if multiple == "most_severe_current" else (note or "")
    disease, stages, grades, extents = [], [], [], []
    for words in _clauses(text):
        neg = _negated(words, negation)
        ok = [not n for n in neg]
        for i, t in _match(words, "disease"):
            if ok[i]:
                disease.append(t.value)
        for i, t in _match(words, "extent"):
            if ok[i]:
                extents.append(t.value)
        for i, t in _match(words, "severity"):
            if ok[i] and any(_similar(w, "periodontitis") for w in words[i + 1: i + 1 + SEVERITY_WINDOW]):
                stages.append(int(t.value))
        for i, t in _match(words, "stage_cue") + _match(words, "grade_cue"):
            if not ok[i]:
                continue
            nxt = next((w for w in words[i + 1:] if w not in ("st", "stage")), None) if t.field == "stage_cue" \
                else (words[i + 1] if i + 1 < len(words) else None)
            m = _NUMERAL.match(nxt or "")
            if t.field == "stage_cue" and m:
                stages.append(_ROMAN[m.group(1)])
                if m.group(2):
                    grades.append(_GRADE[m.group(2)])
            elif t.field == "grade_cue" and nxt in _GRADE:
                grades.append(_GRADE[nxt])
    if stages or grades:
        disease.append(PERIODONTITIS)
    if not disease:
        return PerioDxFinding(NO_DIAGNOSIS, section="M2")
    status = max(disease, key=_DISEASE_RANK.__getitem__)
    extent = max(extents, key=_EXTENT_RANK.__getitem__) if extents else NOT_ASSESSABLE
    if status == HEALTH:
        return PerioDxFinding(HEALTH, section="M2")
    if status == GINGIVITIS:
        box = {"localized": LOCALIZED_GINGIVITIS, "generalized": GENERALIZED_GINGIVITIS}.get(extent, GINGIVITIS)
        return PerioDxFinding(box, extent=extent if box != GINGIVITIS else "NA", section="M2")
    return PerioDxFinding(PERIODONTITIS, max(stages) if stages else None, extent,
                          max(grades) if grades else NOT_ASSESSABLE, "M2")


# ---------------------------------------------------------------- parity inputs for the R twin
_CASE_CHOICES = {
    "bop_pct": [5.0, 10.0, 25.0, 30.0, 45.0], "max_pd_mm": [3.0, 3.9, 4.0, 5.0, 5.5, 7.0],
    "bone_loss_pct": [None, 0.0, 8.0, 14.9, 15.0, 25.0, 33.0, 40.0, "<15", "15-33", ">33"],
    "max_cal_mm": [None, 0.0, 2.0, 2.9, 3.0, 4.5, 6.0], "interproximal_cal_teeth": [None, 0, 1, 2, 6],
    "recession_teeth": [None, 0, 2], "cal5_adjacent_teeth": [None, 0, 1, 2], "pd5_adjacent_teeth": [None, 0, 2],
    "furcation_class": [None, 0, 1, 2, 3], "vertical_bone_loss_mm": [None, 0.0, 2.5, 3.0],
    "occluding_pairs": [None, 6, 9, 10, 14], "mobility2_teeth": [None, 0, 4, 5], "complex_rehab": [None, False, True],
    "teeth_lost_perio": [0, 0, 1, 4, 5, 8], "pct_teeth_involved": [None, 10.0, 29.9, 30.0, 60.0],
    "molar_incisor": [False, False, False, True]}
_PERSON_CHOICES = {"age": [None, 0, 25, 40, 60, 80], "cigarettes_per_day": [None, 0, 5, 10, 20],
                   "diabetes": [None, False, True], "hba1c": [None, 5.6, 6.9, 7.0, 8.4]}


def _bit(x):
    return None if x is None else int(bool(x))


def _result(f: PerioDxFinding) -> dict:
    return {"status": f.status, "stage": f.stage, "extent": f.extent, "grade": f.grade, "label": f.label,
            "partial": ";".join(sorted(f.partial))}


@traced
def write_parity_cases(out_dir, seed: int = 24, n_charts: int = 4000, n_summaries: int = 2000) -> str:
    """Seeded chart inputs (with gaps) and summary charts, with what the Diagnoser found, for r/tests/test_parity.R:
    periodx_chart_cases.csv and periodx_summary_cases.csv in out_dir. Synthetic values only."""
    import random
    from pathlib import Path

    import pandas as pd
    rng = random.Random(seed)
    rows = []
    for _ in range(n_charts):
        kw = {k: rng.choice(v) for k, v in _CASE_CHOICES.items()}
        who = {k: rng.choice(v) for k, v in _PERSON_CHOICES.items()}
        f = chart_status(PerioDxChart(**kw), **who)
        bl = kw["bone_loss_pct"]
        rows.append({**kw, "bone_loss_pct": None if isinstance(bl, str) else bl,
                     "bone_loss_band": bl if isinstance(bl, str) else "",
                     "complex_rehab": _bit(kw["complex_rehab"]), "molar_incisor": _bit(kw["molar_incisor"]),
                     **who, "diabetes": _bit(who["diabetes"]), **_result(f)})
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out / "periodx_chart_cases.csv", index=False)
    rows = []
    for _ in range(n_summaries):
        s = {"max_pd_mm": round(rng.uniform(1, 10), 1), "bop_pct": round(rng.uniform(0, 80), 1),
             "max_cal_mm": rng.choice([None, round(rng.uniform(0, 10), 2)]),
             "rbl_pct": rng.choice([None, round(rng.uniform(0, 80), 1)]), "teeth_lost_perio": rng.choice([0, 0, 2, 6]),
             "pct_teeth_involved": rng.choice([None, 0.0, float(rng.randint(5, 90))])}
        c = chart_from_summary(**s)
        f = chart_status(c, age=55, cigarettes_per_day=0, diabetes=False)
        rows.append({**s, "interproximal_cal_teeth": c.interproximal_cal_teeth,
                     "cal5_adjacent_teeth": c.cal5_adjacent_teeth, "pd5_adjacent_teeth": c.pd5_adjacent_teeth,
                     "chart_pct_teeth_involved": c.pct_teeth_involved, **_result(f)})
    pd.DataFrame(rows).to_csv(out / "periodx_summary_cases.csv", index=False)
    return (f"wrote periodx_chart_cases.csv ({n_charts}) and periodx_summary_cases.csv ({n_summaries}) "
            "for the spec 024 R twin")
