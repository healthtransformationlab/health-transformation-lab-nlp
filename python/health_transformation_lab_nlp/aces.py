"""ACES: the 2018 periodontal status classification applied to epidemiological survey data
(Holtfreter et al., J Clin Periodontol 2024;51:512-521, doi:10.1111/jcpe.13965), from site and tooth
tables (spec 006 layout). Spec 013 G1-G3.

The primary paper is not open access; the rules below are as stated by three open papers that apply
ACES: Tay et al. 2025 (NHANES; PMC12176459), Holde et al. 2025 (Norway; PMC12003053) and Nafz et al.
2026 (SHIP-TREND; PMC13263721). Where they differ, the choice is a parameter (AcesRules).

    exclude       third molars (and, in survey data, implants and primary teeth)
    edentulous    no teeth left
    non-classified  fewer than two non-adjacent teeth that can be assessed
    case          interproximal CAL >= 1 mm at >= 2 non-adjacent teeth, or buccal/oral CAL >= 3 mm with
                  PD > 3 mm at the same site at >= 2 teeth (Tay: PD > 3; Holde: PD >= 3)
    stage         worst interproximal CAL: 1-2 mm I, 3-4 mm II, >= 5 mm III/IV
    complexity    II -> III with PD >= 6 mm at >= 2 non-adjacent teeth (distal sites of second molars
                  ignored); III vs IV by stage4_rule:
                    opposing_pairs     < 10 opposing pairs of natural teeth -> IV (Tay; Nafz)
                    teeth20            < 20 teeth -> IV (Holde)
                    teeth_lost_perio   >= 5 teeth recorded as lost to periodontitis -> IV (2018 criterion)
                    all_missing_perio  every missing tooth counted as lost to periodontitis
                  complexity=False reports 'periodontitis_stage_3_4'
    not a case    healthy, or gingivitis when bleeding on probing >= bop_gingivitis_pct of sites
                  (10%, Chapple et al. 2018; the ACES threshold is not confirmed from the primary paper)
    extent        generalized when >= 30% of teeth have interproximal CAL >= the case threshold

case_cal_min_mm=3 gives the stricter case definition (CAL above 2 mm) reported to improve accuracy
against chart review in a dental-school phenotyping algorithm (Tokede et al.).
R twin: r/R/12_spec013.R.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .telemetry import traced

THIRD_MOLARS = {1, 16, 17, 32}
SECOND_MOLARS = {2, 15, 18, 31}
INTERPROXIMAL = {"MB", "DB", "ML", "DL"}
BUCCAL_ORAL = {"B", "L"}
DISTAL = {"DB", "DL"}
STAGE4_RULES = ("opposing_pairs", "teeth20", "teeth_lost_perio", "all_missing_perio")


@dataclass(frozen=True)
class AcesRules:
    case_cal_min_mm: float = 1.0
    buccal_cal_min_mm: float = 3.0
    buccal_pd_min_mm: float = 3.5        # PD > 3 mm (whole-mm charts); 3 gives Holde's >= 3
    complexity: bool = True
    stage4_rule: str = "opposing_pairs"
    bop_gingivitis_pct: float = 10.0

    def __post_init__(self):
        if self.stage4_rule not in STAGE4_RULES:
            raise ValueError(f"stage4_rule must be one of {STAGE4_RULES}")


DEFAULT = AcesRules()


def _non_adjacent(teeth) -> bool:
    """At least two teeth that are not neighbours in the same arch (universal numbering)."""
    t = sorted(set(teeth))
    if len(t) >= 3:
        return True
    if len(t) < 2:
        return False
    a, b = t
    same_arch = (a <= 16) == (b <= 16)
    return not (same_arch and b - a == 1)


@traced
def opposing_pair_count(present) -> int:
    """Opposing pairs among the present teeth (tooth numbers), third molars excluded: upper t opposes lower 33 - t.
    Also read by labels.stage4_tooth_counts (spec 032 US4)."""
    present = {int(t) for t in present}
    return sum(1 for t in range(2, 16) if t in present and 33 - t in present)


@traced
def occluding_pairs(teeth: pd.DataFrame) -> int:
    """Opposing pairs of present natural teeth, third molars excluded: upper t opposes lower 33 - t."""
    return opposing_pair_count(teeth.loc[teeth["present"].astype(bool), "tooth"])


@traced
def aces(sites: pd.DataFrame, teeth: pd.DataFrame, rules: AcesRules = DEFAULT) -> dict:
    """One exam. sites: tooth, site, cal_mm, pd_mm, bop. teeth: tooth, present, missing_reason."""
    r = rules
    tt = teeth[~teeth["tooth"].isin(THIRD_MOLARS)]
    present = set(tt.loc[tt["present"].astype(bool), "tooth"])
    s = sites[sites["tooth"].isin(present)]
    out = {"status": None, "case_route": "", "max_ip_cal_mm": None, "n_teeth": len(present),
           "occluding_pairs": occluding_pairs(teeth), "extent": "NA"}
    if not present:
        return {**out, "status": "edentulous"}
    ip = s[s["site"].isin(INTERPROXIMAL)].dropna(subset=["cal_mm"])
    if not _non_adjacent(ip["tooth"]):
        return {**out, "status": "non_classified"}
    ip_case = set(ip.loc[ip["cal_mm"] >= r.case_cal_min_mm, "tooth"])
    bo = s[s["site"].isin(BUCCAL_ORAL)]
    bo_case = set(bo.loc[(bo["cal_mm"] >= r.buccal_cal_min_mm) & (bo["pd_mm"] >= r.buccal_pd_min_mm), "tooth"])
    route = "interproximal" if _non_adjacent(ip_case) else "buccal_oral" if len(bo_case) >= 2 else ""
    m = float(ip["cal_mm"].max())
    out.update(case_route=route, max_ip_cal_mm=m)
    if not route:
        bop_pct = 100.0 * float(s["bop"].astype(bool).mean()) if len(s) else 0.0
        return {**out, "status": "gingivitis" if bop_pct >= r.bop_gingivitis_pct else "healthy"}
    out["extent"] = "generalized" if len(ip_case) / len(present) >= 0.30 else "localized"
    if m < 3:
        stage = "1"
    elif m < 5:
        deep = s[(s["pd_mm"] >= 6) & ~(s["tooth"].isin(SECOND_MOLARS) & s["site"].isin(DISTAL))]
        stage = "3" if r.complexity and _non_adjacent(deep["tooth"]) else "2"
    elif not r.complexity:
        stage = "3_4"
    else:
        missing = tt[~tt["present"].astype(bool)]
        four = {"opposing_pairs": out["occluding_pairs"] < 10,
                "teeth20": len(present) < 20,
                "teeth_lost_perio": int((missing["missing_reason"] == "perio").sum()) >= 5,
                "all_missing_perio": len(missing) >= 5}[r.stage4_rule]
        stage = "4" if four else "3"
    return {**out, "status": f"periodontitis_stage_{stage}"}


def _non_adjacent_by(df: pd.DataFrame, key: str, index) -> pd.Series:
    """_non_adjacent per key over the distinct teeth in df, vectorized; False for keys with no rows."""
    g = df.drop_duplicates([key, "tooth"]).groupby(key)["tooth"].agg(["nunique", "min", "max"])
    two_adjacent = (g["nunique"] == 2) & (g["max"] - g["min"] == 1) & ((g["min"] <= 16) == (g["max"] <= 16))
    ok = (g["nunique"] >= 3) | ((g["nunique"] == 2) & ~two_adjacent)
    return ok.reindex(index, fill_value=False)


@traced
def aces_all(sites: pd.DataFrame, teeth: pd.DataFrame, rules: AcesRules = DEFAULT,
             key: str = "visit_id") -> pd.DataFrame:
    """aces() for every exam at once (same rules, vectorized); one row per `key`."""
    r = rules
    idx = pd.Index(sorted(teeth[key].unique()), name=key)
    tt = teeth[~teeth["tooth"].isin(THIRD_MOLARS)]
    pres = tt[tt["present"].astype(bool)]
    n_teeth = pres.groupby(key).size().reindex(idx, fill_value=0)
    wide = teeth.assign(p=teeth["present"].astype(bool)).pivot_table(index=key, columns="tooth", values="p",
                                                                       aggfunc="max", fill_value=False)
    wide = wide.reindex(index=idx, columns=range(1, 33), fill_value=False).astype(bool)
    pairs = sum((wide[t] & wide[33 - t]).astype(int) for t in range(2, 16))
    s = sites.merge(pres[[key, "tooth"]], on=[key, "tooth"])
    ip = s[s["site"].isin(INTERPROXIMAL) & s["cal_mm"].notna()]
    assessable = _non_adjacent_by(ip, key, idx)
    ip_hit = ip[ip["cal_mm"] >= r.case_cal_min_mm]
    ip_case = _non_adjacent_by(ip_hit, key, idx)
    n_case_teeth = ip_hit.groupby(key)["tooth"].nunique().reindex(idx, fill_value=0)
    bo = s[s["site"].isin(BUCCAL_ORAL)]
    bo_hit = bo[(bo["cal_mm"] >= r.buccal_cal_min_mm) & (bo["pd_mm"] >= r.buccal_pd_min_mm)]
    bo_case = bo_hit.groupby(key)["tooth"].nunique().reindex(idx, fill_value=0) >= 2
    m = ip.groupby(key)["cal_mm"].max().reindex(idx)
    bop = (100.0 * s["bop"].astype(bool).groupby(s[key]).mean()).reindex(idx, fill_value=0.0)
    deep = s[(s["pd_mm"] >= 6) & ~(s["tooth"].isin(SECOND_MOLARS) & s["site"].isin(DISTAL))]
    pd6 = _non_adjacent_by(deep, key, idx)
    miss = tt[~tt["present"].astype(bool)]
    n_missing = miss.groupby(key).size().reindex(idx, fill_value=0)
    n_lost_perio = (miss["missing_reason"] == "perio").groupby(miss[key]).sum().reindex(idx, fill_value=0)
    four = {"opposing_pairs": pairs < 10, "teeth20": n_teeth < 20,
            "teeth_lost_perio": n_lost_perio >= 5, "all_missing_perio": n_missing >= 5}[r.stage4_rule]

    route = pd.Series("", index=idx).mask(bo_case, "buccal_oral").mask(ip_case, "interproximal")
    case = route != ""
    mid = (m >= 3) & (m < 5)
    stage = pd.Series("1", index=idx).mask(mid, "2").mask(mid & pd6 & r.complexity, "3")
    stage = stage.mask(m >= 5, four.map({True: "4", False: "3"}) if r.complexity else "3_4")
    status = ("periodontitis_stage_" + stage).where(case, pd.Series("healthy", index=idx).mask(
        bop >= r.bop_gingivitis_pct, "gingivitis"))
    status = status.mask(~assessable, "non_classified").mask(n_teeth == 0, "edentulous")
    extent = pd.Series("localized", index=idx).mask(n_case_teeth / n_teeth.where(n_teeth > 0) >= 0.30,
                                                    "generalized").where(case & assessable, "NA")
    scored = assessable & (n_teeth > 0)
    return pd.DataFrame({key: idx, "status": status.to_numpy(), "case_route": route.where(scored, "").to_numpy(),
                         "max_ip_cal_mm": m.where(scored).to_numpy(),
                         "n_teeth": n_teeth.to_numpy(), "occluding_pairs": pairs.to_numpy(),
                         "extent": extent.to_numpy()})
