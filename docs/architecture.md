# Architecture

## Goal

Defense-only chargeback representment desk:

1. **Component 1 (ML):** predict `P(winnable)` from tabular features at notification time.
2. **Deterministic decision engine:** route to `DO_NOT_FIGHT` / `MANUAL_REVIEW` / `RECOMMEND_CONTEST`.
3. **Component 2 (LLM):** assemble a grounded evidence package **only** for `RECOMMEND_CONTEST`.
4. **Human review** before any submission.

## Stack

- FastAPI backend (`app/`)
- XGBoost + sklearn baselines (`ml/`)
- React + Vite desk UI (`frontend/`)
- Local JSONL audit log (Firestore-ready later)

## Separation of concerns

| Layer | Tool | Why |
|---|---|---|
| Classification | XGBoost | Tabular behavioural data |
| Policy | Pure Python | Deterministic tiers |
| Evidence writing | LLM / template fallback | Language synthesis |
| Explainability | Feature gain / signals | Tied to model, not post-hoc LLM rationalization |

LLM never sets the winnability score.
