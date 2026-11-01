"""Reliability of clinical attachment loss (CAL) in repeated charts (spec 013 G5).

Agreement asks how close two measurements of the same site are; reliability asks whether that
error still lets us tell patients, teeth and sites apart (de Vet et al. 2006).
Model: CAL = b0 + b1 * years + patient + tooth(patient) + site(tooth) + error, all random but time.

    icc_patient   two sites in the same mouth            var_p / total
    icc_tooth     two sites on the same tooth            (var_p + var_t) / total
    icc_site      the same site charted again             (var_p + var_t + var_s) / total
    sem_mm        standard error of one measurement      sqrt(var_error)

`nested_components` uses the balanced nested ANOVA (method of moments) after removing the
time trend, so R (r/R/12_spec013.R) matches it exactly. Real charts are unbalanced (missing teeth,
different numbers of visits): use `reml_components` (statsmodels mixed model, REML) there; the
two agree on balanced data (test).

`draw_repeated_charts` is SYNTHETIC: the variance components, progression and whole-mm rounding
are planning placeholders, not estimates.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .telemetry import traced

SITES = ["MB", "B", "DB", "ML", "L", "DL"]
COMPONENTS = ["var_patient", "var_tooth", "var_site", "var_error"]


@dataclass(frozen=True)
class CalParams:
    mean_mm: float = 2.0
    sd_patient: float = 1.0
    sd_tooth: float = 0.6
    sd_site: float = 0.5
    sd_error: float = 0.8           # one examiner probing the same site again
    mm_per_year: float = 0.1
    years_between_visits: float = 1.0
    round_mm: bool = True           # charts record whole millimetres, never below 0


@traced
def draw_repeated_charts(n_patients: int, n_teeth: int, n_visits: int, params: CalParams,
                         seed: int = 0) -> pd.DataFrame:
    """Balanced: every patient has n_teeth charted teeth, six sites each, at n_visits visits."""
    rng = np.random.default_rng(seed)
    p = params
    u_p = rng.normal(0, p.sd_patient, n_patients)
    u_t = rng.normal(0, p.sd_tooth, (n_patients, n_teeth))
    u_s = rng.normal(0, p.sd_site, (n_patients, n_teeth, 6))
    years = np.arange(n_visits) * p.years_between_visits
    e = rng.normal(0, p.sd_error, (n_patients, n_teeth, 6, n_visits))
    cal = (p.mean_mm + u_p[:, None, None, None] + u_t[:, :, None, None] + u_s[:, :, :, None]
           + p.mm_per_year * years[None, None, None, :] + e)
    if p.round_mm:
        cal = np.clip(np.round(cal), 0, None)
    i, t, s, v = np.meshgrid(np.arange(n_patients), np.arange(n_teeth), np.arange(6), np.arange(n_visits),
                             indexing="ij")
    return pd.DataFrame({"patient_id": i.ravel() + 1, "tooth": t.ravel() + 1,
                         "site": np.array(SITES)[s.ravel()], "visit": v.ravel() + 1,
                         "years": years[v.ravel()], "cal_mm": cal.ravel()})


@traced
def nested_components(d: pd.DataFrame) -> dict:
    """Balanced nested ANOVA on CAL after an OLS time trend. Negative estimates are set to 0."""
    x, y = d["years"].to_numpy(float), d["cal_mm"].to_numpy(float)
    slope = float(np.sum((x - x.mean()) * (y - y.mean())) / np.sum((x - x.mean()) ** 2)) if x.var() > 0 else 0.0
    r = d.assign(res=y - slope * x)
    a = r["patient_id"].nunique()
    b = r.groupby("patient_id")["tooth"].nunique().iloc[0]
    c = r.groupby(["patient_id", "tooth"])["site"].nunique().iloc[0]
    n = len(r) // (a * b * c)
    m_site = r.groupby(["patient_id", "tooth", "site"])["res"].transform("mean")
    m_tooth = r.groupby(["patient_id", "tooth"])["res"].transform("mean")
    m_pat = r.groupby("patient_id")["res"].transform("mean")
    grand = r["res"].mean()
    ms_e = float(((r["res"] - m_site) ** 2).sum()) / (a * b * c * (n - 1))
    ms_s = float(((m_site - m_tooth) ** 2).sum()) / (a * b * (c - 1))
    ms_t = float(((m_tooth - m_pat) ** 2).sum()) / (a * (b - 1))
    ms_p = float(((m_pat - grand) ** 2).sum()) / (a - 1)
    return {"slope_mm_per_year": slope, "var_error": ms_e,
            "var_site": max(0.0, (ms_s - ms_e) / n), "var_tooth": max(0.0, (ms_t - ms_s) / (c * n)),
            "var_patient": max(0.0, (ms_p - ms_t) / (b * c * n)),
            "n_patients": a, "n_teeth": int(b), "n_sites": int(c), "n_visits": int(n)}


@traced
def reml_components(d: pd.DataFrame) -> dict:
    """Mixed model by REML (statsmodels): random patient intercept, tooth and site variance components,
    years as fixed effect. For unbalanced real charts."""
    import statsmodels.formula.api as smf
    df = d.assign(tooth_key=d["tooth"].astype(str), site_key=d["tooth"].astype(str) + "_" + d["site"])
    m = smf.mixedlm("cal_mm ~ years", df, groups="patient_id", re_formula="1",
                    vc_formula={"tooth": "0 + C(tooth_key)", "site": "0 + C(site_key)"}).fit(reml=True)
    vc = dict(zip(m.model.exog_vc.names, m.vcomp))
    return {"slope_mm_per_year": float(m.fe_params["years"]), "var_patient": float(m.cov_re.iloc[0, 0]),
            "var_tooth": float(vc["tooth"]), "var_site": float(vc["site"]), "var_error": float(m.scale)}


@traced
def write_charts(d: pd.DataFrame, path) -> None:
    """CSV, gzipped without a timestamp or file name in the header: the same charts give the same bytes, so
    rerunning the script doesn't show up as a change in git."""
    import gzip
    from pathlib import Path
    Path(path).write_bytes(gzip.compress(d.to_csv(index=False).encode(), mtime=0))


