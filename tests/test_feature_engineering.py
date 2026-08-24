import pandas as pd

from ml.features.engineering import split_xy
from ml.features.schema import LEAKAGE_BLOCKLIST, MODEL_FEATURES


def test_split_xy_uses_only_model_features():
    row = {c: 0 for c in MODEL_FEATURES}
    row.update(
        {
            "reason_code": "unauthorized",
            "merchant_category": "ecommerce",
            "amount": 1000,
            "won": 1,
            "archetype": "no_evidence",
            "procedural_flip": 0,
        }
    )
    df = pd.DataFrame([row])
    X, y = split_xy(df)
    assert list(X.columns) == MODEL_FEATURES
    assert set(X.columns).isdisjoint(set(LEAKAGE_BLOCKLIST) - {"won"})
    assert int(y.iloc[0]) == 1
