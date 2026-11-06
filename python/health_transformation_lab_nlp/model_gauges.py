"""The tooth-loss model's results as gauges (#628): each measure is a question with an answer, the main model
(XGBoost) against a reference model (logistic regression), read from `tooth_loss_model.run`'s `scores` frame.

Measures, in reading order: AUC (how well it separates the two kinds of loss), sensitivity (how many periodontal
losses it finds), PPV (when it flags a tooth, how often it is right), LR+ and LR- (how much a flag, or no flag, moves
the odds), then specificity and NPV. LR+ = sensitivity / (1 - specificity) and LR- = (1 - sensitivity) / specificity
are computed here for display only; the scoring is unchanged. A ratio with a zero denominator stays blank.

Bands (lower, intermediate, higher) only where a published convention exists:
- AUC: Hosmer, Lemeshow & Sturdivant, Applied Logistic Regression, 3rd ed. (2013): under 0.7 poor, 0.7 to 0.8
  acceptable, 0.8 to 0.9 excellent, 0.9 and up outstanding;
- likelihood ratios: Jaeschke, Guyatt & Sackett, JAMA 1994;271(9):703-707 (Users' Guides to the Medical Literature):
  LR+ above 10 (LR- below 0.1) large, 5 to 10 (0.1 to 0.2) moderate, 2 to 5 (0.2 to 0.5) small, otherwise minimal.
Sensitivity, specificity, PPV and NPV get no band: there is no agreed clinical target, so the gauge says so.
Synthetic data only: every number is agreement with the generator's answer key, not performance on real patients.
"""

from __future__ import annotations

import math
from html import escape

import pandas as pd

from .telemetry import traced

AUC_SOURCE = "Hosmer, Lemeshow & Sturdivant 2013"
LR_SOURCE = "Jaeschke, Guyatt & Sackett, JAMA 1994"
NO_TARGET = "no agreed clinical target"

# measure -> (question, short label, kind): kind decides the reading and the band
MEASURES = {
    "auc": ("How well does it separate periodontal from other tooth loss?", "AUC", "auc"),
    "sensitivity": ("How many periodontal losses does it find?", "Sensitivity", "sensitivity"),
    "ppv": ("When it flags a tooth, how often is it periodontal?", "PPV", "ppv"),
    "lr_plus": ("When it flags a tooth, how much more likely is periodontal loss?", "LR+", "lr_plus"),
    "lr_minus": ("When it does not flag a tooth, can periodontal loss be ruled out?", "LR-", "lr_minus"),
    "specificity": ("How many other losses does it correctly leave unflagged?", "Specificity", "specificity"),
    "npv": ("When it does not flag a tooth, how often is that right?", "NPV", "npv"),
}
BAND_COLOUR = {"lower": "#E8A5A0", "intermediate": "#EBD9B4", "higher": "#9CCB9A", "not_set": "#D5DBDE"}
MODEL_LABEL = {"xgboost": "XGBoost", "logistic": "Logistic regression"}


def _ratio(a: float, b: float) -> float:
    return a / b if b and not math.isnan(a) and not math.isnan(b) else float("nan")


@traced
def auc_band(auc: float) -> str:
    """Hosmer, Lemeshow & Sturdivant (2013): under 0.7 lower, 0.7 to 0.8 intermediate, 0.8 and up higher."""
    if math.isnan(auc):
        return "not_set"
    return "lower" if auc < 0.7 else "intermediate" if auc < 0.8 else "higher"


@traced
def lr_band(lr: float, plus: bool) -> tuple[str, str]:
    """(band, evidence) for a likelihood ratio, Jaeschke, Guyatt & Sackett (1994)."""
    if math.isnan(lr):
        return "not_set", "undefined"
    x = lr if plus else (1 / lr if lr > 0 else math.inf)          # LR- read as its reciprocal
    if x > 10:
        return "higher", "strong evidence"
    if x > 5:
        return "higher", "moderate evidence"
    if x > 2:
        return "intermediate", "small effect"
    return "lower", "minimal effect"


def _values(scores: pd.DataFrame, model: str, label_set: str, feature_set: str, eval_set: str,
            threshold_name: str) -> dict:
    s = scores[(scores["model"] == model) & (scores["label_set"] == label_set)
               & (scores["feature_set"] == feature_set) & (scores["eval_set"] == eval_set)]
    if s.empty:
        raise ValueError(f"no scores for {model} on {label_set}/{feature_set}/{eval_set}")
    out = {}
    for _, r in s.iterrows():
        if r["metric"] in ("auc", "outcome_rate") or r.get("threshold_name") == threshold_name:
            out[r["metric"]] = (float(r["value"]), float(r.get("ci_low", float("nan"))),
                                float(r.get("ci_high", float("nan"))))
    nan3 = (float("nan"),) * 3
    sens, spec = out.get("sensitivity", nan3)[0], out.get("specificity", nan3)[0]
    out["lr_plus"] = (_ratio(sens, 1 - spec), float("nan"), float("nan"))
    out["lr_minus"] = (_ratio(1 - sens, spec), float("nan"), float("nan"))
    return out


