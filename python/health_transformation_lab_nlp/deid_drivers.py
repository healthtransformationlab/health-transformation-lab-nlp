"""How each de-identification tool ranks, and what decides whether an identifier is removed (spec 042 US3, #866).

The same format as the phenotyping models' (model_drivers.py, docs/model_drivers.md), applied to the de-identification
benchmark (spec 007, docs/deidentification.md):

1. **A ranked table**: identifiers fully removed of the 2,714 on the synthetic challenge set (a leak is any surviving
   character), its 95% CI and the 95% range of its rank over paired note resamples, an exact McNemar test against the
   best tool on the same identifiers, and decoy damage (dental terms cut: over-redaction) beside it.
2. **Contrasts**: every pair of tools that differ in exactly one ingredient (the dental guard, regex rules, Presidio,
   hf_stanford, hf_obi), tested the same way on identifiers and on decoys.
3. **What decides outcomes**: the removed share by identifier fact (category, shape, length) and note fact (tier,
   identifiers in the note, position), and a logistic regression over every (tool, identifier) run that predicts
   removal from those facts, the tool's ingredients or both, scored by out-of-fold AUC (folds and bootstrap by note).
   Leaving one group out and measuring the AUC lost ranks the drivers.

The paired tests need one row per tool and labelled span. data/deid/scores.csv holds only aggregates, so the tools that
run locally were rerun on CPU on the same challenge set (seed 7, 400 notes; scripts/76_deid_drivers.py --rerun) into
SPAN_RESULT, and `reproduce` checks the rerun gives the committed entity recall and decoy damage exactly. ai_mask (a
Databricks SQL function) can't be rerun here: it is ranked from its committed aggregates, marked not paired.

Every number is a count of what the tools did to fake PHI on synthetic notes, read after the runs: described, not a
planned test. Identifiers in one note are not independent; the CIs and rank ranges resample notes, the McNemar p
treats identifiers as independent and so is optimistic.

    build(span_result)       {table name: DataFrame} for TABLES, plus what the page and the loader need
    details_markdown(built)  docs/deid_drivers.md, the drill-down
    load(built, client, batch)  the tables into Unity Catalog, with comments (scripts/77_load_deid_drivers.py)
"""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from . import readme_results as rr
from .model_drivers import exact_mcnemar
from .paths import DEID_DIR, REPO_ROOT
from .telemetry import traced

OUT_DIR = REPO_ROOT / "data" / "datasets" / "model_drivers"
DETAILS_DOC = REPO_ROOT / "docs" / "deid_drivers.md"
SPAN_RESULT = DEID_DIR / "drivers" / "span_result.csv.gz"
SCORES = DEID_DIR / "scores.csv"
ROUTES = DEID_DIR / "routes.csv"
N_NOTES, CHALLENGE_SEED = 400, 7                    # 26_deid_benchmark.py's defaults
CHALLENGE_TIERS = ("easy", "hard", "unseen")
N_BOOT, SEED, N_FOLDS = 1000, 42, 5
TABLES = ("deid_tool_rank", "deid_reproduction", "deid_contrast", "deid_ingredient_effect", "deid_category_effect",
          "deid_driver_fit", "deid_driver_drop")
LOAD_TABLES = TABLES + ("deid_span_result",)

# The tools that run locally (26_deid_benchmark.py's defaults that ran on 2026-10-26), and the engines they use.
LOCAL_ENGINES = ("regex", "regex_v2", "presidio", "hf_stanford", "hf_obi")
PAIRED_METHODS = ("regex", "regex+guard", "regex_v2", "regex_v2+guard", "presidio", "presidio+guard",
                  "presidio+regex_v2+guard", "hf_stanford", "hf_stanford+guard", "hf_stanford+regex_v2+guard",
                  "hf_obi", "hf_obi+regex_v2+guard", "hf_stanford+hf_obi+regex_v2+guard",
                  "hf_stanford+presidio+regex_v2+guard", "routed+guard")
UNPAIRED_METHODS = ("ai_mask", "ai_mask+regex_v2+guard")   # Databricks SQL ai_mask: committed aggregates only

# ---------- tool ingredients ----------

FEATURES = ("rules_code", "is_with_presidio", "is_with_hf_stanford", "is_with_hf_obi", "is_with_ai_mask",
            "is_with_guard", "is_routed")
CONTRAST_FEATURES = FEATURES
TOOL_GROUPS = ("rules_code", "is_with_presidio", "is_with_hf_stanford", "is_with_hf_obi", "is_with_guard",
               "is_routed")
_RULES_ORDER = ["none", "regex", "regex_v2"]
FEATURE_LABEL = {"rules_code": "regex rules added (none to regex_v2) or extended (regex to regex_v2)",
                 "is_with_guard": "dental guard added", "is_with_presidio": "Presidio added",
                 "is_with_hf_stanford": "hf_stanford added", "is_with_hf_obi": "hf_obi added",
                 "is_with_ai_mask": "ai_mask added", "is_routed": "routed by identifier type"}


@traced
def method_feature(method: str) -> dict:
    """The ingredients of one tool spec ('hf_stanford+regex_v2+guard'). routed+guard draws on hf_stanford, hf_obi,
    Presidio and regex_v2 per identifier type (data/deid/routes.csv), so it is marked routed, not by its engines."""
    parts = method.split("+")
    rules = "regex_v2" if "regex_v2" in parts else "regex" if "regex" in parts else "none"
    return {"method_code": method, "rules_code": rules, "is_with_presidio": "presidio" in parts,
            "is_with_hf_stanford": "hf_stanford" in parts, "is_with_hf_obi": "hf_obi" in parts,
            "is_with_ai_mask": "ai_mask" in parts, "is_with_guard": "guard" in parts, "is_routed": "routed" in parts}


# ---------- the per-identifier results ----------

@traced
def challenge() -> list[dict]:
    from .phi_challenge import build_challenge
    return build_challenge(N_NOTES, CHALLENGE_SEED)


@traced
def rerun_raw(records: list[dict], engines=LOCAL_ENGINES) -> dict:
    """{engine: one list of raw spans per record}, from deid.ENGINES on this machine (CPU)."""
    from . import deid
    return {e: [list(deid.ENGINES[e](r["text"])) for r in records] for e in engines}