@traced
def icc_report(c: dict) -> dict:
    vp, vt, vs, ve = (c[k] for k in COMPONENTS)
    total = vp + vt + vs + ve
    return {"icc_patient": vp / total, "icc_tooth": (vp + vt) / total, "icc_site": (vp + vt + vs) / total,
            "sem_mm": ve ** 0.5, "total_var": total}


@traced
def cal_band(max_cal_mm: float) -> str:
    """2017 AAP/EFP severity band from the worst interdental CAL: <1 (no periodontitis by CAL),
    1-2 (stage I), 3-4 (stage II), >=5 (stage III or IV)."""
    return "<1" if max_cal_mm < 1 else "1-2" if max_cal_mm < 3 else "3-4" if max_cal_mm < 5 else ">=5"


@traced
def stage_band_flips(d: pd.DataFrame) -> dict:
    """What the error does to staging: the worst interproximal CAL per patient and visit, banded; the
    share of consecutive visit pairs whose band changes, and the share where it goes down (implausible
    without treatment)."""
    ip = d[d["site"].isin(["MB", "DB", "ML", "DL"])]
    worst = ip.groupby(["patient_id", "visit"])["cal_mm"].max().reset_index().sort_values(["patient_id", "visit"])
    worst["band"] = worst["cal_mm"].map(lambda x: ["<1", "1-2", "3-4", ">=5"].index(cal_band(x)))
    prev = worst.groupby("patient_id")["band"].shift()
    ok = prev.notna()
    cur, prev = worst.loc[ok, "band"], prev[ok]
    n = int(ok.sum())
    return {"pairs": n, "flip_rate": float((cur != prev).mean()) if n else 0.0,
            "down_rate": float((cur < prev).mean()) if n else 0.0}
