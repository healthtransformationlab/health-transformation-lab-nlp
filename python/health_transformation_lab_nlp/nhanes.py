"""NHANES 2009-2014 full-mouth periodontal exam (spec 013 G4): public charts from real people.

NHANES (CDC/NCHS, public domain) probed six sites on every tooth but third molars for adults 30+ in
2009-10, 2011-12 and 2013-14 (files OHXPER_F/G/H, teeth from OHXDEN_F/G/H, age and survey design
from DEMO_F/G/H). No notes, no diagnoses, no follow-up: it tests the chart algorithms (CDC/AAP 2012,
ACES) on real mouths and checks this repo's code against the published prevalence.

Site letters are read from each variable's SAS label, not hard-coded, so a mislabelled mapping fails
loudly. Values 99 (not assessable) are missing. Teeth: tooth-count codes 2 (permanent) and
5 (permanent root fragment) count as present.

Prevalence is survey-weighted (six-year MEC weight = two-year weight / 3, as in Tay et al. 2025) with
Taylor-linearized standard errors over strata and PSUs and a Wald 95% interval. Domain (adults 30+
with a complete periodontal exam, or edentulous) is kept inside the full design.

The files are downloaded at run time (scripts/38_nhanes_perio.py, or the Databricks job
`nhanes_perio`); only the aggregate table is committed.
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

from .telemetry import traced

CYCLES = {"F": "2009", "G": "2011", "H": "2013"}
FILES = ("OHXPER", "OHXDEN", "DEMO")
URLS = ("https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/{year}/DataFiles/{name}_{suffix}.xpt",
        "https://wwwn.cdc.gov/Nchs/Nhanes/{year}-{year2}/{name}_{suffix}.XPT")
VAR = re.compile(r"^OHX(\d\d)(PC|LA)([A-Z])$")
TOOTH_COUNT = re.compile(r"^OHX(\d\d)TC$")
NOT_ASSESSED = 99
PRESENT_CODES = {2, 5}
# label keyword (lower case, no spaces or hyphens) -> site in spec 006 layout
SITE_WORDS = [("distofacial", "DB"), ("distobuccal", "DB"), ("mesiofacial", "MB"), ("mesiobuccal", "MB"),
              ("midfacial", "B"), ("midbuccal", "B"), ("distolingual", "DL"), ("mesiolingual", "ML"),
              ("midlingual", "L")]
# the abbreviation tokens the OHXPER files of 2009-2014 use ('LOA: Max R(2M) DF FGM-sulcus(mm)'), matched as
# whole words because DF is inside MdF
SITE_TOKENS = {"DF": "DB", "MdF": "B", "MF": "MB", "DL": "DL", "MdL": "L", "ML": "ML"}


@traced
def download(dest: Path) -> list[Path]:
    """Fetch the nine XPT files into dest (skips ones already there)."""
    dest.mkdir(parents=True, exist_ok=True)
    got = []
    for suffix, year in CYCLES.items():
        for name in FILES:
            path = dest / f"{name}_{suffix}.xpt"
            if not path.exists():
                for u in URLS:
                    url = u.format(year=year, year2=int(year) + 1, name=name, suffix=suffix)
                    try:
                        urllib.request.urlretrieve(url, path)
                        break
                    except OSError:
                        path.unlink(missing_ok=True)
                else:
                    raise OSError(f"could not download {name}_{suffix} from cdc.gov")
            got.append(path)
    return got


def _text(v) -> str:
    """Some pandas versions give XPORT field names and labels as bytes (padded with spaces)."""
    return (v.decode("latin-1") if isinstance(v, bytes) else str(v or "")).strip()


@traced
def read_xpt(path: Path) -> tuple[pd.DataFrame, dict[str, str]]:
    """Data and {variable: SAS label}, as text whatever pandas version reads them."""
    with pd.read_sas(path, format="xport", iterator=True) as r:
        labels = {_text(f["name"]): _text(f.get("label")) for f in r.fields}
        return r.read(), labels


@traced
def sites_from_labels(labels: dict[str, str]) -> dict[tuple[str, str, str], str]:
    """(tooth, measure, letter) -> site, from labels such as 'LOA: Max R(2M) DF FGM-sulcus(mm)' (the real files)
    or 'Pocket depth: ..., distofacial'."""
    out = {}
    for var, label in labels.items():
        m = VAR.match(var)
        if not m:
            continue
        site = next((SITE_TOKENS[t] for t in label.split() if t in SITE_TOKENS), None)
        if site is None:
            text = re.sub(r"[\s\-]", "", label.lower())
            site = next((s for w, s in SITE_WORDS if w in text), None)
        if site is None:
            raise ValueError(f"{var}: no site in label {label!r}")
        out[m.groups()] = site
    return out


@traced
def to_site_tables(per: pd.DataFrame, den: pd.DataFrame, labels: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Wide NHANES exam -> sites (SEQN, tooth, site, pd_mm, cal_mm, bop) and teeth (SEQN, tooth, present,
    missing_reason, furcation_class, mobility_degree). Universal tooth numbers, as NHANES uses."""
    smap = sites_from_labels(labels)
    long = per.melt(id_vars="SEQN", value_vars=[v for v in per.columns if VAR.match(v)])
    parts = long["variable"].str.extract(VAR)
    long["tooth"] = parts[0].astype(int)
    long["measure"] = parts[1].map({"PC": "pd_mm", "LA": "cal_mm"})
    long["site"] = [smap[tuple(p)] for p in parts.itertuples(index=False)]
    long["value"] = long["value"].where(long["value"] != NOT_ASSESSED)
    sites = long.pivot_table(index=["SEQN", "tooth", "site"], columns="measure", values="value",
                             aggfunc="first", dropna=False).reset_index()
    sites.columns.name = None
    for c in ("pd_mm", "cal_mm"):
        if c not in sites:
            sites[c] = np.nan
    sites["bop"] = False                       # not recorded in 2009-2014
    tc = den.melt(id_vars="SEQN", value_vars=[v for v in den.columns if TOOTH_COUNT.match(v)])
    tc["tooth"] = tc["variable"].str.extract(TOOTH_COUNT)[0].astype(int)
    teeth = tc.assign(present=tc["value"].isin(PRESENT_CODES), missing_reason="", furcation_class=0,
                      mobility_degree=0)[["SEQN", "tooth", "present", "missing_reason", "furcation_class",
                                          "mobility_degree"]]
    present = teeth.loc[teeth["present"], ["SEQN", "tooth"]]
    sites = sites.merge(present, on=["SEQN", "tooth"])
    return sites[["SEQN", "tooth", "site", "pd_mm", "cal_mm", "bop"]], teeth


