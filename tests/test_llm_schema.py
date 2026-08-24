from app.services.llm_service import assemble_evidence, grounding_metrics


def test_template_evidence_is_grounded():
    case = {
        "reason_code": "item_not_received",
        "amount": 3650.0,
        "delivery_confirmed": 1,
        "three_d_secure": 1,
        "device_fingerprint_match": 1,
        "ip_geolocation_match": 1,
        "customer_email_opened": 1,
        "customer_tenure_days": 540,
        "tracking_id": "TRK48291033",
        "merchant_policy": "Returns accepted with delivery proof.",
    }
    package = assemble_evidence(case)
    metrics = grounding_metrics(case, package)
    assert metrics["schema_valid"] is True
    assert metrics["unsupported_claim_rate"] == 0.0
    assert package.source in {"template_fallback", "openai"}
