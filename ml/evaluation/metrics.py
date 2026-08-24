"""Classification metrics for Component 1 (ML)."""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)


def metrics_at_threshold(y_true: np.ndarray, proba: np.ndarray, threshold: float) -> dict[str, Any]:
    pred = (proba >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, pred, labels=[0, 1]).ravel()
    return {
        "threshold": float(threshold),
        "precision": float(precision_score(y_true, pred, zero_division=0)),
        "recall": float(recall_score(y_true, pred, zero_division=0)),
        "f1": float(f1_score(y_true, pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_true, proba)),
        "roc_auc": float(roc_auc_score(y_true, proba)) if len(np.unique(y_true)) == 2 else None,
        "confusion_matrix": {
            "tn": int(tn),
            "fp": int(fp),
            "fn": int(fn),
            "tp": int(tp),
        },
        "support": {
            "n": int(len(y_true)),
            "positives": int(y_true.sum()),
            "negatives": int((1 - y_true).sum()),
        },
        "predicted_positive_rate": float(pred.mean()),
    }


def pr_curve_points(y_true: np.ndarray, proba: np.ndarray, max_points: int = 40) -> list[dict]:
    p, r, t = precision_recall_curve(y_true, proba)
    idx = np.linspace(0, len(p) - 1, num=min(max_points, len(p)), dtype=int)
    out = []
    for i in idx:
        thr = float(t[i]) if i < len(t) else 1.0
        out.append({"precision": float(p[i]), "recall": float(r[i]), "threshold": thr})
    return out