@traced
def weighted_prevalence(d: pd.DataFrame, col: str, w: str = "w", strata: str = "strata", psu: str = "psu",
                        domain: str = "domain", z: float = 1.959963984540054) -> pd.DataFrame:
    """Share of each category of `col` within the domain, % with linearized SE and Wald 95% CI.
    d holds every examined person in the design; rows outside the domain contribute zero."""
    dom = d[domain].astype(bool).to_numpy()
    wt = d[w].to_numpy(float) * dom
    tot = wt.sum()
    rows = []
    for cat in sorted(d.loc[dom, col].dropna().unique()):
        y = (d[col] == cat).to_numpy(float)
        p = float((wt * y).sum() / tot)
        zi = wt * (y - p) / tot
        g = pd.DataFrame({"h": d[strata].to_numpy(), "c": d[psu].to_numpy(), "z": zi})
        zc = g.groupby(["h", "c"])["z"].sum().reset_index()
        var = 0.0
        for _, gh in zc.groupby("h"):
            n = len(gh)
            if n > 1:
                var += n / (n - 1) * float(((gh["z"] - gh["z"].mean()) ** 2).sum())
        se = var ** 0.5
        rows.append({"category": cat, "pct": 100 * p, "se": 100 * se,
                     "ci_low": 100 * max(0.0, p - z * se), "ci_high": 100 * min(1.0, p + z * se),
                     "n_unweighted": int(((d[col] == cat) & dom).sum())})
    return pd.DataFrame(rows)


# spec 033 US4 (#500): age bands (lower, upper inclusive; None open) for complete tooth loss among adults 30+, the
# synthetic Open Dental extract's bands below 65 (open_dental.Params.edentulous_share_by_age). NHANES top-codes age at 80
EDENTULOUS_AGE_BANDS = ((30, 34), (35, 44), (45, 54), (55, 64), (65, 74), (75, None))


@traced
def edentulous_by_age(people: pd.DataFrame, bands=EDENTULOUS_AGE_BANDS) -> pd.DataFrame:
    """The weighted share with no natural teeth (third molars aside) in each age band, in the adults30_all domain
    (a complete periodontal exam, or edentulous), with its linearized 95% CI. `people`: classify_people's rows with
    `w`, `strata` and `psu`. One row per band; a band with nobody in it has no estimate."""
    rows = []
    for low, high in bands:
        age = people["RIDAGEYR"]
        dom = (age >= low) & ((age <= high) if high is not None else True) & \
            (people["perio_complete"] | people["edentulous"])
        row = {"age_band_low_num": low, "age_band_high_num": high, "edentulous_pct": float("nan"), "se": float("nan"),
               "ci_low": float("nan"), "ci_high": float("nan"), "n_unweighted": 0, "n_domain": int(dom.sum())}
        if dom.any():
            d = people.assign(domain=dom, category=people["edentulous"].map({True: "edentulous", False: "dentate"}))
            p = weighted_prevalence(d, "category").set_index("category")
            hit = p.loc["edentulous"] if "edentulous" in p.index else None
            row.update(edentulous_pct=float(hit["pct"]) if hit is not None else 0.0,
                       se=float(hit["se"]) if hit is not None else 0.0,
                       ci_low=float(hit["ci_low"]) if hit is not None else 0.0,
                       ci_high=float(hit["ci_high"]) if hit is not None else 0.0,
                       n_unweighted=int(hit["n_unweighted"]) if hit is not None else 0)
        rows.append(row)
    out = pd.DataFrame(rows)
    out["age_band_high_num"] = out["age_band_high_num"].astype("Int64")
    return out


