"""The seven evidence types per visit, and a rule that reads each one.

The study compares methods for phenotyping periodontal status from a dental
EHR. Each visit has up to seven evidence types (chart note, exam form, procedure codes completed
and planned, procedure diagnosis codes completed and planned, probing chart), and they disagree:

    1 chart notes                 free text (clinical_notes.py)
    2 exam forms                  structured screening fields (PSR codes, checkboxes)
    3 procedure codes, completed  CDT codes actually done
    4 procedure codes, planned    CDT codes on the treatment plan
    5 procedure diagnosis, completed   ICD-10-CM codes attached to completed procedures
    6 procedure diagnosis, planned     ICD-10-CM codes attached to planned procedures
    7 probing chart               CAL, RBL, tooth loss due to perio (labels.py)

This module generates evidence types 2-6 from the visit's true status with the kinds
of noise real EDRs have (planned != completed because patients decline;
diagnosis codes drift toward "moderate"; forms copied forward; evidence
missing), and gives a reader for each that returns what that evidence type alone
says about status. `phenotype.py` combines them.

Codes used:
  CDT   D0180 comprehensive perio eval, D1110 adult prophy, D4346 gingival
        inflammation scaling, D4341/D4342 SRP 4+/1-3 teeth per quad,
        D4910 perio maintenance, D4260/D4261 osseous surgery, D7140 extraction
  ICD-10-CM  K05.10 chronic gingivitis plaque-induced; K05.3[12][123]
        chronic periodontitis {localized 1, generalized 2} x {slight 1,
        moderate 2, severe 3}; Z01.20 dental exam without abnormal findings
  PSR   0-4 per sextant, * for furcation/mobility; max sextant reported
"""

from __future__ import annotations

import random

from .labels import Status
from .telemetry import traced

STATUSES = [s.value for s in Status]
UNKNOWN = "unknown"   # evidence that is missing or says nothing about status

# ------------------------------------------------------------------ generate
_PSR = {Status.HEALTHY: 0, Status.GINGIVITIS: 1, Status.P1: 3, Status.P2: 3, Status.P3: 4, Status.P4: 4}
_SEVERITY_DIGIT = {Status.P1: "1", Status.P2: "2", Status.P3: "3", Status.P4: "3"}
def _codes(status: Status, rng: random.Random) -> list[str]:
    """CDT cannot stage: SRP (D4341) covers stage II-IV, gingivitis is often
    billed as a plain prophy, mild perio often gets a prophy or limited SRP."""
    if status is Status.HEALTHY:
        return ["D0120", "D1110"]
    if status is Status.GINGIVITIS:
        return ["D0120", rng.choices(["D1110", "D4346"], weights=[0.6, 0.4])[0]]
    if status is Status.P1:
        return ["D0180", rng.choices(["D1110", "D4342", "D4341"], weights=[0.35, 0.4, 0.25])[0]]
    codes = ["D0180", "D4341"]
    if status is Status.P3 and rng.random() < 0.3:
        codes.append("D4260")
    if status is Status.P4:
        codes += rng.sample(["D4260", "D7140", "D4910"], rng.randint(0, 2))
    return codes


def _icd(status: Status, extent: str) -> str:
    if status is Status.HEALTHY:
        return "Z01.20"
    if status is Status.GINGIVITIS:
        return "K05.10"
    ext = "2" if extent == "generalized" else "1"
    return f"K05.3{ext}{_SEVERITY_DIGIT[status]}"


def _drift(status: Status, rng: random.Random, p: float) -> Status:
    """Move one category toward 'moderate' with probability p (billing/charting drift)."""
    if rng.random() >= p:
        return status
    order = list(Status)
    i = order.index(status)
    target = order.index(Status.P2)
    return order[i + (1 if target > i else -1 if target < i else rng.choice([-1, 1]))]


@traced
def generate_sources(status: Status, extent: str, rng: random.Random) -> dict:
    """Evidence types 2-6 for one visit. Values are strings; '' means missing."""
    s = {}
    # 2 exam form: PSR max sextant + a perio-status checkbox that is sometimes stale
    if rng.random() < 0.85:
        psr = _PSR[status] + (rng.choice([-1, 1]) if rng.random() < 0.15 else 0)
        s["exam_form"] = f"PSR max {min(max(psr, 0), 4)}" + ("*" if status is Status.P4 and rng.random() < 0.6 else "")
        box = _drift(status, rng, 0.25)
        s["exam_form"] += f"; perio status: {'WNL' if box is Status.HEALTHY else box.value.replace('_', ' ')}"
    else:
        s["exam_form"] = ""
    # 4 planned codes always reflect the clinician's intent; 3 completed may lag
    planned = _codes(status, rng)
    s["proc_codes_planned"] = " ".join(planned)
    declined = status.is_periodontitis and rng.random() < 0.2
    completed = ["D0180" if status.is_periodontitis else "D0120", "D1110"] if declined else list(planned)
    s["proc_codes_completed"] = " ".join(completed)
    # 6 planned dx, 5 completed dx: present only for some practices; severity drifts
    if rng.random() < 0.7:
        s["proc_dx_planned"] = _icd(_drift(status, rng, 0.2), extent)
        s["proc_dx_completed"] = _icd(Status.GINGIVITIS if declined else _drift(status, rng, 0.2), extent)
    else:
        s["proc_dx_planned"] = s["proc_dx_completed"] = ""
    return s


# ------------------------------------------------------------------ read
@traced
def read_exam_form(v: str) -> str:
    if not v:
        return UNKNOWN
    if "status:" in v:
        box = v.split("status:")[1].strip()
        if box == "WNL":
            return Status.HEALTHY.value
        cand = box.replace(" ", "_")
        if cand in STATUSES:
            return cand
    psr = int(v.split("PSR max ")[1][0])
    return [Status.HEALTHY, Status.GINGIVITIS, Status.GINGIVITIS, Status.P2, Status.P3][psr].value


@traced
def read_proc_codes(v: str) -> str:
    """CDT codes say perio or not, and roughly how severe; they cannot stage."""
    if not v:
        return UNKNOWN
    c = set(v.split())
    if c & {"D4260", "D4261"} or ("D7140" in c and "D4341" in c):
        return Status.P3.value          # surgery / extraction alongside SRP: at least stage III
    if "D4341" in c:
        return Status.P2.value          # SRP 4+ teeth: periodontitis, stage not knowable; II is the mode
    if "D4342" in c:
        return Status.P1.value
    if "D4346" in c:
        return Status.GINGIVITIS.value
    if "D1110" in c and "D0180" not in c:
        return Status.HEALTHY.value     # prophy only: healthy or gingivitis, can't tell; healthy is the mode
    return UNKNOWN                      # D0180 + D1110: evaluated, treatment not done


@traced
def read_proc_dx(v: str) -> str:
    if not v:
        return UNKNOWN
    if v == "Z01.20":
        return Status.HEALTHY.value
    if v.startswith(("K05.0", "K05.1")):
        return Status.GINGIVITIS.value
    if v.startswith("K05.3") and len(v) == 7:   # K05.3 + extent digit + severity digit
        stage = {"1": Status.P1, "2": Status.P2, "3": Status.P3}.get(v[-1])   # another digit: unreadable (#471)
        return stage.value if stage else UNKNOWN
    return UNKNOWN


READERS = {
    "exam_form": read_exam_form,
    "proc_codes_completed": read_proc_codes,
    "proc_codes_planned": read_proc_codes,
    "proc_dx_completed": read_proc_dx,
    "proc_dx_planned": read_proc_dx,
}
