from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.schemas.models import ChargebackCase, EvidenceResponse, PredictResponse
from app.services import audit_service, llm_service, ml_service
from app.services.decision_engine import route, to_dict

ROOT = Path(__file__).resolve().parents[2]
THRESH_PATH = ROOT / "ml" / "artifacts" / "thresholds.json"
METRICS_PATH = ROOT / "evaluation" / "metrics.json"
SEEDS_PATH = ROOT / "app" / "demo_seeds.json"

router = APIRouter()


def _thresholds() -> dict:
    if THRESH_PATH.exists():
        return json.loads(THRESH_PATH.read_text(encoding="utf-8"))
    return {"do_not_fight_max": 0.35, "recommend_contest_min": 0.65}


def _safe_predict(payload: dict) -> tuple[float, list[dict]]:
    try:
        return ml_service.predict_winnability(payload)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Model inference failed: {exc}"
        ) from exc


@router.get("/health")
def health() -> dict:
    model_ok = ml_service.MODEL_PATH.exists()
    thresholds_ok = THRESH_PATH.exists()
    metrics_ok = METRICS_PATH.exists()
    seeds_ok = SEEDS_PATH.exists()
    ready = model_ok and thresholds_ok and metrics_ok and seeds_ok
    return {
        "ok": ready,
        "ready": ready,
        "model": model_ok,
        "thresholds": thresholds_ok,
        "metrics": metrics_ok,
        "demo_seeds": seeds_ok,
        "service": "chargeback-sentinel",
        "version": "1.0.0",
    }


@router.get("/demo-seeds")
def demo_seeds() -> dict:
    if not SEEDS_PATH.exists():
        raise HTTPException(404, "Demo seeds missing.")
    return json.loads(SEEDS_PATH.read_text(encoding="utf-8"))


@router.get("/metrics")
def metrics() -> dict:
    if not METRICS_PATH.exists():
        raise HTTPException(404, "Metrics not generated. Run training first.")
    return json.loads(METRICS_PATH.read_text(encoding="utf-8"))


@router.get("/audit")
def audit(limit: int = 25) -> dict:
    limit = max(1, min(int(limit), 100))
    return {"events": audit_service.recent(limit)}


@router.post("/predict", response_model=PredictResponse)
def predict(case: ChargebackCase) -> PredictResponse:
    payload = case.model_dump()
    winnability, signals = _safe_predict(payload)
    decision = route(
        winnability,
        thresholds=_thresholds(),
        duplicate_chargeback=case.duplicate_chargeback,
        amount=case.amount,
        reason_code=case.reason_code,
        delivery_confirmed=case.delivery_confirmed,
        three_d_secure=case.three_d_secure,
    )
    body = to_dict(decision)
    audit_service.log_event("predict", {"chargeback_id": case.chargeback_id, **body})
    return PredictResponse(
        chargeback_id=case.chargeback_id,
        winnability=round(winnability, 4),
        action=body["action"],
        reasons=body["reasons"],
        llm_allowed=body["llm_allowed"],
        hard_stop=body["hard_stop"],
        top_signals=signals,
    )


@router.post("/generate-evidence", response_model=EvidenceResponse)
def generate_evidence(case: ChargebackCase) -> EvidenceResponse:
    payload = case.model_dump()
    winnability, _ = _safe_predict(payload)
    decision = route(
        winnability,
        thresholds=_thresholds(),
        duplicate_chargeback=case.duplicate_chargeback,
        amount=case.amount,
        reason_code=case.reason_code,
        delivery_confirmed=case.delivery_confirmed,
        three_d_secure=case.three_d_secure,
    )
    if decision.action != "RECOMMEND_CONTEST":
        audit_service.log_event(
            "evidence_blocked",
            {"chargeback_id": case.chargeback_id, "action": decision.action},
        )
        return EvidenceResponse(
            chargeback_id=case.chargeback_id,
            winnability=round(winnability, 4),
            action=decision.action,
            blocked_reason="Evidence runs only for RECOMMEND_CONTEST. Pick demo case 3.",
        )
    try:
        package = llm_service.assemble_evidence(payload)
        proxy = llm_service.grounding_metrics(payload, package)
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Evidence assembly failed: {exc}"
        ) from exc
    audit_service.log_event(
        "evidence",
        {
            "chargeback_id": case.chargeback_id,
            "action": decision.action,
            "source": package.source,
            "proxy_metrics": proxy,
        },
    )
    return EvidenceResponse(
        chargeback_id=case.chargeback_id,
        winnability=round(winnability, 4),
        action=decision.action,
        package=package,
        proxy_metrics=proxy,
    )
