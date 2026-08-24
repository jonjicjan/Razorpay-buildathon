"""Load the frozen XGBoost pipeline and return winnability + local signals."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.features.schema import BOOLEAN_FEATURES, MODEL_FEATURES, NUMERIC_FEATURES

ROOT = Path(__file__).resolve().parents[2]
MODEL_PATH = ROOT / "ml" / "artifacts" / "xgb.joblib"


@lru_cache(maxsize=1)
def load_model():
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Missing {MODEL_PATH}. Run: python -m ml.training.train --final-test"
        )
    return joblib.load(MODEL_PATH)


def case_to_frame(payload: dict) -> pd.DataFrame:
    row = {}
    for key in MODEL_FEATURES:
        val = payload.get(key)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            row[key] = np.nan if key in NUMERIC_FEATURES + BOOLEAN_FEATURES else None
        else:
            row[key] = val
    return pd.DataFrame([row])


def predict_winnability(payload: dict) -> tuple[float, list[dict]]:
    model = load_model()
    X = case_to_frame(payload)
    proba = float(model.predict_proba(X)[0, 1])
    clf = model.named_steps["clf"]
    prep = model.named_steps["prep"]
    names = list(prep.get_feature_names_out())
    gain = clf.get_booster().get_score(importance_type="gain")
    signals = []
    for i, name in enumerate(names):
        key = f"f{i}"
        if key in gain:
            clean = (
                name.replace("cat__", "")
                .replace("bool__", "")
                .replace("num__", "")
            )
            signals.append({"feature": clean, "gain": float(gain[key])})
    signals.sort(key=lambda r: r["gain"], reverse=True)
    return proba, signals[:5]
