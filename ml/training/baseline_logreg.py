from __future__ import annotations

from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.tree import DecisionTreeClassifier

from ml.features.engineering import build_preprocessor


def build_logreg() -> Pipeline:
    return Pipeline(
        [
            ("prep", build_preprocessor(scale_numeric=True)),
            (
                "clf",
                LogisticRegression(max_iter=400, class_weight="balanced", solver="lbfgs"),
            ),
        ]
    )


def build_tree() -> Pipeline:
    return Pipeline(
        [
            ("prep", build_preprocessor(scale_numeric=False)),
            (
                "clf",
                DecisionTreeClassifier(
                    max_depth=4, class_weight="balanced", random_state=42
                ),
            ),
        ]
    )