@traced
def nhanes_cdc_aap_published() -> pd.DataFrame:
    """Published NHANES 2009-2014 prevalence, adults 30+, % (95% CI where given). Checked against the papers."""
    eke = "Eke et al. 2018 (PMC8094373)"     # dentate adults; mild and moderate reported together
    tay = "Tay et al. 2025 (PMC12176459)"    # all adults incl. edentulous
    rows = [(eke, "cdc_aap", "total", 42.2, None, None), (eke, "cdc_aap", "severe", 7.8, None, None),
            (eke, "cdc_aap", "mild_or_moderate", 34.4, None, None),
            (tay, "cdc_aap", "none", 54.3, 51.5, 57.1), (tay, "cdc_aap", "mild", 3.5, 3.0, 4.1),
            (tay, "cdc_aap", "moderate", 28.1, 26.0, 30.2), (tay, "cdc_aap", "severe", 7.3, 6.4, 8.3),
            (tay, "cdc_aap", "edentulous", 6.7, 5.6, 7.9),
            (tay, "aces", "healthy_gingivitis", 0.0, 0.0, 0.1), (tay, "aces", "periodontitis_stage_1", 17.9, 16.2, 19.8),
            (tay, "aces", "periodontitis_stage_2", 46.2, 44.0, 48.4), (tay, "aces", "periodontitis_stage_3", 16.7, 15.4, 18.1),
            (tay, "aces", "periodontitis_stage_4", 12.4, 11.3, 13.6), (tay, "aces", "non_classified", 0.1, 0.1, 0.2),
            (tay, "aces", "edentulous", 6.7, 5.6, 7.9)]
    return pd.DataFrame(rows, columns=["source", "classification", "category", "pct", "ci_low", "ci_high"])


@traced
def classify_people(per: pd.DataFrame, den: pd.DataFrame, demo: pd.DataFrame, labels: dict[str, str]) -> pd.DataFrame:
    """One cycle -> one row per person: age, design, exam status, edentulous, CDC/AAP and ACES categories."""
    from .aces import AcesRules, aces_all
    from .sites import cdc_aap, derive_all

    if "OHDPDSTS" not in per:
        raise KeyError("OHXPER has no OHDPDSTS (periodontal exam status)")
    if "OHDDESTS" not in den:
        raise KeyError("OHXDEN has no OHDDESTS (dentition exam status)")
    sites, teeth = to_site_tables(per, den, labels)
    natural = teeth[~teeth["tooth"].isin({1, 16, 17, 32})]
    n_teeth = natural[natural["present"]].groupby("SEQN").size()
    p = demo[["SEQN", "RIDAGEYR", "WTMEC2YR", "SDMVSTRA", "SDMVPSU"]].copy()
    p["perio_complete"] = p["SEQN"].map(per.set_index("SEQN")["OHDPDSTS"]).eq(1)
    # edentulous only when the dentition exam was done (OHDDESTS 1), every natural tooth has a code and none
    # is 2 or 5 (present): a skipped exam leaves the codes blank, which is missing, not zero teeth
    tc = [c for c in den if TOOTH_COUNT.match(c) and int(c[3:5]) not in (1, 16, 17, 32)]
    recorded = den.set_index("SEQN")[tc].notna().all(axis=1) & den.set_index("SEQN")["OHDDESTS"].eq(1)
    p["edentulous"] = (p["SEQN"].map(recorded).fillna(False).astype(bool)
                       & p["SEQN"].map(n_teeth).fillna(0).eq(0))
    d = derive_all(sites, teeth, key="SEQN")
    p["cdc_aap"] = p["SEQN"].map({k: cdc_aap(r) for k, r in d.to_dict("index").items()})
    five = {"healthy": "healthy_gingivitis", "gingivitis": "healthy_gingivitis"}   # no bleeding in 2009-2014
    for col, rules in (("aces", AcesRules()), ("aces_no_complexity", AcesRules(complexity=False))):
        a = aces_all(sites, teeth, rules, key="SEQN").set_index("SEQN")["status"].replace(five)
        p[col] = p["SEQN"].map(a)
    for c in ("cdc_aap", "aces", "aces_no_complexity"):
        p.loc[p["edentulous"], c] = "edentulous"
    return p
