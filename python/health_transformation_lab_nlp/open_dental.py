"""A seeded synthetic dental-practice extract in Open Dental's table format (spec 029 US1 and US5; #369, #381).

Every row is generated here: synthetic people (`synthetic.draw_history`) and their mouths (`sites.draw_mouth_columns`,
which knows why each tooth is missing), written as the tables a practice-management extract holds, with Open Dental's
table and column names lowercased (specs/029-tooth-loss/research.md; diagrams/_build/opendental_silver_model.py, which
python/tests/test_open_dental.py checks `TABLES` against). Nothing comes from any practice: the diagnosis lists, the
offices, sites and providers, and every rate are invented here and named in `Params`.

What the extract carries, as Open Dental records it:
- a missing tooth is a `toothinitial` row (InitialType 0) with no date or reason, or an extraction recorded as done
  elsewhere (`procedurelog`, ProcStatus 4);
- an extraction is a `procedurelog` row: planned (ProcStatus 1), then the same row set complete (2), or left planned;
- its diagnosis is an item in the practice's own list (`dx` → `definition`, category Diagnosis), drawn from an older
  list before the practice adopts the 2017 classification and a newer one after, over an adoption lag; ICD codes
  appear only on a small share, as on medical claims;
- a planned procedure is copied into every plan saved at that exam (`treatplan`, `proctp`), and again at later exams
  while it stays planned; a few copies are edited;
- perio charts store probing and gingival margin per site (never CAL), -1 for not measured, margins above the
  cementoenamel junction as 100 + mm, and bleeding as bit 1 of a flag sum.

Why each tooth was lost (`tooth_loss_truth`) is returned apart from the extract and written to another folder: the
evaluation reads it, the extract never carries it.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from .sites import MOLARS, SITES, THIRD_MOLARS, draw_mouth_columns
from .synthetic import draw_history, draw_pct_teeth_involved, draw_risk
from .telemetry import traced

TABLES = {
    "patient": ["patnum", "birthdate", "gender", "patstatus", "clinicnum", "priprov", "datefirstvisit", "smokingsnomed",
                "zip", "guarantor", "medurgnote", "premed", "language", "admitdate", "sitenum", "responsparty",
                "datetimedeceased"],
    "clinic": ["clinicnum", "description", "abbr", "address", "address2", "city", "state", "zip", "phone", "fax"],
    "procedurelog": ["procnum", "patnum", "procstatus", "procdate", "datetp", "datecomplete", "codenum", "toothnum",
                     "surf", "dx", "prognosis", "diagnosticcode", "icdversion", "provnum", "clinicnum", "aptnum",
                     "procfee", "toothrange", "priority", "placeservice", "prosthesis", "medicalcode", "unitqty",
                     "sitenum"],
    "procedurecode": ["codenum", "proccode", "descript", "abbrdesc", "treatarea", "proccat", "isprosth", "ishygiene",
                      "medicalcode", "isradiology"],
    "treatplan": ["treatplannum", "patnum", "datetp", "tpstatus", "signature"],
    "proctp": ["proctpnum", "treatplannum", "patnum", "procnumorig", "toothnumtp", "proccode", "descript", "dx",
               "prognosis", "itemorder", "priority", "surf", "procabbr", "provnum", "datetp", "clinicnum"],
    "definition": ["defnum", "category", "itemname", "itemvalue", "itemorder", "ishidden"],
    "perioexam": ["perioexamnum", "patnum", "examdate", "provnum"],
    "periomeasure": ["periomeasurenum", "perioexamnum", "sequencetype", "inttooth", "toothvalue", "mbvalue", "bvalue",
                     "dbvalue", "mlvalue", "lvalue", "dlvalue"],
    "toothinitial": ["toothinitialnum", "patnum", "toothnum", "initialtype", "movement"],
    "disease": ["diseasenum", "patnum", "diseasedefnum", "probstatus", "datestart", "datestop", "patnote"],
    "diseasedef": ["diseasedefnum", "diseasename", "icd10code", "snomedcode", "icd9code", "ishidden"],
    "provider": ["provnum", "suffix", "specialty", "issecondary", "isnotperson", "customid"],
    "appointment": ["aptnum", "patnum", "provnum", "provhyg", "aptdatetime", "pattern", "clinicnum", "ishygiene",
                    "procdescript"],
    "medication": ["medicationnum", "medname", "genericnum", "notes", "rxcui"],
    "medicationpat": ["medicationpatnum", "patnum", "medicationnum", "patnote", "datestart", "datestop", "provnum",
                      "iscpoe"],
    "allergy": ["allergynum", "allergydefnum", "patnum", "reaction", "statusisactive"],
    "allergydef": ["allergydefnum", "description", "ishidden", "snomedtype", "medicationnum", "uniicode"],
    "sheet": ["sheetnum", "sheettype", "patnum", "datetimesheet", "description", "clinicnum"],
    "sheetfield": ["sheetfieldnum", "sheetnum", "fieldname", "fieldvalue", "radiobuttongroup", "reportablename"],
    "vitalsign": ["vitalsignnum", "patnum", "bpsystolic", "bpdiastolic", "pulse", "datetaken"],
    "patientrace": ["patientracenum", "patnum", "cdcreccode"],
    "cdcrec": ["cdcrecnum", "cdcreccode", "heirarchicalcode", "description"],
    "site": ["sitenum", "description", "note", "zip", "placeservice"],
    "procnote": ["procnotenum", "patnum", "procnum", "entrydatetime", "note"],
    "ehrmeasureevent": ["ehrmeasureeventnum", "datetevent", "eventtype", "patnum", "moreinfo", "codevalueresult",
                        "datestarttobacco", "tobaccocessationdesire"],
    "patfield": ["patfieldnum", "patnum", "fieldname", "fieldvalue"],
    "snomed": ["snomednum", "snomedcode", "description"],
}
DATES = {"birthdate", "datefirstvisit", "admitdate", "datetimedeceased", "procdate", "datetp", "datecomplete",
         "examdate", "datestart", "datestop", "aptdatetime", "datetimesheet", "datetaken", "entrydatetime",
         "datetevent", "datestarttobacco"}

# Open Dental enum values (OpenDentBusiness, release 24_3): DefCat, ProcStat, SheetTypeEnum, EhrMeasureEventType,
# SnomedAllergy, PlaceOfService, PerioSequenceType
DEFCAT_PROCCODECATS, DEFCAT_DIAGNOSIS, DEFCAT_TXPRIORITIES, DEFCAT_PROGNOSIS, DEFCAT_SPECIALTIES = 11, 16, 20, 30, 35
PLANNED, COMPLETE, EXISTING_OTHER = 1, 2, 4
SHEET_EXAM, TOBACCO_ASSESSED, DRUG_ALLERGY = 13, 8, 2
POS_OFFICE, POS_NURSING, POS_MOBILE, POS_SCHOOL = 0, 4, 7, 8
SEQ_MOBILITY, SEQ_FURCATION, SEQ_MARGIN, SEQ_PROBING, SEQ_BLEEDING = 0, 1, 2, 4, 6

# the practice's two diagnosis lists, invented here: (name, abbreviation, perio or other)
OLDER_LIST = [("Periodontal disease, advanced", "PDA", "perio"), ("Periodontal disease, moderate", "PDM", "perio"),
              ("Caries, non-restorable", "CNR", "other"), ("Fractured tooth", "FRX", "other"),
              ("Orthodontic extraction", "ORX", "other"), ("Other", "OTH", "other")]
LIST_2017 = [("Periodontitis, stage III", "PS3", "perio"), ("Periodontitis, stage IV", "PS4", "perio"),
             ("Caries, non-restorable (2017 list)", "CN2", "other"), ("Fracture (2017 list)", "FR2", "other"),
             ("Orthodontic (2017 list)", "OR2", "other"), ("Other (2017 list)", "OT2", "other")]
# the declared lookup silver uses: every item of either list -> perio / other (spec 029 FR-004)
DIAGNOSIS_LOOKUP = {name: kind for name, _, kind in OLDER_LIST + LIST_2017}

PROCEDURE_CODES = [  # code, our short description, abbreviation, treat area, category, is hygiene, fee
    ("D0150", "Comprehensive oral evaluation", "CompEx", 3, "Exams", False, 95.0),
    ("D0120", "Periodic oral evaluation", "PerEx", 3, "Exams", False, 55.0),
    ("D1110", "Prophylaxis, adult", "Pro", 3, "Cleanings", True, 90.0),
    ("D4341", "Scaling and root planing, 4+ teeth, per quadrant", "SRP", 4, "Periodontics", True, 230.0),
    ("D4910", "Periodontal maintenance", "PMaint", 3, "Periodontics", True, 140.0),
    ("D7140", "Extraction, erupted tooth", "Ext", 2, "Oral Surgery", False, 170.0),
    ("D7210", "Extraction, surgical", "ExtSurg", 2, "Oral Surgery", False, 290.0),
]
EXTRACTIONS = ("D7140", "D7210")
SNOMED_SMOKING = {"266919005": "Never smoked tobacco", "8517006": "Ex-smoker",
                  "449868002": "Smokes tobacco daily", "428041000124106": "Occasional tobacco smoker"}
DISEASES = [("Type 2 diabetes mellitus", "E11.9", "44054006", "250.00"),
            ("Essential hypertension", "I10", "38341003", "401.9"),
            ("Asthma", "J45.909", "195967001", "493.90")]
MEDICATIONS = [("Metformin", 6809), ("Lisinopril", 29046), ("Amlodipine", 17767), ("Atorvastatin", 83367),
               ("Levothyroxine", 10582), ("Omeprazole", 7646), ("Ibuprofen", 5640), ("Amoxicillin", 723),
               ("Aspirin", 1191)]
CDCREC = [("1002-5", "R1", "American Indian or Alaska Native"), ("2028-9", "R2", "Asian"),
          ("2054-5", "R3", "Black or African American"), ("2076-8", "R4", "Native Hawaiian or Other Pacific Islander"),
          ("2106-3", "R5", "White"), ("2135-2", "E1", "Hispanic or Latino"), ("2186-5", "E2", "Not Hispanic or Latino")]


@dataclass(frozen=True)
class Params:
    """Every rate and date is a named parameter with a fixed default (AGENTS.md: seeds and defaults fixed)."""
    n_patients: int = 2000                   # enough extractions with a diagnosis to train on (spec 029 US3)
    visits: tuple = (2, 8)                    # recall visits per patient, inclusive
    first_years: tuple = (2012, 2022)         # first visit falls in these years
    entry_as_existing: float = 0.3            # teeth missing at entry recorded as an extraction done elsewhere
    other_extraction_per_visit: float = 0.04  # an extraction for another reason (caries, fracture) between visits
    planned_not_done_per_visit: float = 0.10  # a periodontal extraction planned and never completed in the record
    dx_correct: float = 0.80                  # extraction diagnosis matches the true reason
    dx_mismatch: float = 0.05                 # it names the other kind of reason (a recording mismatch)
    dx_none: float = 0.15                     # no diagnosis
    icd_share: float = 0.03                   # an ICD code as for a medical claim
    list_switch_date: date = date(2018, 1, 1)  # the practice adopts the 2017 list ...
    list_adoption_years: float = 2.0          # ... and stops using the older one over this many years
    plans_per_exam: tuple = (1, 3)            # treatment plans saved at an exam that plans something
    replan: float = 0.7                       # a still-planned procedure is copied into the next exam's plans
    edited_copy: float = 0.03                 # a plan copy whose code, tooth or diagnosis text was edited
    n_clinics: int = 4
    n_dentists: int = 8
    n_hygienists: int = 6
    sites: tuple = field(default=(("Maple Grove Nursing Home", POS_NURSING), ("Lakeside School", POS_SCHOOL),
                                  ("Riverview Care Center", POS_NURSING), ("Mobile Unit 1", POS_MOBILE)))


class _Rows:
    """Rows collected per table; calling it adds a row and returns its key (the next number unless given)."""

    def __init__(self):
        self.rows = {t: [] for t in TABLES}
        self.next = {t: 1 for t in TABLES}

    def __call__(self, table, **values):
        key = TABLES[table][0]
        if key not in values:
            values[key] = self.next[table]
            self.next[table] += 1
        self.rows[table].append(values)
        return values[key]


def _frames(r: _Rows) -> dict[str, pd.DataFrame]:
    out = {}
    for t, cols in TABLES.items():
        df = pd.DataFrame(r.rows[t], columns=cols)
        for c in cols:
            if c in DATES:
                df[c] = pd.to_datetime(df[c])
        out[t] = df
    return out


def _adoption(d: date, p: Params) -> float:
    """Share of new diagnoses drawn from the 2017 list on day d: 0 before the switch, rising to 1 over the lag."""
    years = (d - p.list_switch_date).days / 365.25
    return min(1.0, max(0.0, years / p.list_adoption_years)) if years >= 0 else 0.0


@traced
def build(p: Params | None = None, seed: int = 42) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    """The extract, {table: DataFrame} with TABLES' columns, and the truth (patient_id, tooth_num, true_reason_code).
    Its own random stream, so the study datasets and the global random state don't change."""
    p = p or Params()
    rng = random.Random(f"{seed}:open_dental")
    r = _Rows()
    truth: dict[tuple[int, int], str] = {}

    # ---- the practice's lists and reference tables
    def defs(category, items):
        return {name: r("definition", category=category, itemname=name, itemvalue=value, itemorder=i,
                            ishidden=hidden) for i, (name, value, hidden) in enumerate(items)}
    dx_old = defs(DEFCAT_DIAGNOSIS, [(n, a, True) for n, a, _ in OLDER_LIST])     # hidden once retired
    dx_new = defs(DEFCAT_DIAGNOSIS, [(n, a, False) for n, a, _ in LIST_2017])
    prognosis = defs(DEFCAT_PROGNOSIS, [(n, "", False) for n in ("Good", "Fair", "Questionable", "Poor", "Hopeless")])
    priority = defs(DEFCAT_TXPRIORITIES, [(n, "", False) for n in ("1", "2", "3")])
    proccat = defs(DEFCAT_PROCCODECATS, [(n, "", False) for n in ("Exams", "Cleanings", "Periodontics", "Oral Surgery")])
    specialty = defs(DEFCAT_SPECIALTIES, [(n, "", False) for n in ("General", "Hygienist", "Periodontist")])
    code = {}
    for c, desc, abbr, area, cat, hyg, fee in PROCEDURE_CODES:
        code[c] = (r("procedurecode", proccode=c, descript=desc, abbrdesc=abbr, treatarea=area,
                         proccat=proccat[cat], isprosth=False, ishygiene=hyg, medicalcode="", isradiology=False),
                   desc, abbr, fee)
    clinics = [r("clinic", description=f"Synthetic Dental Clinic {chr(65 + i)}", abbr=f"Clinic {chr(65 + i)}",
                     address=f"{100 + 10 * i} Example Avenue", address2="", city="Exampletown", state="ZZ",
                     zip=f"0000{i}", phone="", fax="") for i in range(p.n_clinics)]
    sites = [r("site", description=name, note="", zip=f"0010{i}", placeservice=pos)
             for i, (name, pos) in enumerate(p.sites)]
    dentists = [r("provider", suffix=rng.choice(["DDS", "DMD"]), specialty=specialty["General"],
                      issecondary=False, isnotperson=False, customid=f"D{i:03d}") for i in range(p.n_dentists)]
    dentists[0:1] = [r("provider", suffix="DDS", specialty=specialty["Periodontist"], issecondary=False,
                           isnotperson=False, customid="P001")]
    hygienists = [r("provider", suffix="RDH", specialty=specialty["Hygienist"], issecondary=True,
                        isnotperson=False, customid=f"H{i:03d}") for i in range(p.n_hygienists)]
    r("provider", suffix="", specialty=specialty["General"], issecondary=False, isnotperson=True, customid="BILL")
    meds = {}
    for name, rxcui in MEDICATIONS:
        meds[name] = r("medication", medname=name, genericnum=0, notes="", rxcui=rxcui)
    for row in r.rows["medication"]:
        row["genericnum"] = row["medicationnum"]                          # each is its own generic
    allergens = [r("allergydef", description=f"{m} allergy", ishidden=False, snomedtype=DRUG_ALLERGY,
                       medicationnum=meds[m], uniicode="") for m in ("Amoxicillin", "Ibuprofen", "Aspirin")]
    disease_def = {n: r("diseasedef", diseasename=n, icd10code=icd10, snomedcode=sct, icd9code=icd9,
                            ishidden=False) for n, icd10, sct, icd9 in DISEASES}
    for c, h, d in CDCREC:
        r("cdcrec", cdcreccode=c, heirarchicalcode=h, description=d)
    for c, d in SNOMED_SMOKING.items():
        r("snomed", snomedcode=c, description=d)

    def diagnosis(kind: str, on: date) -> tuple[int, str, str]:
        """(defnum, item name, which list) for an extraction of this true kind planned on this day; 0 is none."""
        use_new = rng.random() < _adoption(on, p)
        items, keys = (LIST_2017, dx_new) if use_new else (OLDER_LIST, dx_old)
        u = rng.random()
        if u < p.dx_none:
            return 0, "", ""
        want = kind if u < p.dx_none + p.dx_correct else ("other" if kind == "perio" else "perio")
        name = rng.choice([n for n, _, k in items if k == want])
        return keys[name], name, "2017" if use_new else "older"

    # ---- patients
    for _ in range(p.n_patients):
        age = rng.randint(25, 85)
        first = date(rng.randint(*p.first_years), rng.randint(1, 12), rng.randint(1, 28))
        n_vis = rng.randint(*p.visits)
        risk = draw_risk(rng)
        hist = draw_history(age, n_vis, risk, rng, months_between=6.0)
        dates = [first + timedelta(days=round(182.5 * k + rng.uniform(-20, 20))) if k else first for k in range(n_vis)]
        clinic, dentist, hyg = rng.choice(clinics), rng.choice(dentists), rng.choice(hygienists)
        site = rng.choice(sites) if rng.random() < 0.08 else 0
        cigs = risk.cigarettes_per_day
        smoke = "449868002" if cigs >= 10 else "428041000124106" if cigs else \
            ("8517006" if rng.random() < 0.2 else "266919005")
        status = rng.choices([0, 2, 5], weights=[0.85, 0.12, 0.03])[0]
        last = dates[-1]
        pat = r("patient", birthdate=first - timedelta(days=round(age * 365.25 + rng.uniform(0, 364))),
                    gender=rng.choice([0, 1]), patstatus=status, clinicnum=clinic, priprov=dentist,
                    datefirstvisit=first, smokingsnomed=smoke, zip=f"0{rng.randint(1000, 9999)}", guarantor=0,
                    medurgnote="", premed=False, language=rng.choices(["eng", "spa"], weights=[0.9, 0.1])[0],
                    admitdate=(first - timedelta(days=rng.randint(30, 900))) if site else None, sitenum=site,
                    responsparty=0, datetimedeceased=(last + timedelta(days=rng.randint(30, 400))) if status == 5 else None)
        row = r.rows["patient"][-1]
        row["guarantor"] = pat
        if rng.random() < 0.05:
            row["premed"], row["medurgnote"] = True, "Premedicate before dental treatment"
        if site and rng.random() < 0.5:
            row["responsparty"] = pat
        for c in (rng.choice(CDCREC[:5])[0], rng.choice(CDCREC[5:])[0]):
            r("patientrace", patnum=pat, cdcreccode=c)
        r("patfield", patnum=pat, fieldname="Research consent",
              fieldvalue=rng.choices(["Yes", "No", "Passive"], weights=[0.65, 0.2, 0.15])[0])
        r("ehrmeasureevent", datetevent=datetime.combine(first, datetime.min.time()), eventtype=TOBACCO_ASSESSED,
              patnum=pat, moreinfo="", codevalueresult=smoke,
              datestarttobacco=date(first.year - rng.randint(2, 30), 1, 1) if cigs else None,
              tobaccocessationdesire=rng.randint(0, 10) if cigs else 0)
        diabetic = risk.hba1c is not None and risk.hba1c >= 6.5
        problems = (["Type 2 diabetes mellitus"] if diabetic else []) + \
            (["Essential hypertension"] if age > 50 and rng.random() < 0.35 else []) + \
            (["Asthma"] if rng.random() < 0.07 else [])
        for name in problems:
            r("disease", patnum=pat, diseasedefnum=disease_def[name], probstatus=0, datestart=None, datestop=None,
                  patnote="")
        taking = (["Metformin"] if diabetic else []) + \
            ([rng.choice(["Lisinopril", "Amlodipine"])] if "Essential hypertension" in problems else []) + \
            ([rng.choice(["Atorvastatin", "Levothyroxine", "Omeprazole"])] if rng.random() < 0.3 else [])
        for m in taking:
            r("medicationpat", patnum=pat, medicationnum=meds[m], patnote="",
                  datestart=first - timedelta(days=rng.randint(30, 2000)) if rng.random() < 0.3 else None,
                  datestop=None, provnum=0, iscpoe=False)
        if rng.random() < 0.12:
            r("allergy", allergydefnum=rng.choice(allergens), patnum=pat, reaction=rng.choice(["rash", "hives", ""]),
                  statusisactive=True)

        # ---- the mouth at the first exam: who is missing, and why (the truth)
        chart0 = hist[0].chart
        site_cols, teeth = draw_mouth_columns(chart0, draw_pct_teeth_involved(chart0, rng), rng)
        base = {(t, s): (pd_, cal, b) for t, s, pd_, cal, b in zip(site_cols["tooth"], site_cols["site"],
                                                                    site_cols["pd_mm"], site_cols["cal_mm"],
                                                                    site_cols["bop"])}
        mobility = dict(zip(teeth["tooth"], teeth["mobility_degree"]))
        furcation = dict(zip(teeth["tooth"], teeth["furcation_class"]))
        present = {t for t, ok in zip(teeth["tooth"], teeth["present"]) if ok}
        for t, reason in zip(teeth["tooth"], teeth["missing_reason"]):
            if not reason:
                continue
            truth[(pat, t)] = reason
            if rng.random() < p.entry_as_existing:
                r("procedurelog", patnum=pat, procstatus=EXISTING_OTHER, procdate=None, datetp=None,
                      datecomplete=None, codenum=code["D7140"][0], toothnum=str(t), surf="", dx=0, prognosis=0,
                      diagnosticcode="", icdversion=0, provnum=0, clinicnum=clinic, aptnum=0, procfee=0.0,
                      toothrange="", priority=0, placeservice=POS_OFFICE, prosthesis="", medicalcode="", unitqty=1,
                      sitenum=0)
            else:
                r("toothinitial", patnum=pat, toothnum=str(t), initialtype=0, movement=0.0)

        cal_tooth = {t: max(base[(t, s)][1] for s in SITES) for t in present}
        planned_open: list[dict] = []       # planned extractions not completed yet, with what a copy needs
        treated = False
        for k, d in enumerate(dates):
            chart = hist[k].chart
            apt = r("appointment", patnum=pat, provnum=dentist, provhyg=hyg,
                        aptdatetime=datetime.combine(d, datetime.min.time()) + timedelta(hours=rng.randint(8, 16)),
                        pattern="/XXXXXX/" if k else "/XXXXXXXXX/", clinicnum=clinic, ishygiene=True,
                        procdescript="CompEx, Pro" if k == 0 else "PerEx, Pro")

            def done(c, tooth="", fee_scale=1.0, dx=0, prog=0, on=d, pat=pat, dentist=dentist, clinic=clinic,
                     apt=apt, site=site):
                return r("procedurelog", patnum=pat, procstatus=COMPLETE, procdate=on, datetp=None,
                             datecomplete=on, codenum=code[c][0], toothnum=tooth, surf="", dx=dx, prognosis=prog,
                             diagnosticcode="", icdversion=0, provnum=dentist, clinicnum=clinic, aptnum=apt,
                             procfee=round(code[c][3] * fee_scale, 2), toothrange="", priority=0,
                             placeservice=POS_MOBILE if site else POS_OFFICE, prosthesis="", medicalcode="",
                             unitqty=1, sitenum=site)
            done("D0150" if k == 0 else "D0120")
            if hist[k].treated_before or treated:
                done("D4910")
            elif hist[k].status.is_periodontitis and rng.random() < 0.5:
                treated = True
                done("D4341")
            else:
                done("D1110")

            # perio chart: probing, gingival margin, bleeding, mobility and furcation for the teeth present today
            exam = r("perioexam", patnum=pat, examdate=d, provnum=hyg)
            grow = max(0.0, chart.max_cal_mm - chart0.max_cal_mm)
            pd_grow = chart.max_probing_depth_mm - chart0.max_probing_depth_mm
            for t in sorted(present):
                probing, margin, bleed = [], [], []
                for s in SITES:
                    pd0, cal0, _ = base[(t, s)]
                    cal = cal0 + (grow * rng.uniform(0.3, 1.0) if cal0 >= 1 else 0)
                    depth = max(1, round(pd0 + pd_grow * rng.uniform(0.2, 1.0)))
                    if rng.random() < 0.01:
                        depth = -1                                   # not measured
                    rec = round(cal) - depth if depth > 0 else -1
                    probing.append(depth)
                    margin.append(-1 if depth < 0 else (100 + abs(rec) if rec < 0 else rec))
                    flags = (1 if rng.random() < chart.bop_pct / 100 else 0) | (4 if rng.random() < 0.3 else 0)
                    bleed.append(flags)
                for seq, vals in ((SEQ_PROBING, probing), (SEQ_MARGIN, margin), (SEQ_BLEEDING, bleed)):
                    r("periomeasure", perioexamnum=exam, sequencetype=seq, inttooth=t, toothvalue=-1,
                          **dict(zip(["mbvalue", "bvalue", "dbvalue", "mlvalue", "lvalue", "dlvalue"], vals)))
                r("periomeasure", perioexamnum=exam, sequencetype=SEQ_MOBILITY, inttooth=t,
                      toothvalue=int(mobility.get(t, 0)), mbvalue=-1, bvalue=-1, dbvalue=-1, mlvalue=-1, lvalue=-1,
                      dlvalue=-1)
                if t in MOLARS and furcation.get(t, 0):
                    r("periomeasure", perioexamnum=exam, sequencetype=SEQ_FURCATION, inttooth=t, toothvalue=-1,
                          mbvalue=-1, bvalue=int(furcation[t]), dbvalue=-1, mlvalue=-1, lvalue=-1, dlvalue=-1)

            sheet = r("sheet", sheettype=SHEET_EXAM, patnum=pat,
                          datetimesheet=datetime.combine(d, datetime.min.time()), description="Oral Exam Form",
                          clinicnum=clinic)
            for group, value in (("Tobacco", "Y" if cigs else "N"), ("Bleeding", "X" if chart.bop_pct >= 10 else ""),
                                 ("Plaque", "X" if rng.random() < 0.4 else ""), ("Calculus", "X" if rng.random() < 0.3 else "")):
                r("sheetfield", sheetnum=sheet, fieldname=group, fieldvalue=value, radiobuttongroup=group,
                      reportablename=group)
            if rng.random() < 0.6:
                r("vitalsign", patnum=pat, bpsystolic=rng.randint(105, 160), bpdiastolic=rng.randint(60, 100),
                      pulse=rng.randint(55, 100), datetaken=d)

            # extractions planned today: periodontal losses before the next visit, another reason now and then,
            # and periodontal extractions that are planned and never done in the record
            new_plans = []
            if k + 1 < n_vis:
                n_lost = max(0, hist[k + 1].chart.teeth_lost_perio - chart.teeth_lost_perio)
                worst = sorted(present - THIRD_MOLARS, key=lambda t: (t not in MOLARS, -cal_tooth.get(t, 0)))
                for t in worst[:n_lost]:
                    new_plans.append((t, "perio", dates[k + 1] - timedelta(days=rng.randint(7, 120))))
                if rng.random() < p.other_extraction_per_visit:
                    left = sorted(present - {t for t, _, _ in new_plans})
                    if left:
                        new_plans.append((rng.choice(left), "other", dates[k + 1] - timedelta(days=rng.randint(7, 120))))
            if chart.max_cal_mm >= 5 and rng.random() < p.planned_not_done_per_visit:
                left = sorted(present - {t for t, _, _ in new_plans} - {o["tooth"] for o in planned_open})
                if left:
                    new_plans.append((max(left, key=lambda t: cal_tooth.get(t, 0)), "perio", None))
            for t, kind, completes in new_plans:
                truth[(pat, t)] = kind
                dx, dx_name, _ = diagnosis(kind, d)
                c = "D7210" if rng.random() < 0.2 else "D7140"
                prog = prognosis["Hopeless" if kind == "perio" else "Poor"]
                icd = rng.random() < p.icd_share
                proc = r("procedurelog", patnum=pat, procstatus=PLANNED, procdate=d, datetp=d, datecomplete=None,
                             codenum=code[c][0], toothnum=str(t), surf="", dx=dx, prognosis=prog,
                             diagnosticcode=("K05.30" if kind == "perio" else "K02.9") if icd else "",
                             icdversion=10 if icd else 0, provnum=dentist, clinicnum=clinic, aptnum=apt,
                             procfee=code[c][3], toothrange="", priority=priority["1"], placeservice=POS_OFFICE,
                             prosthesis="", medicalcode="", unitqty=1, sitenum=site)
                planned_open.append({"proc": proc, "tooth": t, "code": c, "dx_name": dx_name, "kind": kind,
                                     "completes": completes, "row": r.rows["procedurelog"][-1],
                                     "prognosis": "Hopeless" if kind == "perio" else "Poor"})

            # treatment plans saved today copy every planned extraction still open (planned today, or re-planned)
            today = [o for o in planned_open if o["row"]["datetp"] == d or rng.random() < p.replan]
            if today:
                for _ in range(rng.randint(*p.plans_per_exam)):
                    plan = r("treatplan", patnum=pat, datetp=d, tpstatus=0, signature="")
                    for i, o in enumerate(today):
                        tooth, pcode, dx_text = str(o["tooth"]), o["code"], o["dx_name"]
                        if rng.random() < p.edited_copy:         # a copy edited by hand: it no longer matches
                            which = rng.choice(["code", "tooth", "dx"])
                            pcode = "D7210" if which == "code" and pcode == "D7140" else pcode
                            tooth = str(o["tooth"] + 1) if which == "tooth" and o["tooth"] < 32 else tooth
                            dx_text = "See chart" if which == "dx" else dx_text
                        r("proctp", treatplannum=plan, patnum=pat, procnumorig=o["proc"], toothnumtp=tooth,
                              proccode=pcode, descript=code[o["code"]][1], dx=dx_text, prognosis=o["prognosis"],
                              itemorder=i, priority=priority["1"], surf="", procabbr=code[o["code"]][2],
                              provnum=dentist, datetp=d, clinicnum=clinic)
                last_plan = r.rows["treatplan"][-1]
                if rng.random() < 0.5:
                    last_plan["signature"], last_plan["tpstatus"] = "signed", 1

            # planned extractions due before the next visit are done: the same procedure row set complete
            for o in [o for o in planned_open if o["completes"] is not None and o["completes"] <= dates[min(k + 1, n_vis - 1)]]:
                o["row"].update(procstatus=COMPLETE, procdate=o["completes"], datecomplete=o["completes"])
                present.discard(o["tooth"])
                planned_open.remove(o)
                if rng.random() < 0.7:
                    r("procnote", patnum=pat, procnum=o["proc"],
                          entrydatetime=datetime.combine(o["completes"], datetime.min.time()) + timedelta(hours=10),
                          note=f"Tooth #{o['tooth']} extracted. Recorded diagnosis: {o['dx_name'] or 'none'}. "
                               "Post-operative instructions given.")

    frames = _frames(r)
    t = pd.DataFrame([(pat, tooth, reason) for (pat, tooth), reason in sorted(truth.items())],
                     columns=["patient_id", "tooth_num", "true_reason_code"])
    return frames, t


