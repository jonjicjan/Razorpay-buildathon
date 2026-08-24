"""Train baselines + XGBoost, select threshold on val, optionally freeze test metrics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from ml.evaluation.cost import load_cost_assumptions, load_policy_tiers, sweep_thresholds
from ml.evaluation.metrics import metrics_at_threshold, pr_curve_points
from ml.features.engineering import split_xy
from ml.training.baseline_logreg import build_logreg, build_tree
from ml.training.baseline_rules import rule_proba
from ml.training.train_xgb import build_xgb

ROOT = Path(__file__).resolve().parents[2]
SPLIT_DIR = ROOT / "data" / "splits"
ART_DIR = ROOT / "ml" / "artifacts"
EVAL_DIR = ROOT / "evaluation"


def _eval_rule(df: pd.DataFrame) -> dict:
    y = df["won"].to_numpy()
    return metrics_at_threshold(y, rule_proba(df), 0.5)


def _gain_top(model, n: int = 8) -> list[dict]:
    clf = model.named_steps["clf"]
    prep = model.named_steps["prep"]
    names = list(prep.get_feature_names_out())
    raw = clf.get_booster().get_score(importance_type="gain")
    mapped = []
    for i, name in enumerate(names):
        key = f"f{i}"
        if key in raw:
            mapped.append({"feature": name, "gain": float(raw[key])})
    mapped.sort(key=lambda r: r["gain"], reverse=True)
    return mapped[:n]


def train_and_select(run_test: bool = False) -> dict:
    ART_DIR.mkdir(parents=True, exist_ok=True)
    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    train = pd.read_csv(SPLIT_DIR / "train.csv")
    val = pd.read_csv(SPLIT_DIR / "val.csv")
    test = pd.read_csv(SPLIT_DIR / "test.csv")
    X_tr, y_tr = split_xy(train)
    X_va, y_va = split_xy(val)
    costs = load_cost_assumptions()
    policy = load_policy_tiers()

    pos = max(int(y_tr.sum()), 1)
    neg = max(int(len(y_tr) - y_tr.sum()), 1)
    xgb = build_xgb(scale_pos_weight=neg / pos)
    logreg = build_logreg()
    tree = build_tree()
    logreg.fit(X_tr, y_tr)
    tree.fit(X_tr, y_tr)
    xgb.fit(X_tr, y_tr)

    joblib.dump(logreg, ART_DIR / "logreg.joblib")
    joblib.dump(tree, ART_DIR / "tree.joblib")
    joblib.dump(xgb, ART_DIR / "xgb.joblib")

    yv = y_va.to_numpy()
    val_proba = {
        "rule": rule_proba(val),
        "logreg": logreg.predict_proba(X_va)[:, 1],
        "tree": tree.predict_proba(X_va)[:, 1],
        "xgboost": xgb.predict_proba(X_va)[:, 1],
    }
    val_metrics = {
        "rule": _eval_rule(val),
        "logreg": metrics_at_threshold(yv, val_proba["logreg"], 0.5),
        "tree": metrics_at_threshold(yv, val_proba["tree"], 0.5),
        "xgboost_at_0.5": metrics_at_threshold(yv, val_proba["xgboost"], 0.5),
    }
    cost_sweep = sweep_thresholds(
        yv,
        val_proba["xgboost"],
        fp_unit=float(costs["fp_unit_cost_inr"]),
        fn_unit=float(costs["fn_unit_cost_inr"]),
    )
    best_t = float(cost_sweep["best"]["threshold"])
    xgb_val_best = metrics_at_threshold(yv, val_proba["xgboost"], best_t)

    # Workflow bands are explicit business policy — not a padding of the binary cost optimum.
    lo = float(policy["do_not_fight_max"])
    hi = float(policy["recommend_contest_min"])
    thresholds = {
        "do_not_fight_max": lo,
        "recommend_contest_min": hi,
        "cost_optimal_binary": best_t,
        "manual_review": [lo, hi],
        "source": "policy bands from archetypes.yaml; binary cost-optimal kept separate for metrics",
    }

    payload = {
        "disclaimer": (
            "The dataset is synthetic and is used to validate the system methodology, "
            "not to claim production-level chargeback performance."
        ),
        "component": "ml_winnability",
        "validation": {
            "metrics": val_metrics,
            "xgboost_cost_optimal": xgb_val_best,
            "pr_curve": pr_curve_points(yv, val_proba["xgboost"]),
        },
        "cost_model": {
            "assumptions": costs,
            "sweep_best": cost_sweep["best"],
            "curve_sample": cost_sweep["curve"][::4],
        },
        "thresholds": thresholds,
        "feature_gain": _gain_top(xgb),
        "test": None,
        "test_evaluated": False,
    }

    (ART_DIR / "thresholds.json").write_text(json.dumps(thresholds, indent=2), encoding="utf-8")
    (EVAL_DIR / "val_metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if run_test:
        X_te, y_te = split_xy(test)
        yt = y_te.to_numpy()
        te_proba = xgb.predict_proba(X_te)[:, 1]
        payload["test"] = {
            "rule": _eval_rule(test),
            "logreg": metrics_at_threshold(yt, logreg.predict_proba(X_te)[:, 1], 0.5),
            "tree": metrics_at_threshold(yt, tree.predict_proba(X_te)[:, 1], 0.5),
            "xgboost": metrics_at_threshold(yt, te_proba, best_t),
            "note": "Held-out temporal test. Evaluated once after threshold freeze on validation.",
        }
        payload["test_evaluated"] = True
        (EVAL_DIR / "test_metrics.json").write_text(
            json.dumps({"disclaimer": payload["disclaimer"], **payload["test"]}, indent=2),
            encoding="utf-8",
        )

    (EVAL_DIR / "metrics.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final-test", action="store_true", help="Touch held-out test once.")
    args = parser.parse_args()
    result = train_and_select(run_test=args.final_test)
    print(
        json.dumps(
            {
                "val_xgb": result["validation"]["xgboost_cost_optimal"],
                "thresholds": result["thresholds"],
                "test_evaluated": result["test_evaluated"],
                "test": result["test"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
