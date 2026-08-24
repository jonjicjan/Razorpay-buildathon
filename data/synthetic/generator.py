"""Archetype-based synthetic chargeback generator.

Labels are sampled from archetype-level Bernoulli priors plus a hidden
adjudicator factor and random procedural flips. They are NOT a
deterministic function of the model features.

Train / val / test are generated with independent seeds.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
ARCHETYPE_PATH = ROOT / "data" / "synthetic" / "archetypes.yaml"
SPLIT_DIR = ROOT / "data" / "splits"

POLICIES = {
    "ecommerce": "30-day returns on unused goods. Signature on delivery is accepted proof of receipt.",
    "digital_goods": "Digital items are non-refundable after delivery to the registered account.",
    "travel": "Cancellations follow fare rules. 3DS-authenticated bookings are treated as cardholder-present.",
    "grocery": "Perishable goods are non-returnable after delivery confirmation.",
    "fashion": "7-day exchange window. Delivery photo and tracking are retained for 180 days.",
    "subscriptions": "First billing cycle may be refunded; subsequent cycles require unused-period evidence.",
    "services": "Service completion notes and customer confirmation emails are retained.",
}


def load_config() -> dict:
    with ARCHETYPE_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _clip_int(x: float, lo: int, hi: int | None = None) -> int:
    v = int(round(x))
    v = max(lo, v)
    if hi is not None:
        v = min(hi, v)
    return v


def _sample_from_spec(rng: np.random.Generator, spec: dict, n: int) -> np.ndarray:
    if "poisson" in spec:
        return rng.poisson(spec["poisson"], size=n).astype(float)
    if "mean" in spec and "sigma" in spec:
        return rng.lognormal(spec["mean"], spec["sigma"], size=n)
    mean = spec.get("mean", 0.0)
    std = spec.get("std", 1.0)
    vals = rng.normal(mean, std, size=n)
    lo = spec.get("min")
    hi = spec.get("max")
    if lo is not None:
        vals = np.maximum(vals, lo)
    if hi is not None:
        vals = np.minimum(vals, hi)
    return vals


def _archetype_map(cfg: dict) -> dict:
    items = dict(cfg["archetypes"])
    drift = cfg["drift_archetype"]
    name = drift["name"]
    items[name] = {k: v for k, v in drift.items() if k not in {"name", "mix_weight_late"}}
    return items


def _weights(cfg: dict, late: bool) -> tuple[list[str], np.ndarray]:
    names = list(cfg["archetypes"].keys())
    w = np.array([cfg["archetypes"][n]["mix_weight"] for n in names], dtype=float)
    if late:
        drift = cfg["drift_archetype"]
        names = names + [drift["name"]]
        w = w * (1.0 - drift["mix_weight_late"])
        w = np.append(w, drift["mix_weight_late"])
    w = w / w.sum()
    return names, w


def _draw_archetype_rows(
    rng: np.random.Generator,
    spec: dict,
    name: str,
    n: int,
    start: date,
    month_offset: np.ndarray,
) -> pd.DataFrame:
    feats = spec["features"]
    reason = rng.choice(spec["reason_codes"], size=n)
    cat = rng.choice(spec["merchant_categories"], size=n)
    amount = np.round(_sample_from_spec(rng, feats["amount_lognormal"], n), 2)
    tenure = np.array(
        [_clip_int(v, 0, 4000) for v in _sample_from_spec(rng, feats["customer_tenure_days"], n)]
    )
    prior = np.array(
        [_clip_int(v, 0, 40) for v in _sample_from_spec(rng, feats["customer_prior_disputes"], n)]
    )
    vel = np.array(
        [_clip_int(v, 1, 40) for v in _sample_from_spec(rng, feats["transaction_velocity_24h"], n)]
    )
    days = np.array(
        [_clip_int(v, 1, 180) for v in _sample_from_spec(rng, feats["days_since_transaction"], n)]
    )
    amt_vs = np.round(
        np.clip(_sample_from_spec(rng, feats["amount_vs_customer_avg"], n), 0.1, 8.0), 3
    )

    delivery = rng.random(n) < float(feats["delivery_confirmed"])
    tds = rng.random(n) < float(feats["three_d_secure"])
    device = rng.random(n) < float(feats["device_fingerprint_match"])
    geo = rng.random(n) < float(feats["ip_geolocation_match"])
    email = rng.random(n) < float(feats["customer_email_opened"])

    strictness = rng.normal(0.0, 0.12, size=n)
    p = np.clip(spec["win_rate_prior"] - 0.25 * strictness, 0.02, 0.95)
    won = rng.random(n) < p

    tx_dates, dispute_dates, delivery_ts, tracking = [], [], [], []
    for i in range(n):
        month = int(month_offset[i])
        tx = start + timedelta(days=int(month * 30 + int(rng.integers(0, 28))))
        disp = tx + timedelta(days=int(days[i]))
        tx_dates.append(tx.isoformat())
        dispute_dates.append(disp.isoformat())
        if delivery[i]:
            dt = datetime.combine(tx, datetime.min.time()) + timedelta(
                hours=int(rng.integers(18, 96))
            )
            delivery_ts.append(dt.strftime("%Y-%m-%d %H:%M:%S"))
            tracking.append(f"TRK{int(rng.integers(10**8, 10**9))}")
        else:
            delivery_ts.append("")
            tracking.append("")

    ids = [
        hashlib.sha1(f"{name}-{i}-{rng.random()}".encode()).hexdigest()[:12]
        for i in range(n)
    ]
    cust = [f"cust_{int(rng.integers(10_000, 99_999))}" for _ in range(n)]

    return pd.DataFrame(
        {
            "chargeback_id": ids,
            "customer_id": cust,
            "archetype": name,
            "reason_code": reason,
            "merchant_category": cat,
            "amount": amount,
            "delivery_confirmed": delivery.astype(int),
            "three_d_secure": tds.astype(int),
            "device_fingerprint_match": device.astype(int),
            "ip_geolocation_match": geo.astype(int),
            "customer_email_opened": email.astype(int),
            "customer_tenure_days": tenure,
            "customer_prior_disputes": prior,
            "transaction_velocity_24h": vel,
            "days_since_transaction": days,
            "amount_vs_customer_avg": amt_vs,
            "transaction_date": tx_dates,
            "dispute_date": dispute_dates,
            "tracking_id": tracking,
            "delivery_timestamp": delivery_ts,
            "merchant_policy": [POLICIES.get(c, POLICIES["ecommerce"]) for c in cat],
            "hidden_adjudicator_strictness": np.round(strictness, 4),
            "won_raw": won.astype(int),
            "month_index": month_offset.astype(int),
        }
    )


def generate_split(
    cfg: dict,
    *,
    n: int,
    seed: int,
    split: str,
    month_range: tuple[int, int],
    late_drift: bool,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    names, weights = _weights(cfg, late=late_drift)
    specs = _archetype_map(cfg)
    chosen = rng.choice(names, size=n, p=weights)
    month_lo, month_hi = month_range
    months = rng.integers(month_lo, month_hi + 1, size=n)
    start = date.fromisoformat(cfg["generation"]["start_date"])

    frames = []
    for name in names:
        mask = chosen == name
        k = int(mask.sum())
        if k == 0:
            continue
        frames.append(
            _draw_archetype_rows(rng, specs[name], name, k, start, months[mask])
        )
    df = pd.concat(frames, ignore_index=True)
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)

    flip_rate = float(cfg["generation"]["outcome_flip_rate"])
    flip = rng.random(len(df)) < flip_rate
    df["procedural_flip"] = flip.astype(int)
    df["won"] = np.where(flip, 1 - df["won_raw"], df["won_raw"]).astype(int)
    df.drop(columns=["won_raw"], inplace=True)

    miss = float(cfg["generation"]["missingness_rate"])
    optional = ["ip_geolocation_match", "customer_email_opened", "amount_vs_customer_avg"]
    for col in optional:
        drop = rng.random(len(df)) < miss
        if col == "amount_vs_customer_avg":
            df.loc[drop, col] = np.nan
        else:
            df.loc[drop, col] = np.nan

    df["split"] = split
    df["generation_seed"] = seed
    return df


def generate_all(cfg: dict | None = None) -> dict:
    cfg = cfg or load_config()
    g = cfg["generation"]
    train = generate_split(
        cfg, n=g["n_train"], seed=101, split="train", month_range=(1, 8), late_drift=False
    )
    val = generate_split(
        cfg, n=g["n_val"], seed=202, split="val", month_range=(9, 10), late_drift=True
    )
    test = generate_split(
        cfg, n=g["n_test"], seed=303, split="test", month_range=(11, 12), late_drift=True
    )

    SPLIT_DIR.mkdir(parents=True, exist_ok=True)
    train.to_csv(SPLIT_DIR / "train.csv", index=False)
    val.to_csv(SPLIT_DIR / "val.csv", index=False)
    test.to_csv(SPLIT_DIR / "test.csv", index=False)

    manifest = {
        "synthetic": True,
        "disclaimer": (
            "The dataset is synthetic and is used to validate the system methodology, "
            "not to claim production-level chargeback performance."
        ),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "n_train": len(train),
        "n_val": len(val),
        "n_test": len(test),
        "seeds": {"train": 101, "val": 202, "test": 303},
        "temporal": {
            "train_months": [1, 8],
            "val_months": [9, 10],
            "test_months": [11, 12],
        },
        "win_rate": {
            "train": float(train["won"].mean()),
            "val": float(val["won"].mean()),
            "test": float(test["won"].mean()),
        },
        "test_frozen": True,
        "leakage_blocklist": cfg["leakage_blocklist"],
    }
    (SPLIT_DIR / "generation_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-manifest", action="store_true")
    args = parser.parse_args()
    manifest = generate_all()
    if args.print_manifest:
        print(json.dumps(manifest, indent=2))
    else:
        print(f"Wrote splits to {SPLIT_DIR}")
        print(
            json.dumps(
                {k: manifest[k] for k in ("n_train", "n_val", "n_test", "win_rate")},
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
