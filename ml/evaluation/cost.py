"""Expected-cost threshold search. Costs are labelled assumptions."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
ARCHETYPE_PATH = ROOT / "data" / "synthetic" / "archetypes.yaml"


def load_cost_assumptions() -> dict:
    with ARCHETYPE_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg["cost_assumptions"]


def load_policy_tiers() -> dict:
    with ARCHETYPE_PATH.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg.get(
        "policy_tiers",
        {"do_not_fight_max": 0.35, "recommend_contest_min": 0.65},
    )


def expected_cost(fp: int, fn: int, fp_unit: float, fn_unit: float) -> float:
    return fp * fp_unit + fn * fn_unit


def sweep_thresholds(
    y_true: np.ndarray,
    proba: np.ndarray,
    fp_unit: float,
    fn_unit: float,
    grid: np.ndarray | None = None,
) -> dict[str, Any]:
    if grid is None:
        grid = np.round(np.linspace(0.10, 0.90, 81), 3)
    rows = []
    for t in grid:
        pred = (proba >= t).astype(int)
        fp = int(((pred == 1) & (y_true == 0)).sum())
        fn = int(((pred == 0) & (y_true == 1)).sum())
        tp = int(((pred == 1) & (y_true == 1)).sum())
        tn = int(((pred == 0) & (y_true == 0)).sum())
        cost = expected_cost(fp, fn, fp_unit, fn_unit)
        rows.append(
            {
                "threshold": float(t),
                "fp": fp,
                "fn": fn,
                "tp": tp,
                "tn": tn,
                "expected_cost": float(cost),
                "precision": tp / (tp + fp) if (tp + fp) else 0.0,
                "recall": tp / (tp + fn) if (tp + fn) else 0.0,
            }
        )
    best = min(rows, key=lambda r: r["expected_cost"])
    return {
        "fp_unit_cost_inr": fp_unit,
        "fn_unit_cost_inr": fn_unit,
        "assumption_note": (
            "Costs are placeholders from archetypes.yaml, not empirical merchant data."
        ),
        "best": best,
        "curve": rows,
    }
