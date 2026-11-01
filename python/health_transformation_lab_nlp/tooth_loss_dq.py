"""Data-quality checks on an extract in Open Dental's format, run between bronze and the silver tooth table (spec 029
FR-009, T006a; #370). They follow Kookal et al. 2024 (references item 57; the NIH Collaboratory framework of Zozus et
al. 2014): completeness, accuracy and consistency, adapted to these tables, plus checks for plan copies and for which
diagnosis list is in use. Each check reports what it found; nothing is fixed silently.

`group_consistency` adds the consistency split the study lead asked about: is the perio chart kept as well for every
group of patients (office, provider, sex, race, exam year, age band)? Each group is compared with the rest of its
type (mean and SD of the others), flagged beyond 2 SD and at least `MIN_GAP` apart; a group needs `MIN_CHARTS`
charts to be flagged or to count among the rest. Kookal et al. compared 30 offices
with the mean of all of them; with 4 offices one outlier can never sit 2 SD from a mean that includes it, hence the
comparison with the rest. The groups are provisional until the study lead names his.

Counts only: no row-level data leaves these functions. Synthetic data in this repo; `open_dental.plant_faults` plants
a known number of each fault so the tests know what each check must find."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

import pandas as pd

from . import open_dental as od
from .telemetry import traced

MIN_GAP = 0.05                       # a flagged group also differs from the rest by at least 5 points
MIN_CHARTS = 30                      # groups with fewer charts are reported, never flagged or used as the rest
RESULT_COLUMNS = ["check_num", "domain_code", "check_name", "table_name", "checked_count", "found_count",
                  "found_ratio", "is_flagged"]
GROUP_COLUMNS = ["group_type_code", "group_name", "metric_name", "chart_count", "value_ratio", "rest_mean_ratio",
                 "rest_sd_ratio", "is_flagged"]
CDT = re.compile(r"^D\d{4}[a-z]?$")              # CDT codes, with a practice's lettered variants (D0120a)
ICD10 = re.compile(r"^[A-TV-Z]\d[0-9A-Z](\.[0-9A-Z]{1,4})?$")
VALUE_SETS = {("patient", "gender"): {0, 1, 2}, ("procedurelog", "procstatus"): {1, 2, 3, 4, 5, 6, 7, 8},
              ("periomeasure", "sequencetype"): set(range(8)), ("toothinitial", "initialtype"): set(range(12))}
TOOTH_FIELDS = [("procedurelog", "toothnum"), ("toothinitial", "toothnum"), ("proctp", "toothnumtp")]


@dataclass(frozen=True)
class Check:
    num: int | None                  # after Kookal et al. 2024 (their Table 1 order); None for checks added here
    domain: str
    name: str
    table: str
    text: str


CHECKS = [
    Check(1, "completeness", "columns_as_declared", "all", "every declared column is present and none extra"),
    Check(2, "completeness", "values_as_declared", "all", "dates parse and coded fields hold declared values"),
    Check(3, "completeness", "one_value_per_field", "procedurelog, toothinitial, proctp",
          "a tooth field holds one tooth"),
    Check(4, "completeness", "missing_value_share", "all", "null, blank or unknown cells, as a share (reported)"),
    Check(5, "completeness", "duplicate_row", "procedurelog", "rows the same in every column but the key"),
    Check(6, "completeness", "duplicate_key", "patient, procedurelog, toothinitial",
          "a patient, procedure or tooth key used twice"),
    Check(7, "completeness", "tooth_table_value_missing", "procedurelog",
          "an extraction the tooth table needs lacks its tooth, or a completed one its date"),
    Check(8, "accuracy", "probing_out_of_range", "periomeasure", "a probing depth over 15 mm or below -1"),
    Check(8, "accuracy", "mobility_out_of_range", "periomeasure", "a mobility grade outside 0–3"),
    Check(8, "accuracy", "tooth_number_out_of_range", "procedurelog, toothinitial, periomeasure",
          "a tooth number outside 1–32"),
    Check(8, "accuracy", "dates_out_of_order", "procedurelog", "completed before it was planned"),
    Check(9, "accuracy", "procedure_code_not_cdt", "procedurecode", "a code not in CDT form"),
    Check(9, "accuracy", "diagnosis_not_in_lists", "procedurelog", "a diagnosis item in neither declared list"),
    Check(9, "accuracy", "icd_not_valid", "procedurelog", "an ICD-10 code not in ICD-10-CM form"),
    Check(None, "plan_copy", "plan_copy_without_original", "proctp", "a plan copy whose procedure is gone"),
    Check(None, "plan_copy", "plan_copy_differs", "proctp",
          "a plan copy whose code, tooth or diagnosis text differs from its procedure"),
    Check(None, "list_in_use", "older_item_after_switch", "procedurelog", "an older-list item after the switch date"),
    Check(None, "list_in_use", "newer_item_before_switch", "procedurelog", "a 2017-list item before the switch date"),
    Check(12, "consistency", "office_missing_share", "every table naming a patient",
          "an office whose missing-value share is beyond 2 SD of the other offices"),
]


def _is_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Null, NaN or blank text (Open Dental stores blank text, not NULL)."""
    return df.isna() | df.apply(lambda c: c.astype(str).str.strip().eq("") if c.dtype == object else False)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


