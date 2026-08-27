"""Credit-risk ranking metrics.

GINI is 2*AUC - 1 with y=1 as the bad outcome and a higher score meaning
higher predicted risk. Never take the absolute value: an inverted score
must come out negative.
"""
from __future__ import annotations

import numpy as np


def signed_gini(score, y, min_n: int = 20) -> float:
    from sklearn.metrics import roc_auc_score

    score = np.asarray(score, dtype=float)
    y = np.asarray(y, dtype=int)
    mask = np.isfinite(score) & np.isfinite(y)
    score, y = score[mask], y[mask]
    if len(y) < min_n or y.min() == y.max():
        return 0.0
    auc = float(roc_auc_score(y, score))
    return float(2 * auc - 1)
