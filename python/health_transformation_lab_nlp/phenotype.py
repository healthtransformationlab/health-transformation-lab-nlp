"""Method comparison and the rule-based phenotyping algorithm.

Mirrors the study process:

  compare each method against each other   -> agreement_matrix()
  qualitative review (two dental reviewers) -> docs/process.md; outputs feed RULES_V0
  rule-based phenotyping algorithm          -> phenotype_v0()
  quantitative validation                   -> reliability.py (reviewers vs algorithm vs AI)

phenotype_v0 is a placeholder hierarchy so the pipeline runs end to end. The
real rules come out of the qualitative review; edit RULES_V0 and the function,
bump the version, and every downstream number is re-run.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .sources import UNKNOWN
from .telemetry import traced

METHODS = ["notes", "exam_form", "proc_codes_completed", "proc_codes_planned",
           "proc_dx_completed", "proc_dx_planned", "probing_chart", "radiograph_ai"]

RULES_V0 = {
    "version": "v0.1-placeholder",
    # Trust order when evidence types disagree. Probing chart first: it is the measured
    # evidence the 2017 definitions are written against. Then the clinician's
    # written diagnosis, then diagnosis codes, then the form, then procedures.
    # v0.1 (spec 003): when the probing chart is missing, the radiograph AI is a
    # LOWER BOUND on stage (stage = worst criterion, RBL is one of them): if it
    # shows more bone loss than the deciding evidence type implies, raise to its stage.
    # Tested against putting it ahead of the notes, which did worse (spec 003).
    "priority": ["probing_chart", "notes", "proc_dx_completed", "proc_dx_planned",
                 "exam_form", "proc_codes_completed", "proc_codes_planned"],
    "radiograph_lower_bound": True,
}
# Spec 005: the study design's starting order for the integrated phenotype. The order is this repo's own:
# Patel et al. 2022 (Methods Inf Med; docs/references.md item 4) uses the structured diagnosis section, then
# notes, then charting, with no exam-form or PSR step; its order will be algorithm_patel2022 (spec 024, not built
# yet; action item A2, checked against the full text). Not assumed final: scripts/18_phenotype_order.py scores every
# ordering of the four groups so the order can change if another evidence type proves more accurate.
DESIGN_GROUPS = {
    "exam_form": ["exam_form"],
    "dx_code": ["proc_dx_completed", "proc_dx_planned"],
    "notes": ["notes"],
    "probing_chart": ["probing_chart"],
}
DESIGN_ORDER = ["exam_form", "dx_code", "notes", "probing_chart"]


@traced
def rules_for_order(order: list[str], version: str | None = None, radiograph_lower_bound: bool = False) -> dict:
    return {"version": version or "order:" + ">".join(order),
            "priority": [m for g in order for m in DESIGN_GROUPS[g]],
            "radiograph_lower_bound": radiograph_lower_bound}


RULES_DESIGN = rules_for_order(DESIGN_ORDER, version="design-v1")

_ORDER = ["healthy", "gingivitis", "periodontitis_stage_1", "periodontitis_stage_2",
          "periodontitis_stage_3", "periodontitis_stage_4"]
# Five categories: healthy and gingivitis combined, then stage I-IV.
FIVE = ["healthy_gingivitis", *_ORDER[2:]]


@traced
def collapse5(s: pd.Series) -> pd.Series:
    """Map six statuses to five (healthy + gingivitis -> healthy_gingivitis); other values unchanged."""
    return s.replace({"healthy": "healthy_gingivitis", "gingivitis": "healthy_gingivitis"})


@traced
def phenotype(row: pd.Series, rules: dict) -> tuple[str, str]:
    """Integrated phenotype: (status, method that decided) under the given rules."""
    return phenotype_v0(row, rules)


@traced
def phenotype_v0(row: pd.Series, rules: dict = RULES_V0) -> tuple[str, str]:
    """Returns (status, method that decided)."""
    status, by = UNKNOWN, "none"
    for m in rules["priority"]:
        v = row.get(m, UNKNOWN)
        if isinstance(v, str) and v and v != UNKNOWN:
            status, by = v, m
            break
    rad = row.get("radiograph_ai", UNKNOWN)
    if rules.get("radiograph_lower_bound") and by != "probing_chart" and isinstance(rad, str) and rad in _ORDER:
        if status not in _ORDER or _ORDER.index(rad) > _ORDER.index(status):
            return rad, "radiograph_ai"
    return status, by


@traced
def cohen_kappa(a: pd.Series, b: pd.Series) -> float:
    # Plain object arrays, not pandas ops: the reliability bootstrap calls this ~10^5 times.
    a, b = np.asarray(a, dtype=object), np.asarray(b, dtype=object)
    cats = sorted(set(a) | set(b))
    n = len(a)
    if n == 0:
        return float("nan")
    po = (a == b).mean()
    pe = sum((a == c).mean() * (b == c).mean() for c in cats)
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


@traced
def agreement_matrix(df: pd.DataFrame, methods: list[str] = METHODS, level: str = "status") -> pd.DataFrame:
    """Pairwise agreement over visits where BOTH methods give an answer.

    level='status'  six classes; level='perio' periodontitis yes/no.
    Returns long format: method_a, method_b, n, pct_agree, kappa.
    """
    rows = []
    for a, b in itertools.combinations(methods, 2):
        both = df[(df[a] != UNKNOWN) & (df[b] != UNKNOWN)]
        x, y = both[a], both[b]
        if level == "perio":
            x, y = x.str.startswith("periodontitis"), y.str.startswith("periodontitis")
        rows.append({"method_a": a, "method_b": b, "n": len(both),
                     "pct_agree": float((x.values == y.values).mean()) if len(both) else float("nan"),
                     "kappa": cohen_kappa(x, y)})
    return pd.DataFrame(rows)


@traced
def coverage(df: pd.DataFrame, methods: list[str] = METHODS) -> pd.Series:
    """Share of visits where each method says anything at all."""
    return pd.Series({m: float((df[m] != UNKNOWN).mean()) for m in methods})


@traced
def split_halves(ids, seed: int) -> tuple[set, set]:
    """Seeded random halves of the review charts: (select, holdout). Written to
    phenotype_orders_split.csv so the R twin scores the same halves."""
    ids = np.array(sorted(ids))
    np.random.default_rng(seed).shuffle(ids)
    return {int(i) for i in ids[: len(ids) // 2]}, {int(i) for i in ids[len(ids) // 2:]}


@traced
def score_orders(key: pd.DataFrame, reviewer_wide: pd.DataFrame, n_boot: int = 200, seed: int = 0,
                 five: bool = True, margin: float = 0.05) -> pd.DataFrame:
    """Score every ordering of the four evidence groups (spec 005).

    The review charts are split in half by seed. The order is chosen on the
    'select' half (highest kappa vs reviewer consensus) and reported on the
    held-out half, with the acceptance test, so the chosen order isn't graded on
    the charts that chose it. key: review_key indexed by visit_id;
    reviewer_wide: visits x reviewers."""
    from .reliability import agreement_vs_humans, consensus  # local: avoid import cycle
    ids = np.array(sorted(set(key.index) & set(reviewer_wide.index)))
    sel, hold = split_halves(ids, seed)
    f = collapse5 if five else (lambda s: s)
    wide = reviewer_wide.apply(f)
    cons = f(consensus(reviewer_wide))
    cats = FIVE if five else _ORDER
    rows = []
    for order in itertools.permutations(DESIGN_GROUPS):
        rules = rules_for_order(list(order))
        pred = f(pd.Series({vid: phenotype(key.loc[vid], rules)[0] for vid in ids}))
        out = {"order": ">".join(order), "is_design_order": list(order) == DESIGN_ORDER}
        for name, part in (("select", sel), ("holdout", hold)):
            p = pred.reindex(sorted(part))
            c = cons.reindex(p.index)
            ok = c.isin(cats) & p.isin(cats)
            out[f"{name}_n"] = int(ok.sum())
            out[f"{name}_coverage"] = float(p.isin(cats).mean())
            out[f"{name}_pct_agree"] = float((p[ok] == c[ok]).mean()) if ok.any() else float("nan")
            out[f"{name}_kappa"] = cohen_kappa(p[ok], c[ok])
        vh = agreement_vs_humans(wide.reindex(sorted(hold)), {"m": pred.reindex(sorted(hold))},
                                 n_boot=n_boot, seed=seed, margin=margin)
        m = vh[vh["kind"] == "method"].iloc[0]
        out.update({"holdout_diff_vs_human_bar": m["diff_vs_human_bar"], "holdout_ci_low": m["ci_low"],
                    "holdout_ci_high": m["ci_high"], "holdout_verdict": m["verdict"] if n_boot else ""})
        rows.append(out)
    t = pd.DataFrame(rows).sort_values("select_kappa", ascending=False).reset_index(drop=True)
    t["selected"] = t.index == 0
    return t
