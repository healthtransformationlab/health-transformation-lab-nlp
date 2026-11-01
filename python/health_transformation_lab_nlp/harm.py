"""Clinical severity of a misclassification (spec 002).

Adapted from GlobalDentBench's safety grading (arXiv 2605.24636): S0 safe or
low-risk, S1 potential for reversible harm, S2 potential for irreversible harm.
There it grades an answer to a clinical question; here it grades the status a
method assigned to a chart against the reviewers' status.

DRAFT matrix, pending periodontist sign-off (spec 002 task T012):

    correct                                             S0
    healthy <-> gingivitis                              S0
    periodontitis called healthy/gingivitis (missed)
        truth stage I-II                                S1  delayed, reversible
        truth stage III-IV                              S2  risk of irreversible tooth loss
    healthy/gingivitis called periodontitis (overcall)  S1  unneeded SRP / referral
    periodontitis, stage too low (under-staged)
        truth stage III-IV                              S1  misses surgical/referral pathway
        truth stage II -> I                             S0  same initial care
    periodontitis, stage too high (over-staged)
        by one stage                                    S0
        by two or more                                  S1  overtreatment

Unsafe rate = (S1 + S2) / visits where the method gave a status. r/R/04_reliability.R
has the same matrix; the parity test checks they agree.
"""

from __future__ import annotations

import pandas as pd

from .labels import HEALTHY_OR_GINGIVITIS, LABELS
from .telemetry import traced

ORDER = LABELS  # healthy, gingivitis, stage 1..4
_MERGED = ("healthy_gingivitis", HEALTHY_OR_GINGIVITIS)


@traced
def severity(truth: str, pred: str) -> str:
    # five-category reports: the collapsed label grades like "healthy" (healthy_or_gingivitis: labels.GROUPINGS)
    truth, pred = ("healthy" if x in _MERGED else x for x in (truth, pred))
    t, p = ORDER.index(truth), ORDER.index(pred)
    if t == p:
        return "S0"
    t_perio, p_perio = t >= 2, p >= 2
    if not t_perio and not p_perio:
        return "S0"
    if t_perio and not p_perio:
        return "S2" if t >= 4 else "S1"
    if not t_perio and p_perio:
        return "S1"
    if p < t:
        return "S1" if t >= 4 else "S0"
    return "S0" if p - t == 1 else "S1"


@traced
def unsafe_rates(truth: pd.Series, pred: pd.Series) -> dict:
    ok = truth.isin([*ORDER, *_MERGED]) & pred.isin([*ORDER, *_MERGED])
    if not ok.any():
        return {"n": 0, "unsafe_rate": float("nan"), "s2_rate": float("nan")}
    sev = [severity(t, p) for t, p in zip(truth[ok], pred[ok])]
    n = len(sev)
    return {"n": n, "unsafe_rate": sum(s != "S0" for s in sev) / n, "s2_rate": sum(s == "S2" for s in sev) / n}