def _reading(kind: str, v: float, evidence: str) -> str:
    if math.isnan(v):
        return "not defined on these teeth"
    pct = round(v * 100)
    return {"auc": f"{pct} of 100 pairs ranked correctly",
            "sensitivity": f"{pct} caught | {100 - pct} missed, per 100 periodontal losses",
            "ppv": f"{pct} correct | {100 - pct} false, per 100 flagged teeth",
            "lr_plus": f"LR+ {v:.1f}: {evidence}; a flagged tooth is about {v:.0f}x as likely to be periodontal",
            "lr_minus": f"LR- {v:.2f}: {evidence}; an unflagged tooth is "
                        f"{'only slightly' if v > 0.5 else 'somewhat' if v > 0.2 else 'much'} less likely to be "
                        "periodontal",
            "specificity": f"{pct} left unflagged | {100 - pct} flagged, per 100 other losses",
            "npv": f"{pct} right | {100 - pct} wrong, per 100 unflagged teeth",
            }.get(kind, f"{pct} of 100")


@traced
def gauge_table(scores: pd.DataFrame, label_set: str = "completed", feature_set: str = "shared",
                eval_set: str = "held_out", threshold_name: str = "youden_train", main: str = "xgboost",
                reference: str = "logistic") -> pd.DataFrame:
    """One row per measure (MEASURES order): the main model's value and 95% interval, the reference model's value,
    the difference in percentage points (AUC and the rates; ratios as plain differences), a band, a plain reading, the
    random-selection baseline (PPV: the outcome rate) and the band's source."""
    a = _values(scores, main, label_set, feature_set, eval_set, threshold_name)
    b = _values(scores, reference, label_set, feature_set, eval_set, threshold_name)
    nan = float("nan")
    rows = []
    for measure, (question, label, kind) in MEASURES.items():
        v, lo, hi = a.get(measure, (nan, nan, nan))
        ref = b.get(measure, (nan,))[0]
        ratio = measure.startswith("lr_")
        diff = (v - ref) if ratio else (v - ref) * 100
        evidence = ""
        if kind == "auc":
            band, source = auc_band(v), AUC_SOURCE
        elif ratio:
            band, evidence = lr_band(v, measure == "lr_plus")
            source = LR_SOURCE
        else:
            band, source = "not_set", NO_TARGET
        rows.append({"measure": measure, "label": label, "question": question, "model": main, "value": v,
                     "ci_low": lo, "ci_high": hi, "reference_model": reference, "reference_value": ref,
                     "difference_pts": diff, "band": band, "reading": _reading(kind, v, evidence),
                     "baseline": a.get("outcome_rate", (nan,))[0] if measure == "ppv" else nan, "source": source})
    return pd.DataFrame(rows)


def _arc(cx: float, cy: float, r: float, a0: float, a1: float) -> str:
    """An SVG arc along the top half-circle, from fraction a0 to a1 of the way left to right."""
    def pt(f):
        ang = math.pi * (1 - f)
        return cx + r * math.cos(ang), cy - r * math.sin(ang)
    (x0, y0), (x1, y1) = pt(a0), pt(a1)
    return f"M{x0:.1f},{y0:.1f} A{r},{r} 0 0 1 {x1:.1f},{y1:.1f}"


def _bands(measure: str) -> list[tuple[float, float, str]]:
    if measure == "auc":                                         # the dial runs 0.5 (chance) to 1
        return [(0, 0.4, "lower"), (0.4, 0.6, "intermediate"), (0.6, 1, "higher")]
    if measure in ("lr_plus", "lr_minus"):                       # log scale from 1 to 100: lr_band's cut-offs 2 and 5
        return [(0, math.log10(2) / 2, "lower"), (math.log10(2) / 2, math.log10(5) / 2, "intermediate"),
                (math.log10(5) / 2, 1, "higher")]
    return [(0, 1, "not_set")]


def _position(measure: str, v: float) -> float:
    if math.isnan(v):
        return 0.0
    if measure == "auc":
        return min(1.0, max(0.0, (v - 0.5) / 0.5))
    if measure in ("lr_plus", "lr_minus"):                      # LR- reads better as it falls: 1/LR on the dial
        x = v if measure == "lr_plus" else (1 / v if v > 0 else 100)
        return min(1.0, max(0.0, math.log10(max(x, 1)) / 2))     # 1 at the left, 100 at the right
    return min(1.0, max(0.0, v))


def _fmt(measure: str, v: float) -> str:
    if math.isnan(v):
        return "n/a"
    return f"{v:.2f}" if measure.startswith("lr_") else f"{v * 100:.1f}%"


