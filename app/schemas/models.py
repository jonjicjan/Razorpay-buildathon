from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChargebackCase(BaseModel):
    chargeback_id: str = "cb_live"
    reason_code: Literal["unauthorized", "item_not_received", "not_as_described"]
    merchant_category: str = "ecommerce"
    amount: float = Field(gt=0)
    delivery_confirmed: int = Field(ge=0, le=1)
    three_d_secure: int = Field(ge=0, le=1)
    device_fingerprint_match: int = Field(ge=0, le=1)
    ip_geolocation_match: int | None = 1
    customer_email_opened: int | None = 0
    customer_tenure_days: int = Field(ge=0)
    customer_prior_disputes: int = Field(ge=0)
    transaction_velocity_24h: int = Field(ge=1)
    days_since_transaction: int = Field(ge=1)
    amount_vs_customer_avg: float | None = 1.0
    transaction_date: str | None = None
    dispute_date: str | None = None
    tracking_id: str | None = None
    delivery_timestamp: str | None = None
    merchant_policy: str | None = None
    duplicate_chargeback: bool = False


class PredictResponse(BaseModel):
    chargeback_id: str
    winnability: float
    action: str
    reasons: list[str]
    llm_allowed: bool
    hard_stop: bool
    top_signals: list[dict[str, Any]] = []


class EvidenceItem(BaseModel):
    priority: int
    type: str
    description: str
    strength: Literal["strong", "moderate", "weak"]
    source_field: str


class EvidencePackage(BaseModel):
    evidence_package: list[EvidenceItem]
    representment_draft: str
    evidence_gaps: list[str]
    confidence: Literal["high", "medium", "low"]
    recommended_action: Literal["submit", "review", "abandon"]
    source: str = "llm"


class EvidenceResponse(BaseModel):
    chargeback_id: str
    winnability: float
    action: str
    package: EvidencePackage | None = None
    proxy_metrics: dict[str, Any] | None = None
    blocked_reason: str | None = None
