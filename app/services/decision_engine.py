from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DO_NOT_FIGHT = "DO_NOT_FIGHT"
MANUAL_REVIEW = "MANUAL_REVIEW"
RECOMMEND_CONTEST = "RECOMMEND_CONTEST"

DEFAULT_THRESHOLDS = {
    "do_not_fight_max": 0.35,
    "recommend_contest_min": 0.62,
}


@dataclass(frozen=True)
class RoutingDecision:
    action: str
    winnability: float
    reasons: list[str]
    hard_stop: bool


def route(
    winnability: float,
    *,
    thresholds: dict | None = None,
    duplicate_chargeback: bool = False,
    amount: float | None = None,
    reason_code: str | None = None,
    delivery_confirmed: int | None = None,
    three_d_secure: int | None = None,
) -> RoutingDecision:
    t = thresholds or DEFAULT_THRESHOLDS
    lo = float(t.get("do_not_fight_max", t.get("do_not_fight_max", 0.35)))
    hi = float(t.get("recommend_contest_min", t.get("recommend_contest_min", 0.62)))
    reasons: list[str] = []

    if duplicate_chargeback:
        return RoutingDecision(
            action=MANUAL_REVIEW,
            winnability=float(winnability),
            reasons=["Duplicate chargeback id — automatic contest is blocked."],
            hard_stop=True,
        )

    if amount is not None and amount >= 25000:
        reasons.append("High-value dispute (≥ ₹25,000) requires an analyst.")
        return RoutingDecision(
            action=MANUAL_REVIEW,
            winnability=float(winnability),
            reasons=reasons,
            hard_stop=True,
        )

    p = float(winnability)
    if p < lo:
        action = DO_NOT_FIGHT
        reasons.append(f"Winnability {p:.2f} is below {lo:.2f}.")
        if not delivery_confirmed and not three_d_secure:
            reasons.append("No delivery confirmation and no 3DS — weak representment file.")
    elif p >= hi:
        action = RECOMMEND_CONTEST
        reasons.append(f"Winnability {p:.2f} meets the contest bar ({hi:.2f}).")
        if delivery_confirmed:
            reasons.append("Delivery confirmation is on file.")
        if three_d_secure:
            reasons.append("3DS authentication completed.")
    else:
        action = MANUAL_REVIEW
        reasons.append(f"Winnability {p:.2f} sits in the review band [{lo:.2f}, {hi:.2f}).")
        if reason_code:
            reasons.append(f"Reason code {reason_code} needs a human look at mixed evidence.")

    return RoutingDecision(
        action=action,
        winnability=p,
        reasons=reasons,
        hard_stop=False,
    )


def to_dict(decision: RoutingDecision) -> dict[str, Any]:
    return {
        "action": decision.action,
        "winnability": decision.winnability,
        "reasons": decision.reasons,
        "hard_stop": decision.hard_stop,
        "llm_allowed": decision.action == RECOMMEND_CONTEST,
    }