def _gauge_svg(row: pd.Series) -> str:
    cx, cy, r = 110, 105, 80
    arcs = "".join(f'<path d="{_arc(cx, cy, r, a0, a1)}" stroke="{BAND_COLOUR[band]}" stroke-width="18" '
                   'fill="none"/>' for a0, a1, band in _bands(row["measure"]))
    f = _position(row["measure"], row["value"])
    ang = math.pi * (1 - f)
    nx, ny = cx + (r - 14) * math.cos(ang), cy - (r - 14) * math.sin(ang)
    needle = (f'<line x1="{cx}" y1="{cy}" x2="{nx:.1f}" y2="{ny:.1f}" stroke="#1B3139" stroke-width="3"/>'
              f'<circle cx="{cx}" cy="{cy}" r="6" fill="#fff" stroke="#1B3139" stroke-width="3"/>')
    return (f'<svg viewBox="0 0 220 120" width="220" height="120" role="img" '
            f'aria-label="{escape(row["label"])} {escape(_fmt(row["measure"], row["value"]))}">{arcs}{needle}</svg>')


@traced
def gauges_html(table: pd.DataFrame, title: str) -> str:
    """A self-contained page: one gauge per measure (the needle is the main model), the reference model's value and
    the difference under it, the reading, the band and its source. Labelled SYNTHETIC."""
    cards = []
    for _, r in table.iterrows():
        diff = r["difference_pts"] + 0.0 if abs(r["difference_pts"]) >= 0.05 else 0.0   # never "-0.0"
        unit = "" if r["measure"].startswith("lr_") else " pts"
        ref = (f'vs. {escape(MODEL_LABEL.get(r["reference_model"], r["reference_model"]))} '
               f'{_fmt(r["measure"], r["reference_value"])}'
               + (f' | {diff:+.1f}{unit}' if not math.isnan(diff) else ""))
        base = (f'<p class="small">Random selection: {r["baseline"] * 100:.1f}%</p>'
                if not math.isnan(r["baseline"]) else "")
        band = "target not set" if r["band"] == "not_set" else f'{r["band"]} ({escape(r["source"])})'
        ci = (f' <span class="small">95% CI {_fmt(r["measure"], r["ci_low"])} to {_fmt(r["measure"], r["ci_high"])}'
              '</span>' if not math.isnan(r["ci_low"]) else "")
        cards.append(f'<div class="card"><h2>{escape(r["label"])}</h2><p class="q">{escape(r["question"])}</p>'
                     f'{_gauge_svg(r)}<p class="v">{_fmt(r["measure"], r["value"])}{ci}</p>'
                     f'<p class="m">{escape(MODEL_LABEL.get(r["model"], r["model"]))}</p>'
                     f'<p class="small">{ref}</p><p>{escape(r["reading"])}</p>{base}'
                     f'<p class="small">Band: {band}</p></div>')
    legend = "".join(f'<span><i style="background:{BAND_COLOUR[b]}"></i>{t}</span>' for b, t in
                     (("lower", "Lower"), ("intermediate", "Intermediate"), ("higher", "Higher"),
                      ("not_set", "Target not set")))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<style>body{{font-family:Helvetica,Arial,sans-serif;color:#1B3139;background:#F7F5EF;margin:0;padding:16px}}
h1{{font-size:24px}}.banner{{background:#B4501F;color:#fff;padding:6px 12px;border-radius:6px;display:inline-block}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:16px;margin-top:16px}}
.card{{background:#fff;border:1px solid #D9D3C4;border-radius:12px;padding:16px;text-align:center}}
.card h2{{margin:0;font-size:20px}}.q{{margin:4px 0 8px;font-size:14px}}.v{{font-size:28px;font-weight:700;margin:0}}
.m{{margin:0;font-weight:700;letter-spacing:1px;text-transform:uppercase;font-size:12px}}
.small{{font-size:12px;color:#5B6B73;margin:4px 0}}.legend span{{margin-right:14px;font-size:13px}}
.legend i{{display:inline-block;width:12px;height:12px;border-radius:2px;margin-right:4px;vertical-align:middle}}
</style></head><body><h1>{escape(title)}</h1>
<p class="banner">SYNTHETIC: agreement with the generator's answer key, not performance on real patients</p>
<p class="legend">{legend}</p><div class="grid">{''.join(cards)}</div>
<p class="small">The needle is {escape(MODEL_LABEL.get(table['model'].iloc[0], ''))}; the reference value under it
is {escape(MODEL_LABEL.get(table['reference_model'].iloc[0], ''))}. Bands: AUC after {AUC_SOURCE}; likelihood
ratios after {LR_SOURCE}. Sensitivity, specificity, PPV and NPV have no agreed clinical target.</p></body></html>
"""
