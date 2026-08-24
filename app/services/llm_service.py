"""LLM evidence assembler. Never classifies winnability.

If no API key is present, a grounded template assembler is used and labelled
as an offline fallback — not as a live LLM call.
"""

from __future__ import annotations

import json
import os
from typing import Any

from app.schemas.models import EvidenceItem, EvidencePackage

SYSTEM = """You assemble a chargeback representment package for a merchant.
Use ONLY facts in the JSON evidence object. Do not invent tracking IDs,
dates, 3DS results, delivery events, or customer history.
If a fact is missing, put it in evidence_gaps.
Return JSON only matching the schema.
"""


def _present_facts(case: dict) -> list[tuple[str, str, str]]:
    facts: list[tuple[str, str, str]] = []
    if case.get("delivery_confirmed") == 1:
        track = case.get("tracking_id") or "tracking on file"
        facts.append(("delivery_proof", "strong", f"Delivery confirmed ({track})."))
    if case.get("three_d_secure") == 1:
        facts.append(("three_d_secure", "strong", "3-D Secure authentication completed."))
    if case.get("device_fingerprint_match") == 1:
        facts.append(("device_match", "moderate", "Device fingerprint matched the customer's known device."))
    if case.get("ip_geolocation_match") == 1:
        facts.append(("geo_match", "moderate", "IP geolocation was consistent with the customer's usual region."))
    if case.get("customer_email_opened") == 1:
        facts.append(("email_engagement", "moderate", "Customer opened the order / delivery email."))
    tenure = int(case.get("customer_tenure_days") or 0)
    if tenure >= 180:
        facts.append(("customer_history", "moderate", f"Customer tenure is {tenure} days."))
    if case.get("merchant_policy"):
        facts.append(("merchant_policy", "weak", str(case["merchant_policy"])))
    return facts


def _gaps(case: dict) -> list[str]:
    gaps = []
    if case.get("delivery_confirmed") != 1:
        gaps.append("No delivery confirmation or tracking id.")
    if case.get("three_d_secure") != 1:
        gaps.append("3DS was not completed.")
    if case.get("device_fingerprint_match") != 1:
        gaps.append("Device fingerprint did not match.")
    if not case.get("customer_email_opened"):
        gaps.append("No proof the customer opened fulfilment email.")
    return gaps


def template_package(case: dict) -> EvidencePackage:
    facts = _present_facts(case)
    items = [
        EvidenceItem(
            priority=i + 1,
            type=kind,
            description=desc,
            strength=strength,  # type: ignore[arg-type]
            source_field=kind,
        )
        for i, (kind, strength, desc) in enumerate(facts)
    ]
    if not items:
        items = [
            EvidenceItem(
                priority=1,
                type="insufficient_evidence",
                description="No supporting fulfilment or authentication facts were provided.",
                strength="weak",
                source_field="none",
            )
        ]
    reason = case.get("reason_code", "chargeback")
    amount = case.get("amount", 0)
    draft = (
        f"We contest this {reason} chargeback of INR {amount:.2f}. "
        + " ".join(item.description for item in items if item.type != "insufficient_evidence")
        + " Please consider the attached merchant evidence and policy."
    )
    gaps = _gaps(case)
    n_strong = sum(1 for i in items if i.strength == "strong")
    confidence = "high" if n_strong >= 2 else "medium" if n_strong == 1 else "low"
    action = "submit" if n_strong >= 2 else "review" if items and items[0].type != "insufficient_evidence" else "abandon"
    return EvidencePackage(
        evidence_package=items,
        representment_draft=draft[:1200],
        evidence_gaps=gaps,
        confidence=confidence,  # type: ignore[arg-type]
        recommended_action=action,  # type: ignore[arg-type]
        source="template_fallback",
    )