def _detector(method: str, records: list[dict], raw: dict):
    """The tool as 26_deid_benchmark.py builds it, reading each engine's spans from raw instead of running it."""
    from . import deid, deid_eval
    by_text = {e: {r["text"]: s for r, s in zip(records, spans)} for e, spans in raw.items()}
    engines = {e: (lambda t, e=e: [dict(s) for s in by_text[e][t]]) for e in raw}
    if method == "routed+guard":
        return deid.routed_engine(deid_eval.routes_from_table(pd.read_csv(ROUTES)), engines)
    names = [p for p in method.split("+") if p != "guard"]
    guard = "guard" in method.split("+")

    def detect(text):
        spans = deid._merge([s for n in names for s in engines[n](text)])
        return deid.dental_guard(text, spans) if guard else spans
    return detect


@traced
def span_result(records: list[dict], raw: dict, methods=PAIRED_METHODS) -> pd.DataFrame:
    """One row per tool and labelled span (identifier or dental decoy): how many of its characters the tool removed."""
    rows = []
    for m in methods:
        detect = _detector(m, records, raw)
        for r in records:
            red = {i for s in detect(r["text"]) for i in range(s["start"], s["end"])}
            for kind in ("phi", "decoy"):
                for k, s in enumerate(r["phi" if kind == "phi" else "decoys"]):
                    rows.append((m, r["note_id"], kind, k, r["tier"], s["type"], s["end"] - s["start"],
                                 len(red & set(range(s["start"], s["end"])))))
    return pd.DataFrame(rows, columns=["method_code", "note_id", "item_kind_code", "item_num", "tier_code",
                                       "category_code", "char_count", "removed_char_count"])


@traced
def load_span_result() -> pd.DataFrame:
    return pd.read_csv(SPAN_RESULT)


@traced
def load_committed_scores() -> pd.DataFrame:
    return pd.read_csv(SCORES)


def _outcomes(sr: pd.DataFrame) -> pd.DataFrame:
    return sr.assign(is_removed=sr.removed_char_count == sr.char_count, is_touched=sr.removed_char_count > 0)


@traced
def reproduce(sr: pd.DataFrame, scores: pd.DataFrame) -> pd.DataFrame:
    """Per rerun tool and tier: entity recall and decoy damage from the rerun beside data/deid/scores.csv's."""
    o = _outcomes(sr)
    rows = []
    for (m, kind), g in o.groupby(["method_code", "item_kind_code"]):
        for t in (*CHALLENGE_TIERS, "all"):
            gt = g if t == "all" else g[g.tier_code == t]
            rows.append({"method_code": m, "tier_code": t, "kind": kind,
                         "share": gt.is_removed.mean() if kind == "phi" else gt.is_touched.mean(), "n": len(gt)})
    d = pd.DataFrame(rows).pivot_table(index=["method_code", "tier_code"], columns="kind", values=["share", "n"])
    d.columns = [f"{a}_{b}" for a, b in d.columns]
    d = d.reset_index()
    old = scores.set_index(["method", "tier"])
    out = pd.DataFrame({"method_code": d.method_code, "tier_code": d.tier_code,
                        "identifier_count": d.n_phi.astype(int), "decoy_count": d.n_decoy.astype(int),
                        "rerun_removed_ratio": d.share_phi, "committed_removed_ratio":
                        [old.loc[(m, t), "entity_recall"] for m, t in zip(d.method_code, d.tier_code)],
                        "rerun_damaged_ratio": d.share_decoy, "committed_damaged_ratio":
                        [old.loc[(m, t), "decoy_damage"] for m, t in zip(d.method_code, d.tier_code)]})
    out["is_match"] = ((out.rerun_removed_ratio - out.committed_removed_ratio).abs() < 1e-9) & \
                      ((out.rerun_damaged_ratio - out.committed_damaged_ratio).abs() < 1e-9)
    order = {m: i for i, m in enumerate(PAIRED_METHODS)}
    tiers = {t: i for i, t in enumerate((*CHALLENGE_TIERS, "all"))}
    return out.sort_values(["method_code", "tier_code"], key=lambda s: s.map(order if s.name == "method_code" else tiers),
                           kind="stable").reset_index(drop=True)


# ---------- identifier and note facts ----------

def _shape(text: str) -> str:
    letters, digits = any(c.isalpha() for c in text), any(c.isdigit() for c in text)
    if digits and not letters:
        return "digits"
    if digits:
        return "letters_and_digits"
    if text.isupper():
        return "all_caps"
    if text.islower():
        return "lowercase"
    return "capitalised"