@traced
def extraction_codenums(tables: dict[str, pd.DataFrame]) -> set:
    """The procedure codes that are extractions, as codenum keys."""
    pc = tables["procedurecode"]
    return set(pc.loc[pc["proccode"].isin(EXTRACTIONS), "codenum"])


@traced
def extractions(tables: dict[str, pd.DataFrame], truth: pd.DataFrame) -> pd.DataFrame:
    """One row per extraction planned or done in the record (not those done elsewhere), with its true reason, the
    diagnosis item's class by DIAGNOSIS_LOOKUP (perio / other / none) and which list the item came from."""
    pl = tables["procedurelog"]
    ext = pl[pl["codenum"].isin(extraction_codenums(tables)) & pl["procstatus"].isin([PLANNED, COMPLETE])].copy()
    ext["tooth_num"] = ext["toothnum"].astype(int)
    d = tables["definition"][tables["definition"]["category"] == DEFCAT_DIAGNOSIS]
    names = dict(zip(d["defnum"], d["itemname"]))
    ext["dx_class"] = ext["dx"].map(lambda x: DIAGNOSIS_LOOKUP.get(names.get(x, ""), "none"))
    older = {n for n, _, _ in OLDER_LIST}
    ext["dx_list"] = ext["dx"].map(lambda x: None if x == 0 else ("older" if names.get(x) in older else "2017"))
    return ext.merge(truth, left_on=["patnum", "tooth_num"], right_on=["patient_id", "tooth_num"], how="left")