@traced
def flag_against_rest(values: pd.Series) -> pd.DataFrame:
    """Each value against the mean and SD of the others: flagged beyond 2 SD and at least MIN_GAP away; when the
    others don't vary at all, any gap of MIN_GAP flags; with one other value there is no SD and no flag."""
    rows = []
    for k, v in values.items():
        rest = values.drop(k)
        m, sd = rest.mean(), rest.std(ddof=1) if len(rest) > 1 else float("nan")
        gap = abs(v - m)
        flag = bool(len(rest) > 1 and gap >= MIN_GAP and (sd == 0 or gap > 2 * sd))
        rows.append((k, m, sd, flag))
    out = pd.DataFrame(rows, columns=["key", "rest_mean_ratio", "rest_sd_ratio", "is_flagged"]).set_index("key")
    out.index.name = values.index.name
    return out


@traced
def office_missing(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Kookal et al.'s consistency check: each office's share of missing cells, across every table that names a
    patient, against the other offices. One row per office."""
    office = dict(zip(_num(tables["patient"]["patnum"]), tables["patient"]["clinicnum"]))
    cells, missing = {}, {}
    for name, df in tables.items():
        if "patnum" not in df.columns or name == "patient":
            continue
        miss = _is_missing(df).sum(axis=1)
        o = _num(df["patnum"]).map(office)
        for k, n in miss.groupby(o).sum().items():
            missing[k] = missing.get(k, 0) + int(n)
        for k, n in o.value_counts().items():
            cells[k] = cells.get(k, 0) + int(n) * df.shape[1]
    share = pd.Series({k: missing[k] / cells[k] for k in cells}).sort_index()
    share.index = share.index.map(lambda x: str(int(x)))
    f = flag_against_rest(share)
    return pd.DataFrame({"group_name": share.index, "value_ratio": share.values, "cell_count": [cells[int(k)] for k in
                                                                                               share.index],
                         "rest_mean_ratio": f["rest_mean_ratio"].values, "rest_sd_ratio": f["rest_sd_ratio"].values,
                         "is_flagged": f["is_flagged"].values})


@traced
def run_checks(tables: dict[str, pd.DataFrame], switch_date: date = od.Params.list_switch_date) -> pd.DataFrame:
    """One row per check in CHECKS: what was checked, what was found, the share, and whether it is flagged (any
    fault found; the missing-value share is reported, not flagged)."""
    t = tables
    res = {}
    # 1 columns as declared
    found = sum(len(set(od.TABLES[n]) ^ set(df.columns)) for n, df in t.items() if n in od.TABLES)
    res["columns_as_declared"] = (sum(len(od.TABLES[n]) for n in t if n in od.TABLES), found)
    # 2 values as declared: date columns parse, coded fields in their value sets
    checked = bad = 0
    for n, df in t.items():
        for c in df.columns:
            if c in od.DATES:
                v = df[c].dropna()
                v = v[v.astype(str).str.strip() != ""]
                checked += len(v)
                bad += int(pd.to_datetime(v, errors="coerce").isna().sum())
            if (n, c) in VALUE_SETS:
                v = _num(df[c])
                checked += len(v)
                bad += int((~v.isin(VALUE_SETS[(n, c)])).sum())
    res["values_as_declared"] = (checked, bad)
    # 3 one tooth per tooth field
    vals = pd.concat([t[n][c].astype(str) for n, c in TOOTH_FIELDS if n in t])
    vals = vals[vals.str.strip() != ""]
    res["one_value_per_field"] = (len(vals), int(vals.str.contains(r"[,;\s-]").sum()))
    # 4 missing share over every cell
    total = sum(df.size for df in t.values())
    res["missing_value_share"] = (total, int(sum(_is_missing(df).to_numpy().sum() for df in t.values())))
    # 5 duplicate rows (all columns but the key), 6 duplicate keys
    pl = t["procedurelog"]
    res["duplicate_row"] = (len(pl), int(pl.drop(columns="procnum").duplicated().sum()))
    keys = [("patient", ["patnum"]), ("procedurelog", ["procnum"]), ("toothinitial", ["patnum", "toothnum",
                                                                                      "initialtype"])]
    res["duplicate_key"] = (sum(len(t[n]) for n, _ in keys), int(sum(t[n].duplicated(k).sum() for n, k in keys)))
    # 7 what the tooth table needs: an extraction's tooth, a completed extraction's date
    ext = pl[_num(pl["codenum"]).isin(od.extraction_codenums(t)) & _num(pl["procstatus"]).isin([od.PLANNED,
                                                                                                od.COMPLETE])]
    no_tooth = _num(ext["toothnum"]).isna()
    no_date = (_num(ext["procstatus"]) == od.COMPLETE) & _is_missing(ext[["datecomplete"]])["datecomplete"]
    res["tooth_table_value_missing"] = (len(ext), int((no_tooth | no_date).sum()))
    # 8 ranges
    pm = t["periomeasure"]
    probe = pm.loc[_num(pm["sequencetype"]) == od.SEQ_PROBING, od.SITE_VALUES].apply(_num)
    measured = probe.notna() & (probe != -1)
    res["probing_out_of_range"] = (int(measured.to_numpy().sum()), int(((probe > 15) | (probe < -1)).to_numpy().sum()))
    mob = _num(pm.loc[_num(pm["sequencetype"]) == od.SEQ_MOBILITY, "toothvalue"])
    mob = mob[mob != -1]
    res["mobility_out_of_range"] = (len(mob), int((~mob.between(0, 3)).sum()))
    teeth = pd.concat([_num(pl["toothnum"]), _num(t["toothinitial"]["toothnum"]), _num(pm["inttooth"])]).dropna()
    res["tooth_number_out_of_range"] = (len(teeth), int((~teeth.between(1, 32)).sum()))
    done = pl[(_num(pl["procstatus"]) == od.COMPLETE)]
    tp_d, dc = pd.to_datetime(done["datetp"], errors="coerce"), pd.to_datetime(done["datecomplete"], errors="coerce")
    both = tp_d.notna() & dc.notna()
    res["dates_out_of_order"] = (int(both.sum()), int((dc[both] < tp_d[both]).sum()))
    # 9 code sets
    pc = t["procedurecode"]["proccode"].astype(str)
    res["procedure_code_not_cdt"] = (len(pc), int((~pc.str.match(CDT)).sum()))
    d = t["definition"]
    names = dict(zip(_num(d["defnum"]), d["itemname"]))
    dx = _num(pl["dx"]).fillna(0)
    with_dx = dx[dx != 0]
    res["diagnosis_not_in_lists"] = (len(with_dx), int((~with_dx.map(names).isin(od.DIAGNOSIS_LOOKUP)).sum()))
    icd = pl.loc[(_num(pl["icdversion"]) == 10), "diagnosticcode"].astype(str)
    res["icd_not_valid"] = (len(icd), int((~icd.str.match(ICD10)).sum()))
    # plan copies against their procedure
    tp = t["proctp"].copy()
    orig = pl[["procnum", "codenum", "toothnum", "dx"]].rename(columns={"toothnum": "o_tooth", "dx": "o_dx"})
    orig["procnum"] = _num(orig["procnum"])
    tp["procnumorig"] = _num(tp["procnumorig"])
    m = tp.merge(orig, left_on="procnumorig", right_on="procnum", how="left", indicator=True)
    gone = m["_merge"] == "left_only"
    res["plan_copy_without_original"] = (len(tp), int(gone.sum()))
    code_of = dict(zip(_num(t["procedurecode"]["codenum"]), t["procedurecode"]["proccode"]))
    k = m[~gone]
    differs = (k["proccode"].astype(str) != _num(k["codenum"]).map(code_of).astype(str)) | \
        (_num(k["toothnumtp"]) != _num(k["o_tooth"])) | \
        (k["dx"].fillna("").astype(str) != _num(k["o_dx"]).map(names).fillna("").astype(str))
    res["plan_copy_differs"] = (len(k), int(differs.sum()))
    # which list is in use, by the procedure's date
    older = {n for n, _, _ in od.OLDER_LIST}
    newer = {n for n, _, _ in od.LIST_2017}
    when = pd.to_datetime(pl["datetp"].where(pl["datetp"].notna(), pl["procdate"]), errors="coerce")
    item = dx.map(names)
    after = when >= pd.Timestamp(switch_date)
    res["older_item_after_switch"] = (int((dx != 0).sum()), int((item.isin(older) & after).sum()))
    res["newer_item_before_switch"] = (int((dx != 0).sum()), int((item.isin(newer) & ~after & when.notna()).sum()))
    # 12 consistency across offices
    om = office_missing(t)
    res["office_missing_share"] = (len(om), int(om["is_flagged"].sum()))

    rows = []
    for c in CHECKS:
        n, f = res[c.name]
        rows.append({"check_num": c.num, "domain_code": c.domain, "check_name": c.name, "table_name": c.table,
                     "checked_count": int(n), "found_count": int(f), "found_ratio": f / n if n else float("nan"),
                     "is_flagged": pd.NA if c.name == "missing_value_share" else f > 0})
    out = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    out["check_num"] = out["check_num"].astype("Int64")
    out["is_flagged"] = out["is_flagged"].astype("boolean")
    return out


def _age_band(age: float) -> str:
    return "under 30" if age < 30 else "30–44" if age < 45 else "45–64" if age < 65 else "65 and over"


@traced
def group_consistency(tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """For each group of each type (office, provider, sex, race, exam year, age band): how many of its perio charts
    have no gum-margin readings (so no attachment loss), and how many are incomplete in any way (partial, buccal
    only, no margin or no bleeding), each against the rest of its type (`flag_against_rest`)."""
    q = od.chart_quality(tables)
    ex = tables["perioexam"][["perioexamnum", "provnum"]].assign(perioexamnum=lambda x: _num(x["perioexamnum"]))
    q = q.merge(ex, on="perioexamnum", how="left")
    pat = tables["patient"].assign(patnum=lambda x: _num(x["patnum"])).drop_duplicates("patnum")
    race = tables["patientrace"].assign(patnum=lambda x: _num(x["patnum"]))
    race = race[race["cdcreccode"].astype(str).isin([c for c, h, _ in od.CDCREC if h.startswith("R")])]
    race_name = {c: d for c, _, d in od.CDCREC}
    q["office"] = q["patnum"].map(dict(zip(pat["patnum"], pat["clinicnum"])))
    q["provider"] = q["provnum"]
    q["sex"] = q["patnum"].map(dict(zip(pat["patnum"], _num(pat["gender"])))).map(
        {0: "male", 1: "female", 2: "unknown"})
    q["race"] = q["patnum"].map(race.drop_duplicates("patnum").set_index("patnum")["cdcreccode"]).map(race_name)
    q["exam_year"] = q["examdate"].dt.year
    born = pd.to_datetime(q["patnum"].map(dict(zip(pat["patnum"], pat["birthdate"]))), errors="coerce")
    q["age_band"] = ((q["examdate"] - born).dt.days / 365.25).map(_age_band)
    q["no_margin_chart"] = ~q["has_margin"]
    q["incomplete_chart"] = q["is_partial"] | q["is_buccal_only"] | ~q["has_margin"] | ~q["has_bleeding"]
    rows = []
    for gtype in ["office", "provider", "sex", "race", "exam_year", "age_band"]:
        key = q[gtype].map(lambda x: "unknown" if pd.isna(x) else str(int(x)) if isinstance(x, float) else str(x))
        for metric in ["no_margin_chart", "incomplete_chart"]:
            g = q.groupby(key)[metric]
            share, n = g.mean(), g.size()
            f = flag_against_rest(share[n >= MIN_CHARTS]).reindex(share.index)
            f["is_flagged"] = f["is_flagged"].astype("boolean").fillna(False)
            for name in share.index:
                rows.append({"group_type_code": gtype, "group_name": name, "metric_name": metric,
                             "chart_count": int(n[name]), "value_ratio": float(share[name]),
                             "rest_mean_ratio": f.at[name, "rest_mean_ratio"],
                             "rest_sd_ratio": f.at[name, "rest_sd_ratio"], "is_flagged": bool(f.at[name, "is_flagged"])})
    return pd.DataFrame(rows, columns=GROUP_COLUMNS)