@traced
def item_facts(records: list[dict]) -> pd.DataFrame:
    """One row per labelled span: facts of the span itself and of its note, all known to the generator."""
    rows = []
    for r in records:
        n_phi, length = len(r["phi"]), len(r["text"])
        for kind, spans in (("phi", r["phi"]), ("decoy", r["decoys"])):
            for k, s in enumerate(spans):
                words = len(s["text"].split())
                rows.append({"note_id": r["note_id"], "item_kind_code": kind, "item_num": k,
                             "fact_category": s["type"], "fact_char_count": s["end"] - s["start"],
                             "shape_code": _shape(s["text"]),
                             "word_count_code": "1" if words == 1 else "2" if words == 2 else "3 or more",
                             "tier_code": r["tier"],
                             "note_identifier_count_code": "1 to 5" if n_phi <= 5 else "6 to 7" if n_phi <= 7
                             else "8 or more",
                             "position_code": ("first third", "middle third", "last third")[min(2, 3 * s["start"] // length)]})
    f = pd.DataFrame(rows)
    f["char_count_code"] = pd.cut(f.fact_char_count, [0, 4, 10, 20, 10_000],
                                  labels=["1 to 4", "5 to 10", "11 to 20", "21 or more"]).astype(str)
    return f


IDENTIFIER_FACTS = ("category_code", "shape_code", "char_count_code", "word_count_code")
NOTE_FACTS = ("tier_code", "note_identifier_count_code", "position_code")
FACT_LABEL = {"category_code": "identifier category (HIPAA Safe Harbor / i2b2 2014)",
              "shape_code": "how the identifier is written (capitalised, all caps, lowercase, digits, letters and digits)",
              "char_count_code": "identifier length in characters", "word_count_code": "identifier length in words",
              "tier_code": "the note's tier (easy header shapes, hard prose shapes, unseen held-out shapes)",
              "note_identifier_count_code": "identifiers in the note", "position_code": "where in the note it sits"}
_LEVEL_ORDER = ["easy", "hard", "unseen", "1 to 4", "5 to 10", "11 to 20", "21 or more", "1", "2", "3 or more",
                "1 to 5", "6 to 7", "8 or more", "first third", "middle third", "last third"]
_FACT_KIND = {**{f: "identifier" for f in IDENTIFIER_FACTS}, **{f: "note" for f in NOTE_FACTS}}


def _joined(sr: pd.DataFrame, records: list[dict]) -> pd.DataFrame:
    keys = ["note_id", "item_kind_code", "item_num"]
    o = _outcomes(sr).merge(item_facts(records), on=keys, how="left", suffixes=("", "_fact"), validate="many_to_one")
    bad = (o.fact_category != o.category_code) | (o.fact_char_count != o.char_count) | (o.tier_code_fact != o.tier_code)
    if bad.any():
        raise ValueError(f"span_result does not match the challenge generator in {int(bad.sum())} rows: rerun "
                         "scripts/76_deid_drivers.py --rerun")
    return o.drop(columns=["fact_category", "fact_char_count", "tier_code_fact"])


def _matrix(o: pd.DataFrame, kind: str, col: str) -> pd.DataFrame:
    g = o[o.item_kind_code == kind]
    return g.pivot(index=["note_id", "item_num"], columns="method_code", values=col)[list(PAIRED_METHODS)]


# ---------- 1. the ranked table ----------

def _note_boot(hit: pd.DataFrame, n_boot: int, seed: int = SEED):
    """Per method: share hit in each of n_boot note resamples (the same resamples for every method)."""
    notes = hit.index.get_level_values("note_id").to_numpy()
    uniq, inv = np.unique(notes, return_inverse=True)
    per_note = np.zeros((len(uniq), hit.shape[1]))
    np.add.at(per_note, inv, hit.to_numpy(float))
    size = np.bincount(inv).astype(float)
    idx = np.random.default_rng(seed).integers(0, len(uniq), size=(n_boot, len(uniq)))
    return per_note[idx].sum(axis=1) / size[idx].sum(axis=1)[:, None]          # resamples x methods


def _rank_table(o: pd.DataFrame, scores: pd.DataFrame, n_boot: int) -> pd.DataFrame:
    rem, dmg = _matrix(o, "phi", "is_removed"), _matrix(o, "decoy", "is_touched")
    unseen = rem.index.get_level_values("note_id").isin(o.loc[o.tier_code == "unseen", "note_id"].unique())
    order = rem.sum().sort_values(ascending=False, kind="stable")
    leader = order.index[0]
    boot_r = _note_boot(rem[order.index], n_boot)
    boot_d = _note_boot(dmg[order.index], n_boot, seed=SEED + 1)
    ranks = 1 + (boot_r[:, None, :] > boot_r[:, :, None]).sum(axis=2)                # resamples x methods
    rows = []
    for pos, m in enumerate(order.index):
        a_only, b_only, p = exact_mcnemar(rem[leader], rem[m])
        _, _, p_unseen = exact_mcnemar(rem[leader][unseen], rem[m][unseen])
        n, nd = len(rem), len(dmg)
        rows.append({"rank_position_count": pos + 1, "method_code": m, "is_paired": True,
                     "ci_method_code": "note_bootstrap", "removed_count": int(order[m]), "identifier_count": n,
                     "removed_pct": 100 * order[m] / n, "removed_lo_pct": 100 * np.quantile(boot_r[:, pos], 0.025),
                     "removed_hi_pct": 100 * np.quantile(boot_r[:, pos], 0.975),
                     "rank_lo_count": int(np.floor(np.quantile(ranks[:, pos], 0.025))),
                     "rank_hi_count": int(np.ceil(np.quantile(ranks[:, pos], 0.975))),
                     "leader_only_count": a_only, "method_only_count": b_only, "vs_leader_p_ratio": p,
                     "unseen_removed_count": int(rem[m][unseen].sum()), "unseen_identifier_count": int(unseen.sum()),
                     "unseen_removed_pct": 100 * rem[m][unseen].mean(), "unseen_vs_leader_p_ratio": p_unseen,
                     "damaged_count": int(dmg[m].sum()), "decoy_count": nd, "damaged_pct": 100 * dmg[m].mean(),
                     "damaged_lo_pct": 100 * np.quantile(boot_d[:, pos], 0.025),
                     "damaged_hi_pct": 100 * np.quantile(boot_d[:, pos], 0.975),
                     **{k: method_feature(m)[k] for k in FEATURES}})
    s = scores.set_index(["method", "tier"])
    n, nd = len(rem), len(dmg)
    nu = int(unseen.sum())
    for m in UNPAIRED_METHODS:
        k, kd = round(s.loc[(m, "all"), "entity_recall"] * n), round(s.loc[(m, "all"), "decoy_damage"] * nd)
        ku = round(s.loc[(m, "unseen"), "entity_recall"] * nu)
        (lo, hi), (dlo, dhi) = rr.wilson(k, n), rr.wilson(kd, nd)
        rows.append({"rank_position_count": None, "method_code": m, "is_paired": False, "ci_method_code": "wilson",
                     "removed_count": k, "identifier_count": n, "removed_pct": 100 * k / n, "removed_lo_pct": 100 * lo,
                     "removed_hi_pct": 100 * hi, "rank_lo_count": None, "rank_hi_count": None,
                     "leader_only_count": None, "method_only_count": None, "vs_leader_p_ratio": np.nan,
                     "unseen_removed_count": ku, "unseen_identifier_count": nu, "unseen_removed_pct": 100 * ku / nu,
                     "unseen_vs_leader_p_ratio": np.nan, "damaged_count": kd, "decoy_count": nd,
                     "damaged_pct": 100 * kd / nd, "damaged_lo_pct": 100 * dlo, "damaged_hi_pct": 100 * dhi,
                     **{f: method_feature(m)[f] for f in FEATURES}})
    out = pd.DataFrame(rows)
    for c in ("rank_position_count", "rank_lo_count", "rank_hi_count", "leader_only_count", "method_only_count"):
        out[c] = out[c].astype("Int64")
    return out


# ---------- 2. contrasts ----------

def _orient(feature: str, fa: dict, fb: dict) -> bool:
    if feature == "rules_code":
        return _RULES_ORDER.index(fa[feature]) < _RULES_ORDER.index(fb[feature])
    return not fa[feature]


@traced
def contrasts(methods) -> list[tuple[str, str, str]]:
    """(feature, a, b) for every pair of tools that differ in exactly one ingredient; b has the ingredient."""
    feats = {m: method_feature(m) for m in methods}
    out = []
    for i, m in enumerate(methods):
        for n in methods[i + 1:]:
            diff = [k for k in CONTRAST_FEATURES if feats[m][k] != feats[n][k]]
            if len(diff) == 1:
                a, b = (m, n) if _orient(diff[0], feats[m], feats[n]) else (n, m)
                out.append((diff[0], a, b))
    return out


def _contrast_table(o: pd.DataFrame) -> pd.DataFrame:
    rem, dmg = _matrix(o, "phi", "is_removed"), _matrix(o, "decoy", "is_touched")
    unseen = rem.index.get_level_values("note_id").isin(o.loc[o.tier_code == "unseen", "note_id"].unique())
    rows = []
    for f, a, b in contrasts(list(PAIRED_METHODS)):
        fa, fb = method_feature(a), method_feature(b)
        a_only, b_only, p = exact_mcnemar(rem[a], rem[b])
        da, db, dp = exact_mcnemar(dmg[a], dmg[b])
        ua, ub, up = exact_mcnemar(rem[a][unseen], rem[b][unseen])
        rows.append({"feature_code": f, "feature_text": FEATURE_LABEL[f], "method_a_code": a, "method_b_code": b,
                     "level_a_text": str(fa[f]), "level_b_text": str(fb[f]),
                     "a_removed_count": int(rem[a].sum()), "b_removed_count": int(rem[b].sum()),
                     "a_only_count": a_only, "b_only_count": b_only, "p_ratio": p,
                     "a_unseen_removed_count": int(rem[a][unseen].sum()),
                     "b_unseen_removed_count": int(rem[b][unseen].sum()),
                     "a_only_unseen_count": ua, "b_only_unseen_count": ub, "unseen_p_ratio": up,
                     "a_damaged_count": int(dmg[a].sum()), "b_damaged_count": int(dmg[b].sum()),
                     "a_only_damaged_count": da, "b_only_damaged_count": db, "damage_p_ratio": dp})
    return pd.DataFrame(rows).sort_values(["feature_code", "p_ratio"], kind="stable").reset_index(drop=True)


def _ingredient_effect(con: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for f, g in con.groupby("feature_code", sort=False):
        diff, dd = g.b_removed_count - g.a_removed_count, g.b_damaged_count - g.a_damaged_count
        du = g.b_unseen_removed_count - g.a_unseen_removed_count
        rows.append({"feature_code": f, "feature_text": FEATURE_LABEL[f], "pair_count": len(g),
                     "b_better_pair_count": int((diff > 0).sum()), "a_better_pair_count": int((diff < 0).sum()),
                     "tied_pair_count": int((diff == 0).sum()), "median_change_count": float(diff.median()),
                     "min_change_count": int(diff.min()), "max_change_count": int(diff.max()),
                     "p_below_005_pair_count": int((g.p_ratio < 0.05).sum()),
                     "median_unseen_change_count": float(du.median()),
                     "unseen_p_below_005_pair_count": int((g.unseen_p_ratio < 0.05).sum()),
                     "median_damage_change_count": float(dd.median()),
                     "min_damage_change_count": int(dd.min()), "max_damage_change_count": int(dd.max()),
                     "damage_p_below_005_pair_count": int((g.damage_p_ratio < 0.05).sum())})
    return pd.DataFrame(rows).sort_values("median_change_count", ascending=False, kind="stable").reset_index(drop=True)


# ---------- 3. what decides outcomes ----------

def _category_effect(o: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for kind, g in o.groupby("item_kind_code", sort=False):
        hit = "is_removed" if kind == "phi" else "is_touched"
        per_item = g.groupby(["note_id", "item_num"])[hit].mean()
        first = g[g.method_code == PAIRED_METHODS[0]].set_index(["note_id", "item_num"])
        for col in (*IDENTIFIER_FACTS, *NOTE_FACTS):
            groups = first.groupby(col, observed=True).groups
            for level in sorted(groups, key=lambda v: (_LEVEL_ORDER.index(v) if v in _LEVEL_ORDER else 99, str(v))):
                idx = groups[level]
                share = per_item.loc[idx]
                runs = g[g.set_index(["note_id", "item_num"]).index.isin(idx)]
                ratio = float(runs[hit].mean())
                text = "decoy type (tooth number, eponym, code, drug, ...)" if (kind, col) == ("decoy", "category_code") \
                    else FACT_LABEL[col]
                rows.append({"item_kind_code": kind, "fact_code": col, "fact_text": text,
                             "level_text": str(level), "item_count": len(idx), "run_count": len(runs),
                             "removed_ratio": ratio if kind == "phi" else np.nan,
                             "damaged_ratio": ratio if kind == "decoy" else np.nan,
                             "all_methods_item_count": int((share == 1).sum()),
                             "no_method_item_count": int((share == 0).sum())})
    return pd.DataFrame(rows)


def _long(o: pd.DataFrame) -> pd.DataFrame:
    long = o[o.item_kind_code == "phi"].reset_index(drop=True)
    feats = pd.DataFrame([method_feature(m) for m in PAIRED_METHODS])
    return long.merge(feats[["method_code", *TOOL_GROUPS]], on="method_code")


def _oof(long, groups) -> np.ndarray:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import GroupKFold
    x = pd.get_dummies(long[list(groups)].astype(str), drop_first=False).to_numpy(float)
    y = long["is_removed"].to_numpy(int)
    out = np.zeros(len(y))
    for tr, te in GroupKFold(N_FOLDS).split(x, y, groups=long["note_id"]):
        out[te] = LogisticRegression(max_iter=2000, C=1.0).fit(x[tr], y[tr]).predict_proba(x[te])[:, 1]
    return out


def _auc_ci(long, score, n_boot, seed=SEED) -> tuple[float, float, float]:
    from sklearn.metrics import roc_auc_score
    y = long["is_removed"].to_numpy(int)
    notes = long["note_id"].to_numpy()
    uniq = np.unique(notes)
    rows_of = {v: np.flatnonzero(notes == v) for v in uniq}
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(n_boot):
        idx = np.concatenate([rows_of[v] for v in rng.choice(uniq, size=len(uniq))])
        if 0 < y[idx].sum() < len(idx):
            boots.append(roc_auc_score(y[idx], score[idx]))
    return float(roc_auc_score(y, score)), float(np.quantile(boots, 0.025)), float(np.quantile(boots, 0.975))


def _driver_fit(o: pd.DataFrame, n_boot: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    from sklearn.metrics import roc_auc_score
    long = _long(o)
    ident = IDENTIFIER_FACTS + NOTE_FACTS
    sets = {"identifier": ident, "tool": TOOL_GROUPS, "identifier_and_tool": ident + TOOL_GROUPS}
    fit = []
    for name, groups in sets.items():
        auc, lo, hi = _auc_ci(long, _oof(long, groups), n_boot)
        fit.append({"feature_set_code": name, "run_count": len(long), "identifier_count": int(len(long) /
                    long.method_code.nunique()), "note_count": int(long.note_id.nunique()),
                    "method_count": int(long.method_code.nunique()), "auc_ratio": auc, "auc_lo_ratio": lo,
                    "auc_hi_ratio": hi})
    full = fit[-1]["auc_ratio"]
    y = long["is_removed"].to_numpy(int)
    drop = [{"feature_group_code": g, "feature_kind_code": _FACT_KIND.get(g, "tool"),
             "feature_text": FACT_LABEL.get(g) or FEATURE_LABEL[g],
             "auc_without_ratio": float(roc_auc_score(y, _oof(long, [h for h in sets["identifier_and_tool"] if h != g])))}
            for g in sets["identifier_and_tool"]]
    drop = pd.DataFrame(drop).assign(auc_drop_ratio=lambda d: full - d.auc_without_ratio)
    return pd.DataFrame(fit), drop.sort_values("auc_drop_ratio", ascending=False, kind="stable").reset_index(drop=True)


# ---------- build ----------

@traced
def deid_span_result(sr: pd.DataFrame) -> pd.DataFrame:
    """The per-identifier table loaded to Unity Catalog: span_result with whether it leaked or was damaged."""
    phi = sr.item_kind_code.eq("phi")
    return sr.assign(is_leaked=(sr.removed_char_count < sr.char_count).where(phi, None).astype("boolean"),
                     is_damaged=(sr.removed_char_count > 0).where(~phi, None).astype("boolean"))


@traced
def build(sr: pd.DataFrame, n_boot: int = N_BOOT, records: list[dict] | None = None,
          scores: pd.DataFrame | None = None) -> dict:
    records = records if records is not None else challenge()
    scores = scores if scores is not None else load_committed_scores()
    o = _joined(sr, records)
    con = _contrast_table(o)
    fit, drop = _driver_fit(o, n_boot)
    return {"deid_tool_rank": _rank_table(o, scores, n_boot), "deid_reproduction": reproduce(sr, scores),
            "deid_contrast": con, "deid_ingredient_effect": _ingredient_effect(con),
            "deid_category_effect": _category_effect(o), "deid_driver_fit": fit, "deid_driver_drop": drop,
            "span_result": sr}


# ---------- the page ----------

def _p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}" if p < 0.01 else f"{p:.2f}"


def _auc(r) -> str:
    return f"{r.auc_ratio:.2f} ({r.auc_lo_ratio:.2f} to {r.auc_hi_ratio:.2f})"


_SET_LABEL = {"identifier": "The identifier's and its note's facts alone", "tool": "The tool's ingredients alone",
              "identifier_and_tool": "Both"}
_HEAD = ("> **Fake PHI on synthetic notes** (the de-identification challenge set: seed 7, 400 notes, 2,714 identifiers, "
         "2,462 dental decoys). Counts of what the tools did, read after the runs: they describe, they do not prove. "
         "Generated by `python/scripts/76_deid_drivers.py` from `data/deid/drivers/span_result.csv.gz` (a CPU rerun "
         "that reproduces `data/deid/scores.csv` exactly) and `data/deid/scores.csv`; tables in "
         "`data/datasets/model_drivers/deid_*.csv` and, on Databricks, "
         "`health_transformation_lab.gold_perio_bench.deid_*`.")


def _tool_text(r) -> str:
    bits = [] if r.rules_code == "none" else [r.rules_code]
    bits += [n for n, on in (("Presidio", r.is_with_presidio), ("hf_stanford", r.is_with_hf_stanford),
                             ("hf_obi", r.is_with_hf_obi), ("ai_mask", r.is_with_ai_mask),
                             ("routed by type", r.is_routed), ("dental guard", r.is_with_guard)) if on]
    return ", ".join(bits)


@traced
def details_markdown(b: dict) -> str:
    rank, con, eff = b["deid_tool_rank"], b["deid_contrast"], b["deid_ingredient_effect"].set_index("feature_code")
    fit, drop, cat, rep = (b["deid_driver_fit"].set_index("feature_set_code"), b["deid_driver_drop"],
                           b["deid_category_effect"], b["deid_reproduction"])
    paired = rank[rank.is_paired]
    lead = paired.iloc[0]
    tied = paired[(paired.vs_leader_p_ratio >= 0.05) & (paired.method_code != lead.method_code)]
    unp = rank[~rank.is_paired]
    n_match, n_rep = int(rep.is_match.sum()), len(rep)
    top_ident, top_tool = drop[drop.feature_kind_code != "tool"].iloc[0], drop[drop.feature_kind_code == "tool"].iloc[0]
    out = ["# How the de-identification tools rank, and what decides whether an identifier is removed", "",
           "<!-- generated by python/scripts/76_deid_drivers.py; do not edit -->", "", _HEAD, "",
           "The same format as [the note-reading models' page](model_drivers.md), applied to the "
           "[de-identification benchmark](deidentification.md): a ranked table with paired tests against the best "
           "tool; pairs of tools that differ in one ingredient, tested the same way; and which facts of an identifier "
           "and its note, and which ingredients of a tool, predict whether the identifier is removed, scored by AUC.",
           "", "**In plain words.** A tool removes an identifier only if not one character of it survives. "
           f"The best tool run here, **{lead.method_code}**, removes {lead.removed_count:,} of "
           f"{lead.identifier_count:,} ({lead.removed_pct:.1f}%) and cuts {lead.damaged_pct:.1f}% of dental terms. "
           + (f"{len(tied)} other tool{'s are' if len(tied) != 1 else ' is'} not distinguishable from it"
            if len(tied) else "Every other paired tool removes significantly fewer") +
           " on the same identifiers (exact McNemar p < 0.05). What decides removal is mostly the identifier itself "
           f"(its {top_ident.feature_text.split(' (')[0]} above all), then the tool "
           f"({top_tool.feature_text}).", "",
           "## How the per-identifier results were made", "",
           "`data/deid/scores.csv` holds aggregates only, so the paired tests below come from a rerun on CPU of every "
           "tool that runs locally (regex, regex_v2, Presidio with spaCy `en_core_web_lg`, the two Hugging Face "
           "models, their unions and the dental guard), on the same challenge set with the benchmark's own defaults "
           f"(`python/scripts/76_deid_drivers.py --rerun`). The rerun reproduces the committed entity recall and decoy "
           f"damage exactly in {n_match} of {n_rep} tool-tier cells (table `deid_reproduction`). "
           "**ai_mask** (a Databricks SQL function) can't be rerun here: its rows come from the committed aggregates, "
           "with a Wilson interval, and are **not paired** (no McNemar p, no rank range).", "",
           "## 1. The ranking", "",
           "- **Removed**: identifiers with no character left, of 2,714 (95% CI: notes resampled, since identifiers "
           "in one note go together).",
           "- **Rank**: the 95% range of the tool's rank among the paired tools over the same note resamples.",
           "- **Leader only / tool only**: identifiers the leader removes and this tool leaks, and the reverse; the "
           "exact McNemar p is on these two counts (it treats identifiers as independent, so it is optimistic).",
           "- **Unseen**: the held-out tier (identifier shapes added after regex_v2 was frozen): the fair comparison, "
           "since regex_v2 was written alongside the hard tier.",
           "- **Decoy damage**: dental terms that look like PHI (Glickman class II, #19, 6-5-6, D4341) with any "
           "character cut: over-redaction. Lower is better.", "",
           "| # | Tool | Ingredients | Removed of 2,714 (95% CI) | Rank | Leader only | Tool only | p vs leader | "
           "Unseen removed (p vs leader) | Decoy damage (95% CI) |",
           "|---:|---|---|---|---|---:|---:|---|---|---|"]
    for r in paired.itertuples():
        p = "leader" if r.rank_position_count == 1 else _p(r.vs_leader_p_ratio)
        pu = "leader" if r.rank_position_count == 1 else _p(r.unseen_vs_leader_p_ratio)
        out.append(f"| {r.rank_position_count} | `{r.method_code}` | {_tool_text(r)} | **{r.removed_count:,}** "
                   f"({r.removed_lo_pct:.1f}–{r.removed_hi_pct:.1f}%) | {r.rank_lo_count}–{r.rank_hi_count} | "
                   f"{r.leader_only_count} | {r.method_only_count} | {p} | {r.unseen_removed_pct:.0f}% ({pu}) | "
                   f"{r.damaged_pct:.1f}% ({r.damaged_lo_pct:.1f}–{r.damaged_hi_pct:.1f}%) |")
    for r in unp.itertuples():
        out.append(f"| – | `{r.method_code}` (not paired) | {_tool_text(r)} | **{r.removed_count:,}** "
                   f"({r.removed_lo_pct:.1f}–{r.removed_hi_pct:.1f}%, Wilson) | – | – | – | not paired | "
                   f"{r.unseen_removed_pct:.0f}% (not paired) | {r.damaged_pct:.1f}% ({r.damaged_lo_pct:.1f}–"
                   f"{r.damaged_hi_pct:.1f}%, Wilson) |")
    better_unp = unp[unp.removed_count > lead.removed_count]
    if len(better_unp):
        out += ["", f"By its committed aggregate, `{better_unp.iloc[0].method_code}` removes more identifiers "
                f"({better_unp.iloc[0].removed_count:,}) than the paired leader ({lead.removed_count:,}); without "
                "its per-identifier results that gap can't be tested on the same identifiers, and its interval is "
                "Wilson's, which ignores that identifiers in one note go together."]
    out += ["", "## 2. Which ingredients move the score", "",
            "Each row pools the pairs of tools that differ in that one ingredient and nothing else (b is the tool "
            "with it). Pairs share identifiers, so the pooled counts are described, not tested; each pair has its "
            "own exact McNemar p below.", "",
            "| Ingredient | Pairs | Better / worse / same | Median change in removed (of 2,714) | Range | Pairs with "
            "p < 0.05 | Median change on unseen (of 879) | Median change in damaged decoys (of 2,462) | Pairs with "
            "damage p < 0.05 |", "|---|---:|---|---:|---|---:|---:|---:|---:|"]
    for f, r in eff.iterrows():
        out.append(f"| {r.feature_text} | {r.pair_count} | {r.b_better_pair_count} / {r.a_better_pair_count} / "
                   f"{r.tied_pair_count} | {r.median_change_count:+g} | {r.min_change_count:+d} to "
                   f"{r.max_change_count:+d} | {r.p_below_005_pair_count} | {r.median_unseen_change_count:+g} | "
                   f"{r.median_damage_change_count:+g} | {r.damage_p_below_005_pair_count} |")
    out += ["", "<details><summary>Every pair (a → b), with its paired counts</summary>", "",
            "| Ingredient | a | b | a removed | b removed | Only a | Only b | p | Unseen only a / only b (p) | "
            "a damaged | b damaged | Damage p |", "|---|---|---|---:|---:|---:|---:|---|---|---:|---:|---|"]
    for r in con.itertuples():
        out.append(f"| {r.feature_text} | `{r.method_a_code}` | `{r.method_b_code}` | {r.a_removed_count} | "
                   f"{r.b_removed_count} | {r.a_only_count} | {r.b_only_count} | {_p(r.p_ratio)} | "
                   f"{r.a_only_unseen_count} / {r.b_only_unseen_count} ({_p(r.unseen_p_ratio)}) | "
                   f"{r.a_damaged_count} | {r.b_damaged_count} | {_p(r.damage_p_ratio)} |")
    out += ["", "</details>", "", "## 3. What decides whether an identifier is removed", "",
            f"Over all {int(fit.loc['tool', 'run_count']):,} tool-identifier runs ({int(fit.loc['tool', 'method_count'])}"
            " paired tools), a logistic regression predicts removal from the identifier's and its note's facts, the "
            "tool's ingredients, or both (out-of-fold AUC, folds and 95% bootstrap by note):", "",
            "| Predictors | AUC (95% CI) |", "|---|---|",
            *[f"| {_SET_LABEL[r.feature_set_code]} | {_auc(r)} |" for r in fit.reset_index().itertuples()], "",
            "An additive fit can't credit an ingredient that helps only one kind of identifier (regex_v2 on "
            "formatted IDs, the models on names), so the tool's share is a floor. Leaving one group of predictors out "
            "of the full fit, the AUC lost ranks the drivers:", "", "| Left out | Kind | AUC lost |", "|---|---|---:|"]
    for r in drop.itertuples():
        out.append(f"| {r.feature_text} | {r.feature_kind_code} | {r.auc_drop_ratio:.3f} |")
    for kind, title, col, every, none in (
            ("phi", "Identifiers removed", "removed_ratio", "Removed by every tool", "Removed by no tool"),
            ("decoy", "Dental decoys damaged", "damaged_ratio", "Damaged by every tool", "Damaged by no tool")):
        out += ["", f"{title}, across all {len(PAIRED_METHODS)} paired tools, by fact:", "",
                f"| Fact | Level | Items | Share of runs | {every} | {none} |", "|---|---|---:|---:|---:|---:|"]
        for r in cat[cat.item_kind_code == kind].itertuples():
            out.append(f"| {r.fact_text} | {r.level_text} | {r.item_count} | {100 * getattr(r, col):.0f}% | "
                       f"{r.all_methods_item_count} | {r.no_method_item_count} |")
    out += ["", "## Where this lives on Databricks", "",
            "`python/scripts/77_load_deid_drivers.py` loads the tables above into "
            "`health_transformation_lab.gold_perio_bench`, each with a comment on the table and every column and the "
            "batch key (`run_id`, `run_ts`, `git_commit_sha`). Loading again replaces them.", "",
            "| Table | One row per |", "|---|---|",
            "| `deid_tool_rank` | tool (ai_mask rows not paired) |", "| `deid_reproduction` | rerun tool and tier: "
            "rerun against committed scores |", "| `deid_contrast` | pair of tools differing in one ingredient |",
            "| `deid_ingredient_effect` | ingredient |", "| `deid_category_effect` | span kind, fact and level |",
            "| `deid_driver_fit` | predictor set |", "| `deid_driver_drop` | predictor group left out |",
            "| `deid_span_result` | paired tool and labelled span (identifier or decoy): characters removed, "
            "leaked, damaged |", "",
            "```sql", "-- the identifiers the leader leaks, by category and tier",
            "select category_code, tier_code, count(*) as leaked_count",
            "from health_transformation_lab.gold_perio_bench.deid_span_result",
            f"where method_code = '{lead.method_code}' and is_leaked group by all order by leaked_count desc;", "```",
            ""]
    return "\n".join(out)


# ---------- Unity Catalog (scripts/77_load_deid_drivers.py) ----------

_C = {"method_code": "The de-identification tool: engines joined by + (a union of their spans), +guard for the dental "
                     "guard; routed+guard takes each identifier type from the engines precise on it (spec 007)",
      "rules_code": "Regex rules in the tool: none, regex (header shapes) or regex_v2 (also prose shapes)",
      "is_with_presidio": "True when Microsoft Presidio (spaCy en_core_web_lg) is one of the engines",
      "is_with_hf_stanford": "True when StanfordAIMI/stanford-deidentifier-base is one of the engines",
      "is_with_hf_obi": "True when obi/deid_roberta_i2b2 is one of the engines",
      "is_with_ai_mask": "True when the Databricks SQL function ai_mask is one of the engines",
      "is_with_guard": "True when the dental guard keeps dental terms (eponyms, tooth numbers, codes) the engines flag",
      "is_routed": "True for routed+guard: each identifier type from the engines precise on it (data/deid/routes.csv)",
      "identifier_count": "Labelled fake identifiers counted", "decoy_count": "Labelled dental decoys counted",
      "run_count": "Tool-span runs counted", "method_count": "Paired tools counted",
      "note_count": "Synthetic challenge notes counted", "tier_code": "easy, hard, unseen, or all (the three together)",
      "feature_code": "The one ingredient that differs", "feature_text": "That ingredient in words",
      "item_kind_code": "phi (a fake identifier the tool should remove) or decoy (a dental term it should keep)",
      "category_code": "The identifier category (PATIENT, DOCTOR, DATE, PHONE, ...) or decoy type (TOOTH, EPONYM, ...)",
      "run_id": "The load's batch key: one per run of scripts/77_load_deid_drivers.py",
      "run_ts": "When that load ran (UTC, ISO 8601)", "git_commit_sha": "The commit the tables were built from"}
COMMENTS = {
    "deid_tool_rank": (
        "De-identification: every tool ranked by fake identifiers fully removed of 2,714 on the synthetic challenge "
        "set (a leak is any surviving character), with an exact McNemar test against the best tool on the same "
        "identifiers and decoy damage beside it (spec 042 US3, docs/deid_drivers.md). ai_mask rows come from "
        "committed aggregates and are not paired.",
        _C | {"rank_position_count": "Position among the paired tools by removed_count (1 = most); NULL when not "
                                     "paired",
              "is_paired": "True when per-identifier results exist (CPU rerun), so the paired columns are filled",
              "ci_method_code": "note_bootstrap (notes resampled, paired) or wilson (from aggregates)",
              "removed_count": "Identifiers with no character left", "removed_pct": "Removed, per 100 identifiers",
              "removed_lo_pct": "Lower 95% bound of removed_pct", "removed_hi_pct": "Upper 95% bound of removed_pct",
              "rank_lo_count": "Best rank in 95% of paired note resamples",
              "rank_hi_count": "Worst rank in 95% of paired note resamples",
              "leader_only_count": "Identifiers the leader removes and this tool leaks",
              "method_only_count": "Identifiers this tool removes and the leader leaks",
              "vs_leader_p_ratio": "Two-sided exact McNemar p on leader_only_count and method_only_count",
              "unseen_removed_count": "Identifiers removed on the unseen (held-out) tier",
              "unseen_identifier_count": "Identifiers on the unseen tier",
              "unseen_removed_pct": "Removed per 100 unseen-tier identifiers",
              "unseen_vs_leader_p_ratio": "Exact McNemar p against the overall leader on the unseen tier",
              "damaged_count": "Dental decoys with any character cut (over-redaction)",
              "damaged_pct": "Damaged per 100 decoys (lower is better)",
              "damaged_lo_pct": "Lower 95% bound of damaged_pct", "damaged_hi_pct": "Upper 95% bound of damaged_pct"}),
    "deid_reproduction": (
        "De-identification: the CPU rerun behind the paired tests, beside data/deid/scores.csv, per tool and tier "
        "(spec 042 US3). is_match is true when both shares agree to 1e-9.",
        _C | {"rerun_removed_ratio": "Entity recall from the rerun", "committed_removed_ratio":
              "Entity recall in data/deid/scores.csv", "rerun_damaged_ratio": "Decoy damage from the rerun",
              "committed_damaged_ratio": "Decoy damage in data/deid/scores.csv",
              "is_match": "True when the rerun reproduces both committed shares"}),
    "deid_contrast": (
        "De-identification: every pair of tools that differ in exactly one ingredient, with paired counts on the same "
        "identifiers and decoys and exact McNemar p values (spec 042 US3). a is without it, b with it.",
        _C | {"method_a_code": "The tool without the ingredient", "method_b_code": "The tool with it",
              "level_a_text": "a's value of the ingredient", "level_b_text": "b's value",
              "a_removed_count": "Identifiers a removes", "b_removed_count": "Identifiers b removes",
              "a_only_count": "Identifiers only a removes", "b_only_count": "Identifiers only b removes",
              "p_ratio": "Two-sided exact McNemar p on removal",
              "a_unseen_removed_count": "Unseen-tier identifiers a removes",
              "b_unseen_removed_count": "Unseen-tier identifiers b removes",
              "a_only_unseen_count": "Unseen-tier identifiers only a removes",
              "b_only_unseen_count": "Unseen-tier identifiers only b removes",
              "unseen_p_ratio": "Exact McNemar p on removal, unseen tier",
              "a_damaged_count": "Decoys a damages", "b_damaged_count": "Decoys b damages",
              "a_only_damaged_count": "Decoys only a damages", "b_only_damaged_count": "Decoys only b damages",
              "damage_p_ratio": "Two-sided exact McNemar p on decoy damage"}),
    "deid_ingredient_effect": (
        "De-identification: per ingredient, the pairs of deid_contrast pooled: how often adding it removed more "
        "identifiers or damaged more decoys, and by how many (spec 042 US3). Described, not tested: pairs share "
        "identifiers.",
        _C | {"pair_count": "Pairs differing only in it", "b_better_pair_count": "Pairs where adding it removed more",
              "a_better_pair_count": "Pairs where it removed fewer", "tied_pair_count": "Pairs with the same count",
              "median_change_count": "Median of b minus a identifiers removed", "min_change_count": "Smallest change",
              "max_change_count": "Largest change", "p_below_005_pair_count": "Pairs whose removal p is below 0.05",
              "median_unseen_change_count": "Median change in unseen-tier identifiers removed",
              "unseen_p_below_005_pair_count": "Pairs whose unseen-tier p is below 0.05",
              "median_damage_change_count": "Median of b minus a decoys damaged",
              "min_damage_change_count": "Smallest change in decoys damaged",
              "max_damage_change_count": "Largest change in decoys damaged",
              "damage_p_below_005_pair_count": "Pairs whose decoy-damage p is below 0.05"}),
    "deid_category_effect": (
        "De-identification: the share of tool-span runs that removed an identifier, or damaged a dental decoy, by a "
        "fact of the span or its note: what makes an identifier hard to remove (spec 042 US3).",
        _C | {"fact_code": "The fact (category_code, shape_code, char_count_code, word_count_code, tier_code, "
                           "note_identifier_count_code, position_code)", "fact_text": "In words",
              "level_text": "Its level", "item_count": "Spans at this level",
              "removed_ratio": "Share of runs that removed the identifier fully; NULL for decoys",
              "damaged_ratio": "Share of runs that cut the decoy; NULL for identifiers",
              "all_methods_item_count": "Spans every paired tool removed (identifiers) or damaged (decoys)",
              "no_method_item_count": "Spans no paired tool removed (identifiers) or damaged (decoys)"}),
    "deid_driver_fit": (
        "De-identification: how well identifier and note facts, tool ingredients or both predict that a tool removes "
        "an identifier: logistic regression, out-of-fold AUC with folds and 95% bootstrap by note (spec 042 US3).",
        _C | {"feature_set_code": "identifier (identifier and note facts), tool, or identifier_and_tool",
              "auc_ratio": "Out-of-fold AUC", "auc_lo_ratio": "Lower 95% bound (note bootstrap)",
              "auc_hi_ratio": "Upper 95% bound"}),
    "deid_driver_drop": (
        "De-identification: the AUC the full driver fit loses when one predictor group is left out: the drivers of "
        "an identifier being removed, ranked (spec 042 US3).",
        _C | {"feature_group_code": "The predictor group left out", "feature_kind_code": "identifier, note or tool",
              "auc_without_ratio": "Out-of-fold AUC without it",
              "auc_drop_ratio": "AUC of the full fit minus auc_without_ratio"}),
    "deid_span_result": (
        "De-identification: one row per paired tool and labelled span of the synthetic challenge set (seed 7, 400 "
        "notes): a fake identifier or a dental decoy, and how many of its characters the tool removed (spec 042 US3). "
        "Fake PHI only.",
        _C | {"note_id": "The challenge note (0 to 399)",
              "item_num": "The span's position among the note's identifiers or decoys (0 = first)",
              "char_count": "Characters in the span", "removed_char_count": "Of those, characters the tool removed",
              "is_leaked": "Identifiers: true when any character survives; NULL for decoys",
              "is_damaged": "Decoys: true when any character was cut; NULL for identifiers"}),
}


@traced
def load_tables(built: dict) -> dict:
    return {name: built[name] for name in TABLES} | {"deid_span_result": deid_span_result(built["span_result"])}


@traced
def table_sql(name: str, df: pd.DataFrame, batch: dict, catalog: str, schema: str, chunk: int = 1000) -> list[str]:
    """CREATE OR REPLACE with every column's type and comment and the table's comment, then INSERTs in chunks."""
    from .model_drivers_load import _sql_type, sql_literal
    df = df.assign(**batch)
    table_comment, cols = COMMENTS[name]
    fq = f"{catalog}.{schema}.{name}"
    defs = ", ".join(f"{c} {_sql_type(df[c])} COMMENT {sql_literal(cols[c])}" for c in df.columns)
    out = [f"CREATE OR REPLACE TABLE {fq} ({defs}) COMMENT {sql_literal(table_comment)}"]
    rows = ["(" + ",".join(sql_literal(v) for v in r) + ")" for r in df.itertuples(index=False)]
    out += [f"INSERT INTO {fq} VALUES " + ",".join(rows[i:i + chunk]) for i in range(0, len(rows), chunk)]
    return out


@traced
def load(built: dict, client, batch: dict, catalog: str = "health_transformation_lab",
         schema: str = "gold_perio_bench") -> dict:
    tabs = load_tables(built)
    for name in LOAD_TABLES:
        for stmt in table_sql(name, tabs[name], batch, catalog, schema):
            client.sql(stmt)
    return {"table_count": len(LOAD_TABLES), "row_count": int(sum(len(tabs[t]) for t in LOAD_TABLES))}


@traced
def new_batch(commit: str) -> dict:
    now = datetime.now(timezone.utc)
    return {"run_id": f"deid-drivers-{now:%Y%m%dT%H%M%SZ}", "run_ts": now.isoformat(timespec="seconds"),
            "git_commit_sha": commit}
