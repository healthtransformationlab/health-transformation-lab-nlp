"""Quantitative validation: reviewer reliability, and how the algorithm and AI
compare with the reviewers.

    inter-reviewer      Fleiss' kappa (nominal) across all reviewers who staged
                        the same charts; pairwise Cohen's kappa; quadratic
                        weighted kappa treating status as ordinal
                        (healthy < gingivitis < stage I < ... < stage IV)
    consensus           majority vote per visit (ties → 'no_consensus')
    method vs reviewers each method / algorithm / AI model vs consensus, and
                        vs each reviewer (is it inside the reviewers' spread?).
                        Agreement is over visits where the method gives an
                        answer; `coverage` says how often that is. Report both:
                        a source that is right when present but usually absent
                        is a different finding from one that is often wrong.

    AI vs humans        the acceptance test (agreement_vs_humans): does a method
                        agree with the reviewers at least as much as they agree
                        with each other? After OHDSI's case-validation work
                        (Schuemie, Ostropolets et al., npj Digit Med 2025).

r/R/04_reliability.R computes the same numbers in R; the parity test checks.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd

from .harm import unsafe_rates
from .labels import Status
from .phenotype import cohen_kappa
from .telemetry import traced

ORDER = [s.value for s in Status]
# Five-category reports (spec 005) collapse healthy + gingivitis into one label.
FIVE = ["healthy_gingivitis", *ORDER[2:]]
VALID = [*ORDER, "healthy_gingivitis"]   # any value outside this is "no answer"


def _ordinal_for(*series: pd.Series) -> list[str]:
    return FIVE if any((s == "healthy_gingivitis").any() for s in series) else ORDER


@traced
def fleiss_kappa(wide: pd.DataFrame) -> float:
    """wide: rows = visits, cols = reviewers, values = category. Rows with any NA dropped."""
    w = wide.dropna()
    cats = sorted(pd.unique(w.values.ravel()))
    n = w.shape[1]
    counts = np.stack([(w.values == c).sum(axis=1) for c in cats], axis=1)  # N x k
    p_j = counts.sum(axis=0) / counts.sum()
    P_i = ((counts * (counts - 1)).sum(axis=1)) / (n * (n - 1))
    P_bar, P_e = P_i.mean(), (p_j ** 2).sum()
    return float((P_bar - P_e) / (1 - P_e))


@traced
def weighted_kappa(a: pd.Series, b: pd.Series, order: list[str] | None = None) -> float:
    """Quadratic-weighted Cohen's kappa over ordinal statuses; other values dropped.
    Uses the five-level order when the collapsed label is present."""
    order = order or _ordinal_for(a, b)
    keep = a.isin(order) & b.isin(order)
    x = a[keep].map(order.index).to_numpy()
    y = b[keep].map(order.index).to_numpy()
    k = len(order)
    O = np.zeros((k, k))
    for i, j in zip(x, y):
        O[i, j] += 1
    if O.sum() == 0:
        return float("nan")
    W = np.array([[(i - j) ** 2 / (k - 1) ** 2 for j in range(k)] for i in range(k)])
    E = np.outer(O.sum(axis=1), O.sum(axis=0)) / O.sum()
    return float(1 - (W * O).sum() / (W * E).sum())


@traced
def consensus(wide: pd.DataFrame) -> pd.Series:
    def vote(row):
        vc = row.dropna().value_counts()
        if vc.empty or (len(vc) > 1 and vc.iloc[0] == vc.iloc[1]):
            return "no_consensus"
        return vc.index[0]
    return wide.apply(vote, axis=1).rename("consensus")


_VALID = frozenset(VALID)


def _kappa_where_both(a: pd.Series, b: pd.Series) -> float:
    a, b = np.asarray(a, dtype=object), np.asarray(b, dtype=object)
    ok = np.fromiter((x in _VALID and y in _VALID for x, y in zip(a, b)), bool, len(a))
    return cohen_kappa(a[ok], b[ok])


# Labels as integer codes in sorted order (-1 = no answer), so the bootstrap can count with bincount.
# Same arithmetic in the same order as cohen_kappa, so the kappas are the very same floats.
_CODE = {label: i for i, label in enumerate(sorted(_VALID))}


def _label_codes(s: pd.Series) -> np.ndarray:
    return np.fromiter((_CODE.get(x, -1) if isinstance(x, str) else -1 for x in s), np.int64, len(s))


def _kappa_codes(a: np.ndarray, b: np.ndarray) -> float:
    ok = (a >= 0) & (b >= 0)
    a, b = a[ok], b[ok]
    n = len(a)
    if n == 0:
        return float("nan")
    po = (a == b).mean()
    ca, cb = np.bincount(a, minlength=len(_CODE)), np.bincount(b, minlength=len(_CODE))
    pe = sum((ca[c] / n) * (cb[c] / n) for c in range(len(_CODE)) if ca[c] or cb[c])
    return float("nan") if pe == 1 else float((po - pe) / (1 - pe))


@traced
def reliability_report(labels: pd.DataFrame, key: pd.DataFrame, compare: dict[str, pd.Series]) -> dict:
    """labels: reviewer_labels.csv; key: review_key.csv indexed by visit_id;
    compare: name -> Series(status) indexed by visit_id (methods, algorithm, AI)."""
    wide = labels.pivot_table(index="visit_id", columns="reviewer", values="status", aggfunc="first")
    cons = consensus(wide)
    pair = [{"a": a, "b": b, "kappa": cohen_kappa(wide[a].dropna(), wide[b].reindex(wide[a].dropna().index)),
             "weighted_kappa": weighted_kappa(wide[a], wide[b])}
            for a, b in itertools.combinations(wide.columns, 2)]
    rows = []
    for name, s in {"generator_chart_truth": key["truth_status"], **compare}.items():
        s = s.reindex(cons.index)
        has = s.isin(VALID)                  # the method said something about status
        ok = cons.isin(VALID) & has
        rows.append({"method": name, "coverage": float(has.mean()), "n": int(ok.sum()),
                     "pct_agree_consensus": float((s[ok] == cons[ok]).mean()),
                     "kappa_vs_consensus": cohen_kappa(s[ok], cons[ok]),
                     "weighted_kappa_vs_consensus": weighted_kappa(s[ok], cons[ok]),
                     "mean_kappa_vs_each_reviewer": float(np.nanmean(
                         [_kappa_where_both(s, wide[r]) for r in wide.columns])),
                     # spec 002: clinical severity of the errors (GlobalDentBench-style)
                     **{k: v for k, v in unsafe_rates(cons[ok], s[ok]).items() if k != "n"}})
    return {"n_visits": int(wide.shape[0]), "n_reviewers": int(wide.shape[1]),
            "fleiss_kappa": fleiss_kappa(wide),
            "consensus_reached": float(cons.isin(VALID).mean()),
            "pairwise": pd.DataFrame(pair), "methods": pd.DataFrame(rows), "consensus": cons}


@traced
def by_level(key: pd.DataFrame, cons: pd.Series, compare: dict[str, pd.Series]) -> pd.DataFrame:
    """Agreement with consensus per difficulty level (spec 002), plus the macro
    average over levels (as GlobalDentBench macro-averages over reasoning levels)."""
    rows = []
    lev = key["difficulty"].reindex(cons.index)
    for name, s in compare.items():
        s = s.reindex(cons.index)
        per = {}
        for level in ("L1", "L2", "L3"):
            ok = (lev == level) & cons.isin(VALID) & s.isin(VALID)
            per[level] = float((s[ok] == cons[ok]).mean()) if ok.any() else float("nan")
            rows.append({"method": name, "level": level, "n": int(ok.sum()), "pct_agree_consensus": per[level]})
        rows.append({"method": name, "level": "macro", "n": int(sum(r["n"] for r in rows[-3:])),
                     "pct_agree_consensus": float(np.nanmean(list(per.values())))})
    return pd.DataFrame(rows)


@traced
def agreement_vs_humans(wide: pd.DataFrame, compare: dict[str, pd.Series], n_boot: int = 500,
                        seed: int = 0, margin: float = 0.05) -> pd.DataFrame:
    """Is each method as reliable as a human reviewer?

    Human bar: mean Cohen's kappa over all reviewer pairs. Each reviewer also
    gets a row with their mean kappa against the OTHER reviewers (the spread of
    humans). Each method: mean kappa against every reviewer. diff = method - bar.

    A paired bootstrap over charts (same resample for the bar and every method)
    gives a 95% CI for diff. Verdict, with a non-inferiority margin fixed in
    advance: 'non-inferior' if ci_low > -margin; 'inferior' if ci_high < -margin;
    otherwise 'inconclusive'. Comparing with consensus instead would be unfair to
    the humans, since each reviewer is part of the consensus."""
    revs = list(wide.columns)
    pairs = list(itertools.combinations(revs, 2))

    def bar(w):
        return float(np.nanmean([_kappa_codes(w[a], w[b]) for a, b in pairs]))

    def vs_humans(s, w):
        return float(np.nanmean([_kappa_codes(s, w[r]) for r in revs]))

    aligned = {k: v.reindex(wide.index) for k, v in compare.items()}
    codes = {r: _label_codes(wide[r]) for r in revs}           # encode once; the bootstrap indexes arrays
    s_codes = {k: _label_codes(s) for k, s in aligned.items()}
    point_bar = bar(codes)
    rows = [{"rater": "humans (mean pairwise)", "kind": "bar", "mean_kappa_vs_humans": point_bar}]
    for r in revs:
        others = [o for o in revs if o != r]
        rows.append({"rater": f"human:{r}", "kind": "human", "mean_kappa_vs_humans": float(
            np.nanmean([_kappa_where_both(wide[r], wide[o]) for o in others]))})
    point = {k: vs_humans(c, codes) for k, c in s_codes.items()}

    rng = np.random.default_rng(seed)
    n = len(wide)
    boots = {k: [] for k in aligned}
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        wb = {r: c[idx] for r, c in codes.items()}
        b = bar(wb)
        for k, c in s_codes.items():
            boots[k].append(vs_humans(c[idx], wb) - b)
    for k in aligned:
        lo, hi = (np.nanpercentile(boots[k], [2.5, 97.5]) if n_boot else (np.nan, np.nan))
        verdict = ("non-inferior" if lo > -margin else "inferior" if hi < -margin else "inconclusive")
        rows.append({"rater": k, "kind": "method", "mean_kappa_vs_humans": point[k],
                     "diff_vs_human_bar": point[k] - point_bar, "ci_low": float(lo), "ci_high": float(hi),
                     "margin": margin, "verdict": verdict})
    return pd.DataFrame(rows, columns=["rater", "kind", "mean_kappa_vs_humans", "diff_vs_human_bar",
                                       "ci_low", "ci_high", "margin", "verdict"])


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * tp / (2 * tp + fp + fn) if tp + fp + fn else float("nan")
    return p, r, f1


@traced
def confusion_scores(truth: pd.Series, pred: pd.Series, classes: list[str] | None = None) -> pd.DataFrame:
    """Confusion counts with precision, recall and F1 per class, one-vs-rest, and pooled over the classes (spec 024
    FR-006, as Patel et al. 2022 Table 1 reports them). 'Positive' is the truth's class; a prediction outside
    `classes` (no answer, 'no diagnosis') is a negative prediction for every class. F1 = 2TP / (2TP + FP + FN)."""
    classes = classes or ORDER
    t = np.asarray(truth, dtype=object)
    p = np.asarray(pred, dtype=object)
    rows, tot = [], np.zeros(4, dtype=int)
    for c in classes:
        tp = int(((t == c) & (p == c)).sum())
        fp = int(((t != c) & (p == c)).sum())
        fn = int(((t == c) & (p != c)).sum())
        tn = len(t) - tp - fp - fn
        tot += (tp, fp, fn, tn)
        rows.append({"class": c, "tp": tp, "fp": fp, "fn": fn, "tn": tn, **dict(zip(("precision", "recall", "f1"),
                                                                                  _prf(tp, fp, fn)))})
    tp, fp, fn, tn = (int(x) for x in tot)
    rows.append({"class": "pooled", "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                 **dict(zip(("precision", "recall", "f1"), _prf(tp, fp, fn)))})
    return pd.DataFrame(rows, columns=["class", "tp", "fp", "fn", "tn", "precision", "recall", "f1"])
