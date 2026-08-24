"""Train-time feature transforms. Leakage columns are dropped here."""

from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from ml.features.schema import (
    BOOLEAN_FEATURES,
    CATEGORICAL_FEATURES,
    LEAKAGE_BLOCKLIST,
    MODEL_FEATURES,
    NUMERIC_FEATURES,
    TARGET,
)


def assert_no_leakage(columns: list[str]) -> None:
    leaked = [c for c in columns if c in LEAKAGE_BLOCKLIST]
    if leaked:
        raise ValueError(f"Leakage features in model matrix: {leaked}")


def split_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    missing = [c for c in MODEL_FEATURES if c not in df.columns]
    if missing:
        raise KeyError(f"Missing model features: {missing}")
    X = df[MODEL_FEATURES].copy()
    for col in BOOLEAN_FEATURES:
        X[col] = pd.to_numeric(X[col], errors="coerce")
    y = df[TARGET].astype(int)
    assert_no_leakage(list(X.columns))
    return X, y


def build_preprocessor(scale_numeric: bool = True) -> ColumnTransformer:
    numeric_steps: list = [("imputer", SimpleImputer(strategy="median"))]
    if scale_numeric:
        numeric_steps.append(("scaler", StandardScaler()))
    numeric = Pipeline(numeric_steps)
    boolean = Pipeline([("imputer", SimpleImputer(strategy="most_frequent"))])
    categorical = Pipeline(
        [
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("num", numeric, NUMERIC_FEATURES),
            ("bool", boolean, BOOLEAN_FEATURES),
            ("cat", categorical, CATEGORICAL_FEATURES),
        ]
    )