@traced
def write(out_dir: Path, truth_dir: Path, p: Params | None = None, seed: int = 42) -> dict[str, int]:
    """Writes one CSV per table to out_dir and tooth_loss_truth.csv to truth_dir (kept apart). Returns row counts."""
    tables, truth = build(p, seed)
    out_dir, truth_dir = Path(out_dir), Path(truth_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    truth_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    truth.to_csv(truth_dir / "tooth_loss_truth.csv", index=False)
    return {name: len(df) for name, df in tables.items()}


SITE_VALUES = ["mbvalue", "bvalue", "dbvalue", "mlvalue", "lvalue", "dlvalue"]


@traced
def clean(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Silver (spec 029 FR-004): the same tables with the same names and layout, read the way Open Dental means them.
    In periomeasure, -1 (not measured) becomes null, and a gingival margin of 100 or more (above the
    cementoenamel junction) becomes 100 - value, a negative number. Every other table is copied as it is; dates and
    types are already enforced by build."""
    out = {name: df.copy() for name, df in tables.items()}
    if "periomeasure" in out:
        pm = out["periomeasure"]
        for c in [*SITE_VALUES, "toothvalue"]:
            v = pm[c].astype("Int64")
            if c in SITE_VALUES:
                margin = (pm["sequencetype"] == SEQ_MARGIN) & (v >= 100)
                v = v.mask(margin, 100 - v)
            pm[c] = v.mask(v == -1)
    return out


@traced
def load_log(written: dict[str, dict[str, pd.DataFrame]], run_id: str, run_ts: pd.Timestamp, git_commit_sha: str,
             seed: int, n_patients: int) -> pd.DataFrame:
    """One row per table a load wrote ({schema: {table: DataFrame}}), with the run's batch key. The Open Dental tables
    keep Open Dental's columns only, so this is where each row's run is recorded: every table is overwritten per run,
    so all its rows belong to the run logged last for it."""
    rows = [{"schema_name": schema, "table_name": name, "row_count": len(df), "seed_num": seed,
             "patient_count": n_patients, "run_id": run_id, "run_ts": run_ts, "git_commit_sha": git_commit_sha}
            for schema, tables in written.items() for name, df in tables.items()]
    return pd.DataFrame(rows, columns=["schema_name", "table_name", "row_count", "seed_num", "patient_count",
                                       "run_id", "run_ts", "git_commit_sha"])