def _openai_package(case: dict) -> EvidencePackage | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
    except ImportError:
        return None
    client = OpenAI(api_key=api_key)
    schema = {
        "type": "object",
        "properties": {
            "evidence_package": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "priority": {"type": "integer"},
                        "type": {"type": "string"},
                        "description": {"type": "string"},
                        "strength": {"type": "string", "enum": ["strong", "moderate", "weak"]},
                        "source_field": {"type": "string"},
                    },
                    "required": ["priority", "type", "description", "strength", "source_field"],
                },
            },
            "representment_draft": {"type": "string"},
            "evidence_gaps": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "recommended_action": {"type": "string", "enum": ["submit", "review", "abandon"]},
        },
        "required": [
            "evidence_package",
            "representment_draft",
            "evidence_gaps",
            "confidence",
            "recommended_action",
        ],
    }
    payload = {
        "chargeback": {
            "reason_code": case.get("reason_code"),
            "amount": case.get("amount"),
            "transaction_date": case.get("transaction_date"),
            "dispute_date": case.get("dispute_date"),
        },
        "available_evidence": {
            "delivery_confirmed": bool(case.get("delivery_confirmed")),
            "tracking_id": case.get("tracking_id"),
            "delivery_timestamp": case.get("delivery_timestamp"),
            "customer_email_opened": bool(case.get("customer_email_opened")),
            "three_d_secure": bool(case.get("three_d_secure")),
            "device_fingerprint_match": bool(case.get("device_fingerprint_match")),
            "ip_geolocation_match": bool(case.get("ip_geolocation_match")),
            "customer_tenure_days": case.get("customer_tenure_days"),
            "customer_prior_disputes": case.get("customer_prior_disputes"),
        },
        "merchant_policy": case.get("merchant_policy"),
    }
    resp = client.chat.completions.create(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0.2,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )
    raw = json.loads(resp.choices[0].message.content or "{}")
    pkg = EvidencePackage.model_validate({**raw, "source": "openai"})
    return pkg


def assemble_evidence(case: dict) -> EvidencePackage:
    live = _openai_package(case)
    return live or template_package(case)


def grounding_metrics(case: dict, package: EvidencePackage) -> dict[str, Any]:
    allowed = {
        "delivery_proof": case.get("delivery_confirmed") == 1,
        "three_d_secure": case.get("three_d_secure") == 1,
        "device_match": case.get("device_fingerprint_match") == 1,
        "geo_match": case.get("ip_geolocation_match") == 1,
        "email_engagement": case.get("customer_email_opened") == 1,
        "customer_history": True,
        "merchant_policy": True,
        "insufficient_evidence": True,
    }
    claims = package.evidence_package
    unsupported = 0
    for item in claims:
        ok = allowed.get(item.type)
        if ok is False:
            unsupported += 1
        if item.type == "delivery_proof" and item.description:
            tid = case.get("tracking_id") or ""
            if tid and tid not in item.description and "tracking" not in item.description.lower():
                # invented tracking is worse; count if a different TRK-like token appears
                if "TRK" in item.description.upper() and tid not in item.description:
                    unsupported += 1
    required = ["evidence_package", "representment_draft", "evidence_gaps", "confidence", "recommended_action"]
    dump = package.model_dump()
    schema_ok = all(dump.get(k) not in (None, "", []) or k == "evidence_gaps" for k in required)
    completeness = 0.0
    completeness += 0.4 if dump["evidence_package"] else 0.0
    completeness += 0.3 if len(dump["representment_draft"]) >= 80 else 0.15 if dump["representment_draft"] else 0.0
    completeness += 0.3 if isinstance(dump["evidence_gaps"], list) else 0.0
    return {
        "schema_valid": schema_ok,
        "completeness_score": round(completeness, 3),
        "unsupported_claim_rate": round(unsupported / max(len(claims), 1), 3),
        "n_evidence_items": len(claims),
        "n_gaps": len(package.evidence_gaps),
        "note": "Proxy metrics only. Precision/recall are not claimed for the LLM component.",
    }
