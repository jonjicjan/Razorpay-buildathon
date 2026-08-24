"""Canonical feature schema. Leakage columns never enter the model."""

from __future__ import annotations

CATEGORICAL_FEATURES = ["reason_code", "merchant_category"]

BOOLEAN_FEATURES = [
    "delivery_confirmed",
    "three_d_secure",
    "device_fingerprint_match",
    "ip_geolocation_match",
    "customer_email_opened",
]

NUMERIC_FEATURES = [
    "amount",
    "customer_tenure_days",
    "customer_prior_disputes",
    "transaction_velocity_24h",
    "days_since_transaction",
    "amount_vs_customer_avg",
]

MODEL_FEATURES = CATEGORICAL_FEATURES + BOOLEAN_FEATURES + NUMERIC_FEATURES
TARGET = "won"

LEAKAGE_BLOCKLIST = [
    "won",
    "archetype",
    "procedural_flip",
    "hidden_adjudicator_strictness",
    "split",
    "generation_seed",
    "month_index",
    "tracking_id",
    "delivery_timestamp",
    "merchant_policy",
    "chargeback_id",
    "customer_id",
    "transaction_date",
    "dispute_date",
]
