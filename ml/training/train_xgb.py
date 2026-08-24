"""XGBoost winnability model."""

from __future__ import annotations

from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from ml.features.engineering import build_preprocessor


def build_xgb(scale_pos_weight: float = 1.0) -> Pipeline:
    return Pipeline(
        [
            ("prep", build_preprocessor(scale_numeric=False)),
            (
                "clf",
                XGBClassifier(
                    n_estimators=350,
                    max_depth=4,
                    learning_rate=0.06,
                    subsample=0.85,
                    colsample_bytree=0.85,
                    min_child_weight=4,
                    reg_lambda=1.4,
                    objective="binary:logistic",
                    eval_metric="aucpr",
                    n_jobs=4,
                    random_state=42,
                    scale_pos_weight=scale_pos_weight,
                    tree_method="hist",
                ),
            ),
        ]
    )
