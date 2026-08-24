"""Rule baseline: contest only when delivery AND 3DS are both present."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rule_predict(df: pd.DataFrame) -> np.ndarray:
    delivery = pd.to_numeric(df["delivery_confirmed"], errors="coerce").fillna(0)
    tds = pd.to_numeric(df["three_d_secure"], errors="coerce").fillna(0)
    return ((delivery == 1) & (tds == 1)).astype(int).to_numpy()


def rule_proba(df: pd.DataFrame) -> np.ndarray:
    pred = rule_predict(df)
    return np.where(pred == 1, 0.85, 0.20)
